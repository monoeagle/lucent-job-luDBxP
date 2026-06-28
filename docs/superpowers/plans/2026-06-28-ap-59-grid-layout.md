# AP-59 — SQL-Builder 2-Spalten-Raster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die vier SQL-Builder-Sektionen verlieren ihre Kopfzeile; das Label wird zum Button `+ Filter`/`+ Sortierung`/`+ Spalten`/`+ HAVING` in der linken Spalte, die erste Klausel-Zeile liegt auf derselben Linie, und alle Felder fluchten in einer Spalte (wie Start/Ziel).

**Architecture:** Reines Frontend. `openSqlBuilder` baut die Sektionen ohne `sb-section-head`/`sb-section-label` (ein Button + Zeilen-Container, IDs unverändert); CSS macht `.sb-section` zu einer Flex-Zeile (Button links, Zeilen rechts), gibt linker Spalte eine einheitliche Breite `--sb-label-w` und entfernt die alte Zeilen-Einrückung. Add/Collect/Move-Logik bleibt unberührt, weil alle Element-IDs gleich bleiben.

**Tech Stack:** Vanilla JS (`web/static/js/app.js`), CSS (`web/static/css/app.css`), Playwright-Browser-Smoke (System-`python3`).

## Global Constraints

- **NO CDN:** keine externen Assets — reine lokale Edits.
- **Sprache:** Button-Texte/Tooltips Deutsch; Code-Bezeichner englisch wie im Bestand.
- **Layering:** nur `web/`; keine Route, kein `core/`, **kein** verändertes SQL.
- **IDs unverändert:** `#btn_add_filter/_orderby/_col/_having` + Container `#filters/#order_bys/#extra_cols/#havings` bleiben exakt gleich → Add-/Collect-/Move-Funktionen unberührt.
- **CSS-Spezifität:** Start/Ziel-Label-Breite über `.sqlbuilder label.sb-rl` setzen (höher als `.sqlbuilder label`), sonst gewinnt `min-width:3rem`.
- **Server live:** JS/CSS werden live ausgeliefert (kein App-Neustart); Server läuft auf `http://127.0.0.1:5057`.
- **venv:** Python 3.14; volle Suite `./venv/bin/python -m pytest -q` = **324 passed, 2 skipped** (muss unverändert bleiben — kein Python berührt).
- **Smoke:** System-`python3` + Playwright, Demo-DB `sample_data/demo_cmdb.db`, Vorlage `.superpowers/sdd/verify_*.py`.
- **Version-Bump:** `sync_version.py --patch` (0.45.1 → 0.45.2) + icon-rail `APP_VERSION` manuell (TEST_COUNT bleibt 324).

---

## File Structure

- `web/static/js/app.js` — `openSqlBuilder`: Start/Ziel-Labels erhalten `sb-rl`; die vier Sektionen werden zu `<div class="sb-section"><button class="sb-add" …>+ Label</button><div class="filters" id="…"></div></div>`.
- `web/static/css/app.css` — `--sb-label-w`, `.sqlbuilder label.sb-rl`, `.sb-section` (flex), `.sb-section .filters`, `.sb-add` (umgebaut), Zeilen-`padding-left` entfernt, `.sb-section-head`/`.sb-section-label` entfernt.
- `.superpowers/sdd/verify_grid.py` — Browser-Smoke (Buttons, Fluchtung, gleiche Button-Breite, leere Sektion).

---

### Task 1: 2-Spalten-Raster (Markup + CSS)

**Files:**
- Create: `.superpowers/sdd/verify_grid.py`
- Modify: `web/static/js/app.js` (`openSqlBuilder`, ~Z.323-346)
- Modify: `web/static/css/app.css` (~Z.162-172, 221-229)

**Interfaces:**
- Consumes (bestehend): `aggOptions()`, `addFilterRow/addOrderByRow/addColRow/addHavingRow` (verdrahtet auf die unveränderten Button-IDs), CSS-Vars `--sb-ctrl-w/h`.
- Produces: neue Klasse `sb-rl` (Start/Ziel-Label), neue Var `--sb-label-w`; Sektions-Buttons tragen jetzt Text `+ Filter`/`+ Sortierung`/`+ Spalten`/`+ HAVING`.

- [ ] **Step 1: Failing Browser-Smoke schreiben**

Create `.superpowers/sdd/verify_grid.py`:

```python
"""Browser smoke for AP-59: the SQL-Builder is a 2-column grid — each clause
section is a single '+ Label' button in the left column with the first row on the
same line; all field columns align with Start/Ziel. Demo CMDB."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5057/"
DB = "/home/meagle/Dokumente/_Projects/lucent-job-luDBxP/sample_data/demo_cmdb.db"
BOOT = """async (d)=>{const r=await postJSON('/api/connect',{db_type:'sqlite',filepath:d});setCurrentUrl(r.connection_url);await doConnect();return 1;}"""

results = []
def check(n, ok, d=""):
    results.append((n, ok)); print(("PASS" if ok else "FAIL"), n, ("- " + d) if d else "")

def launch(p):
    last = None
    for kw in ({"executable_path": "/usr/bin/chromium"}, {"executable_path": "/usr/bin/google-chrome"}, {}):
        try: return p.chromium.launch(headless=True, **kw)
        except Exception as e: last = e
    raise last

with sync_playwright() as p:
    b = launch(p); page = b.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(f"{m.text} [{m.location.get('url','')}]") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.evaluate(BOOT, DB)
    page.wait_for_selector(".sqlbuilder", timeout=5000)

    # buttons carry the "+ Label" text
    texts = page.eval_on_selector_all(".sb-add", "els => els.map(e => e.textContent.trim())")
    want = ["+ Filter", "+ Sortierung", "+ Spalten", "+ HAVING"]
    check("section buttons show '+ Label' text", texts == want, str(texts))

    # all four add-buttons are equally wide (longest '+ Sortierung' must not overflow)
    widths = page.eval_on_selector_all(".sb-add", "els => els.map(e => Math.round(e.offsetWidth))")
    check("all add-buttons equal width (no overflow)", len(set(widths)) == 1, str(widths))

    # empty section shows only the button (rows container empty)
    nFilterRows = page.eval_on_selector_all("#filters .filter-row", "els => els.length")
    check("empty section has no rows before click", nFilterRows == 0, f"{nFilterRows} rows")

    # add one Filter row and one Sortierung row
    page.click("#btn_add_filter")
    page.click("#btn_add_orderby")
    page.wait_for_selector("#filters .filter-row", timeout=5000)

    startX = page.eval_on_selector("#start_table", "el => el.getBoundingClientRect().left")
    fX = page.eval_on_selector("#filters .filter-row .f-table", "el => el.getBoundingClientRect().left")
    oX = page.eval_on_selector("#order_bys .orderby-row .ob-table", "el => el.getBoundingClientRect().left")
    check("filter fields align with Start column", abs(fX - startX) <= 2, f"start={startX:.0f} filter={fX:.0f}")
    check("sortierung fields align with Start column (widest button)", abs(oX - startX) <= 2, f"start={startX:.0f} sort={oX:.0f}")

    # first row sits on the same line as its '+ Filter' button
    btnTop = page.eval_on_selector("#btn_add_filter", "el => el.getBoundingClientRect().top")
    rowTop = page.eval_on_selector("#filters .filter-row", "el => el.getBoundingClientRect().top")
    check("first filter row on the button's line", abs(rowTop - btnTop) <= 2, f"btn={btnTop:.0f} row={rowTop:.0f}")

    real = [e for e in errors if "favicon" not in e.lower()]
    check("no console errors (favicon ignored)", not real, "; ".join(real[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
```

- [ ] **Step 2: Smoke laufen lassen, Fehlschlag bestätigen**

Voraussetzung: Server läuft (`bash run.sh --tray` bzw. bereits aktiv auf :5057).
Run: `python3 .superpowers/sdd/verify_grid.py`
Expected: FAIL — der erste Check scheitert (Buttons zeigen heute „+", nicht „+ Filter"; `texts == ['+','+','+','+']`).

- [ ] **Step 3: Markup — Start/Ziel-Labels + Sektionen umbauen (`app.js`)**

In `openSqlBuilder` die Start/Ziel-Label-Zeilen (~Z.323/326) — Klasse ergänzen:
```js
    `<div class="row"><label class="sb-rl">Start</label>` +
```
```js
    `<div class="row"><label class="sb-rl">Ziel</label>` +
```

Den gesamten Sektions-Block (~Z.331-346, die vier `sb-section`/`sb-section-head`-Konstrukte) ersetzen durch:
```js
    `<div class="sb-section">` +
    `<button id="btn_add_filter" class="sb-add" title="Filterbedingung (mit UND verknüpft)">+ Filter</button>` +
    `<div class="filters" id="filters"></div></div>` +
    `<div class="sb-section">` +
    `<button id="btn_add_orderby" class="sb-add" title="Sortierungsspalte hinzufügen">+ Sortierung</button>` +
    `<div class="filters" id="order_bys"></div></div>` +
    `<div class="sb-section">` +
    `<button id="btn_add_col" class="sb-add" title="Weitere SELECT-Spalte hinzufügen">+ Spalten</button>` +
    `<div class="filters" id="extra_cols"></div></div>` +
    `<div class="sb-section">` +
    `<button id="btn_add_having" class="sb-add" title="Gruppen nach Aggregat filtern (HAVING)">+ HAVING</button>` +
    `<div class="filters" id="havings"></div></div>` +
```
(Die Event-Verdrahtung `$("btn_add_filter").addEventListener(...)` etc. bleibt unverändert — IDs sind identisch.)

- [ ] **Step 4: CSS — Variable + Start/Ziel-Label-Breite (`app.css`)**

In `.sqlbuilder { … }` (~Z.162-166) die Variable ergänzen:
```css
  --sb-label-w: 6.5rem; /* Breite der linken Label-/Button-Spalte */
```
Direkt nach `.sqlbuilder label { min-width: 3rem; }` (Z.168) einfügen:
```css
.sqlbuilder label.sb-rl { min-width: var(--sb-label-w); }  /* Spezifität schlägt die 3rem-Regel */
```

- [ ] **Step 5: CSS — Zeilen-Einrückung entfernen (`app.css`)**

Die Regel `.filter-row, .orderby-row, .col-row, .having-row` (~Z.169-172): `padding-left` streichen. Resultat:
```css
.filter-row, .orderby-row, .col-row, .having-row {
  display: flex; gap: .4rem; align-items: center; margin: .3rem 0;
}
```

- [ ] **Step 6: CSS — Sektion als Flex-Zeile + `.sb-add` umbauen (`app.css`)**

Die Regeln `.sb-section`, `.sb-section-head`, `.sb-section-label` (~Z.221-223) ersetzen durch:
```css
.sb-section { display: flex; align-items: flex-start; gap: .4rem; margin: .25rem 0; }
.sb-section .filters { display: flex; flex-direction: column; gap: .3rem; flex: 1 1 auto; min-width: 0; }
```
Und die `.sb-add`-Regel (~Z.224-229) ersetzen durch:
```css
.sb-add {
  min-width: var(--sb-label-w); height: var(--sb-ctrl-h);
  padding: 0 .5rem; flex: 0 0 auto; text-align: left;
  border: 1px solid #bcbcc6; border-radius: 4px; background: #f3f3f6;
  cursor: pointer; font-size: .85rem; line-height: 1;
}
.sb-add:hover { background: #e8e8ef; }
```

- [ ] **Step 7: Smoke laufen lassen, Erfolg bestätigen**

Run: `python3 .superpowers/sdd/verify_grid.py`
Expected: `7/7 checks passed`, Exit 0.
Falls Check „all add-buttons equal width" scheitert (Sortierung-Button überläuft 6.5rem): in `app.css` `--sb-label-w` auf `7rem` erhöhen und erneut laufen lassen.

- [ ] **Step 8: Regression — volle pytest-Suite**

Run: `./venv/bin/python -m pytest -q`
Expected: **324 passed, 2 skipped** (unverändert — kein Python berührt).

- [ ] **Step 9: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat: SQL-Builder — 2-Spalten-Raster, Sektions-Label als '+ Label'-Button (AP-59)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
(`.superpowers/` ist gitignored — `verify_grid.py` wird nicht committet; **kein** `git add -A`.)

---

### Task 2: Release v0.45.2 + Doku/Übersichten + Deploy

**Files:**
- Modify: `config.py`, `lucent-hub.yml` (via `sync_version.py`)
- Modify: `luDBxP-docs/docs/javascripts/icon-rail.js` (`APP_VERSION`)
- Modify: `luDBxP-docs/zensical.toml` (`site_description`-Version)
- Modify: `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd`, `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd`
- Build: `luDBxP-docs/site/**` via `build_docs.py`

**Interfaces:**
- Consumes: fertiges Feature aus Task 1.
- Produces: Version 0.45.2, aktualisierte Doku/Übersichten, gh-pages-Deploy.

- [ ] **Step 1: Version-Bump (PATCH)**

```bash
./venv/bin/python sync_version.py --patch
grep APP_VERSION config.py
```
Erwartung: `0.45.1 → 0.45.2`.

- [ ] **Step 2: icon-rail `APP_VERSION`**

In `luDBxP-docs/docs/javascripts/icon-rail.js`: `const APP_VERSION   = '0.45.1';` → `'0.45.2'`. **TEST_COUNT bleibt `324`**, TEST_DATE bleibt `2026-06-28`.

- [ ] **Step 3: `zensical.toml`**

`site_description` endet auf `· v0.45.1` → `· v0.45.2`.

- [ ] **Step 4: Changelog (Root EN)**

In `CHANGELOG.md` oben einfügen:
```markdown
## [0.45.2] — 2026-06-28

### Changed
- SQL-Builder layout: each clause section (Filter, Sortierung, Spalten, HAVING)
  is now a single „+ Label" button in the left column with its first row on the
  same line, instead of a separate „Label [+]" header row. The whole builder is
  one 2-column grid — every field column aligns with Start/Ziel. Saves a row per
  populated section. Markup/CSS only — IDs and generated SQL unchanged. (AP-59)
```

- [ ] **Step 5: Changelog-Mirror (DE)**

In `luDBxP-docs/docs/entwicklung/changelog.md` oben einfügen:
```markdown
## [0.45.2] — 2026-06-28

### Geändert
- SQL-Builder-Layout: jede Klausel-Sektion (Filter, Sortierung, Spalten, HAVING)
  ist jetzt ein einzelner „+ Label"-Button in der linken Spalte mit der ersten
  Zeile auf derselben Linie — statt einer eigenen „Label [+]"-Kopfzeile. Der
  ganze Builder ist ein 2-Spalten-Raster; alle Feld-Spalten fluchten mit
  Start/Ziel. Spart eine Zeile je gefüllter Sektion. Nur Markup/CSS — IDs und
  erzeugte SQL unverändert. (AP-59)
```

- [ ] **Step 6: roadmap.md Versionslog**

In `luDBxP-docs/docs/projekt/roadmap.md` direkt nach dem `**v0.45.1** … AP-58 … — v0.45.1`-Block (vor der `> **AP-17** …`-Zeile) einfügen:
```markdown
**v0.45.2** (2026-06-28):

- **AP-59** — SQL-Builder 2-Spalten-Raster: die Klausel-Sektionen werden zu „+ Label"-Buttons in der linken Spalte (erste Zeile auf gleicher Linie); alle Felder fluchten mit Start/Ziel, eine Kopfzeile je Sektion gespart. Nur Markup/CSS — v0.45.2
```

- [ ] **Step 7: Gantt — AP-59**

In `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd` in der erledigt-Sektion nach der `AP-58 — Fix HAVING-Layout … f17 …`-Zeile einfügen:
```
    AP-59 — SQL-Builder 2-Spalten-Raster        :done, f18, 2026-06-28, 1d
```
Und die Sektionsüberschrift `section v0.33.0–v0.45.1 (erledigt)` → `section v0.33.0–v0.45.2 (erledigt)`.

- [ ] **Step 8: Board — AP-59**

In `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd`, C3-Sektion: nach `J31["AP-58\nFix HAVING-Layout"]` ergänzen:
```
        J32["AP-59\n2-Spalten-Raster"]
```
Die letzte Gitter-Kette `J26 ~~~ J27 ~~~ J28 ~~~ J29 ~~~ J30 ~~~ J31` → `… ~~~ J31 ~~~ J32`.
Und die `class J1,…,J31 done`-Zeile um `,J32` erweitern.

- [ ] **Step 9: Site bauen + Übersichten gegenprüfen**

```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
cd luDBxP-docs/site/images/mermaid
grep -o "AP-59" projekt-roadmap-1.svg | head -1
grep -o "AP-59" entwicklung-arbeitspakete-1.svg | head -1
grep -o "v0.45.2" ../../index.html | head -1
grep -o "0.45.2" ../../entwicklung/changelog/index.html | head -1
```
Erwartung: jeweils FOUND.

- [ ] **Step 10: SDD-Final-Review**

Final-Review (opus) über den Branch-Diff: Korrektheit (IDs unverändert, Fluchtung, CSS-Spezifität), NO-CDN, Layering, Doku-Vollständigkeit. (Vom Controller via subagent-driven-development gesteuert.)

- [ ] **Step 11: Commit Doku/Version**

```bash
git add -A
git commit -m "docs: Release v0.45.2 — SQL-Builder 2-Spalten-Raster (AP-59)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 12: Merge + Deploy (nur auf Nutzer-Ansage)**

Nach Freigabe: `feat/ap-59-grid-layout` → `master` (ff), `git push origin master`, dann gh-pages-Deploy via temporärem Worktree (`rsync -a --delete --exclude='.git' --exclude='.nojekyll' luDBxP-docs/site/ <tmp>/`, commit „docs: Site-Deploy v0.45.2 …", `git push origin gh-pages`, Worktree entfernen). `.nojekyll` MUSS erhalten bleiben.

---

## Self-Review

**Spec coverage:**
- Label→Button `+ Label` in linker Spalte → Task 1 Step 3. ✓
- Erste Zeile auf gleicher Linie (`.sb-section` flex, `align-items:flex-start`) → Task 1 Step 6 + Smoke Check 4. ✓
- Felder fluchten mit Start/Ziel (`--sb-label-w`, `.sb-rl`, padding-left entfernt) → Task 1 Steps 4/5/6 + Smoke Check 3. ✓
- CSS-Spezifitäts-Falle (`label.sb-rl`) → Task 1 Step 4. ✓
- IDs unverändert → Task 1 Step 3 (explizit). ✓
- Längster Button darf nicht überlaufen → Smoke Check 2 + Step 7 Fallback 7rem. ✓
- pytest unverändert → Task 1 Step 8. ✓
- Release patch + Übersichten namentlich + gh-pages → Task 2. ✓

**Placeholder scan:** keine TBD/TODO; alle Code-Hunks vollständig. ✓

**Type/Name-Konsistenz:** Klasse `sb-rl`, Var `--sb-label-w`, Klasse `sb-add`, Container-IDs `#filters/#order_bys/#extra_cols/#havings`, Button-IDs `#btn_add_*` — identisch in Markup, CSS und Smoke. ✓
