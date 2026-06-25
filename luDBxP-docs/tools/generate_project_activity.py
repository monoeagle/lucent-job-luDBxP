#!/usr/bin/env python3
"""
generate_project_activity.py — ADB Control

SYNOPSIS
    Liest die Git-Historie und schreibt ein JSON-File mit Tages-Aggregaten +
    Phasen-Block fuer die Projektverlauf-Doku-Seite.

DESCRIPTION
    Output-Schema (siehe adb-control-docs/docs/_data/project-activity.json):
      {
        "generatedAt": "2026-05-24T20:30:00",
        "range": { "from": "2025-05-25", "to": "2026-05-24" },
        "byDay": {
          "2026-05-24": {
            "commits": 12,
            "kinds": { "feat": 8, "fix": 2, "docs": 2 },
            "list": [
              { "sha": "abc1234", "subject": "feat(p31k): ...", "kind": "feat" },
              ...
            ]
          }
        },
        "stats": {
          "totalCommits": 350,
          "activeDays": 45,
          "longestStreak": 14,
          "topKinds": [
            { "kind": "feat", "count": 180 },
            ...
          ]
        },
        "phases": [
          {
            "id": "phase-p31k",
            "label": "P31k",
            "start": "2026-05-24",
            "end": "2026-05-24",
            "kind": "feature"
          },
          ...
        ]
      }

    Phasen werden aus Commit-Messages per Heuristik erkannt (P31[a-z]-Pattern)
    sowie aus CHANGELOG-Headers (## v<ver> — <date> — <description>) geparst.

USAGE
    python3 generate_project_activity.py
    python3 generate_project_activity.py --repo-root /path/to/repo
    python3 generate_project_activity.py --out custom/path.json

NOTES
    Tool ist idempotent + read-only gegenueber dem Repo (nutzt nur git log).
    Standard-Library only — kein pip-install noetig.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ── Defaults ─────────────────────────────────────────────────────────────────

# Projektagnostisch aus dem Skript-Pfad ableiten — Layout <repo>/<docs>/tools/diese-datei.py:
#   parents[2] = Repo-Root, parents[1] = Docs-Root. Mit --repo-root / --out überschreibbar.
_HERE = Path(__file__).resolve()
DEFAULT_REPO_ROOT = str(_HERE.parents[2])
DEFAULT_OUT = str(_HERE.parents[1] / "docs" / "_data" / "project-activity.json")

# ── Conventional-Commit kinds ────────────────────────────────────────────────

CC_KINDS = (
    "feat", "fix", "docs", "refactor", "test", "chore",
    "perf", "style", "build", "ci", "revert",
)

# Regex: matches "feat", "fix(scope)", "docs!:", etc.
_CC_RE = re.compile(
    r"^(" + "|".join(CC_KINDS) + r")(\([^)]+\))?[!:]",
    re.IGNORECASE,
)

# P31x pattern — matches P31a … P31z (upper or lower) anywhere in a string
_P31_RE = re.compile(r"\bP(31[a-z])\b", re.IGNORECASE)

# CHANGELOG header pattern — handles two formats:
#   ## v0.28.0 — 2026-05-24 — P31k APK-Backup ...       (new style, v prefix)
#   ## [0.24.0] — 2026-05-23 — P31b AES-256-GCM ...     (old style, brackets)
_CHANGELOG_RE = re.compile(
    r"^##\s+(?:v[\d.]+|\[[\d.]+\])\s+[—–-]+\s+(\d{4}-\d{2}-\d{2})\s+[—–-]+\s+(.+)$"
)


# ── Classification ────────────────────────────────────────────────────────────

def classify_kind(subject: str) -> str:
    """Return the Conventional-Commit kind (or special case) for a subject."""
    # Conventional-Commits prefix check
    m = _CC_RE.match(subject)
    if m:
        kind = m.group(1).lower()
    else:
        kind = "other"

    # Special-case overrides (checked after base kind is set)
    subj_lower = subject.lower()

    # audit: commit subject mentions "audit" explicitly or "chore(audit)"
    if re.search(r"audit[- ]marathon|chore\(audit\)|^audit", subj_lower):
        kind = "audit"

    # hotfix: fix-commits that mention hotfix or regression
    if kind == "fix" and re.search(r"hotfix|regression", subj_lower):
        kind = "hotfix"

    return kind


# ── Git log ──────────────────────────────────────────────────────────────────

SEP = "\x01"  # SOH — virtually never appears in commit messages


def read_git_log(repo_root: str) -> list[tuple[str, str, str]]:
    """
    Run git log and return list of (date_str, sha7, subject) tuples.
    Raises RuntimeError if git produces no output.
    """
    result = subprocess.run(
        [
            "git", "log",
            f"--pretty=format:%ad{SEP}%h{SEP}%s",
            "--date=short",
        ],
        cwd=repo_root,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = result.stdout.strip()
    if not raw:
        raise RuntimeError(
            "git log produced no output — is the tool running in the correct directory?"
        )

    commits: list[tuple[str, str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split(SEP, 2)
        if len(parts) != 3:
            continue
        date_str, sha, subject = parts
        commits.append((date_str.strip(), sha.strip(), subject.strip()))
    return commits


# ── Aggregation ──────────────────────────────────────────────────────────────

def aggregate_by_day(
    commits: list[tuple[str, str, str]],
    range_from: date,
    range_to: date,
) -> dict[str, Any]:
    """
    Filter commits to [range_from, range_to] and aggregate per calendar day.

    Returns dict keyed by ISO date string with structure:
      { "commits": int, "kinds": {kind: count}, "list": [{sha, subject, kind}] }
    """
    by_day: dict[str, dict[str, Any]] = {}
    kind_totals: dict[str, int] = defaultdict(int)
    total = 0

    for date_str, sha, subject in commits:
        try:
            commit_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        if not (range_from <= commit_date <= range_to):
            continue

        kind = classify_kind(subject)
        short_subject = subject[:200] + "..." if len(subject) > 200 else subject

        if date_str not in by_day:
            by_day[date_str] = {"commits": 0, "kinds": {}, "list": []}

        by_day[date_str]["commits"] += 1
        by_day[date_str]["kinds"][kind] = by_day[date_str]["kinds"].get(kind, 0) + 1
        by_day[date_str]["list"].append(
            {"sha": sha, "subject": short_subject, "kind": kind}
        )

        kind_totals[kind] += 1
        total += 1

    return by_day, kind_totals, total


# ── Stats ────────────────────────────────────────────────────────────────────

def count_tests(repo_root: str) -> int:
    """Zaehlt Unit-Tests im Repo, projektagnostisch: Python `def test_*` unter
    irgendeinem tests/-Verzeichnis + Kotlin `@Test` in irgendeinem src/test/
    (Instrumented androidTest/ und Build-Output ausgeklammert). Deckt Mehr-Modul-
    Projekte (z.B. :app + :core-Submodul) ab, nicht nur ein festes Unterverzeichnis."""
    root = Path(repo_root)
    n = 0
    py_re = re.compile(r"^\s*def test_\w+", re.MULTILINE)
    for p in root.rglob("*.py"):
        ps = p.as_posix()
        if "/tests/" in ps and "/.venv" not in ps and "/venv" not in ps and "/build/" not in ps:
            try:
                n += len(py_re.findall(p.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                pass
    kt_re = re.compile(r"@Test\b")
    for p in root.rglob("*.kt"):
        ps = p.as_posix()
        # nur Unit-Tests (src/test), Instrumented (androidTest) + Build-Output ausklammern
        if "/src/test/" in ps and "/androidTest/" not in ps and "/build/" not in ps:
            try:
                n += len(kt_re.findall(p.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                pass
    return n


def compute_stats(
    by_day: dict[str, Any],
    kind_totals: dict[str, int],
    total_commits: int,
    range_from: date,
    range_to: date,
) -> dict[str, Any]:
    """Compute activeDays, longestStreak, topKinds."""
    active_days = len(by_day)

    # Longest streak of consecutive active days within the range
    longest_streak = 0
    current_streak = 0
    cursor = range_from
    while cursor <= range_to:
        key = cursor.isoformat()
        if key in by_day:
            current_streak += 1
            if current_streak > longest_streak:
                longest_streak = current_streak
        else:
            current_streak = 0
        cursor += timedelta(days=1)

    # Top-8 kinds by count, descending
    top_kinds = [
        {"kind": k, "count": v}
        for k, v in sorted(kind_totals.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    return {
        "totalCommits": total_commits,
        "activeDays": active_days,
        "longestStreak": longest_streak,
        "topKinds": top_kinds,
    }


# ── Phase detection from commits ─────────────────────────────────────────────

def detect_phases_from_commits(
    commits: list[tuple[str, str, str]],
    range_from: date,
    range_to: date,
) -> dict[str, dict[str, Any]]:
    """
    Scan commits for P31[a-z] patterns and collect per-phase start/end/kind.
    Returns dict keyed by normalized phase key (e.g. "p31k").
    """
    phases: dict[str, dict[str, Any]] = {}

    for date_str, _sha, subject in commits:
        try:
            commit_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        if not (range_from <= commit_date <= range_to):
            continue

        for m in _P31_RE.finditer(subject):
            key = "p" + m.group(1).lower()  # e.g. "p31k"
            kind = classify_kind(subject)
            if key not in phases:
                phases[key] = {
                    "start": date_str,
                    "end": date_str,
                    "kind": kind,
                }
            else:
                # expand date range
                if date_str < phases[key]["start"]:
                    phases[key]["start"] = date_str
                if date_str > phases[key]["end"]:
                    phases[key]["end"] = date_str

    return phases


# ── Phase detection from CHANGELOG ───────────────────────────────────────────

def parse_changelog_phases(changelog_path: str) -> list[dict[str, Any]]:
    """
    Parse CHANGELOG.md for headers of the form:
      ## v0.28.0 — 2026-05-24 — P31k APK-Backup-Source (Read-only, MVP)

    Returns list of dicts with keys: id, label, start, end, kind.
    """
    path = Path(changelog_path)
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    for line in text.splitlines():
        m = _CHANGELOG_RE.match(line.strip())
        if not m:
            continue
        entry_date = m.group(1)
        description = m.group(2).strip()

        # Derive phase id from P31x pattern in description
        pm = _P31_RE.search(description)
        if pm:
            phase_key = "p" + pm.group(1).lower()
            phase_id = f"phase-{phase_key}"
            label = description
        else:
            # Fallback: use sanitized description as id
            phase_id = "phase-" + re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")
            label = description

        # Determine kind heuristically from description keywords
        desc_lower = description.lower()
        if any(w in desc_lower for w in ("fix", "hotfix", "regression", "patch")):
            kind = "fix"
        elif any(w in desc_lower for w in ("docs", "doku", "readme", "changelog")):
            kind = "docs"
        elif any(w in desc_lower for w in ("chore", "cleanup", "refactor")):
            kind = "chore"
        elif any(w in desc_lower for w in ("perf", "performance", "optimier")):
            kind = "perf"
        else:
            kind = "feature"

        entries.append({
            "id": phase_id,
            "label": label,
            "start": entry_date,
            "end": entry_date,
            "kind": kind,
        })

    return entries


# ── Merge phases ─────────────────────────────────────────────────────────────

def build_phases(
    commit_phases: dict[str, dict[str, Any]],
    changelog_phases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge commit-detected phases with CHANGELOG phases.
    CHANGELOG entries provide richer labels; commit phases provide accurate
    date ranges. Priority: CHANGELOG label wins, commit dates win for range.
    """
    # Build final phases dict keyed by phase_key (e.g. "p31k")
    merged: dict[str, dict[str, Any]] = {}

    # Seed with commit-detected phases
    for key, data in commit_phases.items():
        merged[key] = {
            "id": f"phase-{key}",
            "label": key.upper(),  # fallback label, e.g. "P31K"
            "start": data["start"],
            "end": data["end"],
            "kind": data["kind"],
        }

    # Overlay CHANGELOG entries (richer labels, may extend date range)
    for entry in changelog_phases:
        # Extract phase key from id if it matches phase-p31x pattern
        id_m = re.match(r"phase-(p31[a-z])", entry["id"])
        if id_m:
            key = id_m.group(1)
        else:
            key = entry["id"]

        if key in merged:
            # Upgrade label from CHANGELOG; expand date range
            merged[key]["label"] = entry["label"]
            if entry["start"] < merged[key]["start"]:
                merged[key]["start"] = entry["start"]
            if entry["end"] > merged[key]["end"]:
                merged[key]["end"] = entry["end"]
        else:
            # New entry from CHANGELOG only
            merged[key] = entry

    # Sort by start date descending (most recent first)
    phases = sorted(merged.values(), key=lambda p: p["start"], reverse=True)
    return phases


# ── Main ─────────────────────────────────────────────────────────────────────

def generate(repo_root: str, out_path: str) -> None:
    """Full pipeline: git log -> aggregate -> stats -> phases -> JSON write."""
    today = date.today()
    range_from = today - timedelta(days=364)  # 365-day window inclusive

    print(f"  Repo:      {repo_root}")
    print(f"  Range:     {range_from.isoformat()} … {today.isoformat()}")

    # 1. Read git history
    commits = read_git_log(repo_root)
    print(f"  Raw commits in repo:  {len(commits)}")

    # 2. Aggregate by day (filtered to range)
    by_day, kind_totals, total_commits = aggregate_by_day(commits, range_from, today)

    # 3. Stats
    stats = compute_stats(by_day, kind_totals, total_commits, range_from, today)
    stats["testCount"] = count_tests(repo_root)

    # 4. Phases
    commit_phases = detect_phases_from_commits(commits, range_from, today)

    changelog_path = os.path.join(repo_root, "CHANGELOG.md")
    changelog_phases = parse_changelog_phases(changelog_path)

    phases = build_phases(commit_phases, changelog_phases)

    # 5. Assemble payload
    payload = {
        "generatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "range": {
            "from": range_from.isoformat(),
            "to": today.isoformat(),
        },
        "byDay": by_day,
        "stats": stats,
        "phases": phases,
    }

    # 6. Write JSON
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 7. Summary
    top_kinds_str = ", ".join(
        f"{e['kind']} ({e['count']})" for e in stats["topKinds"]
    )
    print()
    print(f"  Total commits:   {stats['totalCommits']}")
    print(f"  Active days:     {stats['activeDays']}")
    print(f"  Longest streak:  {stats['longestStreak']}")
    print(f"  Top kinds:       {top_kinds_str}")
    print(f"  Phases found:    {len(phases)}")
    print(f"  Output:          {out_file.resolve()}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate project-activity.json from git history (ADB Control).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo-root",
        default=DEFAULT_REPO_ROOT,
        help=f"Path to the git repo root (default: {DEFAULT_REPO_ROOT})",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"Output JSON path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    try:
        generate(repo_root=args.repo_root, out_path=args.out)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
