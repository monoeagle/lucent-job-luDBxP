# Analyzer Zeilennummern-Gutter + Fehlerzeilen-Highlight (AP-65·B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Analyzer-Eingabefeld bekommt eine scroll-synchrone Zeilennummern-Spalte, und bei einem Parse-Fehler wird die Fehlerzeile (`parse_error_line`) im Feld farbig hinterlegt.

**Architecture:** Reines Frontend (Vanilla-JS + CSS), kein Backend-Change. Ein selbstständiger Baustein `attachLineGutter(textarea)` wickelt die bestehende `#an_sql`-Textarea in einen 3-Schicht-Container (Gutter · Backdrop-Highlight · transparente Textarea, `wrap="off"` → 1 logische Zeile = 1 visuelle Zeile). Scroll wird per `transform: translate` synchronisiert. `renderAnalyzeResult` ruft `setErrorLine(res.parse_error_line)`.

**Tech Stack:** Vanilla JS (kein Framework, kein Editor-Lib), CSS. Verifikation via Playwright (System-`python3`), kein pytest-Change.

## Global Constraints

- NO-CDN: reines Markup/CSS, keine externe Editor-Lib, kein `<script src="http…">`.
- Read-only: der Analyzer führt weiterhin nichts aus; Gutter/Backdrop sind reine Anzeige (`aria-hidden="true"`).
- Deutsch für user-sichtbaren Text (hier keiner nötig — Gutter zeigt nur Zahlen).
- Textarea bleibt einziger Wert-Träger: `runAnalyze` liest weiter `panel.querySelector("#an_sql").value`.
- Kein Python-Change → pytest-Suite bleibt **438 passed / 10 skipped** (Regressions-Guard).
- Version nie von Hand editieren — `sync_version.py`.

---

### Task 1: `attachLineGutter` — Gutter + Scroll-Sync + CSS

**Files:**
- Modify: `web/static/js/app.js` — neue Funktion `attachLineGutter` im Analyzer-Abschnitt (nahe `openAnalyzer`, ~Zeile 620); Verdrahtung in `openAnalyzer`.
- Modify: `web/static/css/app.css` — `.an-editor`/`.an-gutter`/`.an-backdrop`/`.an-line` + `#an_sql`-Neustyling (nach der bestehenden `#an_sql`-Regel ~Zeile 357).
- Verifikation: Playwright-DOM-Smoke (Controller).

**Interfaces:**
- Produces: `attachLineGutter(textarea) -> { refresh() }` — wickelt `textarea` in den 3-Schicht-Container, hält Gutter + Backdrop synchron. (In Task 2 kommt `setErrorLine` dazu.)

- [ ] **Step 1: CSS ergänzen.** In `web/static/css/app.css` direkt nach der `#an_sql`-Regel (die alte `#an_sql`-Regel bei ~Zeile 356-357 durch die neue unten ersetzen) einfügen:

```css
/* AP-65·B: Analyzer-Editor — 3 Schichten (Gutter · Backdrop-Highlight · Textarea). */
.an-editor { display: flex; align-items: stretch; border: 1px solid #ccc;
  border-radius: 4px; overflow: hidden; background: #fff; min-height: 17rem;
  resize: vertical; font-family: monospace; font-size: .82rem; line-height: 1.5; }
.an-gutter { position: relative; flex: 0 0 auto; width: 3.2rem; overflow: hidden;
  background: #f3f3f7; border-right: 1px solid #e3e3ea; color: #9a9aa6;
  text-align: right; user-select: none; }
/* inner ist absolut → treibt die Gutter-/Editor-Höhe NICHT auf; feste Gutter-Breite. */
.an-gutter-inner { position: absolute; top: 0; left: 0; right: 0;
  padding: .4rem .45rem .4rem .55rem; will-change: transform; }
.an-gutter-num { white-space: pre; }
.an-edit-area { position: relative; flex: 1 1 auto; overflow: hidden; }
.an-backdrop { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
.an-backdrop-inner { padding: .4rem; will-change: transform; }
.an-line { white-space: pre; min-width: 100%; height: calc(.82rem * 1.5); }
.an-line-error { background: #fdecea; }
/* AP-48/AP-65·B: analyzer input — transparent, no wrap, sits over the backdrop. */
#an_sql { position: relative; display: block; width: 100%; height: 100%;
  box-sizing: border-box; margin: 0; border: 0; outline: none;
  padding: .4rem; background: transparent; color: #1a1a2e;
  font-family: monospace; font-size: .82rem; line-height: 1.5;
  white-space: pre; overflow: auto; tab-size: 4; }
```

Die alte Regel `#an_sql { width: 100%; box-sizing: border-box; font-family: monospace; font-size: .82rem; min-height: 17rem; resize: vertical; }` wird durch die obige `#an_sql`-Regel ersetzt (nicht doppelt lassen).

- [ ] **Step 2: `attachLineGutter` implementieren.** In `web/static/js/app.js`, unmittelbar **vor** `function openAnalyzer()` einfügen:

```javascript
// AP-65·B: wraps the analyzer textarea in a 3-layer editor (line-number gutter +
// scroll-synced backdrop). The textarea stays the single value source. Returns a
// small handle; setErrorLine is added in AP-65·B Task 2.
function attachLineGutter(textarea) {
  textarea.setAttribute("wrap", "off");
  const editor = document.createElement("div");
  editor.className = "an-editor";
  const gutter = document.createElement("div");
  gutter.className = "an-gutter";
  gutter.setAttribute("aria-hidden", "true");
  const gutterInner = document.createElement("div");
  gutterInner.className = "an-gutter-inner";
  gutter.appendChild(gutterInner);
  const area = document.createElement("div");
  area.className = "an-edit-area";
  const backdrop = document.createElement("div");
  backdrop.className = "an-backdrop";
  backdrop.setAttribute("aria-hidden", "true");
  const backdropInner = document.createElement("div");
  backdropInner.className = "an-backdrop-inner";
  backdrop.appendChild(backdropInner);

  textarea.parentNode.insertBefore(editor, textarea);
  area.appendChild(backdrop);
  area.appendChild(textarea);
  editor.appendChild(gutter);
  editor.appendChild(area);

  function lineCount() {
    return Math.max(1, textarea.value.split("\n").length);
  }
  function refresh() {
    const n = lineCount();
    let g = "";
    for (let i = 1; i <= n; i++) g += `<div class="an-gutter-num">${i}</div>`;
    gutterInner.innerHTML = g;
    let b = "";
    for (let i = 1; i <= n; i++) b += `<div class="an-line"></div>`;
    backdropInner.innerHTML = b;
  }
  function syncScroll() {
    gutterInner.style.transform = `translateY(${-textarea.scrollTop}px)`;
    backdropInner.style.transform =
      `translate(${-textarea.scrollLeft}px, ${-textarea.scrollTop}px)`;
  }
  textarea.addEventListener("input", () => { refresh(); syncScroll(); });
  textarea.addEventListener("scroll", syncScroll);
  refresh();
  syncScroll();
  return { refresh };
}
```

- [ ] **Step 3: In `openAnalyzer` verdrahten.** Am Ende von `openAnalyzer` (nach dem `addEventListener` für `#an_run`) ergänzen:

```javascript
  panel._gutter = attachLineGutter(panel.querySelector("#an_sql"));
```

- [ ] **Step 4: Playwright-Smoke schreiben + ausführen** (Controller-Schritt; App vorher auf :5057 neu starten, da JS live ist genügt Hard-Reload — aber Neustart schadet nicht). Smoke-Skript:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:5057/", wait_until="networkidle")
    pg.evaluate("openAnalyzer()")
    pg.wait_for_selector("#an_sql")
    pg.fill("#an_sql", "SELECT a\nFROM t\nWHERE x = 1")
    pg.dispatch_event("#an_sql", "input")
    nums = pg.eval_on_selector_all(".an-gutter-num", "els => els.map(e => e.textContent)")
    print("gutter nums:", nums)          # erwartet ['1','2','3']
    # 60 Zeilen → vertikaler Overflow, damit scrollTop > 0 möglich ist
    pg.fill("#an_sql", "\n".join(f"line {i}" for i in range(1, 61)))
    pg.dispatch_event("#an_sql", "input")
    count = pg.eval_on_selector_all(".an-gutter-num", "els => els.length")
    print("gutter count:", count)         # erwartet 60
    ty = pg.eval_on_selector("#an_sql",
        "e => { e.scrollTop = 40; e.dispatchEvent(new Event('scroll'));"
        " return [document.querySelector('.an-gutter-inner').style.transform, e.scrollTop]; }")
    print("gutter transform / scrollTop:", ty)  # erwartet ['translateY(-40px)', 40]
    print("PAGE ERRORS:", errs)
    b.close()
```

Expected: `gutter nums: ['1', '2', '3']`; `gutter transform: translateY(-40px)`; keine Page-Errors. Plus ein Screenshot zur Alignment-Sichtprüfung (Gutter-Zahlen auf Höhe der Textzeilen).

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat(ui): Analyzer-Zeilennummern-Gutter (scroll-synchron, 3-Schicht-Editor) [AP-65·B]"
```

---

### Task 2: `setErrorLine` — Fehlerzeile hervorheben + verdrahten

**Files:**
- Modify: `web/static/js/app.js` — `attachLineGutter` um `errorLine`-Zustand + `setErrorLine` erweitern; `renderAnalyzeResult` ruft es auf.
- Verifikation: Playwright-DOM-Smoke (Controller).

**Interfaces:**
- Consumes: `attachLineGutter` (Task 1), `panel._gutter` (in `openAnalyzer` gesetzt), `res.parse_error`, `res.parse_error_line`.
- Produces: `attachLineGutter(textarea) -> { refresh(), setErrorLine(n) }`; `setErrorLine(n)` markiert Backdrop-Zeile `n` (1-basiert) mit `.an-line-error` und scrollt sie in den sichtbaren Bereich; `null`/außerhalb Bereich → alle Markierungen entfernt.

- [ ] **Step 1: `attachLineGutter` um Highlight erweitern.** In `web/static/js/app.js` die `refresh`-Funktion und das `input`-Listener anpassen und `setErrorLine` ergänzen. Ersetze in `attachLineGutter` den Block ab `function refresh()` bis `return { refresh };` durch:

```javascript
  let errorLine = null;
  function refresh() {
    const n = lineCount();
    let g = "";
    for (let i = 1; i <= n; i++) g += `<div class="an-gutter-num">${i}</div>`;
    gutterInner.innerHTML = g;
    let b = "";
    for (let i = 1; i <= n; i++) {
      const cls = (i === errorLine) ? "an-line an-line-error" : "an-line";
      b += `<div class="${cls}"></div>`;
    }
    backdropInner.innerHTML = b;
  }
  function syncScroll() {
    gutterInner.style.transform = `translateY(${-textarea.scrollTop}px)`;
    backdropInner.style.transform =
      `translate(${-textarea.scrollLeft}px, ${-textarea.scrollTop}px)`;
  }
  function setErrorLine(n) {
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
  textarea.addEventListener("input", () => { errorLine = null; refresh(); syncScroll(); });
  textarea.addEventListener("scroll", syncScroll);
  refresh();
  syncScroll();
  return { refresh, setErrorLine };
```

(Das ersetzt die alten `refresh`/`syncScroll`/`input`-Listener/`return`-Zeilen aus Task 1 — es gibt sie danach nur einmal, mit Highlight-Logik.)

- [ ] **Step 2: In `renderAnalyzeResult` aufrufen.** In `web/static/js/app.js`, `function renderAnalyzeResult(panel, res)` — direkt nach `const out = panel.querySelector("#an_result");` einfügen:

```javascript
  if (panel._gutter) {
    panel._gutter.setErrorLine(res.parse_error ? (res.parse_error_line ?? null) : null);
  }
```

- [ ] **Step 3: Playwright-Smoke schreiben + ausführen** (Controller-Schritt):

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:5057/", wait_until="networkidle")
    pg.evaluate("openAnalyzer()"); pg.wait_for_selector("#an_sql")
    # unclosed quote in line 1, balanced below → redirect to line 1 (AP-65·A-Härtung 2)
    pg.fill("#an_sql", 'SELECT "a\nFROM t\nWHERE x = "b"')
    pg.click("#an_run")
    pg.wait_for_function("() => document.querySelectorAll('.an-line-error').length === 1")
    idx = pg.eval_on_selector_all(".an-backdrop .an-line",
        "els => els.findIndex(e => e.classList.contains('an-line-error'))")
    print("error-line index (0-based):", idx)   # erwartet 0 (Zeile 1)
    pg.fill("#an_sql", 'SELECT 1'); pg.dispatch_event("#an_sql", "input")
    after = pg.eval_on_selector_all(".an-line-error", "els => els.length")
    print("highlights nach Edit:", after)        # erwartet 0
    print("PAGE ERRORS:", errs)
    b.close()
```

Expected: `error-line index (0-based): 0`; `highlights nach Edit: 0`; keine Page-Errors. Plus Screenshot: rote Zeile 1 hinter dem Text, deckungsgleich.

- [ ] **Step 4: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(ui): Analyzer-Fehlerzeile im Eingabefeld hervorheben (setErrorLine) [AP-65·B]"
```

---

### Task 3: Release v0.62.0 + Doku

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`); Changelog EN (`CHANGELOG.md`) + DE-Mirror (`luDBxP-docs/docs/entwicklung/changelog.md`); Roadmap-Prosa (`roadmap.md`, AP-65-Zeile: Stufe B erledigt) + Gantt (`projekt-roadmap-1.mmd`: neuer done-Eintrag + Band-Obergrenze) + Board (`entwicklung-arbeitspakete-1.mmd`: J34 „AP-65·B/C" → AP-65·B done, AP-65·C bleibt plan); `zensical.toml`; `icon-rail.js` (Version/Test-Count/Datum); Kennzahlen (`kennzahlen.md`: Version, Tests, Commits, Stand-Datum); Konzept-Status; Referenz `oberflaeche.md` (Gutter-Beschreibung); Site-Build + gh-pages.

**Interfaces:**
- Consumes: fertige, verifizierte Änderungen aus Task 1-2.

- [ ] **Step 1: Version bumpen (minor — neues Feature)**

```bash
./venv/bin/python sync_version.py --minor   # 0.61.0 → 0.62.0
```

- [ ] **Step 2: Doku nachziehen (am echten Code geprüft, nicht geraten).** Changelog EN + DE (neuer `[0.62.0]`-Abschnitt: Gutter + Fehlerzeilen-Highlight, rein Frontend); `roadmap.md` AP-65-Zeile „Stufe B (S–M, offen)" → „Stufe B erledigt v0.62.0: Zeilennummern-Gutter + Fehlerzeilen-Highlight (3-Schicht-Editor, NO-CDN)" + Detail-Eintrag in der erledigt-Liste; Gantt neuer Eintrag `AP-65·B — Analyzer Zeilennummern-Gutter :done, f37, 2026-07-01, 1d` (aus dem `:pNN`-Block in den done-Block verschieben; Band-Header ggf. Obergrenze auf v0.62.0); Board J34 aufteilen: neuer Node „AP-65·B\nZeilennummern-Gutter" done, „AP-65·C\nLints mit Zeilenbezug" bleibt plan; `oberflaeche.md` um einen Absatz „Zeilennummern-Gutter (AP-65·B)" ergänzen; Konzept-Status um „Stufe B erledigt (v0.62.0)". Kennzahlen frisch erheben:

```bash
git rev-list --count HEAD
./venv/bin/python -m pytest -q | tail -1
```

`zensical.toml` (`v0.61.0` → `v0.62.0`), `icon-rail.js` (`APP_VERSION`/`TEST_COUNT`/`TEST_DATE`), `kennzahlen.md` (Version, Tests=438 unverändert, Commits neu, Stand-Datum). Danach per `grep` gegenprüfen, dass Changelog/Roadmap/Gantt-SVG/Board-SVG/Kennzahlen den Gutter nennen.

- [ ] **Step 3: Suite + Site bauen**

Run: `./venv/bin/python -m pytest`
Expected: **438 passed, 10 skipped** (kein Python-Change).
Danach `./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py`; gerenderte Gantt-/Board-SVGs + `index.html`-Version inhaltlich gegenprüfen.

- [ ] **Step 4: Commit (+ Merge/Push/gh-pages nur auf Nutzer-Ansage)**

```bash
git add -A
git commit -m "release: v0.62.0 — AP-65·B Analyzer Zeilennummern-Gutter + Fehlerzeilen-Highlight"
```
