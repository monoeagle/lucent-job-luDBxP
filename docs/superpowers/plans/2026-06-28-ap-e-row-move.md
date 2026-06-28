# AP-E — Zeilen Move ↑/↓ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Im SQL-Builder ORDER-BY- und Spalten-Zeilen per ↑/↓-Button innerhalb ihrer Sektion verschieben, sodass sich Sortier-Priorität bzw. SELECT-/GROUP-BY-Reihenfolge ändert.

**Architecture:** Reines Frontend. Die `collect*`-Funktionen lesen Zeilen in DOM-Reihenfolge, daher ist ein Move ein `insertBefore` im DOM — keine Datenstruktur, kein State. Markup-Buttons in `addOrderByRow`/`addColRow`, zwei kleine Helper (`moveRow`, `refreshMoveBtns`), eine CSS-Klasse `.sb-move`. Verifikation per Playwright-Browser-Smoke (kein pytest-Pfad, da kein Python berührt wird).

**Tech Stack:** Vanilla JS (`web/static/js/app.js`), CSS (`web/static/css/app.css`), Playwright-Smoke (System-`python3`).

## Global Constraints

- **NO CDN:** keine externen `<script>`/`<link>` — nichts hinzuzufügen hier, reine lokale Edits.
- **Sprache:** UI-Texte/Tooltips/Kommentare Deutsch (Code-Bezeichner englisch wie im Bestand).
- **Layering:** nur `web/` — `core/` und Routen bleiben unberührt.
- **Server:** läuft auf `http://127.0.0.1:5057`. JS/CSS sind **live** (kein App-Neustart nötig; nur Template-Änderungen bräuchten Neustart — hier keine).
- **venv:** Python 3.14 unter `./venv/`; voller Test `./venv/bin/python -m pytest` → Baseline **308 passed, 2 skipped**.
- **Smoke:** System-`python3` mit Playwright, Vorlage `.superpowers/sdd/verify_cd.py`, Demo-DB `sample_data/demo_cmdb.db`.
- **Version-Bump:** `sync_version.py --minor` (Feature) **+** icon-rail `APP_VERSION` manuell.

---

## File Structure

- `web/static/css/app.css` — neue `.sb-move`-Regel + Aufnahme in die `:not(...)`-Ausschlusslisten der generischen Builder-Button-Regel.
- `web/static/js/app.js` — Helper `moveRow`/`refreshMoveBtns`; Buttons + Verdrahtung in `addOrderByRow`/`addColRow`; Refresh-Aufrufe in den Del-Handlern und in `_removeColumn`.
- `.superpowers/sdd/verify_move.py` — neuer Browser-Smoke (Test-Artefakt).

---

### Task 1: Move-Buttons (↑/↓) für ORDER BY + Spalten

**Files:**
- Create: `.superpowers/sdd/verify_move.py`
- Modify: `web/static/css/app.css` (Button-Ausschlussregel ~Z.193/198; neue `.sb-move`-Regel nahe `.f-del, .ob-del, .c-del` ~Z.203)
- Modify: `web/static/js/app.js` (`addOrderByRow` ~Z.654, `addColRow` ~Z.689, `_removeColumn` ~Z.925; neue Helper)

**Interfaces:**
- Consumes (bestehend): `$(id)`, `optionList`, `aggOptions`, `tableByName`, `wireAggColDisable`, Container `#order_bys` / `#extra_cols`, Build-Button `#btn_build`, Output `#sql_out`. Row-Klassen `.orderby-row`/`.ob-table`/`.ob-col`/`.ob-dir`/`.ob-del`, `.col-row`/`.c-table`/`.c-col`/`.c-del`.
- Produces: neue Buttons `.sb-move.sb-up` / `.sb-move.sb-down` je Zeile; Helper `moveRow(row, dir)` und `refreshMoveBtns(container)`.

- [ ] **Step 1: Failing Browser-Smoke schreiben**

Create `.superpowers/sdd/verify_move.py`:

```python
"""Browser smoke for AP-E: ↑/↓ move buttons on ORDER BY + column rows reorder
the rows (and thus the generated SQL); edge buttons are disabled. Demo CMDB."""
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
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.evaluate(BOOT, DB)
    page.wait_for_selector(".sqlbuilder", timeout=5000)

    # --- ORDER BY: two rows, move buttons present, reorder changes priority ---
    page.click("#btn_add_orderby"); page.click("#btn_add_orderby")
    rows = "#order_bys .orderby-row"
    n_up = page.eval_on_selector_all(f"{rows} .sb-up", "els => els.length")
    n_dn = page.eval_on_selector_all(f"{rows} .sb-down", "els => els.length")
    check("orderby rows have up+down buttons", n_up == 2 and n_dn == 2, f"up={n_up} down={n_dn}")

    # first row -> VMID, second row -> Name (distinct columns on VirtualMachine)
    obt = page.query_selector_all(f"{rows} .ob-table")
    for el in obt: el.select_option("VirtualMachine")
    obc = page.query_selector_all(f"{rows} .ob-col")
    obc[0].select_option("VMID"); obc[1].select_option("Name")

    # edge state: first ↑ disabled, last ↓ disabled
    up_first = page.eval_on_selector(f"{rows}:first-child .sb-up", "el => el.disabled")
    dn_last = page.eval_on_selector(f"{rows}:last-child .sb-down", "el => el.disabled")
    check("edge buttons disabled (first up, last down)", up_first and dn_last,
          f"up_first={up_first} dn_last={dn_last}")

    # build -> ORDER BY VMID before Name
    page.select_option("#start_table", "VirtualMachine"); page.select_option("#start_col", "Name")
    page.select_option("#target_table", "Datacenter"); page.select_option("#target_col", "Name")
    page.click("#btn_build")
    page.wait_for_function("document.getElementById('sql_out').textContent.includes('ORDER BY')", timeout=8000)
    sql1 = page.eval_on_selector("#sql_out", "el => el.textContent")
    ob1 = sql1[sql1.index("ORDER BY"):]
    check("VMID sorted before Name initially", ob1.index("VMID") < ob1.index("Name"),
          ob1.split(chr(10))[0])

    # move second row (Name) up, rebuild -> Name before VMID
    page.click(f"{rows}:last-child .sb-up")
    page.click("#btn_build")
    page.wait_for_timeout(600)
    sql2 = page.eval_on_selector("#sql_out", "el => el.textContent")
    ob2 = sql2[sql2.index("ORDER BY"):]
    check("after move-up, Name sorted before VMID", ob2.index("Name") < ob2.index("VMID"),
          ob2.split(chr(10))[0])

    # --- Columns: two extra-select rows reorder the SELECT list ---
    page.click("#btn_add_col"); page.click("#btn_add_col")
    crows = "#extra_cols .col-row"
    ct = page.query_selector_all(f"{crows} .c-table")
    for el in ct: el.select_option("VirtualMachine")
    cc = page.query_selector_all(f"{crows} .c-col")
    cc[0].select_option("HostID"); cc[1].select_option("OSID")
    page.click("#btn_build"); page.wait_for_timeout(600)
    sel1 = page.eval_on_selector("#sql_out", "el => el.textContent")
    body1 = sel1[:sel1.index("FROM")]
    check("HostID selected before OSID initially", body1.index("HostID") < body1.index("OSID"))

    page.click(f"{crows}:last-child .sb-up")
    page.click("#btn_build"); page.wait_for_timeout(600)
    sel2 = page.eval_on_selector("#sql_out", "el => el.textContent")
    body2 = sel2[:sel2.index("FROM")]
    check("after move-up, OSID selected before HostID", body2.index("OSID") < body2.index("HostID"))

    real = [e for e in errors if "favicon" not in e.lower()]
    check("no console errors (favicon ignored)", not real, "; ".join(real[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
```

- [ ] **Step 2: Smoke laufen lassen, Fehlschlag bestätigen**

Voraussetzung: Server läuft (`bash run.sh --tray`, oder bereits aktiv auf :5057).
Run: `python3 .superpowers/sdd/verify_move.py`
Expected: FAIL — die ersten Checks scheitern (`up=0 down=0`), weil es noch keine `.sb-up`/`.sb-down`-Buttons gibt.

- [ ] **Step 3: CSS `.sb-move` ergänzen**

In `web/static/css/app.css`: die generische Builder-Button-Regel um `:not(.sb-move)` erweitern (beide Selektoren — Basis **und** Hover), damit die Move-Buttons nicht 140px breit werden.

Aus:
```css
.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sql-copy):not(.sb-add) {
```
wird:
```css
.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sb-move):not(.sql-copy):not(.sb-add) {
```
Und analog die Hover-Zeile darunter:
```css
.sqlbuilder button:not(.f-del):not(.ob-del):not(.c-del):not(.sb-move):not(.sql-copy):not(.sb-add):hover {
```

Direkt nach dem Block `.f-del:hover, .ob-del:hover, .c-del:hover { background: #fde8e8; }` einfügen:
```css
/* AP-E: Zeilen-Move-Buttons (↑/↓) — kleine neutrale Quadrate wie die Löschbuttons. */
.sb-move {
  width: var(--sb-ctrl-h); height: var(--sb-ctrl-h); padding: 0; flex: 0 0 auto;
  border: 1px solid #bcbcc6; border-radius: 4px; background: #fff;
  color: #444; cursor: pointer; line-height: 1;
}
.sb-move:hover { background: #eef0f4; }
.sb-move:disabled { opacity: .35; cursor: default; }
```

- [ ] **Step 4: JS-Helper `moveRow` + `refreshMoveBtns` hinzufügen**

In `web/static/js/app.js` direkt **vor** `function addOrderByRow()` (~Z.654) einfügen:
```js
// AP-E: verschiebt eine Builder-Zeile innerhalb ihres Containers; dir = -1 (hoch) / +1 (runter).
// Die collect*-Funktionen lesen in DOM-Reihenfolge, daher folgt die SQL-Semantik direkt aus der Position.
function moveRow(row, dir) {
  const ref = dir < 0 ? row.previousElementSibling : row.nextElementSibling;
  if (!ref) return;                                  // schon am Rand
  if (dir < 0) row.parentNode.insertBefore(row, ref);
  else         row.parentNode.insertBefore(ref, row);
  refreshMoveBtns(row.parentNode);
}

// AP-E: graut ↑ in der ersten und ↓ in der letzten Zeile aus.
function refreshMoveBtns(container) {
  const rows = [...container.children];
  rows.forEach((r, i) => {
    const up = r.querySelector(".sb-up"), down = r.querySelector(".sb-down");
    if (up)   up.disabled   = (i === 0);
    if (down) down.disabled = (i === rows.length - 1);
  });
}
```

- [ ] **Step 5: Buttons in `addOrderByRow` einbauen + verdrahten**

In `addOrderByRow` (~Z.659) die `row.innerHTML`-Zuweisung: vor dem `.ob-del`-Button die zwei Move-Buttons ergänzen.

Aus:
```js
    `<select class="ob-dir"><option>ASC</option><option>DESC</option></select>` +
    `<button type="button" class="ob-del">✕</button>`;
```
wird:
```js
    `<select class="ob-dir"><option>ASC</option><option>DESC</option></select>` +
    `<button type="button" class="sb-move sb-up" title="nach oben">↑</button>` +
    `<button type="button" class="sb-move sb-down" title="nach unten">↓</button>` +
    `<button type="button" class="ob-del">✕</button>`;
```

In derselben Funktion, beim Del-Handler den Refresh ergänzen und die Move-Buttons verdrahten; danach beim `appendChild` einmal refreshen.

Aus:
```js
  row.querySelector(".ob-del").addEventListener("click", () => row.remove());
  wireAggColDisable(row.querySelector(".ob-agg"), row.querySelector(".ob-col"));
  $("order_bys").appendChild(row);
}
```
wird:
```js
  row.querySelector(".ob-del").addEventListener("click", () => { row.remove(); refreshMoveBtns($("order_bys")); });
  row.querySelector(".sb-up").addEventListener("click", () => moveRow(row, -1));
  row.querySelector(".sb-down").addEventListener("click", () => moveRow(row, 1));
  wireAggColDisable(row.querySelector(".ob-agg"), row.querySelector(".ob-col"));
  $("order_bys").appendChild(row);
  refreshMoveBtns($("order_bys"));
}
```

- [ ] **Step 6: Buttons in `addColRow` einbauen + verdrahten**

In `addColRow` (~Z.694) analog. Aus:
```js
    `<select class="c-agg sb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<button type="button" class="c-del">✕</button>`;
```
wird:
```js
    `<select class="c-agg sb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<button type="button" class="sb-move sb-up" title="nach oben">↑</button>` +
    `<button type="button" class="sb-move sb-down" title="nach unten">↓</button>` +
    `<button type="button" class="c-del">✕</button>`;
```

Aus:
```js
  row.querySelector(".c-del").addEventListener("click", () => row.remove());
  wireAggColDisable(row.querySelector(".c-agg"), row.querySelector(".c-col"));
  $("extra_cols").appendChild(row);
}
```
wird:
```js
  row.querySelector(".c-del").addEventListener("click", () => { row.remove(); refreshMoveBtns($("extra_cols")); });
  row.querySelector(".sb-up").addEventListener("click", () => moveRow(row, -1));
  row.querySelector(".sb-down").addEventListener("click", () => moveRow(row, 1));
  wireAggColDisable(row.querySelector(".c-agg"), row.querySelector(".c-col"));
  $("extra_cols").appendChild(row);
  refreshMoveBtns($("extra_cols"));
}
```

- [ ] **Step 7: `_removeColumn` — Refresh nach direktem Entfernen**

`_removeColumn` (~Z.925) entfernt col-rows direkt (am Del-Handler vorbei). Aus:
```js
  if (removed && SB_LAST) runBuild(true);
}
```
wird:
```js
  if (removed) refreshMoveBtns($("extra_cols"));
  if (removed && SB_LAST) runBuild(true);
}
```
(`_sortByColumn` braucht keinen Zusatz: es ruft `addOrderByRow()`, dessen abschließender Refresh den Zustand bereits korrigiert.)

- [ ] **Step 8: Smoke erneut laufen lassen, Erfolg bestätigen**

Run: `python3 .superpowers/sdd/verify_move.py`
Expected: `8/8 checks passed`, Exit 0.
(Falls `selectsbuilder` noch alten Stand zeigt: nur JS/CSS geändert → Hard-Reload reicht, **kein** App-Neustart.)

- [ ] **Step 9: Regression — volle pytest-Suite**

Run: `./venv/bin/python -m pytest -q`
Expected: **308 passed, 2 skipped** (unverändert — kein Python berührt).

- [ ] **Step 10: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css .superpowers/sdd/verify_move.py
git commit -m "feat: SQL-Builder — Zeilen Move ↑/↓ für ORDER BY + Spalten (AP-E)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Legenden-Fix committen + Release AP-E

**Files:**
- Modify (bereits im Working Tree): `web/static/css/app.css` (Legenden-Fix `.lg-many` ohne `margin-left`)
- Modify: `config.py`, `lucent-hub.yml` (via `sync_version.py`), icon-rail `APP_VERSION` (manuell)
- Modify: Changelog + Doc-Mirror, Roadmap/Board/Gantt-Quellen, Badge, Site-Build-Artefakte

**Interfaces:**
- Consumes: fertiges Move-Feature aus Task 1.
- Produces: neue MINOR-Version, aktualisierte Doku/Übersichten, gh-pages-Deploy.

- [ ] **Step 1: Legenden-Fix als eigenen Commit**

Der 1-N-Ausrichtungs-Fix (`.lg-many` ohne `margin-left: 3px`, bereits verifiziert: 1-N und N-1 starten bei gleicher x-Position) liegt noch uncommittet im Working Tree. Vor dem Release separat committen:
```bash
git add web/static/css/app.css
git commit -m "fix: Graph-Legende — 1-N linksbündig wie N-1 (margin-left entfernt)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Hinweis: Falls Task 1 dieselbe Datei schon committet hat, enthält dieser Schritt nur noch den Legenden-Hunk — `git status` prüfen; ist nichts offen, Schritt überspringen.

- [ ] **Step 2: Version-Bump (MINOR)**

```bash
./venv/bin/python sync_version.py --minor
```
Erwartung: `0.43.4 → 0.44.0` in `config.py` + `lucent-hub.yml`.
Danach **icon-rail `APP_VERSION` manuell** nachziehen (sync_version.py erfasst sie nicht — siehe Handoff/Memory).

- [ ] **Step 3: Doku nachziehen**

- Changelog-Eintrag v0.44.0 (AP-E: Zeilen Move ↑/↓ für ORDER BY + Spalten; dazu Legenden-Fix) + Doc-Mirror.
- **Roadmap/Board/Gantt:** AP-E als erledigt führen — **jedes Item namentlich** (kein Sammel-Eintrag), gemäß globaler Konvention.
- Versions-Badge aktualisieren.

- [ ] **Step 4: Site bauen + Übersichten gegenprüfen**

Site-Build ausführen (wie in vorherigen Releases) und die **gerenderte** Roadmap/Board/Gantt inhaltlich prüfen, dass AP-E namentlich erscheint (Render-Kodierung beachten: `&#45;` etc.).

- [ ] **Step 5: SDD-Final-Review**

Final-Review nicht weglassen (opus-Review über den Diff): Korrektheit, NO-CDN, Layering, Doku-Vollständigkeit, keine SQLite-Blindspots.

- [ ] **Step 6: Deploy**

```bash
git push origin master
```
Anschließend gh-pages-Deploy (manuelles Worktree-Deploy wie etabliert), github.io verifizieren.

- [ ] **Step 7: Commit der Doku/Version**

```bash
git add -A
git commit -m "docs: Release v0.44.0 — Zeilen Move ↑/↓ (AP-E) + Legenden-Fix

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- ORDER BY + Spalten Move → Task 1 (Steps 5/6). ✓
- Buttons statt D&D → nur `<button>`, kein D&D. ✓
- Rand-Verhalten (disabled) → `refreshMoveBtns` (Step 4) + Smoke-Check. ✓
- Gestaged (kein Auto-Rebuild) → Move ruft kein `_rebuildIfBuilt`; Smoke klickt explizit Build. ✓
- WHERE/HAVING **nicht** betroffen → nur `addOrderByRow`/`addColRow` geändert. ✓
- Verifikation per Browser-Smoke, pytest bleibt 308 → Task 1 Steps 8/9. ✓
- Release inkl. Version-Bump + icon-rail + Übersichten namentlich + gh-pages → Task 2. ✓
- Legenden-Fix gebündelt → Task 2 Step 1. ✓

**Placeholder scan:** keine TBD/TODO; alle Code-Hunks vollständig. ✓

**Type/Name-Konsistenz:** `moveRow(row, dir)`, `refreshMoveBtns(container)`, Klassen `.sb-move`/`.sb-up`/`.sb-down` durchgängig identisch in CSS, JS und Smoke. ✓
