# AP-B — SQL-Builder Layout (Klausel-Sektionen + Aktionsleiste) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the SQL-Builder form into four labeled clause sections (each with its own compact „+" add-button) plus a separate bottom action bar, without any behavior change.

**Architecture:** A pure markup + CSS reorganization. The `openSqlBuilder` `innerHTML` template (`web/static/js/app.js`) replaces the four bare row-containers + the single crammed `sb-controls` row with four `sb-section` blocks (label + „+" + existing container) and one `sb-actions` row (DISTINCT/LIMIT/Dialekt + „Generieren"). All element IDs are unchanged, so the by-ID event wiring and the `addFilterRow()`/`addOrderByRow()`/`addColRow()`/`addHavingRow()` functions keep working untouched. New CSS classes style the sections; one existing button-width rule gains a `:not(.sb-add)` exclusion.

**Tech Stack:** vanilla JS, CSS, Markdown, pytest (regression guard only).

## Global Constraints

- **No behavior/logic/API change:** identical element IDs, no JS logic edits, no `web/routes.py`/`core/` touch, generated SQL unchanged.
- **No CDN:** no new external assets.
- **Language:** German user-facing copy and commit messages. Section labels: „Filter", „Sortierung", „Spalten", „HAVING". Build button stays „Generieren".
- **Tests:** `./venv/bin/python -m pytest`. Baseline **308 passed, 2 skipped** — must stay exactly that (no Python/test touched; suite is a regression guard).
- **Element IDs preserved (verbatim):** `btn_add_filter`, `btn_add_orderby`, `btn_add_col`, `btn_add_having`, `sb_distinct`, `sb_limit`, `sb_dialect`, `btn_build`; containers `filters`, `order_bys`, `extra_cols`, `havings`.
- **CSS collision (binding):** the existing rule `.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy) { min-width:140px; … }` (and its `:hover` sibling) must gain `:not(.sb-add)`, else the compact „+" button renders 140px wide.
- **Scope OUT (other APs / unchanged):** join-type inline (AP-C — `#sb_join_types` row stays), 1-N badge → graph legend (AP-D), row move ↑/↓ (AP-E), Start/Ziel rows, fanout hint, path list, SQL output.
- **Version:** patch bump 0.43.2 → 0.43.3 via `./venv/bin/python sync_version.py --patch` (never hand-edit `config.APP_VERSION`).

---

## Task 1: Layout markup + CSS

**Files:**
- Modify: `web/static/js/app.js` (`openSqlBuilder` — the block currently at the four `<div class="filters" …>` containers + the `<div class="row sb-controls">…</div>`), `web/static/css/app.css` (the 140px button rule ~`193`/`198`; add new section/action rules)
- Test: none added (no JS unit harness; verified by `node --check` + the existing pytest suite as regression guard + a controller browser smoke afterwards).

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the SQL-Builder shows four labeled clause sections with compact „+" add-buttons and a bottom action bar. Task 2 (docs/release) describes the new layout.

- [ ] **Step 1: Replace the containers + controls row in `openSqlBuilder` (`web/static/js/app.js`)**

Find this exact block (between the Ziel-row markup and the `sb-fanout-hint` div):

```javascript
    `<div class="filters" id="filters"></div>` +
    `<div class="filters" id="order_bys"></div>` +
    `<div class="filters" id="extra_cols"></div>` +
    `<div class="filters" id="havings"></div>` +
    `<div class="row sb-controls">` +
    `<button id="btn_add_filter" title="Filterbedingung (mit UND verknüpft)">Filter +</button>` +
    `<button id="btn_add_orderby" title="Sortierungsspalte hinzufügen">Sortierung +</button>` +
    `<button id="btn_add_col" title="Weitere SELECT-Spalte hinzufügen">Spalten +</button>` +
    `<button id="btn_add_having" title="Gruppen nach Aggregat filtern (HAVING)">HAVING +</button>` +
    `<label class="sb-check"><input type="checkbox" id="sb_distinct"> DISTINCT</label>` +
    `<label class="sb-limit">LIMIT <input id="sb_limit" type="number" min="1" placeholder="–"></label>` +
    `<label class="sb-dialect" title="SQL-Dialekt der generierten Abfrage">Dialekt ` +
    `<select id="sb_dialect">` +
    `<option value="sqlite">SQLite</option>` +
    `<option value="postgresql">PostgreSQL</option>` +
    `<option value="mysql">MySQL</option>` +
    `<option value="mssql">MSSQL</option>` +
    `<option value="oracle">Oracle</option></select></label>` +
    `<button id="btn_build">Generieren</button></div>` +
```

Replace it with (four sections, then the action bar — IDs identical, add-buttons now compact „+" with class `sb-add`):

```javascript
    `<div class="sb-section"><div class="sb-section-head">` +
    `<span class="sb-section-label">Filter</span>` +
    `<button id="btn_add_filter" class="sb-add" title="Filterbedingung (mit UND verknüpft)">+</button>` +
    `</div><div class="filters" id="filters"></div></div>` +
    `<div class="sb-section"><div class="sb-section-head">` +
    `<span class="sb-section-label">Sortierung</span>` +
    `<button id="btn_add_orderby" class="sb-add" title="Sortierungsspalte hinzufügen">+</button>` +
    `</div><div class="filters" id="order_bys"></div></div>` +
    `<div class="sb-section"><div class="sb-section-head">` +
    `<span class="sb-section-label">Spalten</span>` +
    `<button id="btn_add_col" class="sb-add" title="Weitere SELECT-Spalte hinzufügen">+</button>` +
    `</div><div class="filters" id="extra_cols"></div></div>` +
    `<div class="sb-section"><div class="sb-section-head">` +
    `<span class="sb-section-label">HAVING</span>` +
    `<button id="btn_add_having" class="sb-add" title="Gruppen nach Aggregat filtern (HAVING)">+</button>` +
    `</div><div class="filters" id="havings"></div></div>` +
    `<div class="row sb-actions">` +
    `<label class="sb-check"><input type="checkbox" id="sb_distinct"> DISTINCT</label>` +
    `<label class="sb-limit">LIMIT <input id="sb_limit" type="number" min="1" placeholder="–"></label>` +
    `<label class="sb-dialect" title="SQL-Dialekt der generierten Abfrage">Dialekt ` +
    `<select id="sb_dialect">` +
    `<option value="sqlite">SQLite</option>` +
    `<option value="postgresql">PostgreSQL</option>` +
    `<option value="mysql">MySQL</option>` +
    `<option value="mssql">MSSQL</option>` +
    `<option value="oracle">Oracle</option></select></label>` +
    `<button id="btn_build">Generieren</button></div>` +
```

- [ ] **Step 2: Add `:not(.sb-add)` to the 140px button rule (`web/static/css/app.css`)**

Find (around line 193 and 198):

```css
.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy) {
  min-width: 140px; height: var(--sb-ctrl-h); padding: 0 .8rem;
  border: 1px solid #bcbcc6; border-radius: 4px; background: #f3f3f6;
  cursor: pointer; font-size: .85rem; white-space: nowrap;
}
.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy):hover {
  background: #e8e8ef;
}
```

Add `:not(.sb-add)` to BOTH selectors:

```css
.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy):not(.sb-add) {
  min-width: 140px; height: var(--sb-ctrl-h); padding: 0 .8rem;
  border: 1px solid #bcbcc6; border-radius: 4px; background: #f3f3f6;
  cursor: pointer; font-size: .85rem; white-space: nowrap;
}
.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy):not(.sb-add):hover {
  background: #e8e8ef;
}
```

- [ ] **Step 3: Add the new section/action CSS (`web/static/css/app.css`)**

Append these rules near the other `.sqlbuilder` rules (e.g. right after the `.f-del, .ob-del, .c-del` block):

```css
/* AP-B: clause sections (label + compact "+") and bottom action bar. */
.sb-section { margin: .3rem 0; }
.sb-section-head { display: flex; align-items: center; gap: .4rem; }
.sb-section-label { min-width: 5.5rem; font-size: .8rem; font-weight: 600; color: #555; }
.sb-add {
  width: var(--sb-ctrl-h); height: var(--sb-ctrl-h); padding: 0; flex: 0 0 auto;
  border: 1px solid #bcbcc6; border-radius: 4px; background: #f3f3f6;
  cursor: pointer; line-height: 1; font-size: 1rem;
}
.sb-add:hover { background: #e8e8ef; }
.sb-actions { margin-top: .5rem; }
.sb-actions #btn_build { margin-left: auto; }
```

(`.sb-actions` is rendered as `class="row sb-actions"`, so it inherits the existing `.sqlbuilder .row` flex layout; only the top margin and the right-aligned build button are new.)

- [ ] **Step 4: Verify JS syntax + that all IDs survived**

Run: `node --check web/static/js/app.js`
Expected: exit 0, no output.

Run: `grep -oE 'id="(btn_add_filter|btn_add_orderby|btn_add_col|btn_add_having|sb_distinct|sb_limit|sb_dialect|btn_build)"|id="(filters|order_bys|extra_cols|havings)"' web/static/js/app.js | sort -u | wc -l`
Expected: `12` (all eight control IDs + four container IDs still present).

Run: `grep -c "sb-controls" web/static/js/app.js web/static/css/app.css`
Expected: `0` for both files (the old controls row is gone; no orphan CSS — note: if `app.css` had a `.sb-controls` rule it should be removed; confirm there is none left by this grep).

- [ ] **Step 5: Run the full suite (regression guard)**

Run: `./venv/bin/python -m pytest -q`
Expected: `308 passed, 2 skipped` (unchanged — no Python touched).

- [ ] **Step 6: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat: SQL-Builder-Layout — Klausel-Sektionen mit '+' + getrennte Aktionsleiste

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Controller browser smoke (the four sections render with label + a COMPACT „+" button — not 140px wide; each „+" appends a row to its own section's container; the action bar shows DISTINCT/LIMIT/Dialekt and a right-aligned „Generieren"; „Generieren" builds a path + SQL; no console errors) runs after this task, not in the implementer.

---

## Task 2: Release v0.43.3 + oberflaeche doc

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md` + mirror `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/javascripts/icon-rail.js` (APP_VERSION), `luDBxP-docs/docs/referenz/oberflaeche.md` (describe the new layout), site rebuild.

**Interfaces:**
- Consumes: the new layout from Task 1.
- Produces: a v0.43.3 patch release documenting the layout change.

- [ ] **Step 1: Bump the version (patch)**

Run: `./venv/bin/python sync_version.py --patch`
Expected: `config.py` + `lucent-hub.yml` go `0.43.2 → 0.43.3`.

- [ ] **Step 2: Add the changelog entry (root + mirror)**

Add a `[0.43.3] — 2026-06-28` section to `CHANGELOG.md`:

```markdown
## [0.43.3] — 2026-06-28

### Changed
- SQL-Builder layout: the clause builders are now four labeled sections
  (Filter, Sortierung, Spalten, HAVING), each with its own compact „+"
  add-button, and the output options (DISTINCT, LIMIT, Dialekt) plus the
  „Generieren" button moved into a separate bottom action bar. Markup/CSS
  only — no behavior change, all element IDs and the generated SQL are
  unchanged.
```

and to the mirror `luDBxP-docs/docs/entwicklung/changelog.md`:

```markdown
## [0.43.3] — 2026-06-28

### Geändert
- SQL-Builder-Layout: die Klausel-Builder sind jetzt vier beschriftete
  Sektionen (Filter, Sortierung, Spalten, HAVING) mit je eigenem kompaktem
  „+"-Button; die Ausgabe-Optionen (DISTINCT, LIMIT, Dialekt) und der
  „Generieren"-Button liegen in einer getrennten Aktionsleiste unten. Nur
  Markup/CSS — keine Verhaltensänderung, alle Element-IDs und das generierte
  SQL bleiben gleich.
```

- [ ] **Step 3: Bump icon-rail APP_VERSION (TEST_COUNT unchanged)**

In `luDBxP-docs/docs/javascripts/icon-rail.js`, change `APP_VERSION` from `'0.43.2'` to `'0.43.3'`. Leave `TEST_COUNT` at `'308'`.

- [ ] **Step 4: Update the UI reference page**

In `luDBxP-docs/docs/referenz/oberflaeche.md`, update the SQL-Builder description to match the new layout: the four clause sections each with a „+" add-button, and the bottom action bar (DISTINCT / LIMIT / Dialekt / „Generieren"). Adjust any sentence that describes the old single control row. Keep it concise and factual.

- [ ] **Step 5: Build the site and verify**

Run: `cd luDBxP-docs && ./run_luDBxP_docs.sh --build`
Expected: site builds, no errors. Then:
Run: `grep -o "APP_VERSION *= *'0.43.3'" site/javascripts/icon-rail.js` → expect a match.
Run: `grep -o "0.43.3" site/entwicklung/changelog/index.html | head -1` → expect `0.43.3`.
Then from the repo root re-run `./venv/bin/python -m pytest -q` → still `308 passed, 2 skipped`.

- [ ] **Step 6: Commit the release**

```bash
git add -A
git commit -m "docs: Release v0.43.3 — SQL-Builder-Layout (Klausel-Sektionen + Aktionsleiste)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Pushing to `origin/master` and the `gh-pages` deploy are a separate, user-confirmed step — do not push without confirmation.

---

## Self-Review

**Spec coverage:**
- Four labeled clause sections, always visible, each with a compact „+" → Task 1 Step 1 + CSS Step 3. ✓
- Bottom action bar (DISTINCT/LIMIT/Dialekt + right-aligned „Generieren") → Task 1 Step 1 + `.sb-actions #btn_build{margin-left:auto}` Step 3. ✓
- All element IDs preserved (event wiring + addRow functions unchanged) → Task 1 Step 1 keeps IDs; Step 4 grep verifies 12 IDs. ✓
- CSS 140px collision fixed via `:not(.sb-add)` → Task 1 Step 2. ✓
- No behavior/API/SQL change, suite stays 308/2 → Task 1 Step 5, Task 2 Step 5. ✓
- Out-of-scope items (join-type inline, 1-N legend, move ↑/↓, Start/Ziel) untouched → no task edits them; Global Constraints. ✓
- Patch bump 0.43.2→0.43.3 + changelog + badge version + oberflaeche doc + site → Task 2. ✓
- Browser smoke (controller) → noted after Task 1. ✓

**Placeholder scan:** No TBD/TODO; every code/markup step shows the exact content. ✓

**Type consistency:** class names identical across spec, Task 1 markup, and CSS (`sb-section`, `sb-section-head`, `sb-section-label`, `sb-add`, `sb-actions`); the `:not(.sb-add)` exclusion matches the `.sb-add` button class; element IDs identical to the Global Constraints list. ✓
