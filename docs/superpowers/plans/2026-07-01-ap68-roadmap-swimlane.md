# AP-68 — Roadmap-Swimlane-Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Roadmap-Grafik von einem pro-AP-wachsenden Mermaid-Gantt auf einen eigenen, regenerierbaren Python-SVG-Swimlane mit konstanter Höhe (10 Themen-Lanes) umstellen.

**Architecture:** Reines Datenmodul (`roadmap_data.py`, Single Source of Truth) → stdlib-only Generator (`tools/generate_roadmap_svg.py`, testbare Logik getrennt von SVG-Emission) → `build_docs.py`-Schritt (Muster wie `generate_project_activity.py`) → SVG unter `docs/images/roadmap/`, in `roadmap.md` eingebettet.

**Tech Stack:** Python 3 stdlib (`datetime`, String-Templating für SVG). Keine neue Dependency. Doku-Build via zensical/mmdc bleibt unangetastet außer der neuen Roadmap-Grafik.

## Global Constraints

- **Stdlib-only** — kein neues Paket; SVG ist String-Templating (`datetime` erlaubt).
- **Tests laufen im Projekt-venv** (`./venv/bin/python -m pytest`, Python 3.14, `testpaths = tests`). Generator-Logik ist stdlib → importierbar per `sys.path`-Insert von `luDBxP-docs/tools/`.
- **Palette** (aus `entwicklung-arbeitspakete-1.mmd`): erledigt `#1f6f3c`, offen/plan `#234a78`, Marken-Text `#fff`.
- **Intrinsische Pixel-Breite** im SVG (`width="1200"`, nicht `width="100%"`) — sonst kollabiert die Grafik in der `<img>`-Lightbox (gleiche Falle wie `render_mermaid.sh`).
- **Enumerate-Regel:** jede *offene* AP erscheint als eigene benannte Raute; maschinell im Test abgesichert.
- **Sprache Deutsch**, NO-CDN.
- **10 Lanes fix** = die C1–C10-Kategorien; Historie je Lane als **ein** Done-Balken verdichtet.
- **Version je AP** via `sync_version.py --minor`; Doku-Nachzug vollständig (Changelog EN+DE, Kennzahlen frisch, Site, gh-pages).

---

### Task 1: Reine Zeit-/Skalen-Logik

**Files:**
- Create: `luDBxP-docs/tools/generate_roadmap_svg.py`
- Test: `tests/test_roadmap_svg.py`

**Interfaces:**
- Produces:
  - `parse_date(s: str) -> datetime.date`
  - `date_range(aps: list[dict]) -> tuple[date, date]` — (min, max) über alle `aps["date"]`
  - `date_to_x(d: date, dmin: date, dmax: date, x0: float, x1: float) -> float` — lineare Abbildung; `dmin→x0`, `dmax→x1`; bei `dmin==dmax` → `x0`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_roadmap_svg.py
import sys
from datetime import date
from pathlib import Path

# Generator liegt in der Doku-Toolchain; stdlib-only → unter dem Projekt-venv importierbar.
_TOOLS = Path(__file__).resolve().parent.parent / "luDBxP-docs" / "tools"
sys.path.insert(0, str(_TOOLS))

import generate_roadmap_svg as g  # noqa: E402


def test_parse_date():
    assert g.parse_date("2026-06-25") == date(2026, 6, 25)


def test_date_range():
    aps = [
        {"date": "2026-06-25"},
        {"date": "2026-07-12"},
        {"date": "2026-06-28"},
    ]
    assert g.date_range(aps) == (date(2026, 6, 25), date(2026, 7, 12))


def test_date_to_x_endpoints_and_midpoint():
    dmin, dmax = date(2026, 6, 25), date(2026, 7, 5)  # 10 Tage
    assert g.date_to_x(dmin, dmin, dmax, 100.0, 1100.0) == 100.0
    assert g.date_to_x(dmax, dmin, dmax, 100.0, 1100.0) == 1100.0
    # Tag 5 von 10 → Mitte
    assert g.date_to_x(date(2026, 6, 30), dmin, dmax, 100.0, 1100.0) == 600.0


def test_date_to_x_collapsed_range():
    d = date(2026, 6, 25)
    assert g.date_to_x(d, d, d, 100.0, 1100.0) == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_roadmap_svg.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generate_roadmap_svg'`

- [ ] **Step 3: Write minimal implementation**

```python
# luDBxP-docs/tools/generate_roadmap_svg.py
"""AP-68 — Roadmap-Swimlane-Generator.

Erzeugt aus roadmap_data.py (Single Source of Truth) einen SVG mit konstanter
Höhe: eine Lane je Themenbereich, erledigte Historie als ein verdichteter Balken,
offene APs als benannte Rauten an ihrem Zieldatum. Stdlib-only.
"""
from __future__ import annotations

from datetime import date


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def date_range(aps: list[dict]) -> tuple[date, date]:
    ds = [parse_date(a["date"]) for a in aps]
    return min(ds), max(ds)


def date_to_x(d: date, dmin: date, dmax: date, x0: float, x1: float) -> float:
    span = (dmax - dmin).days
    if span == 0:
        return x0
    frac = (d - dmin).days / span
    return x0 + frac * (x1 - x0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_roadmap_svg.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add luDBxP-docs/tools/generate_roadmap_svg.py tests/test_roadmap_svg.py
git commit -m "feat(roadmap): AP-68 Zeit-/Skalen-Logik (parse_date/date_range/date_to_x)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Lane-Modell + Validierung

**Files:**
- Modify: `luDBxP-docs/tools/generate_roadmap_svg.py`
- Test: `tests/test_roadmap_svg.py`

**Interfaces:**
- Consumes: `parse_date` (Task 1)
- Produces:
  - `class Lane` mit Attributen `key: str`, `label: str`, `done_span: tuple[date, date] | None`, `markers: list[tuple[str, str, date]]` (ap, label, date) nach Datum sortiert
  - `validate(aps: list[dict], themes: list[tuple[str, str]]) -> None` — wirft `ValueError` bei leerem `aps`, unbekanntem `theme`, ungültigem `status`, kaputtem Datum
  - `lane_spans(aps: list[dict], themes: list[tuple[str, str]]) -> list[Lane]` — je Theme in `themes`-Reihenfolge eine `Lane`

- [ ] **Step 1: Write the failing test**

```python
# in tests/test_roadmap_svg.py anfügen
import pytest

_THEMES = [("engine", "⚙️ Engine"), ("betrieb", "🚀 Betrieb")]


def _aps():
    return [
        {"ap": "AP-1", "label": "A", "theme": "engine", "date": "2026-06-25", "status": "done"},
        {"ap": "AP-2", "label": "B", "theme": "engine", "date": "2026-06-28", "status": "done"},
        {"ap": "AP-31", "label": "Idle", "theme": "betrieb", "date": "2026-07-05", "status": "open"},
        {"ap": "AP-35", "label": "venv", "theme": "betrieb", "date": "2026-07-02", "status": "open"},
    ]


def test_lane_spans_done_and_markers():
    lanes = g.lane_spans(_aps(), _THEMES)
    assert [l.key for l in lanes] == ["engine", "betrieb"]
    engine = lanes[0]
    assert engine.done_span == (date(2026, 6, 25), date(2026, 6, 28))
    assert engine.markers == []
    betrieb = lanes[1]
    assert betrieb.done_span is None
    # nach Datum sortiert: AP-35 (07-02) vor AP-31 (07-05)
    assert [m[0] for m in betrieb.markers] == ["AP-35", "AP-31"]


def test_validate_rejects_unknown_theme():
    bad = [{"ap": "AP-9", "label": "x", "theme": "nope", "date": "2026-06-25", "status": "done"}]
    with pytest.raises(ValueError, match="theme"):
        g.validate(bad, _THEMES)


def test_validate_rejects_empty():
    with pytest.raises(ValueError, match="leer"):
        g.validate([], _THEMES)


def test_validate_rejects_bad_status():
    bad = [{"ap": "AP-9", "label": "x", "theme": "engine", "date": "2026-06-25", "status": "wip"}]
    with pytest.raises(ValueError, match="status"):
        g.validate(bad, _THEMES)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_roadmap_svg.py -k "lane_spans or validate" -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'lane_spans'`

- [ ] **Step 3: Write minimal implementation**

```python
# in generate_roadmap_svg.py anfügen (unter date_to_x)
from dataclasses import dataclass, field


@dataclass
class Lane:
    key: str
    label: str
    done_span: tuple[date, date] | None
    markers: list[tuple[str, str, date]] = field(default_factory=list)


def validate(aps: list[dict], themes: list[tuple[str, str]]) -> None:
    if not aps:
        raise ValueError("APS ist leer")
    keys = {k for k, _ in themes}
    for a in aps:
        if a["theme"] not in keys:
            raise ValueError(f"unbekanntes theme {a['theme']!r} ({a['ap']})")
        if a["status"] not in ("done", "open"):
            raise ValueError(f"ungültiger status {a['status']!r} ({a['ap']})")
        parse_date(a["date"])  # wirft ValueError bei kaputtem Datum


def lane_spans(aps: list[dict], themes: list[tuple[str, str]]) -> list[Lane]:
    validate(aps, themes)
    lanes: list[Lane] = []
    for key, label in themes:
        mine = [a for a in aps if a["theme"] == key]
        done = [parse_date(a["date"]) for a in mine if a["status"] == "done"]
        span = (min(done), max(done)) if done else None
        markers = sorted(
            ((a["ap"], a["label"], parse_date(a["date"])) for a in mine if a["status"] == "open"),
            key=lambda m: m[2],
        )
        lanes.append(Lane(key, label, span, markers))
    return lanes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_roadmap_svg.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add luDBxP-docs/tools/generate_roadmap_svg.py tests/test_roadmap_svg.py
git commit -m "feat(roadmap): AP-68 Lane-Modell + Validierung (lane_spans/validate)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: SVG-Emission

**Files:**
- Modify: `luDBxP-docs/tools/generate_roadmap_svg.py`
- Test: `tests/test_roadmap_svg.py`

**Interfaces:**
- Consumes: `Lane`, `lane_spans`, `date_range`, `date_to_x` (Tasks 1–2)
- Produces:
  - `esc(s: str) -> str` — XML-Escape für `& < >`
  - `render_svg(lanes: list[Lane], dmin: date, dmax: date, *, width: int = 1200) -> str` — vollständiges `<svg>…</svg>`; Titel, Label-Spalte, X-Achsen-Ticks, je Lane wechselnder Hintergrund + Done-Balken + offene Rauten mit Text-Label, Legende. Höhe = `MARGIN_TOP + len(lanes)*LANE_H + LEGEND_H`.

**Layout-Konstanten (im Modul):** `MARGIN_LEFT = 210`, `MARGIN_TOP = 70`, `LANE_H = 34`, `LEGEND_H = 44`, `PLOT_PAD_RIGHT = 30`. Plot: `x0 = MARGIN_LEFT`, `x1 = width - PLOT_PAD_RIGHT`.

- [ ] **Step 1: Write the failing test**

```python
# in tests/test_roadmap_svg.py anfügen
def test_render_svg_wellformed_and_contains_open_labels():
    lanes = g.lane_spans(_aps(), _THEMES)
    dmin, dmax = g.date_range(_aps())
    svg = g.render_svg(lanes, dmin, dmax)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # Enumerate-Regel: jede offene AP muss namentlich im SVG stehen
    assert "AP-31" in svg and "AP-35" in svg
    # intrinsische Pixel-Breite, nicht width="100%"
    assert 'width="1200"' in svg
    assert 'width="100%"' not in svg
    # Done-Farbe der erledigten Lane vorhanden
    assert "#1f6f3c" in svg


def test_esc():
    assert g.esc("A & B <x>") == "A &amp; B &lt;x&gt;"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_roadmap_svg.py -k "render_svg or esc" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'render_svg'`

- [ ] **Step 3: Write minimal implementation**

```python
# in generate_roadmap_svg.py anfügen
from datetime import timedelta

MARGIN_LEFT = 210
MARGIN_TOP = 70
LANE_H = 34
LEGEND_H = 44
PLOT_PAD_RIGHT = 30

DONE_FILL = "#1f6f3c"
OPEN_FILL = "#234a78"
LANE_BG_A = "#f7f7fa"
LANE_BG_B = "#ffffff"
AXIS_COL = "#9aa0a6"
LABEL_COL = "#33373b"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _axis_ticks(dmin: date, dmax: date, step_days: int = 3) -> list[date]:
    ticks, d = [], dmin
    while d <= dmax:
        ticks.append(d)
        d += timedelta(days=step_days)
    if ticks[-1] != dmax:
        ticks.append(dmax)
    return ticks


def render_svg(lanes: list[Lane], dmin: date, dmax: date, *, width: int = 1200) -> str:
    x0, x1 = MARGIN_LEFT, width - PLOT_PAD_RIGHT
    height = MARGIN_TOP + len(lanes) * LANE_H + LEGEND_H
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="#ffffff"/>')
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="30" font-size="20" font-weight="700" '
        f'fill="{LABEL_COL}">LucentTools DB Explorer — Arbeitspaket-Roadmap</text>'
    )

    # X-Achse (Datums-Ticks) über die volle Plot-Höhe
    plot_bottom = MARGIN_TOP + len(lanes) * LANE_H
    for t in _axis_ticks(dmin, dmax):
        x = date_to_x(t, dmin, dmax, x0, x1)
        parts.append(
            f'<line x1="{x:.1f}" y1="{MARGIN_TOP}" x2="{x:.1f}" y2="{plot_bottom}" '
            f'stroke="{AXIS_COL}" stroke-width="0.5" stroke-dasharray="2 3"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{MARGIN_TOP - 6}" font-size="10" text-anchor="middle" '
            f'fill="{AXIS_COL}">{t.strftime("%d.%m")}</text>'
        )

    # Lanes
    for i, lane in enumerate(lanes):
        ly = MARGIN_TOP + i * LANE_H
        bg = LANE_BG_A if i % 2 == 0 else LANE_BG_B
        parts.append(f'<rect x="0" y="{ly}" width="{width}" height="{LANE_H}" fill="{bg}"/>')
        parts.append(
            f'<text x="{MARGIN_LEFT - 12}" y="{ly + LANE_H/2 + 4:.0f}" font-size="12" '
            f'text-anchor="end" fill="{LABEL_COL}">{esc(lane.label)}</text>'
        )
        # Done-Balken
        if lane.done_span:
            s, e = lane.done_span
            bx0 = date_to_x(s, dmin, dmax, x0, x1)
            bx1 = date_to_x(e, dmin, dmax, x0, x1)
            bw = max(6.0, bx1 - bx0)
            parts.append(
                f'<rect x="{bx0:.1f}" y="{ly + 8}" width="{bw:.1f}" height="{LANE_H - 16}" '
                f'rx="3" fill="{DONE_FILL}"/>'
            )
        # Offene Marker (Rauten) + Label, mit einfachem Anti-Overlap-Versatz
        last_label_end = -1e9
        for (ap, label, d) in lane.markers:
            mx = date_to_x(d, dmin, dmax, x0, x1)
            cy = ly + LANE_H / 2
            r = 5
            parts.append(
                f'<polygon points="{mx:.1f},{cy-r:.1f} {mx+r:.1f},{cy:.1f} '
                f'{mx:.1f},{cy+r:.1f} {mx-r:.1f},{cy:.1f}" fill="{OPEN_FILL}"/>'
            )
            txt = f"{ap} {label}"
            ty = cy + 4
            if mx < last_label_end + 8:      # Labels zu nah → zweite Zeile
                ty = cy - 8
            parts.append(
                f'<text x="{mx + 8:.1f}" y="{ty:.1f}" font-size="10" fill="{OPEN_FILL}">'
                f'{esc(txt)}</text>'
            )
            last_label_end = mx + 8 + len(txt) * 5.4

    # Legende
    lgy = plot_bottom + 22
    parts.append(f'<rect x="{MARGIN_LEFT}" y="{lgy-9}" width="22" height="12" rx="3" fill="{DONE_FILL}"/>')
    parts.append(f'<text x="{MARGIN_LEFT+28}" y="{lgy+1}" font-size="11" fill="{LABEL_COL}">erledigt (Zeitraum)</text>')
    dx = MARGIN_LEFT + 190
    parts.append(f'<polygon points="{dx},{lgy-6} {dx+6},{lgy} {dx},{lgy+6} {dx-6},{lgy}" fill="{OPEN_FILL}"/>')
    parts.append(f'<text x="{dx+14}" y="{lgy+1}" font-size="11" fill="{LABEL_COL}">offen (Ziel-Datum)</text>')

    parts.append("</svg>")
    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_roadmap_svg.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add luDBxP-docs/tools/generate_roadmap_svg.py tests/test_roadmap_svg.py
git commit -m "feat(roadmap): AP-68 SVG-Emission (render_svg/esc, Swimlane-Layout)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Datenquelle `roadmap_data.py` + `main()`

**Files:**
- Create: `luDBxP-docs/roadmap_data.py`
- Create (Einmal-Helfer): `luDBxP-docs/tools/_bootstrap_roadmap_data.py`
- Modify: `luDBxP-docs/tools/generate_roadmap_svg.py` (add `main()`)
- Test: `tests/test_roadmap_svg.py`

**Interfaces:**
- Produces:
  - `roadmap_data.THEMES: list[tuple[str, str]]` (10 Einträge, C1–C10-Reihenfolge)
  - `roadmap_data.APS: list[dict]` (je AP genau ein Eintrag; keys: `ap, label, theme, date, status`)
  - `generate_roadmap_svg.main() -> int` — lädt `roadmap_data`, ruft `lane_spans`+`render_svg`, schreibt `docs/images/roadmap/projekt-roadmap.svg`

**Erst-Befüllung (Prozedur, nicht raten):** Der Bootstrap-Helfer liest die zwei vorhandenen `.mmd`
und schlägt Einträge vor; Themen-Zuordnung kommt aus dem Flowchart (jeder `AP-N`-Knoten sitzt in
genau einem `subgraph C…`). Ergebnis wird kuratiert in `roadmap_data.py` übernommen (das ist Daten,
keine Logik — der Helfer bleibt Einmal-Werkzeug, nicht Teil des Builds).

- [ ] **Step 1: Bootstrap-Helfer schreiben**

```python
# luDBxP-docs/tools/_bootstrap_roadmap_data.py
"""Einmal-Helfer (NICHT Teil des Builds): liest projekt-roadmap-1.mmd (Datum+Status)
und entwicklung-arbeitspakete-1.mmd (Thema je AP via subgraph) und druckt APS-Kandidaten.
Ergebnis manuell in roadmap_data.py kuratieren."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "mermaid-sources"

# 1) Datum + Status + Label aus dem Gantt
gantt = (SRC / "projekt-roadmap-1.mmd").read_text(encoding="utf-8")
# Zeilenform:  AP-11 — Composite FK … :done, b2, 2026-06-26, 1d
row = re.compile(r"^\s*(AP-\d+[^:]*?)\s*:(done|active|crit|)?[^,]*,\s*\w+,\s*(\d{4}-\d{2}-\d{2})", re.M)
gantt_rows = [(m.group(1).strip(), m.group(3), "done" if ":done" in m.group(0) else "open")
              for m in row.finditer(gantt)]

# 2) Thema je AP aus dem Flowchart (subgraph-Zuordnung)
flow = (SRC / "entwicklung-arbeitspakete-1.mmd").read_text(encoding="utf-8")
theme_of: dict[str, str] = {}
cur = None
CMAP = {  # subgraph-Id → THEMES-key (siehe roadmap_data.THEMES)
    "C1": "engine", "C2": "backends", "C3": "sqlbuilder", "C4": "graphviz",
    "C5": "datenui", "C6": "betrieb", "C7": "doku", "C8": "migration",
    "C9": "objekte", "C10": "verbux",
}
for line in flow.splitlines():
    sg = re.search(r"subgraph (C\d+)\[", line)
    if sg:
        cur = CMAP.get(sg.group(1))
    for ap in re.findall(r"AP-\d+", line):
        if cur:
            theme_of.setdefault(ap, cur)

for label, d, status in gantt_rows:
    ap = re.match(r"AP-\d+", label).group(0)
    theme = theme_of.get(ap, "?TODO?")
    print(f'    {{"ap": "{ap}", "label": "…", "theme": "{theme}", "date": "{d}", "status": "{status}"}},')
```

- [ ] **Step 2: Bootstrap laufen lassen + Kandidaten prüfen**

Run: `cd luDBxP-docs && python3 tools/_bootstrap_roadmap_data.py | head -40`
Expected: Zeilen der Form `{"ap": "AP-11", "theme": "engine", "date": "2026-06-26", "status": "done"}, …`.
Jede `?TODO?`-Themen-Zuordnung von Hand ergänzen (AP nicht im Flowchart → passende C-Kategorie wählen; Kern-v0.1.0-Zeilen ohne AP-Nummer den Themen `engine`/`datenui`/`doku` zuordnen). Offene APs (AP-19/31/34/35/57/61/62/66) mit **Zieldatum** aus der `roadmap.md`-Prosa versehen.

- [ ] **Step 3: `roadmap_data.py` schreiben**

```python
# luDBxP-docs/roadmap_data.py
"""Single Source of Truth für die Roadmap-Swimlane-Grafik (AP-68).
Bei jeder neuen AP hier eine Zeile ergänzen (Thema/Datum/Status) — analog zur
Prosa-Liste in docs/projekt/roadmap.md. Reine Daten, kein Import."""

THEMES = [
    ("engine",     "⚙️ Engine / Fundament"),
    ("backends",   "🔌 Verbindungen & Backends"),
    ("sqlbuilder", "🧩 SQL-Builder & SQL-Ausgabe"),
    ("graphviz",   "🕸️ Graph-Visualisierung"),
    ("datenui",    "🗂️ Daten & UI-Rahmen"),
    ("betrieb",    "🚀 Deployment & Betrieb"),
    ("doku",       "📚 Doku & Prozess"),
    ("migration",  "🧬 Legacy-DB-Migration / Export"),
    ("objekte",    "🗃️ DB-Objekt-Kategorien"),
    ("verbux",     "🔧 Verbindungs-UX & Demo-Daten"),
]

# Aus _bootstrap_roadmap_data.py kuratiert. Labels gekürzt (passen ins Diagramm).
APS = [
    # … alle erledigten APs (status="done") + offene (status="open") …
    {"ap": "AP-31", "label": "Idle-Shutdown/Deploy", "theme": "betrieb",   "date": "2026-07-05", "status": "open"},
    {"ap": "AP-35", "label": "run.ps1 leeres venv",  "theme": "betrieb",   "date": "2026-07-02", "status": "open"},
    {"ap": "AP-34", "label": "Log-Fenster",          "theme": "betrieb",   "date": "2026-07-03", "status": "open"},
    {"ap": "AP-19", "label": "pattern_transfer",     "theme": "doku",      "date": "2026-07-04", "status": "open"},
    {"ap": "AP-57", "label": "Cross-Schema-Joins",   "theme": "migration", "date": "2026-07-08", "status": "open"},
    {"ap": "AP-66", "label": "Views→Routinen (S2/3)","theme": "objekte",   "date": "2026-07-10", "status": "open"},
    {"ap": "AP-61", "label": "Demo→volle CMDB",      "theme": "verbux",    "date": "2026-07-11", "status": "open"},
    {"ap": "AP-62", "label": "Passwort-Keyring",     "theme": "verbux",    "date": "2026-07-12", "status": "open"},
]
```

- [ ] **Step 4: `main()` im Generator + Test**

```python
# in generate_roadmap_svg.py ganz unten anfügen
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "images" / "roadmap" / "projekt-roadmap.svg"


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import roadmap_data as data
    lanes = lane_spans(data.APS, data.THEMES)
    dmin, dmax = date_range(data.APS)
    svg = render_svg(lanes, dmin, dmax)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"✓ Roadmap-SVG → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```python
# in tests/test_roadmap_svg.py anfügen — echte Datenquelle konsistent + jede offene AP im Render
def test_real_data_consistent_and_open_aps_rendered():
    sys.path.insert(0, str(_TOOLS.parent))  # luDBxP-docs/
    import roadmap_data as data
    g.validate(data.APS, data.THEMES)                       # keine kaputten Zeilen
    lanes = g.lane_spans(data.APS, data.THEMES)
    dmin, dmax = g.date_range(data.APS)
    svg = g.render_svg(lanes, dmin, dmax)
    open_aps = [a["ap"] for a in data.APS if a["status"] == "open"]
    assert open_aps, "es sollte offene APs geben"
    for ap in open_aps:                                     # Enumerate-Regel
        assert ap in svg, f"offene {ap} fehlt im gerenderten SVG"
```

- [ ] **Step 5: Tests laufen lassen**

Run: `./venv/bin/python -m pytest tests/test_roadmap_svg.py -v`
Expected: PASS (12 passed) — inkl. `test_real_data_consistent_and_open_aps_rendered`

- [ ] **Step 6: Generator einmal ausführen (Sichtprüfung)**

Run: `cd luDBxP-docs && python3 tools/generate_roadmap_svg.py`
Expected: `✓ Roadmap-SVG → …/docs/images/roadmap/projekt-roadmap.svg`; Datei existiert, im Browser/Viewer 10 Lanes + offene Rauten sichtbar, keine Überlappung der Achsen-Labels.

- [ ] **Step 7: Commit**

```bash
git add luDBxP-docs/roadmap_data.py luDBxP-docs/tools/_bootstrap_roadmap_data.py \
        luDBxP-docs/tools/generate_roadmap_svg.py tests/test_roadmap_svg.py \
        luDBxP-docs/docs/images/roadmap/projekt-roadmap.svg
git commit -m "feat(roadmap): AP-68 Datenquelle roadmap_data.py + main() + gerenderte SVG

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Build-Integration + altes Gantt archivieren + Embed umstellen

**Files:**
- Modify: `luDBxP-docs/build_docs.py` (neuer `step_generate_roadmap()` + Aufruf in `main()`)
- Modify: `luDBxP-docs/docs/projekt/roadmap.md` (`<img src>`)
- Move: `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd` → `luDBxP-docs/mermaid-sources/archiv/projekt-roadmap-1.mmd`
- Delete: `luDBxP-docs/docs/images/mermaid/projekt-roadmap-1.svg`

**Interfaces:**
- Consumes: `generate_roadmap_svg.main` (Task 4)

- [ ] **Step 1: `step_generate_roadmap()` in build_docs.py ergänzen**

Nach `step_generate_activity()` (um Zeile 151) einfügen:

```python
def step_generate_roadmap() -> None:
    script = TOOLS_DIR / "generate_roadmap_svg.py"
    if not script.is_file():
        warn("generate_roadmap_svg.py fehlt — uebersprungen")
        return
    step("Roadmap-Swimlane-SVG generieren")
    rc = run([sys.executable, str(script)], check=False)
    if rc == 0:
        ok("projekt-roadmap.svg aktualisiert")
    else:
        warn(f"generate_roadmap_svg.py exit {rc} (nicht-fatal)")
```

- [ ] **Step 2: Aufruf in `main()` verdrahten**

In `main()` direkt bei den anderen Generator-Schritten (nach `step_extract_mermaid()`/`step_render_mermaid()` bzw. neben `step_generate_activity()`) ergänzen:

```python
    step_generate_roadmap()
```

(Unabhängig von `--no-mermaid`, da kein `mmdc` nötig.)

- [ ] **Step 3: Altes Gantt archivieren + Alt-SVG entfernen**

```bash
mkdir -p luDBxP-docs/mermaid-sources/archiv
git mv luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd luDBxP-docs/mermaid-sources/archiv/projekt-roadmap-1.mmd
git rm luDBxP-docs/docs/images/mermaid/projekt-roadmap-1.svg
```

Prüfen, dass `render_mermaid.sh` nur `mermaid-sources/*.mmd` (nicht `archiv/`) rendert:
Run: `grep -n 'SOURCES.*mmd\|/\${filter}' luDBxP-docs/tools/render_mermaid.sh`
Expected: Glob ist `"$SOURCES"/${filter}*.mmd` (nicht rekursiv) → `archiv/` wird nicht erfasst. Falls doch rekursiv: `archiv/`-Ausschluss ergänzen.

- [ ] **Step 4: Embed in roadmap.md umstellen**

In `luDBxP-docs/docs/projekt/roadmap.md`:

```
- <img src="../images/mermaid/projekt-roadmap-1.svg" alt="Arbeitspaket-Roadmap (Gantt)">
+ <img src="../images/roadmap/projekt-roadmap.svg" alt="Arbeitspaket-Roadmap (Themen-Swimlane)">
```

- [ ] **Step 5: Vollen Doku-Build fahren**

Run: `cd luDBxP-docs && python3 build_docs.py --no-mermaid` (falls mmdc nicht installiert; sonst ohne Flag)
Expected: Schritt „Roadmap-Swimlane-SVG generieren" → `ok`; `site/` gebaut. `grep -c 'projekt-roadmap.svg' site/projekt/roadmap/index.html` ≥ 1.

- [ ] **Step 6: Commit**

```bash
git add luDBxP-docs/build_docs.py luDBxP-docs/docs/projekt/roadmap.md \
        luDBxP-docs/mermaid-sources/archiv/projekt-roadmap-1.mmd
git add -A luDBxP-docs/docs/images
git commit -m "feat(roadmap): AP-68 build_docs-Integration, Gantt archiviert, Embed umgestellt

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Verifikation + Release-/Doku-Nachzug

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py --minor`)
- Modify: Changelog EN + DE-Mirror, `docs/session-kennzahlen.md`
- Modify: ggf. `entwicklung-arbeitspakete-1.mmd` (AP-68-Knoten in `C7 Doku & Prozess`, done-Klasse)

- [ ] **Step 1: Enumerate-Regel am gerenderten SVG gegenprüfen**

Run: `for ap in AP-19 AP-31 AP-34 AP-35 AP-57 AP-61 AP-62 AP-66; do grep -q "$ap" luDBxP-docs/docs/images/roadmap/projekt-roadmap.svg && echo "$ap ok" || echo "$ap FEHLT"; done`
Expected: alle `ok` (echte Render-Kodierung beachten; APs stehen als Text-Knoten unescaped).

- [ ] **Step 2: Volle Test-Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: alle bisherigen + die neuen 12 Roadmap-Tests PASS, 0 Fehler.

- [ ] **Step 3: Version bumpen**

Run: `./venv/bin/python sync_version.py --minor`
Expected: `config.APP_VERSION` + `lucent-hub.yml` im Lockstep erhöht (v0.65.1 → v0.66.0).

- [ ] **Step 4: Changelog EN + DE-Mirror**

Neuer Eintrag unter der neuen Version (beide Sprachen), Kern: „Roadmap-Grafik: eigener Swimlane-Generator (10 Themen-Lanes, konstante Höhe) ersetzt den pro-AP wachsenden Gantt; erledigte Historie verdichtet, offene APs als benannte Marker. Mermaid-Gantt archiviert."

- [ ] **Step 5: Kennzahlen frisch erheben**

Run: `git rev-list --count HEAD` (Commits) und `./venv/bin/python -m pytest -q 2>&1 | tail -1` (Tests). Werte in `docs/session-kennzahlen.md` eintragen (nicht fortschreiben — frisch messen).

- [ ] **Step 6: Arbeitspakete-Flowchart ergänzen**

In `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd` einen `AP-68`-Knoten in `C7 Doku & Prozess` mit `done`-Klasse ergänzen; danach `./tools/render_mermaid.sh entwicklung-arbeitspakete`.

- [ ] **Step 7: Site-Build + Sichtprüfung**

Run: `cd luDBxP-docs && python3 build_docs.py` (voll, inkl. mmdc falls verfügbar)
Expected: `site/` gebaut; `site/images/roadmap/projekt-roadmap.svg` vorhanden; Roadmap-Seite zeigt den Swimlane.

- [ ] **Step 8: Commit + (auf Ansage) gh-pages-Deploy**

```bash
git add -A
git commit -m "release: v0.66.0 — AP-68 Roadmap-Swimlane (Doku/Version/Kennzahlen)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
gh-pages-Deploy (manuelles Worktree-Deploy) nur auf ausdrückliche Ansage des Nutzers.

---

## Self-Review

**Spec coverage:** Datenquelle (T4) · Generator reine Logik (T1/T2) · SVG-Emission (T3) · Integration/Archiv/Embed (T5) · Tests inkl. Enumerate-Regel (T1–T4/T6) · Doku-Nachzug (T6) — alle Spec-Abschnitte haben eine Task. Risiko „Datums-Enge" ist im Render (Anti-Overlap-Versatz, T3-Step-3) + Sichtprüfung (T4-Step-6) adressiert.

**Placeholder-Scan:** Der einzige bewusst offene Block ist die vollständige `APS`-Liste in T4 — das sind **Daten**, per Bootstrap-Helfer (T4-Step-1/2) konkret abgeleitet, nicht geratene Logik. Alle Code-Steps enthalten vollständigen Code.

**Type-Konsistenz:** `lane_spans`/`validate`/`date_range`/`date_to_x`/`render_svg`/`esc`/`main` — Signaturen über Tasks hinweg identisch verwendet; `Lane`-Felder (`key/label/done_span/markers`) konsistent in T2 definiert und in T3/T4 gelesen.
