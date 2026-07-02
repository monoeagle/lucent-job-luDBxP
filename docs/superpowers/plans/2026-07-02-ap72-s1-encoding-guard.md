# AP-72·S1 — Encoding-Hygiene-Guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein pytest-Guard, der künftiges Mojibake / UTF-8-BOM / ungültiges UTF-8 in getrackten Code-Dateien abfängt (das Repo ist heute bereits sauber — reine Prävention).

**Architecture:** Eine Testdatei `tests/test_encoding_hygiene.py` sammelt getrackte Code-Dateien via `git ls-files`, prüft je Datei BOM / UTF-8-Dekodierbarkeit / Doppelkodierungs-Signatur, und schlägt gebündelt fehl. Ein zweiter Test injiziert bekanntes Mojibake/BOM in tmp-Dateien und beweist, dass der Checker greift.

**Tech Stack:** Python 3.14, pytest, stdlib (`subprocess`, `re`, `pathlib`).

## Global Constraints

- **Reiner Test — kein Produktionscode ändert sich.**
- Die Testdatei selbst muss **reines ASCII** sein: alle Mojibake-Muster werden aus `\uXXXX`-Escapes gebaut, sonst flaggt der Guard sich selbst (die Datei wird von sich selbst mitgeprüft).
- Datei-Auswahl: `git ls-files`, Endungen `.py .js .html .css .sh .ps1`, **ausgeschlossen** `luDBxP-docs/site/` + `build/`. Kein Git → `pytest.skip`.
- Mojibake-Signatur: `[ÂÃâ][-¿]` (Â/Ã/â + Fortsetzungs-Byte-Bereich). Echte Umlaute (`ü` etc.) matchen nicht.
- Markdown/Doku werden NICHT geprüft (dürfen Beispiel-Strings legitim tragen).
- Version: `sync_version.py --patch` → **v0.68.1** (nie von Hand).
- Branch `feat/ap72-s1-encoding-guard` (existiert, Spec committet).

---

### Task 1: Encoding-Hygiene-Guard-Test

**Files:**
- Create: `tests/test_encoding_hygiene.py`

**Interfaces:**
- Produces: `test_source_files_are_clean_utf8()` (repo-weit) + `test_guard_detects_injected_mojibake(tmp_path)` (Detektions-Beweis); Helfer `_tracked_code_files()`, `_violations(rel, raw) -> list[tuple[str,int,str]]`.

- [ ] **Step 1: Testdatei schreiben** — `tests/test_encoding_hygiene.py` (ASCII-only!):

> **WICHTIG (Markdown-Rendering):** Im Code unten erscheinen die Mojibake-Muster teils literal. In der ECHTEN `.py` MÜSSEN sie als `\uXXXX`-Escapes stehen, sonst flaggt der Guard sich selbst. Konkret: `_MOJIBAKE_RE = re.compile("[ÂÃâ][-¿]")`; im Detektions-Test `"x = 'cafÃ©'\n"` (Mojibake) und `"x = 'grüß'\n"` (echte Umlaute, kein Verstoß); Kommentare ohne Nicht-ASCII-Zeichen.

```python
"""AP-72.S1 - Encoding-Hygiene-Guard.

Verhindert, dass Mojibake (doppelt kodierte UTF-8-Bytes), ein UTF-8-BOM oder
ungueltiges UTF-8 in getrackte Code-Dateien gelangt. Reiner Test, kein
Produktionscode. Markdown/Doku bewusst ausgenommen (duerfen solche Muster als
Beispiel legitim tragen); generierte Site-/Build-Artefakte ausgeschlossen.

Diese Datei ist bewusst reines ASCII: die Mojibake-Muster werden aus
\\uXXXX-Escapes gebaut, damit der Guard sich nicht selbst flaggt.
"""
import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CODE_SUFFIXES = {".py", ".js", ".html", ".css", ".sh", ".ps1"}
_EXCLUDED_PREFIXES = ("luDBxP-docs/site/", "build/")
# Latin-1-"Fuehrungszeichen" (Â=A-circ, Ã=A-tilde, â=a-circ)
# direkt gefolgt von einem UTF-8-Fortsetzungs-Byte-Zeichen (-¿) =
# Doppelkodierungs-Signatur. Echte Zeichen wie ü (u-umlaut) matchen nicht.
_MOJIBAKE_RE = re.compile("[ÂÃâ][-¿]")
_BOM = b"\xef\xbb\xbf"


def _tracked_code_files():
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        pytest.skip("kein git-Repo (git ls-files fehlgeschlagen)")
    files = []
    for rel in out.stdout.splitlines():
        if not rel or Path(rel).suffix not in _CODE_SUFFIXES:
            continue
        if rel.startswith(_EXCLUDED_PREFIXES):
            continue
        p = _REPO_ROOT / rel
        if p.is_file():
            files.append((rel, p))
    return files


def _violations(rel, raw):
    """Alle Encoding-Verstoesse einer Datei als (rel, zeile, art)-Tupel."""
    out = []
    if raw.startswith(_BOM):
        out.append((rel, 1, "UTF-8-BOM"))
        raw = raw[len(_BOM):]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        out.append((rel, 1, "kein gueltiges UTF-8: " + str(e)))
        return out
    for i, line in enumerate(text.splitlines(), 1):
        m = _MOJIBAKE_RE.search(line)
        if m:
            out.append((rel, i, "Mojibake " + repr(m.group())))
    return out


def test_guard_detects_injected_mojibake(tmp_path):
    """Beweist, dass der Checker greift (nicht tautologisch gruen)."""
    # Ã© == doppelt kodiertes 'e-accent' (Mojibake 'A-tilde ©').
    bad = tmp_path / "bad.py"
    bad.write_bytes("x = 'cafÃ©'\n".encode("utf-8"))
    v = _violations("bad.py", bad.read_bytes())
    assert v and "Mojibake" in v[0][2]

    bom = tmp_path / "bom.py"
    bom.write_bytes(_BOM + b"x = 1\n")
    assert any("BOM" in art for _, _, art in _violations("bom.py", bom.read_bytes()))

    # Echte Umlaute sind KEIN Verstoss:
    good = tmp_path / "good.py"
    good.write_bytes("x = 'grüß'\n".encode("utf-8"))
    assert _violations("good.py", good.read_bytes()) == []


def test_source_files_are_clean_utf8():
    files = _tracked_code_files()
    assert files, "keine Code-Dateien gefunden (unerwartet)"
    bad = []
    for rel, p in files:
        bad.extend(_violations(rel, p.read_bytes()))
    assert not bad, "Encoding-Verstoesse:\n" + "\n".join(
        "  {}:{}: {}".format(rel, ln, art) for rel, ln, art in bad)
```

- [ ] **Step 2: Detektions-Beweis läuft (RED→GREEN in einem — der injizierte Fall MUSS erkannt werden)**

Run: `./venv/bin/python -m pytest tests/test_encoding_hygiene.py::test_guard_detects_injected_mojibake -v`
Expected: PASS (Mojibake + BOM erkannt, echte Umlaute nicht). Falls FAIL → Regex/Logik prüfen, **nicht** den Test aufweichen.

- [ ] **Step 3: Repo-weiter Guard ist grün (beweist: Repo ist sauber)**

Run: `./venv/bin/python -m pytest tests/test_encoding_hygiene.py -v`
Expected: beide Tests PASS. Falls `test_source_files_are_clean_utf8` FAIL → echte Fund-Datei(en) reparieren (das wäre dann die eigentliche Bereinigung).

- [ ] **Step 4: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: 468 passed, 11 skipped.

- [ ] **Step 5: Commit**

```bash
git add tests/test_encoding_hygiene.py
git commit -m "feat(ap-72-s1): Encoding-Hygiene-Guard (UTF-8/kein BOM/kein Mojibake)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Release v0.68.1 + Doku

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/javascripts/icon-rail.js` (`TEST_COUNT`), `luDBxP-docs/roadmap_data.py` (AP-72·S1 → done), `luDBxP-docs/docs/projekt/roadmap.md` (Prosa), `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd` (B10 → done), `luDBxP-docs/docs/projekt/kennzahlen.md` (Tests-Zahl).

- [ ] **Step 1: Version bump**

Run: `./venv/bin/python sync_version.py --patch`
Expected: `0.68.0` → `0.68.1`.

- [ ] **Step 2: Doku nachziehen** — Changelog EN + DE (v0.68.1: „Encoding-Hygiene-Guard — pytest prüft getrackte Code-Dateien auf UTF-8/kein BOM/kein Mojibake; Repo war bereits sauber, reine Prävention"); icon-rail `TEST_COUNT` 466 → 468; kennzahlen Tests-Zeile 466 → 468; Roadmap AP-72·S1 `open`→`done` in `roadmap_data.py` (Datum 2026-07-02) + Prosa aus „Encoding / UTF-8" nach „Erledigte" + `.mmd` B10 nach `class … done`; Swimlane- + Board-SVG neu rendern (`tools/generate_roadmap_svg.py`, `tools/render_mermaid.sh entwicklung-arbeitspakete`).

- [ ] **Step 3: Whole-Branch-Review (opus)** — Reviewfunde adressieren.

- [ ] **Step 4: Commit + finishing-branch** — Release-Commit, dann merge nach master + Site/gh-pages-Deploy (mit Nutzer bestätigen).

---

## Self-Review (gegen Spec)

- **Coverage:** git-ls-files-Auswahl + Endungs-Filter + site/build-Ausschluss ✅ Task 1 (`_tracked_code_files`) · BOM/UTF-8/Mojibake-Prüfung ✅ (`_violations`) · Selbst-Referenz via Escapes ✅ (ASCII-only + `_MOJIBAKE_RE` aus `\u`-Escapes) · Detektions-Beweis ✅ (`test_guard_detects_injected_mojibake`) · gebündelter Fehlerbericht mit Datei:Zeile ✅ · Release/patch ✅ Task 2.
- **Placeholder-Scan:** keine.
- **Typ-Konsistenz:** `_violations` liefert überall `(rel, zeile, art)`-Tupel; beide Tests konsumieren identisch. `_MOJIBAKE_RE`/`_BOM`/`_CODE_SUFFIXES`/`_EXCLUDED_PREFIXES` einheitlich benannt.
