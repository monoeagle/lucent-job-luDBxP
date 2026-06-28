# AP-E — Zeilen Move ↑/↓ (SQL-Builder)

**Datum:** 2026-06-28
**Status:** genehmigt (Design)
**Scope:** reines Frontend — `web/static/js/app.js` + `web/static/css/app.css`. Keine Route, kein `core/`, keine SQL-Generierung serverseitig.

## Ziel

Im SQL-Builder einzelne Zeilen per **Button** (kein Drag&Drop — Entscheidung steht) innerhalb ihrer Sektion nach oben/unten verschieben. Nur die zwei Sektionen, in denen die Reihenfolge die erzeugte SQL ändert:

- **ORDER BY** (`#order_bys`, `.orderby-row`) → Reihenfolge = Sortier-**Priorität**.
- **Spalten / extra SELECTs** (`#extra_cols`, `.col-row`) → Reihenfolge = **SELECT-/GROUP-BY-Reihenfolge**.

WHERE (`#filters`) und HAVING (`#havings`) bekommen **keine** Move-Buttons — dort ist die Reihenfolge nur kosmetisch (AND-verknüpft).

## Warum das genügt

Die `collect*`-Funktionen lesen ihre Zeilen via `querySelectorAll` in **DOM-Reihenfolge**:

- `collectOrderBy()` iteriert `#order_bys .orderby-row` → Array in DOM-Order.
- `collectExtraSelects()` iteriert `#extra_cols .col-row` → Array in DOM-Order.

Damit folgt die Semantik automatisch aus der DOM-Position. Ein Move ist ein reines `insertBefore` — keine Datenstruktur, kein State außerhalb des DOM.

## Komponenten

### 1. Markup (in `addOrderByRow` / `addColRow`)

Vor dem bestehenden `✕`-Button (`.ob-del` / `.c-del`) zwei kleine quadratische Buttons:

```html
<button type="button" class="sb-move sb-up">↑</button>
<button type="button" class="sb-move sb-down">↓</button>
```

`type="button"` (kein Form-Submit). Gemeinsame Klasse `.sb-move` für beide Zeilentypen.

### 2. CSS (`app.css`)

- Neue Regel `.sb-move`: Quadrat `width/height: var(--sb-ctrl-h)`, `padding: 0`, `flex: 0 0 auto`, neutraler Rahmen/Hintergrund (wie `.ob-del`/`.c-del`, aber **nicht** rot — Standardfarbe), `cursor: pointer`, `line-height: 1`. Hover: leichtes Grau.
- `:disabled`-Zustand: `opacity: .35; cursor: default;`.
- `.sb-move` muss in die `:not(...)`-Ausschlussliste der generischen Button-Regel (aktuell Zeile ~193: `.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy):not(.sb-add)`) **und** ihrer Hover-Variante aufgenommen werden, sonst erbt sie `min-width: 140px`.

### 3. Verhalten (JS)

```js
// Verschiebt eine Builder-Zeile innerhalb ihres Containers; dir = -1 (hoch) / +1 (runter).
function moveRow(row, dir) {
  const ref = dir < 0 ? row.previousElementSibling : row.nextElementSibling;
  if (!ref) return;                       // schon am Rand
  if (dir < 0) row.parentNode.insertBefore(row, ref);
  else         row.parentNode.insertBefore(ref, row);
  refreshMoveBtns(row.parentNode);
}
```

In `addOrderByRow` / `addColRow` werden die zwei Buttons verdrahtet:
`up.addEventListener("click", () => moveRow(row, -1))`, analog `down` mit `+1`.

### 4. Rand-Zustand (`refreshMoveBtns`)

```js
// Graut ↑ in der ersten und ↓ in der letzten Zeile eines Containers aus.
function refreshMoveBtns(container) {
  const rows = [...container.children];
  rows.forEach((r, i) => {
    const up = r.querySelector(".sb-up"), down = r.querySelector(".sb-down");
    if (up)   up.disabled   = (i === 0);
    if (down) down.disabled = (i === rows.length - 1);
  });
}
```

Aufruf nach jedem **Add** (am Ende von `addOrderByRow`/`addColRow`, nach `appendChild`), **Move** (in `moveRow`) und **Delete** (im `✕`-Handler, nach `row.remove()`). Container: `$("order_bys")` bzw. `$("extra_cols")`.

### 5. Rebuild-Verhalten

Move bleibt **gestaged** (kein Auto-Rebuild) — konsistent mit dem bestehenden Verhalten genau dieser zwei Zeilentypen: deren `✕`-Delete und Add lösen ebenfalls **kein** `_rebuildIfBuilt()` aus (nur WHERE/HAVING rebuilden live). Der Build wird per Build-Button angewandt.

## Datenfluss

```
Klick ↑/↓  →  moveRow(row, dir)  →  DOM insertBefore  →  refreshMoveBtns()
                                          │
Klick "Build"  →  collectOrderBy()/collectExtraSelects() liest DOM-Order  →  /api/joinpath  →  SQL spiegelt neue Reihenfolge
```

## Verifikation

Reines JS → die **pytest-Suite (308 passed, 2 skipped) wächst nicht**. Verifikation per neuem Playwright-Browser-Smoke `verify_move.py` (Vorlage: `.superpowers/sdd/verify_*.py`, System-`python3`, Server auf `127.0.0.1:5057`). Prüfpunkte:

1. ORDER-BY-Zeile und Spalten-Zeile haben je `↑`/`↓`-Buttons.
2. Nach `↓`-Klick auf die erste von zwei Zeilen ist die DOM-Reihenfolge getauscht.
3. `↑` der ersten Zeile und `↓` der letzten Zeile sind `disabled`.
4. Nach Reorder + Build spiegelt die generierte SQL die neue Reihenfolge:
   - ORDER BY: getauschte Spalten-Priorität in der `ORDER BY`-Klausel.
   - SELECT: getauschte Spaltenreihenfolge in der Auswahlliste (und damit GROUP BY).
5. Keine neuen Console-Errors (außer vorbestehendem benignen `favicon.ico`-404).

## Release-Schritte

- Version-Bump `--minor` (Feature) via `sync_version.py` **+ icon-rail `APP_VERSION` manuell**.
- Changelog + Doc-Mirror, Roadmap/Board/Gantt (AP-E **namentlich**, jedes Item einzeln), Badge, Site-Build, gh-pages-Deploy.
- Deutsch / NO-CDN. SDD-Final-Review nicht weglassen.

## Nicht im Scope

- WHERE/HAVING-Move (kosmetisch, bewusst weggelassen).
- Drag&Drop (verworfen).
- Move zwischen Sektionen.
- Live-Rebuild bei Move (kann später nachgezogen werden, falls gewünscht).
