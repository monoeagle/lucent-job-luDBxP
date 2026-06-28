# AP-59 — SQL-Builder als einheitliches 2-Spalten-Raster

**Datum:** 2026-06-28
**Status:** genehmigt (Design)
**Scope:** `web/static/js/app.js` (`openSqlBuilder`-Markup) + `web/static/css/app.css`. Reines Frontend-Layout, keine Route, kein `core/`, keine SQL-Änderung.

## Ziel

Den SQL-Builder vertikal kompakter und konsistenter machen: die vier Klausel-Sektionen (Filter, Sortierung, Spalten, HAVING) verlieren ihre separate **Kopfzeile** (`Label [+]`). Stattdessen wird das Label **selbst zum Button** mit „+"-Präfix (`+ Filter`, `+ Sortierung`, `+ Spalten`, `+ HAVING`), der in der linken Spalte steht — wie die `Start`/`Ziel`-Labels. Die erste Klausel-Zeile liegt **auf derselben Linie** wie der Button; weitere Zeilen darunter. Alle Feld-Spalten fluchten in **einer** Spalte (Start, Ziel und alle Klausel-Zeilen).

Effekt: pro gefüllter Sektion wird eine Zeile gespart, und der Builder wird ein sauberes 2-Spalten-Raster (Label/Button-Spalte + Feld-Spalte).

## Ist-Stand (verifiziert)

- Start/Ziel sind `<div class="row"><label>Start</label> …Felder…</div>`; `.sqlbuilder label { min-width: 3rem }` (`app.css:168`), `.sqlbuilder .row` ist flex mit `gap:.4rem`.
- Jede Sektion: `<div class="sb-section"><div class="sb-section-head"><span class="sb-section-label">Filter</span><button class="sb-add" id="btn_add_filter">+</button></div><div class="filters" id="filters"></div></div>` (`app.js:331-346`).
- Klausel-Zeilen `.filter-row/.orderby-row/.col-row/.having-row` haben `padding-left: calc(3rem + .4rem)` zur Einrückung (`app.css:169-172`).
- `.sb-add` ist ein kleiner quadratischer `+`-Button (`width: var(--sb-ctrl-h)`, `app.css:224-229`).
- `.filters` hat kein eigenes CSS.

## Markup-Änderungen (`app.js`, `openSqlBuilder`)

1. Start/Ziel-Labels bekommen die Klasse `sb-rl`:
   - `<label class="sb-rl">Start</label>`, `<label class="sb-rl">Ziel</label>`.
2. Jede Sektion wird zu **einem** Button + Zeilen-Container (kein `sb-section-head`/`sb-section-label` mehr). Beispiel Filter:
   ```js
   `<div class="sb-section">` +
   `<button id="btn_add_filter" class="sb-add" title="Filterbedingung (mit UND verknüpft)">+ Filter</button>` +
   `<div class="filters" id="filters"></div></div>` +
   ```
   Analog: `+ Sortierung` (`#order_bys`), `+ Spalten` (`#extra_cols`), `+ HAVING` (`#havings`). **Button-IDs und Container-IDs bleiben exakt gleich** → `addFilterRow`/`addOrderByRow`/`addColRow`/`addHavingRow`, ihre Event-Verdrahtung und alle `collect*`/`clear`-Funktionen bleiben unberührt.

## CSS-Änderungen (`app.css`)

1. Neue Variable in `.sqlbuilder { … }` (bei `--sb-ctrl-w/h`):
   ```css
   --sb-label-w: 6.5rem;   /* Breite der linken Label-/Button-Spalte */
   ```
2. Start/Ziel-Label-Breite — **mit höherer Spezifität als `.sqlbuilder label`** (sonst gewinnt dessen `min-width:3rem`; CSS-Spezifitäts-Falle):
   ```css
   .sqlbuilder label.sb-rl { min-width: var(--sb-label-w); }
   ```
3. Sektion als Flex-Zeile (Button links, Zeilen rechts):
   ```css
   .sb-section { display: flex; align-items: flex-start; gap: .4rem; margin: .25rem 0; }
   .sb-section .filters { display: flex; flex-direction: column; gap: .3rem; flex: 1 1 auto; min-width: 0; }
   ```
4. `.sb-add` umbauen vom kleinen Quadrat zum linksbündigen, beschrifteten Button in Spaltenbreite:
   ```css
   .sb-add {
     min-width: var(--sb-label-w); height: var(--sb-ctrl-h);
     padding: 0 .5rem; flex: 0 0 auto; text-align: left;
     border: 1px solid #bcbcc6; border-radius: 4px; background: #f3f3f6;
     cursor: pointer; font-size: .85rem; line-height: 1;
   }
   .sb-add:hover { background: #e8e8ef; }
   ```
   (ersetzt die bisherige `.sb-add`-Regel mit fixem `width: var(--sb-ctrl-h)`.)
5. Einrückung der Klausel-Zeilen **entfernen** — die Button-Spalte liefert den Offset jetzt über das Flex-Layout. Aus `app.css:169`:
   ```css
   .filter-row, .orderby-row, .col-row, .having-row {
     display: flex; gap: .4rem; align-items: center; margin: .3rem 0;
   }
   ```
   (`padding-left: calc(3rem + .4rem)` streichen.)
6. Die nun ungenutzten Regeln `.sb-section-head` und `.sb-section-label` entfernen.

## Verhalten

- **Leere Sektion:** nur der Button (`+ Filter`) auf seiner Zeile.
- **Klick auf `+ Filter`:** fügt die erste Klausel-Zeile hinzu; sie liegt rechts neben dem Button auf **derselben Linie** (`align-items: flex-start` richtet Button-Oberkante und Zeilen-Oberkante aus; beide Höhe `var(--sb-ctrl-h)`).
- **Weitere Zeilen:** stapeln im `.filters`-Container unter der ersten, fluchten mit Start/Ziel-Feldern.
- Add/Delete/Move/Collect-Logik unverändert (nur das Container-Wrapping ändert sich, IDs identisch).

## Verifikation

Reines JS/CSS (live, kein App-Neustart). pytest **unverändert** (kein Python). Browser-Smoke `verify_grid.py` (System-`python3`, Vorlage `.superpowers/sdd/verify_*.py`, Demo-CMDB):

1. Buttons zeigen die Texte `+ Filter`, `+ Sortierung`, `+ Spalten`, `+ HAVING`.
2. **Alle vier `.sb-add`-Buttons sind gleich breit** (`offsetWidth` identisch) — d. h. kein Button (insb. der längste, `+ Sortierung`) überläuft die Spalte. Schlägt das fehl, `--sb-label-w` erhöhen, bis alle gleich breit sind.
3. **Fluchtung:** nach Hinzufügen je einer Zeile in **Filter** *und* **Sortierung** ist die linke x-Position des ersten Dropdowns beider Zeilen gleich der des `#start_table`-Dropdowns (±2px). (Sortierung ist der bindende Fall, weil `+ Sortierung` der breiteste Button ist.)
4. Vor dem Klick zeigt eine leere Sektion **nur** den Button (Zeilen-Container leer); nach `+ Filter`-Klick liegt die erste Zeile auf der Button-Linie (gleiche `getBoundingClientRect().top`, ±2px).
5. Keine neuen Console-Errors (favicon ignoriert).

> Startwert `--sb-label-w: 6.5rem`. Da „+ Sortierung" knapp ist, ist Check 2 das Gate: notfalls auf 7rem erhöhen.

## Release

- Patch-Bump `--patch` (0.45.1 → **0.45.2**, reines Layout — wie AP-B v0.43.3) + icon-rail `APP_VERSION` (TEST_COUNT bleibt 324) + `zensical.toml`.
- Changelog (Root EN + Mirror DE), `roadmap.md`-Versionslog + Gantt + Board (AP-59 **namentlich**), Site, gh-pages.
- Deutsch / NO-CDN. SDD-Final-Review nicht weglassen.

## Nicht im Scope

- Keine Änderung an Add/Delete/Move/Generieren-Logik oder am erzeugten SQL.
- Keine Pfeile (↑/↓) bei Filter/HAVING (bleibt Status quo, AND-verknüpft).
- Keine Änderung an der Aktions-/Ergebnisleiste (DISTINCT/LIMIT/Dialekt/Generieren) oder am `Zeilen`-Label der Ergebnisleiste (deren `min-width:3rem` bleibt).
