# Design: AP-C + AP-D — Join-Typ inline + 1-N-Erklärung in die Graph-Legende

**Datum:** 2026-06-28
**Status:** Genehmigt (Brainstorming abgeschlossen)
**Kontext:** Drittes/viertes AP des UI-Umbau-Blocks nach AP-A (Umbenennung) und AP-B (Layout). Beide
Änderungen betreffen dieselbe Zone (Pfad-/Fan-out-Anzeige) und werden in **einem** Zyklus/Release
gebündelt. Reine UI-Umordnung; keine Funktions-/SQL-/API-Änderung.

## Ziel

Zwei verwandte Aufräum-Schritte am SQL-Builder:
- **AP-C:** Die separate Join-Typ-Zeile (`#sb_join_types`) entfällt; die Join-Typ-Dropdowns wandern
  **inline** in die aktive Pfad-Sequenz (neben die 1-N/N-1-Chips), Dropdowns ≤ Schriftgröße.
- **AP-D:** Die Fan-out-Erklärkachel (`#sb_fanout_hint`) im Builder entfällt; die 1-N/N-1-Erklärung
  wandert in die **Graph-Legende** (`#graph_legend`), was im Builder Platz freigibt.

## Ist-Stand (verifiziert)

- `renderPathSeq(p)` (`app.js`) rendert je Kandidatenpfad `Tabelle <chip> Tabelle …`; `chip` ist
  `<span class="step-dir one|many">N-1|1-N</span>` mit `title`.
- `renderJoinTypeControls(i)` (`app.js`, AP-41) füllt die **separate** Zeile `#sb_join_types` mit
  einem `<select>` (INNER/LEFT/RIGHT/FULL) je Schritt des **aktiven** Pfads, plus den AP-47-Orphan-
  Hinweisen (`.jt-orphan`-Spans, gesetzt von `_applyOrphanHints(i)` via `_loadOrphans(i)`). Änderung
  setzt `SB_JOIN_TYPES[step]` und ruft `runBuild(true)`.
- Die Zeile selbst: Markup `<div class="row sb-join-types" id="sb_join_types"></div>` in
  `openSqlBuilder`; CSS `.sb-join-types`/`.jt-lbl`/`.jt-step` in `app.css`.
- `#sb_fanout_hint`-Kachel: in `runBuild` gesetzt auf
  `<span class="step-dir many">1-N</span> kann Zeilen vervielfachen (Fan-out)`, wenn ein
  Kandidatenpfad einen `to_many`-Schritt hat. CSS `.sb-fanout-hint` (absolut positioniert).
- Graph-Legende: **statisch** in `web/templates/index.html` (`#graph_legend`), Einträge
  gelesen/geschrieben/Join-Pfad/Start/Ziel; CSS `.graph-legend`/`.lg-sw` in `app.css`.
- Die Per-Ergebnis-Statuszeile in `renderJoinResult` zeigt `· ⚠ 1-N` bei Fan-out (bleibt).

## Scope

**In Scope (AP-C):**
- `#sb_join_types`-Zeile (Markup + `renderJoinTypeControls`-Befüllung der separaten Box) entfernen.
- `renderPathSeq` um einen `isActive`-Modus erweitern: beim **aktiven** Pfad an jedem Schritt ein
  **kompaktes** `<select class="sb-jt">` (Optionen INNER/LEFT/RIGHT/FULL, aktueller Wert aus
  `SB_JOIN_TYPES[k]`) neben dem Richtungs-Chip + ein `<span class="jt-orphan" data-step="k">`;
  nicht-aktive Pfade unverändert read-only (nur Chips).
- Die Pfadliste re-rendern, wenn ein anderer Pfad aktiv wird (damit nur der aktive editierbar ist).
- Inline-Selects an `SB_JOIN_TYPES` + `runBuild(true)` verdrahten; die AP-47-Orphan-Logik
  (`_loadOrphans`/`_applyOrphanHints`) auf die inline `.jt-orphan`-Spans des aktiven Pfads zeigen
  lassen (Feature-Parität, keine Regression).
- CSS: `.sb-jt` ≤ Schriftgröße (kompakt). Alte `.sb-join-types`/`.jt-lbl`-Regeln entfernen/umwidmen.

**In Scope (AP-D):**
- `#sb_fanout_hint`-Kachel-Markup + die `runBuild`-Befüllung entfernen; CSS `.sb-fanout-hint`
  entfernen.
- In `#graph_legend` (`index.html`) zwei Einträge ergänzen, mit den vorhandenen Chip-Stilen:
  `<span class="step-dir many">1-N</span> kann Zeilen vervielfachen` und
  `<span class="step-dir one">N-1</span> sicher`.

**Out of Scope (bleibt unverändert):**
- Die inline 1-N/N-1-**Richtungs-Chips** in den Pfadzeilen (markieren weiter die Richtung).
- Die Per-Ergebnis-Statuszeile `· ⚠ 1-N` in `renderJoinResult`.
- AP-E (Move ↑/↓), AP-F (Analyzer-Vorschläge). Generiertes SQL, Endpoints, `core/`, `web/routes.py`.

## Entscheidungen

- **Join-Typ-Selects nur am aktiven Pfad** — Join-Typen gelten für den zu generierenden Pfad;
  editierbare Selects an jedem Kandidaten wären semantisch falsch und verwirrend.
- **Orphan-Hinweise (AP-47) bleiben** — sie ziehen mit an die inline-Selects.
- **Nur die Erklär-Kachel wandert in die Legende** — Richtungs-Chips und Ergebnis-Statuszeile
  bleiben, wo sie sind.

## Komponenten & Änderungen

### 1. `web/static/js/app.js`
- `openSqlBuilder`: `<div class="row sb-join-types" id="sb_join_types"></div>` **entfernen**; den
  `#sb_fanout_hint`-Div **entfernen**.
- `renderPathSeq(p, isActive)`: aktive Variante rendert je Schritt Chip + kompaktes `<select.sb-jt
  data-step="k">` (Wert aus `SB_JOIN_TYPES`) + `<span.jt-orphan data-step="k">`.
- Die Pfadlisten-Erzeugung (in `runBuild`) markiert den aktiven Index und rendert dessen Zeile mit
  `isActive=true`; Klick auf einen anderen Pfad (`renderJoinResult`) re-rendert die Liste mit neuem
  aktivem Index und verdrahtet die Selects neu.
- `renderJoinTypeControls` entfällt/wird zu einer Funktion, die die inline-Selects des aktiven
  Pfads verdrahtet + `_loadOrphans(i).then(_applyOrphanHints(i))` aufruft; `_applyOrphanHints` zielt
  auf die inline `.jt-orphan[data-step]`-Spans statt auf `#sb_join_types`.
- `runBuild`: die `#sb_fanout_hint`-Befüllung entfernen; das Leeren von `#sb_join_types` (im
  Leer-Pfad-Zweig) entfernen.

### 2. `web/templates/index.html`
- In `#graph_legend` zwei `<span>`-Einträge für 1-N und N-1 ergänzen (Chip-Stile wiederverwenden).

### 3. `web/static/css/app.css`
- `.sb-jt` (kompakter Inline-Select ≤ Schriftgröße) ergänzen.
- `.sb-join-types`/`.jt-lbl` entfernen (nicht mehr genutzt); `.jt-step`/`.jt-orphan` ggf. an den
  inline-Kontext anpassen. `.sb-fanout-hint` entfernen.
- `.graph-legend span .step-dir` ggf. minimale Größenanpassung, damit die Chips in die Legende
  passen.

## Rückwärtskompatibilität / Risiko

Keine ID-relevante Logik-, API- oder SQL-Änderung; `SB_JOIN_TYPES`/`runBuild`/Orphan-Logik bleiben
funktional gleich, nur der Render-Ort ändert sich. Risiko: (a) die Pfad-Reselektion muss die
inline-Selects sauber neu verdrahten (sonst tote Dropdowns), (b) `.sb-jt` muss wirklich kompakt
sein. Gegenmittel: Browser-Smoke.

## Teststrategie

- **Kein neuer pytest-Test** (keine Python-Änderung); volle Suite bleibt **308/2** als
  Regressionswächter. **`node --check`** (Syntax).
- **Browser-Smoke (Controller, Playwright):**
  - Es gibt **keine** `#sb_join_types`-Zeile mehr und **keine** `#sb_fanout_hint`-Kachel.
  - Der aktive Pfad in `#path_list` zeigt je Schritt ein **kompaktes** Join-Typ-`<select>`
    (Höhe/Schrift ≈ Text, deutlich < Standard-Steuerelement) neben dem Richtungs-Chip; ein anderer
    Kandidatenpfad zeigt **kein** Select.
  - Join-Typ ändern → SQL wird neu gebaut (z. B. `LEFT JOIN` erscheint); Pfadwechsel überträgt die
    Selects auf den neuen aktiven Pfad.
  - Die Graph-Legende enthält die Einträge **1-N** und **N-1**.
  - Keine Konsolenfehler.

## Release

UI-only, kein Core/Endpoint/Verhalten → **Patch-Bump 0.43.3 → 0.43.4** via `sync_version.py
--patch`. Changelog (Root + Mirror) „Changed/Geändert: Join-Typ-Dropdowns inline in die aktive
Pfad-Zeile (separate Zeile entfällt); 1-N/N-1-Erklärung in die Graph-Legende verschoben", CLAUDE.md/
Roadmap nachziehen, Test-Badge unverändert (308), Oberflächen-Referenz (`referenz/oberflaeche.md`)
anpassen, Site-Build + (nutzer-gated) gh-pages-Deploy.
