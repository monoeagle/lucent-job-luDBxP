# Design: AP-B — SQL-Builder Layout-Neuordnung (Klausel-Sektionen + Aktionsleiste)

**Datum:** 2026-06-28
**Status:** Genehmigt (Brainstorming abgeschlossen)
**Kontext:** Zweites AP des UI/UX-Umbau-Blocks nach AP-A (Umbenennung, v0.43.2). Reine Layout-/CSS-
Umordnung des SQL-Builder-Formulars; keine Funktions-/Verhaltensänderung.

## Ziel

Die heutige Steuerleiste (`sb-controls`) quetscht alles in **eine** Reihe — vier „+"-Add-Buttons
(Filter/Sortierung/Spalten/HAVING), die DISTINCT-Checkbox, LIMIT, den Dialekt-Wähler **und** den
„Generieren"-Button. Zudem stehen die „+"-Buttons **unter** den Zeilen-Containern, die sie befüllen,
was die Zuordnung trübt. **AP-B ordnet das Formular in beschriftete Klausel-Sektionen (je mit
eigenem Add-Button) plus eine getrennte Aktionsleiste neu** (gewählte Mockup-Variante „C"). Start/
Ziel-Zeilen bleiben unverändert.

## Scope

**In Scope:**
- **Vier Klausel-Sektionen** (Filter, Sortierung, Spalten, HAVING), jede **immer sichtbar** (auch
  leer), mit Sektions-Label (trägt den Namen) links und einem **kompakten „+"-Button** rechts; der
  bestehende Zeilen-Container der Sektion steht darunter.
- **Aktionsleiste** unten (`sb-actions`): `[✓ DISTINCT] [LIMIT __] [Dialekt ▾]` links,
  **`[ Generieren ]`** rechtsbündig.
- Neue CSS-Klassen + die nötige Anpassung der bestehenden Button-Breitenregel (siehe unten).

**Out of Scope (eigene APs / unverändert):**
- Join-Typ-Dropdowns inline in die Pfad-Schritt-Zeile (**AP-C**) — die `#sb_join_types`-Zeile bleibt
  hier wie sie ist.
- „1-N"-Badge in die Graph-Legende (**AP-D**).
- Zeilen Move ↑/↓ (**AP-E**).
- Start-/Ziel-Zeilen, Fanout-Hinweis, Pfadliste, SQL-Ausgabe-Block: **unverändert**.
- Keine Änderung an Element-IDs, JS-Logik, Endpoints oder generiertem SQL.

## Kernprinzip: nur Markup-Umordnung + CSS

Die Umstrukturierung passiert ausschließlich im `innerHTML`-Template von `openSqlBuilder`
(`web/static/js/app.js`) und in `web/static/css/app.css`. **Alle Element-IDs bleiben identisch**
(`btn_add_filter`, `btn_add_orderby`, `btn_add_col`, `btn_add_having`, `sb_distinct`, `sb_limit`,
`sb_dialect`, `btn_build`), nur ihre Position im DOM ändert sich. Die Event-Verdrahtung erfolgt
nach dem `innerHTML`-Setzen **per ID** (`$("btn_add_filter").addEventListener(...)` etc.) und greift
daher unverändert. `addFilterRow()`/`addOrderByRow()`/`addColRow()`/`addHavingRow()` hängen weiter an
`#filters`/`#order_bys`/`#extra_cols`/`#havings` — diese Container existieren weiter, nur in eine
Sektion eingebettet.

## Komponenten & Änderungen

### 1. `web/static/js/app.js` — `openSqlBuilder`-Markup
Der Block zwischen den Ziel-Zeilen und dem Fanout-Hinweis wird ersetzt. Heute:
- `#filters`, `#order_bys`, `#extra_cols`, `#havings` (vier leere Container hintereinander), danach
  die eine `sb-controls`-Zeile mit allen Buttons/Optionen.

Neu — vier Sektionen, dann die Aktionsleiste:

```html
<div class="sb-section">
  <div class="sb-section-head">
    <span class="sb-section-label">Filter</span>
    <button id="btn_add_filter" class="sb-add" title="Filterbedingung (mit UND verknüpft)">+</button>
  </div>
  <div class="filters" id="filters"></div>
</div>
<!-- analog: Sortierung/#order_bys (btn_add_orderby), Spalten/#extra_cols (btn_add_col),
     HAVING/#havings (btn_add_having) -->

<div class="row sb-actions">
  <label class="sb-check"><input type="checkbox" id="sb_distinct"> DISTINCT</label>
  <label class="sb-limit">LIMIT <input id="sb_limit" type="number" min="1" placeholder="–"></label>
  <label class="sb-dialect" title="SQL-Dialekt der generierten Abfrage">Dialekt
    <select id="sb_dialect">…fünf Optionen unverändert…</select></label>
  <button id="btn_build">Generieren</button>
</div>
```

Die Button-Tooltips bleiben (Texte wie heute). Der `btn_build`-Button wird in der Aktionsleiste per
CSS rechtsbündig (`margin-left:auto`).

### 2. `web/static/css/app.css` — neue Regeln
- `.sb-section { … }` — vertikaler Block, kleiner Abstand zwischen den Sektionen.
- `.sb-section-head { display:flex; align-items:center; gap:.4rem; }` — Label links, „+" rechts
  (oder Label mit `margin-right:auto`, damit „+" rechtsbündig).
- `.sb-section-label { … }` — gedämpfte, kleine Überschrift (Sektionsname).
- `.sb-add { … }` — **kompakter** quadratischer Button (≈ `var(--sb-ctrl-h)`), wie die
  bestehenden `.f-del`/`.ob-del`/`.c-del`-Buttons.
- `.sb-actions { display:flex; flex-wrap:wrap; align-items:center; gap:.4rem; }` und
  `.sb-actions #btn_build { margin-left:auto; }`.

**Wichtige Kollision (verifiziert):** die bestehende Regel
`/* app.css:193 */ .sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy) { min-width:140px; … }`
zwingt allen anderen Buttons 140px Mindestbreite auf. Der neue `.sb-add`-Button **muss** in diese
`:not(...)`-Ausschlusskette aufgenommen werden (→ `:not(.sb-add)`), sonst wird das „+" 140px breit.
`btn_build` bleibt absichtlich von der 140px-Regel erfasst (breiter Primär-Button).

## Rückwärtskompatibilität / Risiko

Keine ID-, JS- oder API-Änderung; generiertes SQL identisch. Risiko ist rein visuell: die
`:not(.sb-add)`-Ergänzung muss greifen, und die Sektionen/Aktionsleiste müssen sauber umbrechen.
Gegenmittel: Browser-Smoke (unten).

## Teststrategie

- **Kein neuer pytest-Test** (keine Python-/Verhaltensänderung); volle Suite bleibt **308/2** als
  Regressionswächter.
- **`node --check web/static/js/app.js`** (Syntax).
- **Browser-Smoke (Controller, Playwright):** die vier Sektionen rendern mit Label + kompaktem „+";
  jeder „+"-Button fügt eine Zeile **in seine** Sektion (`#filters` etc.) ein; die Aktionsleiste
  enthält DISTINCT, LIMIT, Dialekt und einen rechtsbündigen „Generieren"-Button; „Generieren" baut
  einen Pfad + SQL; der „+"-Button ist kompakt (nicht 140px breit); keine Konsolenfehler.

## Release

UI-only, kein Core/Endpoint/Verhalten → **Patch-Bump 0.43.2 → 0.43.3** via `sync_version.py --patch`.
Changelog (Root + Mirror) „Changed/Geändert: SQL-Builder-Layout — Klausel-Sektionen mit eigenem
Add-Button + getrennte Aktionsleiste", CLAUDE.md/Roadmap nachziehen, Test-Badge unverändert (308),
Oberflächen-Referenzseite (`referenz/oberflaeche.md`) ans neue Layout anpassen, Site-Build +
(nutzer-gated) gh-pages-Deploy. Architektur-Diagramme unverändert (kein neues Modul/Endpoint).
