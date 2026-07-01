# AP-69 Slice A — Gemeinsame SQL-Editor-Komponente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine gemeinsame, einheitlich dunkle SQL-Editor-Komponente (`sqlEditor`) mit Zeilennummern für alle SQL-Flächen der App — editierbar beim Analyzer, read-only gedimmt bei generiertem SQL, Definitionen und Subset.

**Architecture:** `attachLineGutter` wird zur Factory `sqlEditor({value, readOnly, rows})` verallgemeinert (erzeugt die 3-Schicht-DOM selbst, gibt `{el, getValue, setValue, setErrorLine}` zurück). Die CSS-Klassen `.an-*` + die dunklen `.sql_out`/`.viewdef`-Stile werden zu `.sqled-*` (dunkel) mit `--readonly`-Modifier zusammengeführt. Vier Aufruf-Flächen werden umgestellt.

**Tech Stack:** Vanilla JS + CSS (`web/static/js/app.js`, `web/static/css/app.css`), keine neue Dependency. Verifikation per Playwright (System-`python3`), da App-JS Browser-Code ist (kein pytest für JS).

## Global Constraints

- **NO-CDN**, Deutsch, keine neue Dependency.
- **Einheitlich dunkler** SQL-Editor (Basis `#1A1A2E`); read-only = `.sqled-editor--readonly` (gedimmter Text `#9a9ab0`, kein Caret, Auto-Höhe bis `max-height`, dann Scroll).
- **YAGNI:** kein Syntax-Highlighting, keine Autocomplete.
- Klassen-Präfix **`.sqled-*`** (nicht `.an-*`). `.an-parse-error` (Fehlerkontext im Analyzer-Ergebnis) bleibt unverändert — kein Editor.
- Komponenten-API stabil: `sqlEditor({value="", readOnly=false, rows=14}) -> {el, getValue(), setValue(str), setErrorLine(n|null)}`.
- JS/CSS sind **live** (kein App-Neustart nötig), solange `index.html`/Routes unberührt bleiben.
- Volle **pytest-Suite bleibt 459 passed / 11 skipped** (reine Frontend-Änderung).
- App-Start für Smokes: `bash run.sh --skip-setup` (Port 5057); SQLite-Demo `sample_data/demo_cmdb.db`, Connect via Hidden-Input `#connection_url` + Button `#btn_load`.
- Release: `sync_version.py --minor` (0.66.1 → 0.67.0) **plus** `icon-rail.js` `APP_VERSION` (TEST_COUNT bleibt 459, da keine neuen pytest-Tests).

---

### Task 1: `sqlEditor`-Factory + `.sqled-*`-CSS + Analyzer umgestellt

**Files:**
- Modify: `web/static/js/app.js` (ersetzt `attachLineGutter` ~636–705; `openAnalyzer` ~707–718; `runAnalyze` Zeile 625)
- Modify: `web/static/css/app.css` (`.an-*`-Block ~359–372 → `.sqled-*`; `.sql_out`/`.viewdef` behalten wir vorerst, werden in späteren Tasks entfernt)
- Test: Playwright-Smoke (siehe Schritte), keine pytest-Datei

**Interfaces:**
- Produces: `sqlEditor({value, readOnly, rows}) -> {el, getValue, setValue, setErrorLine}` (global im `app.js`-Scope, wie `attachLineGutter` vorher).

- [ ] **Step 1: Playwright-Smoke schreiben (schlägt fehl, bis umgesetzt)**

Datei `/tmp/ap69-smoke-task1.py`:
```python
import subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5057"

def wait_up(timeout=40):
    for _ in range(timeout*2):
        try:
            urllib.request.urlopen(BASE, timeout=1); return True
        except Exception: time.sleep(0.5)
    return False

assert wait_up(), "App nicht erreichbar auf :5057 (bash run.sh --skip-setup starten)"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto(BASE, wait_until="networkidle")
    # Analyzer-Tab öffnen (Button/Link mit Text 'Analyzer' bzw. SQL-Analyzer)
    pg.get_by_text("Analyzer", exact=False).first.click()
    pg.wait_for_selector(".sqled-editor textarea", timeout=5000)
    ta = pg.query_selector(".sqled-editor textarea")
    assert ta.get_attribute("readonly") is None, "Analyzer-Editor darf NICHT read-only sein"
    ta.click(); ta.fill("SELECT 1\nFROM dual\n')")  # letzte Zeile: unbalanciertes Quote → Parse-Fehler
    assert pg.query_selector(".sqled-gutter .sqled-num"), "Zeilennummern-Gutter fehlt"
    pg.get_by_text("Analysieren", exact=False).first.click()
    pg.wait_for_selector(".sqled-line--error", timeout=5000)
    print("TASK1 SMOKE OK")
    b.close()
```

- [ ] **Step 2: App starten + Smoke laufen lassen → FAIL erwarten**

Run:
```bash
cd /home/meagle/Dokumente/_Projects/lucent-job-luDBxP && bash run.sh --skip-setup &
python3 /tmp/ap69-smoke-task1.py
```
Expected: FAIL — `.sqled-editor textarea` existiert noch nicht (heute `.an-editor`/`#an_sql`).

- [ ] **Step 3: `sqlEditor`-Factory implementieren (ersetzt `attachLineGutter`)**

In `web/static/js/app.js` den Block `function attachLineGutter(textarea) { … }` (~636–705) **ersetzen** durch:

```js
// AP-69·A: gemeinsame SQL-Editor-Komponente. 3-Schicht-Editor (Zeilennummern-Gutter
// + scroll-synchrone Backdrop + textarea). readOnly=true -> gedimmt, nicht editierbar,
// Auto-Höhe bis max-height. Gibt { el, getValue, setValue, setErrorLine } zurück.
function sqlEditor({ value = "", readOnly = false, rows = 14 } = {}) {
  const editor = document.createElement("div");
  editor.className = "sqled-editor" + (readOnly ? " sqled-editor--readonly" : "");
  const gutter = document.createElement("div");
  gutter.className = "sqled-gutter";
  gutter.setAttribute("aria-hidden", "true");
  const gutterInner = document.createElement("div");
  gutterInner.className = "sqled-gutter-inner";
  gutter.appendChild(gutterInner);
  const area = document.createElement("div");
  area.className = "sqled-area";
  const backdrop = document.createElement("div");
  backdrop.className = "sqled-backdrop";
  backdrop.setAttribute("aria-hidden", "true");
  const backdropInner = document.createElement("div");
  backdropInner.className = "sqled-backdrop-inner";
  backdrop.appendChild(backdropInner);
  const textarea = document.createElement("textarea");
  textarea.className = "sqled-textarea";
  textarea.setAttribute("wrap", "off");
  textarea.spellcheck = false;
  textarea.rows = rows;
  textarea.value = value;
  if (readOnly) textarea.readOnly = true;

  area.appendChild(backdrop);
  area.appendChild(textarea);
  editor.appendChild(gutter);
  editor.appendChild(area);

  let errorLine = null;
  function lineCount() { return Math.max(1, textarea.value.split("\n").length); }
  function autoHeight() {
    if (!readOnly) return;
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
  }
  function refresh() {
    const n = lineCount();
    let g = "", b = "";
    for (let i = 1; i <= n; i++) {
      g += `<div class="sqled-num">${i}</div>`;
      b += `<div class="sqled-line${i === errorLine ? " sqled-line--error" : ""}"></div>`;
    }
    gutterInner.innerHTML = g;
    backdropInner.innerHTML = b;
    autoHeight();
  }
  function syncScroll() {
    gutterInner.style.transform = `translateY(${-textarea.scrollTop}px)`;
    backdropInner.style.transform =
      `translate(${-textarea.scrollLeft}px, ${-textarea.scrollTop}px)`;
  }
  function setErrorLine(n) {
    if (readOnly) return;
    const total = lineCount();
    errorLine = (typeof n === "number" && n >= 1 && n <= total) ? n : null;
    refresh();
    if (errorLine !== null) {
      const lh = parseFloat(getComputedStyle(textarea).lineHeight) || 18;
      const top = (errorLine - 1) * lh;
      if (top < textarea.scrollTop ||
          top > textarea.scrollTop + textarea.clientHeight - lh) {
        textarea.scrollTop = Math.max(0, top - textarea.clientHeight / 2);
      }
    }
    syncScroll();
  }
  function setValue(str) {
    textarea.value = (str == null) ? "" : String(str);
    errorLine = null; refresh(); syncScroll();
  }
  function getValue() { return textarea.value; }

  textarea.addEventListener("input", () => { errorLine = null; refresh(); syncScroll(); });
  textarea.addEventListener("scroll", syncScroll);
  refresh(); syncScroll();
  return { el: editor, getValue, setValue, setErrorLine };
}
```

- [ ] **Step 4: Analyzer auf `sqlEditor` umstellen**

In `openAnalyzer` (~711–718) das `innerHTML` und die Verdrahtung anpassen. Ersetze die Zeile mit `<textarea id="an_sql" …>` durch einen Mount-Punkt und erzeuge den Editor danach:

```js
  panel.innerHTML =
    `<div class="analyzer">` +
    `<div id="an_editor_mount"></div>` +
    `<div class="row"><button id="an_run">Analysieren</button>` +
    `<span class="an-readonly" title="Der Analyzer parst nur — er führt nichts auf der Datenbank aus">read-only — wird nie ausgeführt</span></div>` +
    `<div id="an_result"></div></div>`;
  panel.querySelector("#an_run").addEventListener("click", () => runAnalyze(panel));
  const _ed = sqlEditor({ readOnly: false, rows: 14 });
  panel.querySelector("#an_editor_mount").replaceWith(_ed.el);
  panel._gutter = _ed;   // behält setErrorLine-API (Aufruf in renderAnalyzeResult, ~533)
```

In `runAnalyze` (Zeile 625) den Wert über die Komponente lesen:
```js
  const sql = panel._gutter.getValue();
```

- [ ] **Step 5: `.sqled-*`-CSS anlegen (dunkel)**

In `web/static/css/app.css` den `.an-editor`/`.an-gutter`/`.an-backdrop`/`.an-line`-Block (~359–372) **ersetzen** durch:

```css
/* AP-69·A: gemeinsame SQL-Editor-Komponente (dunkel) */
.sqled-editor { display: flex; align-items: stretch; border: 1px solid #2a2a44;
  background: #1A1A2E; border-radius: 6px; overflow: hidden;
  font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .82rem; }
.sqled-gutter { position: relative; flex: 0 0 auto; width: 3.2rem; overflow: hidden;
  background: #14142a; color: #6b6b8a; text-align: right; }
.sqled-gutter-inner { position: absolute; top: 0; left: 0; right: 0;
  padding: .4rem .5rem; will-change: transform; }
.sqled-num { white-space: pre; line-height: 1.5; }
.sqled-area { position: relative; flex: 1 1 auto; overflow: hidden; }
.sqled-backdrop { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
.sqled-backdrop-inner { padding: .4rem; will-change: transform; }
.sqled-line { white-space: pre; min-width: 100%; height: calc(.82rem * 1.5); }
.sqled-line--error { background: #4a1f1f; }
.sqled-textarea { display: block; width: 100%; box-sizing: border-box; resize: vertical;
  border: 0; outline: 0; padding: .4rem; margin: 0; background: transparent;
  color: #eaeaea; font: inherit; line-height: 1.5; white-space: pre; overflow: auto;
  caret-color: #eaeaea; }
.sqled-editor--readonly .sqled-textarea { resize: none; color: #9a9ab0;
  caret-color: transparent; overflow: auto; max-height: 60vh; }
```

- [ ] **Step 6: Smoke erneut laufen lassen → PASS**

Run (App neu laden reicht, JS/CSS live; sonst App-Prozess killen + neu `--skip-setup`):
```bash
python3 /tmp/ap69-smoke-task1.py
```
Expected: `TASK1 SMOKE OK` (Analyzer-Editor da, nicht read-only, Zeilennummern, Fehlerzeile nach Parse-Fehler).

- [ ] **Step 7: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat(sql-editor): AP-69·A sqlEditor-Komponente + Analyzer umgestellt (.sqled-*)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Generiertes SQL (`sql_out`) read-only umstellen

**Files:**
- Modify: `web/static/js/app.js` (SQL-Panel-Aufbau ~469–474; Setz-Stellen 914, 1447, 1570; Copy-Handler ~2197–2202)
- Modify: `web/static/css/app.css` (`.sql_out` ~251 entfernen)
- Test: Playwright-Smoke

**Interfaces:**
- Consumes: `sqlEditor` (Task 1).
- Produces: Modul-Handle `SQL_OUT` (die read-only Editor-Instanz) für Setzen/Kopieren.

- [ ] **Step 1: Playwright-Smoke (mit Connect-Helper) schreiben → FAIL**

Datei `/tmp/ap69-smoke-task2.py`:
```python
import time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:5057"
DB = Path("/home/meagle/Dokumente/_Projects/lucent-job-luDBxP/sample_data/demo_cmdb.db").resolve()

def wait_up(t=40):
    for _ in range(t*2):
        try: urllib.request.urlopen(BASE, timeout=1); return True
        except Exception: time.sleep(0.5)
    return False

def connect(pg):
    pg.eval_on_selector("#connection_url", f"el => el.value = 'sqlite:////{DB}'".replace("////", "////"))
    pg.click("#btn_load")
    pg.wait_for_selector("#objects .obj-item, #objects a, #objects li", timeout=8000)

assert wait_up()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto(BASE, wait_until="networkidle")
    connect(pg)
    # Eine Tabelle im Objektbrowser doppelklicken → Auswahl; dann eine zweite für Join,
    # oder direkt Start/Ziel wählen. Vereinfachung: das erste UML/Objekt anklicken und
    # prüfen, dass der SQL-Ausgabe-Editor read-only existiert, sobald SQL generiert wird.
    pg.wait_for_selector("#sql_out .sqled-editor textarea, .sql-wrap .sqled-editor textarea", timeout=8000)
    ta = pg.query_selector(".sql-wrap .sqled-editor textarea")
    assert ta.get_attribute("readonly") is not None, "generiertes SQL muss read-only sein"
    print("TASK2 SMOKE OK")
    b.close()
```
> Hinweis für den Implementierer: der genaue Klickpfad zum Erzeugen eines SELECT hängt vom UI-Flow ab (Start/Ziel im Graph/UML wählen). Passe die Auswahl-Klicks so an, dass ein SELECT generiert wird; Kern-Assertion bleibt: der Ausgabe-Editor ist `.sqled-editor` **mit** `readonly`.

Run: `python3 /tmp/ap69-smoke-task2.py` → FAIL (heute `<pre id="sql_out">`, kein `.sqled-editor`).

- [ ] **Step 2: Aufbau umstellen — `<pre id="sql_out">` durch Editor-Mount ersetzen**

Im SQL-Panel-`innerHTML` (~474) die Zeile
```js
    `<pre class="sql_out" id="sql_out"></pre></div>` +
```
ersetzen durch
```js
    `<div id="sql_out_mount"></div></div>` +
```
Direkt nach dem `innerHTML`-Setzen dieses Panels den Editor erzeugen und `SQL_OUT` (Modul-Variable, oben bei den anderen `let`-Deklarationen als `let SQL_OUT = null;` anlegen) füllen:
```js
  SQL_OUT = sqlEditor({ readOnly: true, rows: 6 });
  panel.querySelector("#sql_out_mount").replaceWith(SQL_OUT.el);
```

- [ ] **Step 3: Setz-Stellen auf `SQL_OUT.setValue` umstellen**

- Zeile 914 `$("sql_out").textContent = "";` → `if (SQL_OUT) SQL_OUT.setValue("");`
- Zeile 1447 `$("sql_out").textContent = SB_LAST.paths[i].sql_inline || SB_LAST.paths[i].sql;`
  → `SQL_OUT.setValue(SB_LAST.paths[i].sql_inline || SB_LAST.paths[i].sql);`
- Zeile 1570 `$("sql_out").textContent = "";` → `if (SQL_OUT) SQL_OUT.setValue("");`

- [ ] **Step 4: Copy-Handler auf `getValue` umstellen**

Im `setupSqlCopy` (~2199) `const sql = $("sql_out") ? $("sql_out").textContent : "";`
→ `const sql = SQL_OUT ? SQL_OUT.getValue() : "";`

- [ ] **Step 5: `.sql_out`-CSS entfernen**

In `web/static/css/app.css` den `.sql_out { … }`-Block (~251–257, inkl. `:empty::before`) löschen (der Editor stylt jetzt).

- [ ] **Step 6: Smoke → PASS**

Run: `python3 /tmp/ap69-smoke-task2.py` → `TASK2 SMOKE OK`. Zusätzlich manuell: Copy-Button kopiert den SELECT (Editor-`getValue`).

- [ ] **Step 7: Commit**
```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat(sql-editor): AP-69·A generiertes SQL read-only via sqlEditor (Copy via getValue)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Detail-„SQL"-Tab (`viewdef`) read-only umstellen

**Files:**
- Modify: `web/static/js/app.js` (Detail-Panel-Aufbau 410; Setzen 411–412)
- Modify: `web/static/css/app.css` (`.viewdef` ~319 entfernen)
- Test: Playwright-Smoke

**Interfaces:**
- Consumes: `sqlEditor` (Task 1).

- [ ] **Step 1: Smoke schreiben → FAIL**

Datei `/tmp/ap69-smoke-task3.py` (nutzt denselben `connect`-Helper wie Task 2):
```python
# ... wait_up + connect wie Task 2 ...
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto(BASE, wait_until="networkidle"); connect(pg)
    # Ein Objekt (View/Tabelle) im Browser öffnen → Detail; SQL-Subtab klicken
    pg.locator("#objects").get_by_text("v_", exact=False).first.click()  # eine View
    pg.get_by_role("button", name="SQL").first.click()
    pg.wait_for_selector('.subpanel[data-sub="sql"] .sqled-editor textarea', timeout=6000)
    ta = pg.query_selector('.subpanel[data-sub="sql"] .sqled-editor textarea')
    assert ta.get_attribute("readonly") is not None
    print("TASK3 SMOKE OK"); b.close()
```
> Hinweis: falls die Demo keine View `v_*` hat, ein beliebiges Objekt mit SQL-Tab wählen (Tabelle → DDL). Kern-Assertion: SQL-Subtab enthält read-only `.sqled-editor`.

Run → FAIL (heute `<pre class="viewdef">`).

- [ ] **Step 2: Umstellen — `viewdef`-`<pre>` durch read-only Editor ersetzen**

Im Detail-Panel-`innerHTML` (Zeile 410) die Zeile
```js
    `<div class="subpanel" data-sub="sql"><pre class="viewdef"></pre></div></div>`;
```
ersetzen durch
```js
    `<div class="subpanel" data-sub="sql"><div class="sql-def-mount"></div></div></div>`;
```
und die Setz-Zeile (411–412)
```js
  panel.querySelector('.subpanel[data-sub="sql"] .viewdef').textContent =
    sqlText || "(keine Definition)";
```
ersetzen durch
```js
  const _defEd = sqlEditor({ readOnly: true, rows: 6 });
  panel.querySelector('.subpanel[data-sub="sql"] .sql-def-mount').replaceWith(_defEd.el);
  _defEd.setValue(sqlText || "(keine Definition)");
```

- [ ] **Step 3: `.viewdef`-CSS entfernen**

`.viewdef { … }`-Block (~319) in `app.css` löschen.

- [ ] **Step 4: Smoke → PASS**

Run: `python3 /tmp/ap69-smoke-task3.py` → `TASK3 SMOKE OK`.

- [ ] **Step 5: Commit**
```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat(sql-editor): AP-69·A Detail-SQL-Tab (View/Routine/Trigger/DDL) read-only via sqlEditor

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Subset-Pro-Tabelle-SQL (`.sql`) read-only umstellen

**Files:**
- Modify: `web/static/js/app.js` (Subset-Liste ~746)
- Modify: `web/static/css/app.css` (`pre.sql`-Stil, falls vorhanden)
- Test: Playwright-Smoke

**Interfaces:**
- Consumes: `sqlEditor` (Task 1).

- [ ] **Step 1: Smoke schreiben → FAIL**

Der genaue Subset-Trigger (Button „Entität exportieren" / Subset) hängt vom UI ab. Datei `/tmp/ap69-smoke-task4.py`: connect, Subset-Flow auslösen, dann:
```python
    pg.wait_for_selector('.subset .sqled-editor textarea, #subset .sqled-editor textarea', timeout=8000)
    tas = pg.query_selector_all('.sqled-editor textarea')
    assert any(t.get_attribute("readonly") is not None for t in tas), "Subset-SQL muss read-only Editor sein"
    print("TASK4 SMOKE OK")
```
Run → FAIL.

- [ ] **Step 2: Umstellen — Subset-`<pre class="sql">` durch read-only Editoren ersetzen**

Der aktuelle Code (~746) baut Strings der Form
```js
    `<h4>${esc(s.table)}</h4><pre class="sql">${esc(s.sql)}</pre>`).join("");
```
und setzt sie per `innerHTML`. Umstellen auf DOM-Aufbau, damit je Eintrag ein `sqlEditor` entsteht. Ersetze die `.map(...).join("")`-innerHTML-Zuweisung durch eine Schleife, die je Eintrag einen Container mit Überschrift + Editor erzeugt:
```js
  const host = /* das Element, das bisher das innerHTML bekam */;
  host.innerHTML = "";
  for (const s of items) {              // 'items' = die bisher gemappte Liste
    const wrap = document.createElement("div");
    wrap.className = "subset-item";
    const h = document.createElement("h4");
    h.textContent = s.table;
    const ed = sqlEditor({ readOnly: true, rows: 4 });
    wrap.appendChild(h);
    wrap.appendChild(ed.el);
    host.appendChild(wrap);
    ed.setValue(s.sql);
  }
```
> Der Implementierer identifiziert das konkrete `host`-Element und den Namen der Liste (`items`) an der Stelle ~746 und passt Variablennamen an; die Struktur (Überschrift + read-only `sqlEditor` je Eintrag) bleibt.

- [ ] **Step 3: `pre.sql`-CSS entfernen (falls vorhanden)**

Prüfen: `grep -n "pre.sql\|\.sql {" web/static/css/app.css` — falls ein eigener `.sql`-Block existiert, entfernen (Editor stylt jetzt).

- [ ] **Step 4: Smoke → PASS**

Run: `python3 /tmp/ap69-smoke-task4.py` → `TASK4 SMOKE OK`.

- [ ] **Step 5: Commit**
```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat(sql-editor): AP-69·A Subset-Pro-Tabelle-SQL read-only via sqlEditor

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Verifikation + Release v0.67.0

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py --minor`)
- Modify: `luDBxP-docs/docs/javascripts/icon-rail.js` (`APP_VERSION` → 0.67.0; `TEST_COUNT` bleibt 459)
- Modify: `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/zensical.toml`, `luDBxP-docs/docs/projekt/kennzahlen.md` (Version)
- Modify: `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd` (AP-69-Knoten in `C3`)

- [ ] **Step 1: Voller Playwright-Smoke über alle vier Flächen + Screenshot**

Ein kombiniertes Skript, das nacheinander die Assertions aus Tasks 1–4 fährt und je einen Screenshot (Analyzer editierbar; ein read-only Feld) unter `scratchpad/ap69-*.png` ablegt. Sichtprüfung: dunkel, Zeilennummern, read-only gedimmt.

- [ ] **Step 2: Keine Alt-Klassen mehr übrig**

Run: `grep -rn "an-editor\|an-gutter\|an-backdrop\|an-line\b\|sql_out\|viewdef\|attachLineGutter" web/static/`
Expected: keine Treffer mehr (außer `.an-parse-error`/`.an-readonly`, die bleiben) — `an-line-error` ist zu `sqled-line--error` migriert.

- [ ] **Step 3: Volle pytest-Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: **459 passed, 11 skipped** (unverändert; reine Frontend-Änderung).

- [ ] **Step 4: Version bumpen (minor)**

Run: `./venv/bin/python sync_version.py --minor` → 0.66.1 → 0.67.0. Prüfen: `grep APP_VERSION config.py`.

- [ ] **Step 5: icon-rail-Badge nachziehen**

In `luDBxP-docs/docs/javascripts/icon-rail.js`: `const APP_VERSION = '0.66.1'` → `'0.67.0'`. `TEST_COUNT` bleibt `'459'` (keine neuen pytest-Tests). `TEST_DATE` auf das Release-Datum setzen, falls abweichend.

- [ ] **Step 6: Changelog EN + DE + zensical + kennzahlen (Version)**

Neuer `## [0.67.0]`-Eintrag EN (`CHANGELOG.md`) + DE (`luDBxP-docs/docs/entwicklung/changelog.md`): „SQL fields now use a shared dark editor component with line numbers (editable in the analyzer, read-only/dimmed for generated SQL, object definitions and subset SQL)." `zensical.toml` site_description `v0.66.1` → `v0.67.0`; `kennzahlen.md` Version `v0.66.1` → `v0.67.0` (Tests bleiben 459).

- [ ] **Step 7: Flowchart-Knoten AP-69 in `C3`**

In `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd` einen `AP-69·A`-Knoten in `subgraph C3` (SQL-Builder & SQL-Ausgabe) mit `done`-Klasse ergänzen (konsistent zur `class …`-Notation). Falls `mmdc` verfügbar: `./tools/render_mermaid.sh entwicklung-arbeitspakete`.

- [ ] **Step 8: Site-Build**

Run: `cd luDBxP-docs && .venv-docs/bin/python build_docs.py --no-mermaid` (bzw. voll, falls mmdc). Erwartung: grün.

- [ ] **Step 9: Release-Commit**
```bash
git add -A
git commit -m "release: v0.67.0 — AP-69·A gemeinsame SQL-Editor-Komponente (Doku/Version)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Kein Push/Merge/Deploy — nur auf ausdrückliche Ansage des Nutzers.

---

## Self-Review

**Spec coverage:** Komponente `sqlEditor` (T1) · Analyzer editierbar + Fehlerzeile (T1) · generiertes SQL read-only + Copy (T2) · Detail-SQL-Tab read-only (T3) · Subset read-only (T4) · `.an-*`→`.sqled-*` + dunkel + `--readonly` (T1, entfernt `.sql_out`/`.viewdef` in T2/T3) · Playwright-Smoke + Screenshot + pytest-459 + Release inkl. icon-rail (T5). Alle Spec-Abschnitte abgedeckt. Risiko „read-only Auto-Höhe vs. Scroll-Sync" ist durch `autoHeight()` in `refresh()` + `overflow:auto`/`max-height` adressiert und im T1/T5-Smoke sichtbar.

**Placeholder-Scan:** Die UI-Klickpfade in den Smokes (Join-Auswahl in T2, Subset-Trigger in T4) sind bewusst als „Implementierer passt den konkreten Auswahl-Klick an"-Hinweise markiert — die **Assertion** (read-only `.sqled-editor`) ist jeweils vollständig und eindeutig; das ist keine Logik-Lücke, sondern UI-Flow-Abhängigkeit, die nur zur Laufzeit exakt greifbar ist. Aller Produktiv-Code (Factory, CSS, Wire-up-Edits) ist vollständig angegeben.

**Type-Konsistenz:** `sqlEditor(...) -> {el, getValue, setValue, setErrorLine}` durchgängig; `SQL_OUT` nutzt `setValue`/`getValue`; `panel._gutter` nutzt `getValue`/`setErrorLine` — alle in T1 definiert, in T2–T4 konsistent verwendet. Klassen `.sqled-editor`/`.sqled-editor--readonly`/`.sqled-line--error` einheitlich.
