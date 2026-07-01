# Analyzer Lints mit Zeilenbezug (AP-65·C) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jede knoten-spezifische Analyzer-Warnung/Empfehlung trägt ihre Quellzeile, wird im Ergebnis mit „Zeile N:" präfixt und markiert die Zeile im Eingabefeld per Klick.

**Architecture:** `core/sqlanalyze.py` bekommt einen reinen Helfer `_node_line(node, sql)` (frühester `meta['start']` unter den Nachfahren → 1-basierte Zeile) und fädelt die Zeile durch die knoten-spezifischen Lints; `AnalysisWarning`/`AnalysisSuggestion` erhalten ein `line`-Feld. `/api/analyze` serialisiert es; das Frontend präfixt „Zeile N:" und ruft bei Klick das bestehende `setErrorLine` (AP-65·B).

**Tech Stack:** Python 3.10+ (venv 3.14), sqlglot, pytest; Vanilla-JS-Frontend, Playwright-Smoke.

## Global Constraints

- Read-only: kein DB-Zugriff, führt nichts aus.
- `core/` importiert **nie** Flask; die neuen Helfer/Felder bleiben pur.
- NO-CDN: keine externen Assets.
- Deutsch für user-sichtbaren Text („Zeile N: ").
- Version nie von Hand — `sync_version.py`.
- Baseline: `./venv/bin/python -m pytest` → **438 passed, 10 skipped** (v0.62.0).

---

### Task 1: Core — `_node_line` + Zeilen an Warnungen/Vorschlägen

**Files:**
- Modify: `core/sqlanalyze.py`
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Produces: `_node_line(node, sql) -> int | None`; `AnalysisWarning(..., line: int | None = None)`;
  `AnalysisSuggestion(..., line: int | None = None)`. `analyze()` befüllt `line` für
  knoten-spezifische Meldungen, `None` für Statement-Ebene.

- [ ] **Step 1: Failing tests** (ans Ende von `tests/test_sqlanalyze.py`)

```python
def test_node_line_helper():
    import sqlglot
    from sqlglot import exp
    from core.sqlanalyze import _node_line
    sql = 'SELECT *\nFROM t\nWHERE upper(x) = 1'
    node = sqlglot.parse_one(sql)
    star = next(node.find_all(exp.Star))
    assert _node_line(star, sql) == 1                       # * in Zeile 1
    tbl = next(node.find_all(exp.Table))
    assert _node_line(tbl, sql) == 2                        # FROM t in Zeile 2
    fn = next(node.find(exp.Where).find_all(exp.Func))
    assert _node_line(fn, sql) == 3                         # upper(x) in Zeile 3


def test_lint_select_star_carries_line():
    r = analyze('SELECT *\nFROM t')
    w = next(w for w in r.warnings if w.code == "SELECT_STAR")
    assert w.line == 1


def test_lint_leading_wildcard_line():
    r = analyze("SELECT a\nFROM t\nWHERE b LIKE '%x'")
    w = next(w for w in r.warnings if w.code == "LEADING_WILDCARD")
    assert w.line == 3


def test_lint_func_on_column_line():
    r = analyze('SELECT a\nFROM t\nWHERE upper(b) = 1')
    w = next(w for w in r.warnings if w.code == "FUNC_ON_COLUMN")
    assert w.line == 3


def test_suggestion_or_in_where_line():
    r = analyze('SELECT a\nFROM t\nWHERE b = 1 OR c = 2')
    s = next(s for s in r.suggestions if s.code == "OR_IN_WHERE")
    assert s.line == 3


def test_statement_level_warnings_have_no_line():
    r = analyze('UPDATE t SET x = 1')
    w = next(w for w in r.warnings if w.code == "WRITE_STATEMENT")
    assert w.line is None
```

- [ ] **Step 2: Tests laufen rot**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -k "node_line or carries_line or wildcard_line or func_on_column_line or or_in_where_line or statement_level_warnings" -v`
Expected: FAIL (ImportError `_node_line` / `AttributeError: line`).

- [ ] **Step 3a: `line`-Feld an beide Dataclasses.** In `core/sqlanalyze.py` das `AnalysisWarning` und `AnalysisSuggestion` je um ein letztes Feld ergänzen:

```python
@dataclass(frozen=True)
class AnalysisWarning:
    level: str    # "info" | "warn" | "danger"
    code: str     # stable machine code, e.g. "WRITE_STATEMENT"
    message: str  # German user-facing text
    line: "int | None" = None   # 1-based source line, or None for statement-level
```

```python
@dataclass(frozen=True)
class AnalysisSuggestion:
    code: str     # stabile Maschinen-Code, z. B. "DISTINCT_WITH_GROUP_BY"
    message: str  # deutscher, anzeigbarer Vorschlagstext
    line: "int | None" = None   # 1-based source line, or None
```

- [ ] **Step 3b: Helfer `_node_line`.** In `core/sqlanalyze.py` direkt vor `def _static_lints(` einfügen:

```python
def _node_line(node, sql):
    """1-based source line of the earliest positioned descendant of node, else
    None. sqlglot records char offsets in leaf-node ``.meta['start']``; a
    composite node inherits a line via its descendants. Pure, read-only."""
    starts = [e.meta["start"] for e in node.walk()
              if isinstance(e, exp.Expression) and e.meta.get("start") is not None]
    if not starts:
        return None
    return sql.count("\n", 0, min(starts)) + 1
```

- [ ] **Step 3c: `_static_lints` — Signatur + Zeilen.** Ersetze die ganze Funktion `_static_lints` durch:

```python
def _static_lints(node, sql) -> list:
    """Schema-free static-quality lints (SELECT *, non-sargable predicates, …)."""
    out: list[AnalysisWarning] = []
    star = next((e for e in node.find_all(exp.Star)), None)
    if star is not None:
        out.append(AnalysisWarning(
            "info", "SELECT_STAR",
            "SELECT * — nur benötigte Spalten auswählen (klarer + weniger I/O).",
            line=_node_line(star, sql)))
    # Leading-wildcard LIKE ('%…') cannot use a normal index.
    for like in node.find_all(exp.Like):
        pat = like.expression
        if isinstance(pat, exp.Literal) and pat.is_string and pat.this.startswith("%"):
            out.append(AnalysisWarning(
                "warn", "LEADING_WILDCARD",
                "LIKE mit führendem '%' ist nicht index-nutzbar (Full Scan).",
                line=_node_line(like, sql)))
            break
    # A function wrapping a column inside WHERE defeats an index on that column.
    where = node.find(exp.Where)
    if where is not None:
        for fn in where.find_all(exp.Func):
            if fn.find(exp.Column) is not None:
                out.append(AnalysisWarning(
                    "info", "FUNC_ON_COLUMN",
                    "Funktion auf einer Spalte in WHERE — ein Index darauf wird ignoriert.",
                    line=_node_line(fn, sql)))
                break
    # Typo heuristic: sqlglot silently parses a mistyped join keyword as a table
    # alias (LEFTI → alias). Flag aliases that closely resemble a join keyword.
    flagged = set()
    for tbl in node.find_all(exp.Table):
        alias = (tbl.alias or "")
        au = alias.upper()
        if len(au) < 4 or au in flagged:
            continue
        for kw in _JOIN_KEYWORD_LOOKALIKES:
            if au != kw and _within_edit1(au, kw):
                flagged.add(au)
                out.append(AnalysisWarning(
                    "warn", "SUSPICIOUS_ALIAS",
                    f'Tabellen-Alias „{alias}“ ähnelt dem Schlüsselwort „{kw}“ — '
                    f'möglicher Tippfehler im Join-Typ?',
                    line=_node_line(tbl, sql)))
                break
    return out
```

- [ ] **Step 3d: `_optimization_suggestions` — Signatur + Zeilen.** Ersetze die ganze Funktion `_optimization_suggestions` durch:

```python
def _optimization_suggestions(node, sql) -> list:
    """Schema-freie Optimierungs-Hinweise für ein Top-Level-SELECT — neutrale
    Ratschläge, getrennt vom Warnungs-Kanal. Max. ein Vorschlag je Heuristik."""
    out: list[AnalysisSuggestion] = []
    if node.args.get("distinct") is not None and node.args.get("group") is not None:
        out.append(AnalysisSuggestion(
            "DISTINCT_WITH_GROUP_BY",
            "DISTINCT ist überflüssig — GROUP BY macht die Zeilen bereits eindeutig."))
    if node.args.get("order") is not None and node.args.get("limit") is None:
        out.append(AnalysisSuggestion(
            "ORDER_BY_NO_LIMIT",
            "ORDER BY ohne LIMIT sortiert das gesamte Ergebnis — LIMIT ergänzen, "
            "wenn nur ein Ausschnitt gebraucht wird."))
    where = node.args.get("where")
    if where is not None:
        or_node = next((o for o in where.find_all(exp.Or)
                        if o.find_ancestor(exp.Select) is node), None)
        if or_node is not None:
            out.append(AnalysisSuggestion(
                "OR_IN_WHERE",
                "OR in WHERE kann die Nutzung von Indizes verhindern — "
                "IN(…) (gleiche Spalte) oder UNION erwägen.",
                line=_node_line(or_node, sql)))
    if where is not None:
        for sub in where.find_all(exp.Select):
            if sub.find_ancestor(exp.Exists) is None:   # EXISTS ist bereits empfohlen
                out.append(AnalysisSuggestion(
                    "SUBQUERY_IN_WHERE",
                    "Unterabfrage in WHERE — oft als JOIN oder EXISTS "
                    "effizienter formulierbar.",
                    line=_node_line(sub, sql)))
                break
    return out
```

- [ ] **Step 3e: CARTESIAN_JOIN + Schema-Warnungen + Call-Sites in `analyze()`.**

(1) Ersetze den Cartesian-Block:

```python
    joins_without_on = any(
        j.args.get("on") is None and j.args.get("using") is None
        for j in node.find_all(exp.Join)
    )
    if joins_without_on and node.args.get("where") is None:
        warnings.append(AnalysisWarning(
            "warn", "CARTESIAN_JOIN",
            "Join ohne Verknüpfungsbedingung — möglicher kartesischer Join "
            "(Zeilen-Explosion)."))
```

durch:

```python
    bad_join = next((j for j in node.find_all(exp.Join)
                     if j.args.get("on") is None and j.args.get("using") is None), None)
    if bad_join is not None and node.args.get("where") is None:
        warnings.append(AnalysisWarning(
            "warn", "CARTESIAN_JOIN",
            "Join ohne Verknüpfungsbedingung — möglicher kartesischer Join "
            "(Zeilen-Explosion).", line=_node_line(bad_join, sql)))
```

(2) In den Schema-Warnungen die beiden `AnalysisWarning(...)` um `line` ergänzen. `UNKNOWN_TABLE`:

```python
            if real.lower() not in known:
                warnings.append(AnalysisWarning(
                    "warn", "UNKNOWN_TABLE",
                    f'Tabelle „{real}“ ist im verbundenen Schema nicht vorhanden.',
                    line=_node_line(tbl, sql)))
```

`UNKNOWN_COLUMN`:

```python
            if cols is not None and col.name.lower() not in cols:
                warnings.append(AnalysisWarning(
                    "warn", "UNKNOWN_COLUMN",
                    f'Spalte „{col.name}“ existiert nicht in Tabelle „{real}“.',
                    line=_node_line(col, sql)))
```

(3) Die Aufrufstellen anpassen: `warnings.extend(_static_lints(node))` → `warnings.extend(_static_lints(node, sql))`; und `suggestions = (_optimization_suggestions(node) if isinstance(node, exp.Select) else [])` → `suggestions = (_optimization_suggestions(node, sql) if isinstance(node, exp.Select) else [])`.

- [ ] **Step 4: Tests grün + volle Suite**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -v`
Expected: PASS (die neuen 6 Tests + alle bestehenden bleiben grün).

- [ ] **Step 5: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "feat(analyze): Zeilenbezug an Lints/Vorschlägen (_node_line) [AP-65·C]"
```

---

### Task 2: API-Serialisierung + Frontend-Präfix + Klick

**Files:**
- Modify: `web/routes.py` — `line` in Warn-/Vorschlags-Serialisierung
- Modify: `web/static/js/app.js` — Präfix „Zeile N:" + `an-lint-clickable` + delegierter Klick-Listener
- Modify: `web/static/css/app.css` — `.an-lint-clickable`
- Test: `tests/test_api.py` (API); Playwright-DOM-Smoke (Controller)

**Interfaces:**
- Consumes: `AnalysisWarning.line`/`AnalysisSuggestion.line` (Task 1); `panel._gutter.setErrorLine` (AP-65·B).

- [ ] **Step 1: API-Failing-Test** (ans Ende von `tests/test_api.py`)

```python
def test_api_analyze_warning_carries_line(client):
    r = client.post("/api/analyze", json={"sql": "SELECT *\nFROM t"})
    assert r.status_code == 200
    warns = r.get_json()["warnings"]
    star = next(w for w in warns if w["code"] == "SELECT_STAR")
    assert star["line"] == 1
```

(Der `client`-Fixture existiert bereits in `tests/test_api.py`.)

- [ ] **Step 2: Test rot**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_api_analyze_warning_carries_line -v`
Expected: FAIL (`KeyError: 'line'`).

- [ ] **Step 3a: `web/routes.py` — `line` serialisieren.** Ersetze:

```python
        warnings=[{"level": w.level, "code": w.code, "message": w.message}
                  for w in result.warnings],
        suggestions=[{"code": s.code, "message": s.message}
                     for s in result.suggestions],
```

durch:

```python
        warnings=[{"level": w.level, "code": w.code, "message": w.message,
                   "line": w.line}
                  for w in result.warnings],
        suggestions=[{"code": s.code, "message": s.message, "line": s.line}
                     for s in result.suggestions],
```

- [ ] **Step 3b: Frontend-Rendern.** In `web/static/js/app.js::renderAnalyzeResult` die `warns`- und `suggs`-Blöcke ersetzen. Vorher:

```javascript
  const warns = res.warnings.length
    ? res.warnings.map((w) =>
        `<div class="an-warn an-l-${esc(w.level)}">${esc(w.message)}</div>`).join("")
    : `<p class="hint">keine Warnungen</p>`;
  const suggs = (res.suggestions && res.suggestions.length)
    ? `<h4>Optimierungs-Vorschläge</h4>` +
      res.suggestions.map((s) =>
        `<div class="an-sugg">💡 ${esc(s.message)}</div>`).join("")
    : "";
```

Nachher:

```javascript
  // AP-65·C: line-bearing messages get a "Zeile N:" prefix + are click-to-locate.
  const lintBits = (o) => {
    const has = (o.line != null);
    return {
      cls: has ? " an-lint-clickable" : "",
      attr: has ? ` data-line="${esc(String(o.line))}"` : "",
      prefix: has ? "Zeile " + esc(String(o.line)) + ": " : "",
    };
  };
  const warns = res.warnings.length
    ? res.warnings.map((w) => {
        const b = lintBits(w);
        return `<div class="an-warn an-l-${esc(w.level)}${b.cls}"${b.attr}>` +
          `${b.prefix}${esc(w.message)}</div>`;
      }).join("")
    : `<p class="hint">keine Warnungen</p>`;
  const suggs = (res.suggestions && res.suggestions.length)
    ? `<h4>Optimierungs-Vorschläge</h4>` +
      res.suggestions.map((s) => {
        const b = lintBits(s);
        return `<div class="an-sugg${b.cls}"${b.attr}>💡 ${b.prefix}${esc(s.message)}</div>`;
      }).join("")
    : "";
```

- [ ] **Step 3c: Delegierter Klick-Listener.** In `openAnalyzer`, direkt nach der Zeile `panel._gutter = attachLineGutter(panel.querySelector("#an_sql"));` ergänzen:

```javascript
  panel.querySelector("#an_result").addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-line]");
    if (el && panel._gutter) panel._gutter.setErrorLine(Number(el.dataset.line));
  });
```

- [ ] **Step 3d: CSS.** In `web/static/css/app.css` nach der `.an-sugg`-Regel (~Zeile 353) ergänzen:

```css
/* AP-65·C: line-bearing lints are click-to-locate in the input. */
.an-lint-clickable { cursor: pointer; }
.an-lint-clickable:hover { text-decoration: underline; }
```

- [ ] **Step 4: API-Test grün + volle Suite**

Run: `./venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS. Danach `./venv/bin/python -m pytest` → **445 passed** erwartet (438 Baseline + 6 Task-1-Tests + 1 API-Test), 10 skipped.

- [ ] **Step 5: Commit**

```bash
git add web/routes.py web/static/js/app.js web/static/css/app.css tests/test_api.py
git commit -m "feat(ui): Lint-Meldungen mit „Zeile N:\" + Klick markiert Zeile [AP-65·C]"
```

- [ ] **Step 6: Controller-Playwright-Smoke** (nach App-Neustart auf :5057, da Core/Route geändert):

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:5057/", wait_until="networkidle")
    pg.evaluate("openAnalyzer()"); pg.wait_for_selector("#an_sql")
    pg.fill("#an_sql", "SELECT a\nFROM t\nWHERE b LIKE '%x'")
    pg.click("#an_run")
    pg.wait_for_selector(".an-lint-clickable[data-line]")
    info = pg.eval_on_selector(".an-lint-clickable[data-line]",
        "e => ({text: e.textContent, line: e.dataset.line})")
    print("lint:", info)   # text beginnt mit "Zeile 3:", line == "3"
    pg.click(".an-lint-clickable[data-line]")
    pg.wait_for_function("() => document.querySelectorAll('.an-line-error').length === 1")
    idx = pg.eval_on_selector_all(".an-backdrop .an-line",
        "els => els.findIndex(e => e.classList.contains('an-line-error'))")
    print("highlighted index:", idx)   # erwartet 2 (Zeile 3)
    print("PAGE ERRORS:", errs)
    b.close()
```

Expected: `lint.text` beginnt mit „Zeile 3:", `lint.line == "3"`; nach Klick `highlighted index: 2`; keine Page-Errors.

---

### Task 3: Release v0.63.0 + Doku

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`); `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`; `roadmap.md` (AP-65-Zeile: Stufe C erledigt + Detail-Eintrag) + Gantt `projekt-roadmap-1.mmd` (AP-65·C done + Band-Obergrenze; `:p36`-Zeile entfernen) + Board `entwicklung-arbeitspakete-1.mmd` (J34 „AP-65·C" von plan → done); `zensical.toml`; `icon-rail.js`; `kennzahlen.md`; Referenz `oberflaeche.md` + `datenmodell.md` (`line`-Feld an AnalysisWarning/Suggestion); Konzept-Status; Site + gh-pages.

**Interfaces:**
- Consumes: fertige, verifizierte Änderungen aus Task 1-2.

- [ ] **Step 1: Version bumpen (minor)**

```bash
./venv/bin/python sync_version.py --minor   # 0.62.0 → 0.63.0
```

- [ ] **Step 2: Doku nachziehen (am echten Code geprüft, nicht geraten).** Changelog EN + DE (neuer `[0.63.0]`: Lints mit Zeilenbezug + Klick-Lokalisierung); `roadmap.md` AP-65-Zeile „Stufe C (M, offen)" → „Stufe C erledigt v0.63.0: …" + Detail-Eintrag; Gantt: `AP-65·C — Lints mit Zeilenbezug :done, f38, 2026-07-01, 1d` (aus dem `:p36`-Block in den done-Block; Band-Header ggf. v0.63.0); Board: `class J34` von `plan` nach `done`; `oberflaeche.md`-Analyzer-Abschnitt um „Lints mit Zeilenbezug (AP-65·C)"; `datenmodell.md` — `AnalysisWarning`/`AnalysisSuggestion` um das `line`-Feld ergänzen; Konzept-Status „Stufe C erledigt (v0.63.0)". Kennzahlen frisch:

```bash
git rev-list --count HEAD
./venv/bin/python -m pytest -q | tail -1
```

`zensical.toml` (v0.62.0 → v0.63.0), `icon-rail.js` (`APP_VERSION`/`TEST_COUNT`/`TEST_DATE`), `kennzahlen.md` (Version, Tests neu, Statements neu via `--cov`, Commits, Stand-Datum). Danach per `grep` gegenprüfen, dass Changelog/Roadmap/Gantt-SVG/Board-SVG/Kennzahlen den Zeilenbezug nennen.

- [ ] **Step 3: Suite + Site**

Run: `./venv/bin/python -m pytest`
Expected: **445 passed erwartet** (438 + 6 Task-1 + 1 API), 10 skipped.
Danach `./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py`; gerenderte Gantt-/Board-SVGs + `index.html`-Version gegenprüfen.

- [ ] **Step 4: Commit (Merge/Push/gh-pages nur auf Nutzer-Ansage)**

```bash
git add -A
git commit -m "release: v0.63.0 — AP-65·C Lints mit Zeilenbezug (Zeile N: + Klick-Lokalisierung)"
```
