# AP-68 — Roadmap-Swimlane-Grafik (Design)

**Datum:** 2026-07-01 · **Status:** freigegeben (Brainstorm), Plan folgt
**Betrifft:** `luDBxP-docs/` (nur Doku-Toolchain — kein `core/`/`web/`-Code)

## Problem

Die Roadmap-Grafik ist ein Mermaid-Gantt (`luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd`),
in dem **jede AP eine eigene Zeile** ist. Bei ~90 erledigten APs sind das ~130 Zeilen — unlesbar,
und es kommt **pro AP eine Zeile hinzu**. Die ~7 *offenen* APs sind nicht das Problem; die Masse
sind erledigte APs, je als eigene Gantt-Zeile.

Mermaid-Gantt kann strukturell **nicht** mehrere Bars auf eine physische Zeile legen (jeder Task =
eine Zeile). Ein echter Swimlane (mehrere Items pro Lane, positioniert nach Datum) ist damit in
Mermaid nicht darstellbar → Mermaid ist für dieses Bild das falsche Werkzeug.

## Ziel

Eine Grafik mit **konstanter Höhe = Themenbereiche** (nicht wachsend mit der AP-Zahl):
- Höhe = feste **10 Themen-Lanes** (die C1–C10-Kategorien aus dem Arbeitspakete-Flowchart).
- X-Achse = **echte Datumsskala** (Projektstart → spätestes offenes Zieldatum).
- Je Lane **ein verdichteter Done-Span-Balken** (min→max Done-Datum des Themas) + jede **offene AP
  als benannte Raute** auf der Lane an ihrem Zieldatum.
- Wächst nur noch mit **offener** Arbeit; eine ausgelieferte AP wandert von offener Raute →
  Done-Span (nie eine neue Zeile).

Nicht-Ziel: die erledigten APs einzeln im Diagramm zeigen (bleiben in der Prosa-Liste der
`roadmap.md` vollständig enumeriert). Kein neues Diagramm-Framework, keine neue Dependency.

## Entscheidungen (aus dem Brainstorm)

1. **Themen-Lanes, Historie verdichtet** (nicht: nur-vorausschauend, nicht: Meilenstein-Punkte).
2. **10 Lanes, ein Done-Balken je Lane** (die C1–C10-Kategorien 1:1, keine Konsolidierung).
3. **Eigener Python-SVG-Generator** (Pfad 1) — Mermaid ist das falsche Tool; kein PlantUML/D3.
4. Datenquelle als **`.py`-Datenmodul** (nicht JSON), altes Gantt-`.mmd` **archivieren**,
   neue SVG unter **`docs/images/roadmap/`**.

## Architektur / Komponenten

Layering: reine Datentrennung + testbare Logik getrennt von der SVG-Emission (analog zur
Projekt-Linie „Logik testbar, Render dünn"). Alles stdlib-only (Docs-venv = Python 3.12).

### 1. Datenquelle — `luDBxP-docs/roadmap_data.py`
Reines Datenmodul, **Single Source of Truth** für die Grafik. Kein Import von Generator/Build.

```python
# Lane-Reihenfolge + Anzeige (wiederverwendet aus entwicklung-arbeitspakete-1.mmd C1–C10)
THEMES = [
    ("engine",    "⚙️ Engine / Fundament"),
    ("backends",  "🔌 Verbindungen & Backends"),
    ("sqlbuilder","🧩 SQL-Builder & SQL-Ausgabe"),
    ("graphviz",  "🕸️ Graph-Visualisierung"),
    ("datenui",   "🗂️ Daten & UI-Rahmen"),
    ("betrieb",   "🚀 Deployment & Betrieb"),
    ("doku",      "📚 Doku & Prozess"),
    ("migration", "🧬 Legacy-DB-Migration / Export"),
    ("objekte",   "🗃️ DB-Objekt-Kategorien"),
    ("verbux",    "🔧 Verbindungs-UX & Demo-Daten"),
]

# Eine Zeile je AP. status ∈ {"done", "open"}. date = ISO (Zieldatum bei open).
APS = [
    {"ap": "AP-11", "label": "Composite-FK", "theme": "engine",  "date": "2026-06-26", "status": "done"},
    ...
    {"ap": "AP-31", "label": "Idle-Shutdown/Deploy", "theme": "betrieb", "date": "2026-07-05", "status": "open"},
    ...
]
```

Regeln:
- Jede AP genau einmal. `theme` muss ein `THEMES`-Key sein (Generator validiert, sonst Fehler).
- Erst-Befüllung: aus `projekt-roadmap-1.mmd` (Datum + done/plan) + Themen-Zuordnung analog
  `entwicklung-arbeitspakete-1.mmd` (C1–C10). Die Prosa-`roadmap.md` bleibt die Volltext-Quelle.

### 2. Generator — `luDBxP-docs/tools/generate_roadmap_svg.py`
Stdlib-only. Zwei Schichten:

**Reine Logik (unit-testbar, ohne Rendern):**
- `date_range(aps) -> (dmin, dmax)` — früheste bis späteste relevante Datumsgrenze (inkl. offener
  Zieldaten); ggf. auf Wochengrenzen gerundet.
- `date_to_x(d, dmin, dmax, x0, x1) -> float` — lineare Datums→Pixel-Abbildung.
- `lane_spans(aps, themes) -> list[LaneModel]` — je Lane: Done-Span `(start, end)` aus min/max der
  `done`-APs des Themas (oder `None`, wenn keine); Liste der offenen Marker `(ap, label, date)`.
- Validierung: unbekanntes `theme`, leeres `APS`, kein Datum → klare `ValueError`.

**SVG-Emission (String-Templating):**
- `render_svg(model, opts) -> str` — Titel, linke Label-Spalte, X-Achsen-Ticks (Wochen/Tage),
  je Lane wechselnder Hintergrund + Done-Balken + offene Rauten mit Text-Label, Legende.
- `main()` schreibt nach `docs/images/roadmap/projekt-roadmap.svg`; folgt dem
  `generate_project_activity.py`-Muster (Exit 0 / nicht-fatale Warnung).

**Layout-Konstanten:** Lane-Höhe ~34px, 10 Lanes → ~340px + Achsen/Titel/Legende (~120px) ≈ 460px
Höhe; Breite ~1200px. Palette aus dem Flowchart: `done` `#1f6f3c`, `open/plan` `#234a78`,
Text `#fff` auf Marken, neutrale Achsen/Labels. Intrinsische Pixel-Breite (kein `width="100%"`),
damit die SVG in der `<img>`-Lightbox nicht kollabiert (gleiche Falle wie in `render_mermaid.sh`).

### 3. Integration — `luDBxP-docs/build_docs.py`
- Neuer `step_generate_roadmap()` (Muster wie `step_generate_activity`): ruft
  `tools/generate_roadmap_svg.py` via `run([sys.executable, script], check=False)`, nicht-fatal
  bei Fehler, `ok`/`warn`.
- In `main()` verdrahten (bei den anderen Generator-Schritten; unabhängig von `--no-mermaid`, da
  kein mmdc nötig — eigener `--no-roadmap`-Schalter optional, YAGNI: vorerst nicht).
- `mermaid-sources/projekt-roadmap-1.mmd` → nach `mermaid-sources/archiv/` verschieben (oder
  löschen), damit `render_mermaid.sh` es nicht mehr rendert. Alt-SVG
  `docs/images/mermaid/projekt-roadmap-1.svg` entfernen.
- `docs/projekt/roadmap.md`: `<img src>` von `../images/mermaid/projekt-roadmap-1.svg` auf
  `../images/roadmap/projekt-roadmap.svg` umstellen. Die Prosa-Listen (offene/erledigte APs)
  bleiben unverändert vollständig.

### 4. Tests
Es gibt heute **kein** Doku-Test-Verzeichnis, und `pytest.ini` hat `testpaths = tests`. Daher liegt
der Test in der **Projekt-Suite**: `tests/test_roadmap_svg.py` (wird so von `./venv/bin/python -m
pytest` erfasst). Er importiert die **reine Generator-Logik** per `sys.path`-Insert von
`luDBxP-docs/tools/` — der Generator ist stdlib-only und läuft daher problemlos unter dem
3.14-Projekt-venv (keine Docs-venv-Grenze für den Logik-Teil). Geprüft:
- `date_to_x` monoton + Randwerte (dmin→x0, dmax→x1).
- `lane_spans`: Done-Span = min/max korrekt; Lane ohne done → `None`; offene Marker vollständig.
- Validierung wirft bei unbekanntem `theme` / leerem `APS`.
- Smoke: `render_svg` liefert wohlgeformtes `<svg …>…</svg>` und enthält **jedes offene AP-Label**
  (Enumerate-Regel maschinell abgesichert).

## Enumerate-Regel (globale Konvention)

Jede **offene** AP erscheint als eigene benannte Raute im Diagramm → „jedes offene Item einzeln"
ist erfüllt. Erledigte APs werden im Lane-Balken verdichtet (Historie) und bleiben in der
Prosa-Liste der `roadmap.md` vollständig namentlich. **Nach dem Build** inhaltliche
Gegenprüfung, dass jedes offene AP-Label im gerenderten SVG vorkommt (Test oben + manueller
Grep im SVG, echte Render-Kodierung beachten).

## Doku-Nachzug (bei Umsetzung)

- Changelog EN + DE-Mirror (AP-68).
- `roadmap.md`-Embed umgestellt (s. o.); Prosa unverändert.
- Kennzahlen-Zeile (Commits/Sessions/Coverage frisch), Version-Bump via `sync_version.py --minor`.
- Site-Build + gh-pages-Deploy; nach Build prüfen, dass das neue SVG live jedes offene AP zeigt.
- Insight optional (Werkzeug-Wahl: „Mermaid-Gantt kann keine Swimlanes").

## Risiken / offene Punkte

- **Datums-Enge:** Projekt spannt nur ~17 Tage (2026-06-25 → ~07-12) → offene Marker liegen dicht.
  Mildern per Label-Versatz/Zeilenumbruch oder leichter horizontaler Streuung; im Plan festzurren.
- **Erst-Befüllung von `roadmap_data.py`** ist Handarbeit (~90 done + ~7 open) — aus den beiden
  vorhandenen `.mmd` ableitbar, aber sorgfältig gegenzuprüfen (Datum/Thema).
- **Zwei Sichten** (Generator-Daten + Prosa) = leichtes Drift-Risiko; akzeptiert, Update-Pfad
  dokumentiert (beide bei neuer AP pflegen — steht ohnehin im Handoff-Regelwerk).
