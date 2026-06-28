# AP-F — Optimierungs-Vorschläge im SQL-Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der SQL-Analyzer liefert eine neue, eigene Kategorie „Optimierungs-Vorschläge" mit vier rein AST-basierten Heuristiken (DISTINCT+GROUP BY redundant, ORDER BY ohne LIMIT, OR in WHERE, Subquery in WHERE).

**Architecture:** `core/sqlanalyze.py` erhält eine `AnalysisSuggestion`-Dataclass, ein `suggestions`-Feld an `AnalysisResult` und eine reine Funktion `_optimization_suggestions(node)`, die nur am Top-Level-SELECT greift. Die Route serialisiert `suggestions`; das Analyzer-Panel rendert einen eigenen Abschnitt. Read-only, sqlglot-AST-basiert, `core/` bleibt Flask-frei.

**Tech Stack:** Python 3.14 / sqlglot (Backend), Flask-Route (JSON), Vanilla JS + CSS (Render), pytest (Backend-Tests) + Playwright-Browser-Smoke (UI).

## Global Constraints

- **Read-only:** der Analyzer parst nur, führt nie etwas aus. Keine DB-Mutation.
- **Layering:** `core/sqlanalyze.py` importiert **kein** Flask. Web ruft core.
- **NO CDN:** keine externen Assets.
- **Sprache:** alle Vorschlagstexte/Tooltips/Kommentare Deutsch; Codes (`DISTINCT_WITH_GROUP_BY` etc.) englisch/stabil.
- **Eigene Kategorie:** Vorschläge sind getrennt von `warnings`; `AnalysisSuggestion` hat **kein** `level`.
- **Nur Top-Level-SELECT** wird auf Vorschläge geprüft (keine Subquery-Analyse).
- **`SUBQUERY_IN_WHERE`** schließt `EXISTS (SELECT …)` aus (bereits empfohlene Form).
- **venv:** Python 3.14 unter `./venv/`; Baseline `./venv/bin/python -m pytest -q` = **308 passed, 2 skipped**.
- **Server-Smoke:** System-`python3` (Playwright), Server `http://127.0.0.1:5057`, JS/CSS live.
- **Version-Bump:** `sync_version.py --minor` (0.44.0 → 0.45.0) + icon-rail `APP_VERSION` manuell + `TEST_COUNT` auf die neue pytest-Zahl.

---

## File Structure

- `core/sqlanalyze.py` — `AnalysisSuggestion`-Dataclass, `suggestions`-Feld, `_optimization_suggestions()`, Verdrahtung in `analyze()`.
- `tests/test_sqlanalyze.py` — Unit-Tests der vier Heuristiken (Positiv/Negativ).
- `web/routes.py` — `suggestions` im `/api/analyze`-JSON.
- `web/static/js/app.js` — Abschnitt „Optimierungs-Vorschläge" in `renderAnalyzeResult`.
- `web/static/css/app.css` — Klasse `.an-sugg`.
- `tests/test_api.py` — Route-Test (suggestions im JSON).
- `.superpowers/sdd/verify_suggestions.py` — Browser-Smoke (UI-Abschnitt).

---

### Task 1: Backend — Suggestions-Logik in `core/sqlanalyze.py`

**Files:**
- Modify: `core/sqlanalyze.py` (Dataclasses ~Z.40-67, neue Funktion nahe `_static_lints` ~Z.195, `analyze()` ~Z.370-391)
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Consumes (bestehend): `sqlglot`, `from sqlglot import exp`, `analyze(sql, schema=None, dialect=None) -> AnalysisResult`, `AnalysisWarning`-Dataclass-Muster, `node.args.get("distinct"/"group"/"order"/"limit"/"where")`.
- Produces: `AnalysisSuggestion(code: str, message: str)` (frozen); `AnalysisResult.suggestions: tuple[AnalysisSuggestion, ...]` (Default `()`); `_optimization_suggestions(node) -> list[AnalysisSuggestion]`. Codes: `DISTINCT_WITH_GROUP_BY`, `ORDER_BY_NO_LIMIT`, `OR_IN_WHERE`, `SUBQUERY_IN_WHERE`.

- [ ] **Step 1: Failing Tests schreiben**

Am Ende von `tests/test_sqlanalyze.py` anhängen:

```python
# --- AP-F: Optimierungs-Vorschläge ---------------------------------------

def _sugg_codes(sql):
    return {s.code for s in analyze(sql).suggestions}


def test_suggest_distinct_with_group_by():
    assert "DISTINCT_WITH_GROUP_BY" in _sugg_codes(
        "SELECT DISTINCT a FROM t GROUP BY a")


def test_no_distinct_suggestion_without_group_by():
    assert "DISTINCT_WITH_GROUP_BY" not in _sugg_codes("SELECT DISTINCT a FROM t")


def test_no_distinct_suggestion_without_distinct():
    assert "DISTINCT_WITH_GROUP_BY" not in _sugg_codes("SELECT a FROM t GROUP BY a")


def test_suggest_order_by_without_limit():
    assert "ORDER_BY_NO_LIMIT" in _sugg_codes("SELECT a FROM t ORDER BY a")


def test_no_order_by_suggestion_with_limit():
    assert "ORDER_BY_NO_LIMIT" not in _sugg_codes(
        "SELECT a FROM t ORDER BY a LIMIT 10")


def test_suggest_or_in_where():
    assert "OR_IN_WHERE" in _sugg_codes("SELECT a FROM t WHERE a = 1 OR b = 2")


def test_no_or_suggestion_for_and_only():
    assert "OR_IN_WHERE" not in _sugg_codes("SELECT a FROM t WHERE a = 1 AND b = 2")


def test_suggest_subquery_in_where():
    assert "SUBQUERY_IN_WHERE" in _sugg_codes(
        "SELECT a FROM t WHERE a IN (SELECT x FROM u)")


def test_no_subquery_suggestion_for_exists():
    assert "SUBQUERY_IN_WHERE" not in _sugg_codes(
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.t_id = t.id)")


def test_no_subquery_suggestion_without_subquery():
    assert "SUBQUERY_IN_WHERE" not in _sugg_codes("SELECT a FROM t WHERE a = 1")


def test_plain_select_has_no_suggestions():
    assert analyze("SELECT a FROM t").suggestions == ()


def test_non_select_has_no_suggestions():
    assert analyze("UPDATE t SET a = 1 WHERE id = 2").suggestions == ()
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: FAIL — `AttributeError: 'AnalysisResult' object has no attribute 'suggestions'` (Feld existiert noch nicht).

- [ ] **Step 3: `AnalysisSuggestion`-Dataclass ergänzen**

In `core/sqlanalyze.py` direkt **nach** der `AnalysisWarning`-Dataclass (vor `@dataclass … AnalysisResult`):

```python
@dataclass(frozen=True)
class AnalysisSuggestion:
    code: str     # stabile Maschinen-Code, z. B. "DISTINCT_WITH_GROUP_BY"
    message: str  # deutscher, anzeigbarer Vorschlagstext
```

- [ ] **Step 4: `suggestions`-Feld an `AnalysisResult` anhängen**

In der `AnalysisResult`-Dataclass als **letztes** Feld (nach `complexity_grade: str = "A"`):

```python
    suggestions: tuple[AnalysisSuggestion, ...] = ()  # AP-F: Optimierungs-Vorschläge
```

- [ ] **Step 5: `_optimization_suggestions` implementieren**

In `core/sqlanalyze.py` direkt **vor** `def analyze(` einfügen:

```python
def _optimization_suggestions(node) -> list:
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
    if where is not None and where.find(exp.Or) is not None:
        out.append(AnalysisSuggestion(
            "OR_IN_WHERE",
            "OR in WHERE kann die Nutzung von Indizes verhindern — "
            "IN(…) (gleiche Spalte) oder UNION erwägen."))
    if where is not None:
        for sub in where.find_all(exp.Select):
            if sub.find_ancestor(exp.Exists) is None:   # EXISTS ist bereits empfohlen
                out.append(AnalysisSuggestion(
                    "SUBQUERY_IN_WHERE",
                    "Unterabfrage in WHERE — oft als JOIN oder EXISTS "
                    "effizienter formulierbar."))
                break
    return out
```

- [ ] **Step 6: In `analyze()` verdrahten**

In `analyze()` die Zeile `structure, score, grade = _structure_and_complexity(node)` / `warnings.extend(_static_lints(node))` um die Suggestions-Berechnung ergänzen. Aus:

```python
    structure, score, grade = _structure_and_complexity(node)
    warnings.extend(_static_lints(node))

    return AnalysisResult(
```
wird:
```python
    structure, score, grade = _structure_and_complexity(node)
    warnings.extend(_static_lints(node))
    suggestions = (_optimization_suggestions(node)
                   if isinstance(node, exp.Select) else [])

    return AnalysisResult(
```

Und in der `return AnalysisResult(...)`-Konstruktion als letztes Keyword-Argument (nach `complexity_grade=grade,`):
```python
        complexity_grade=grade,
        suggestions=tuple(suggestions),
    )
```

- [ ] **Step 7: Tests laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: PASS — alle neuen Tests grün, keine bestehenden gebrochen.

- [ ] **Step 8: Volle Suite (Regression)**

Run: `./venv/bin/python -m pytest -q`
Expected: vorher 308 passed + 12 neue = **320 passed, 2 skipped** (Zahl in Task 3 aus der echten Ausgabe übernehmen).

- [ ] **Step 9: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "feat: SQL-Analyzer — Optimierungs-Vorschläge (4 AST-Heuristiken, AP-F core)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Verdrahtung — Route + Analyzer-Panel-Render

**Files:**
- Modify: `web/routes.py` (`api_analyze` `jsonify`, ~Z.662-682)
- Modify: `web/static/js/app.js` (`renderAnalyzeResult`, ~Z.446-466)
- Modify: `web/static/css/app.css` (nahe `.an-warn` ~Z.333)
- Test: `tests/test_api.py`
- Create: `.superpowers/sdd/verify_suggestions.py`

**Interfaces:**
- Consumes (aus Task 1): `result.suggestions` (Tuple aus `AnalysisSuggestion`, je `.code`/`.message`).
- Produces: JSON-Feld `suggestions: [{code, message}]`; UI-Abschnitt mit `.an-sugg`-Einträgen unter „Optimierungs-Vorschläge".

- [ ] **Step 1: Failing Route-Test schreiben**

In `tests/test_api.py` anhängen (nutzt das bestehende `client`-Fixture, text-only ohne Connection):

```python
def test_analyze_returns_optimization_suggestions(client):
    resp = client.post("/api/analyze",
                       json={"sql": "SELECT DISTINCT a FROM t GROUP BY a"})
    assert resp.status_code == 200
    data = resp.get_json()
    codes = {s["code"] for s in data["suggestions"]}
    assert "DISTINCT_WITH_GROUP_BY" in codes
```

- [ ] **Step 2: Route-Test laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_analyze_returns_optimization_suggestions -q`
Expected: FAIL — `KeyError: 'suggestions'` (Feld noch nicht im JSON).

- [ ] **Step 3: Route — `suggestions` serialisieren**

In `web/routes.py`, `api_analyze`, im `jsonify(...)` direkt nach dem `warnings=[...]`-Block ergänzen:

```python
        suggestions=[{"code": s.code, "message": s.message}
                     for s in result.suggestions],
```

- [ ] **Step 4: Route-Test laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_analyze_returns_optimization_suggestions -q`
Expected: PASS.

- [ ] **Step 5: JS — Abschnitt „Optimierungs-Vorschläge" rendern**

In `web/static/js/app.js`, `renderAnalyzeResult`, **vor** der `out.innerHTML = …`-Zuweisung (direkt nach dem `warns`-Const-Block) einfügen:

```js
  const suggs = (res.suggestions && res.suggestions.length)
    ? `<h4>Optimierungs-Vorschläge</h4>` +
      res.suggestions.map((s) =>
        `<div class="an-sugg">💡 ${esc(s.message)}</div>`).join("")
    : "";
```

In der `out.innerHTML`-Verkettung den Vorschlags-Block direkt **vor** der Warnungen-Zeile einsetzen. Aus:
```js
    (res.limit ? `<h4>LIMIT</h4><p>${esc(res.limit)}</p>` : "") +
    `<h4>Warnungen</h4>${warns}`;
```
wird:
```js
    (res.limit ? `<h4>LIMIT</h4><p>${esc(res.limit)}</p>` : "") +
    suggs +
    `<h4>Warnungen</h4>${warns}`;
```

- [ ] **Step 6: CSS `.an-sugg`**

In `web/static/css/app.css` direkt nach `.an-l-info   { … }` (~Z.336) einfügen:

```css
/* AP-F: Optimierungs-Vorschläge — neutral/hilfreich, abgesetzt von den Warn-Levels. */
.an-sugg { padding: 4px 8px; margin: 3px 0; border-radius: 3px; font-size: 0.9em;
           background: #eafaf1; color: #1e6b3a; border-left: 3px solid #1e7e34; }
```

- [ ] **Step 7: Browser-Smoke schreiben**

Create `.superpowers/sdd/verify_suggestions.py`:

```python
"""Browser smoke for AP-F: the SQL-Analyzer panel shows an 'Optimierungs-
Vorschläge' section for a triggering statement and hides it otherwise.
Text-only — no DB connection needed."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5057/"

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
    page.evaluate("openAnalyzer()")
    page.wait_for_selector("#an_sql", timeout=5000)

    # triggering SQL -> suggestions section appears with >=1 .an-sugg
    page.fill("#an_sql", "SELECT DISTINCT a FROM t GROUP BY a")
    page.click("#an_run")
    page.wait_for_selector("#an_result .an-sugg", timeout=8000)
    n = page.eval_on_selector_all("#an_result .an-sugg", "els => els.length")
    head = page.eval_on_selector("#an_result", "el => el.textContent")
    check("suggestions section shown for triggering SQL", n >= 1, f"{n} suggestions")
    check("section heading present", "Optimierungs-Vorschläge" in head)

    # non-triggering SQL -> no .an-sugg, no heading
    page.fill("#an_sql", "SELECT a FROM t WHERE a = 1")
    page.click("#an_run")
    page.wait_for_function(
        "document.querySelectorAll('#an_result .an-sugg').length === 0", timeout=8000)
    head2 = page.eval_on_selector("#an_result", "el => el.textContent")
    check("no suggestions section for plain SQL", "Optimierungs-Vorschläge" not in head2)

    real = [e for e in errors if "favicon" not in e.lower()]
    check("no console errors (favicon ignored)", not real, "; ".join(real[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
```

- [ ] **Step 8: Browser-Smoke laufen lassen**

Voraussetzung: Server läuft (`bash run.sh --tray` oder bereits aktiv auf :5057). JS/CSS sind live (kein Neustart).
Run: `python3 .superpowers/sdd/verify_suggestions.py`
Expected: `4/4 checks passed`, Exit 0.

- [ ] **Step 9: Route-Regression**

Run: `./venv/bin/python -m pytest tests/test_api.py -q`
Expected: alle grün (inkl. neuer Test).

- [ ] **Step 10: Commit**

```bash
git add web/routes.py web/static/js/app.js web/static/css/app.css tests/test_api.py
git commit -m "feat: SQL-Analyzer — Vorschläge in Route + Panel (.an-sugg) (AP-F web)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Release v0.45.0 + Doku/Übersichten + Deploy

**Files:**
- Modify: `config.py`, `lucent-hub.yml` (via `sync_version.py`)
- Modify: `luDBxP-docs/docs/javascripts/icon-rail.js` (`APP_VERSION`, `TEST_COUNT`)
- Modify: `luDBxP-docs/zensical.toml` (`site_description`-Version)
- Modify: `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd`, `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd`
- Modify: `luDBxP-docs/docs/referenz/oberflaeche.md`
- Build: `luDBxP-docs/site/**` via `build_docs.py`

**Interfaces:**
- Consumes: fertiges Feature aus Task 1+2; die echte pytest-Zahl aus Task 1 Step 8.
- Produces: Version 0.45.0, aktualisierte Doku/Übersichten, gh-pages-Deploy.

- [ ] **Step 1: Version-Bump (MINOR)**

```bash
./venv/bin/python sync_version.py --minor
```
Erwartung: `0.44.0 → 0.45.0` in `config.py` + `lucent-hub.yml`. Verifizieren:
```bash
grep APP_VERSION config.py
```

- [ ] **Step 2: icon-rail `APP_VERSION` + `TEST_COUNT`**

Echte Testzahl ermitteln:
```bash
./venv/bin/python -m pytest -q 2>&1 | tail -1   # z. B. "320 passed, 2 skipped"
```
In `luDBxP-docs/docs/javascripts/icon-rail.js`:
- `const APP_VERSION   = '0.44.0';` → `'0.45.0'`
- `const TEST_COUNT    = '308';` → die neue Zahl (passed-Wert aus der pytest-Ausgabe).
- `TEST_DATE` bleibt `'2026-06-28'`.

- [ ] **Step 3: `zensical.toml`**

In `luDBxP-docs/zensical.toml`: `site_description` endet auf `· v0.44.0` → `· v0.45.0`.

- [ ] **Step 4: Changelog (Root EN)**

In `CHANGELOG.md` oben (über `## [0.44.0]`) einfügen:

```markdown
## [0.45.0] — 2026-06-28

### Added
- SQL-Analyzer: a new „Optimierungs-Vorschläge" (optimization suggestions)
  section, separate from warnings, with four schema-free AST heuristics:
  redundant DISTINCT alongside GROUP BY, ORDER BY without LIMIT, OR in WHERE
  (can defeat index use), and a non-EXISTS subquery in WHERE (often better as
  a JOIN/EXISTS). Read-only, suggestions only — no query rewriting. (AP-F)
```

- [ ] **Step 5: Changelog-Mirror (DE)**

In `luDBxP-docs/docs/entwicklung/changelog.md` oben einfügen:

```markdown
## [0.45.0] — 2026-06-28

### Hinzugefügt
- SQL-Analyzer: neue Kategorie „Optimierungs-Vorschläge" (getrennt von den
  Warnungen) mit vier schema-freien AST-Heuristiken: überflüssiges DISTINCT
  neben GROUP BY, ORDER BY ohne LIMIT, OR in WHERE (kann Indexnutzung
  verhindern) und eine Nicht-EXISTS-Unterabfrage in WHERE (oft besser als
  JOIN/EXISTS). Read-only, nur Hinweise — kein Umschreiben. (AP-F)
```

- [ ] **Step 6: roadmap.md Versionslog**

In `luDBxP-docs/docs/projekt/roadmap.md` direkt nach dem `**v0.44.0** … — v0.44.0`-Block (vor der `> **AP-17** …`-Zeile) einfügen:

```markdown
**v0.45.0** (2026-06-28):

- **AP-F** — SQL-Analyzer Optimierungs-Vorschläge: neue, von den Warnungen getrennte Kategorie mit vier schema-freien AST-Heuristiken (DISTINCT+GROUP BY redundant, ORDER BY ohne LIMIT, OR in WHERE, Nicht-EXISTS-Unterabfrage in WHERE). Read-only, nur Hinweise; Änderungen in `core/sqlanalyze.py`, `web/routes.py`, `web/static/js/app.js` + CSS — v0.45.0
```

- [ ] **Step 7: Gantt — AP-F**

In `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd` in der erledigt-Sektion nach der `AP-E — Zeilen Move ↑/↓ … f15 …`-Zeile einfügen:

```
    AP-F — Analyzer-Optimierungs-Vorschläge      :done, f16, 2026-06-28, 1d
```
Und die Sektionsüberschrift `section v0.33.0–v0.44.0 (erledigt)` → `section v0.33.0–v0.45.0 (erledigt)`.

- [ ] **Step 8: Board — AP-F**

In `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd`, C3-Sektion: nach `J29["AP-E\nZeilen Move ↑/↓"]` eine Box ergänzen:

```
        J30["AP-F\nAnalyzer-Vorschläge"]
```
Und die letzte Gitter-Kette `J26 ~~~ J27 ~~~ J28 ~~~ J29` → `J26 ~~~ J27 ~~~ J28 ~~~ J29 ~~~ J30`.

- [ ] **Step 9: oberflaeche.md**

In `luDBxP-docs/docs/referenz/oberflaeche.md`: im SQL-Analyzer-Abschnitt (Liste der Analyzer-Ausgaben, nahe „Struktur-Zähler … Filter/GROUP BY/HAVING/ORDER BY") einen Satz/Punkt zu den Optimierungs-Vorschlägen ergänzen — die vier Heuristiken kurz benennen, „read-only, nur Hinweise". (Bestehenden Wortlaut des Abschnitts respektieren; falls eine `Stand vX.Y.Z`-Marke existiert, auf v0.45.0 ziehen.)

- [ ] **Step 10: Site bauen + Übersichten gegenprüfen**

```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
```
Danach **gerendert** gegenprüfen, dass AP-F in Gantt + Board erscheint und v0.45.0 in Changelog/Roadmap-HTML steht:
```bash
cd luDBxP-docs/site/images/mermaid
grep -o "AP-F" projekt-roadmap-1.svg | head -1
grep -o "AP-F" entwicklung-arbeitspakete-1.svg | head -1
grep -o "v0.45.0" ../../index.html | head -1
grep -o "0.45.0" ../../entwicklung/changelog/index.html | head -1
```
Erwartung: jeweils FOUND.

- [ ] **Step 11: SDD-Final-Review**

Final-Review (opus) über den gesamten Branch-Diff: Korrektheit der Heuristiken (EXISTS-Ausschluss, nur Top-Level-SELECT), Layering (core Flask-frei), NO-CDN, Doku-Vollständigkeit. (Wird vom Controller via subagent-driven-development gesteuert.)

- [ ] **Step 12: Commit Doku/Version**

```bash
git add -A
git commit -m "docs: Release v0.45.0 — SQL-Analyzer Optimierungs-Vorschläge (AP-F)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 13: Merge + Deploy (nur auf Nutzer-Ansage)**

Nach Freigabe: `feat/ap-f-suggestions` → `master` (ff), `git push origin master`, dann gh-pages-Deploy via temporärem Worktree (`rsync -a --delete --exclude='.git' --exclude='.nojekyll' luDBxP-docs/site/ <tmp>/`, commit „docs: Site-Deploy v0.45.0 …", `git push origin gh-pages`, Worktree entfernen). `.nojekyll` MUSS erhalten bleiben.

---

## Self-Review

**Spec coverage:**
- `AnalysisSuggestion` (ohne level) → Task 1 Step 3. ✓
- `suggestions`-Feld, Default `()` → Task 1 Step 4. ✓
- Vier Heuristiken mit exakten Bedingungen + EXISTS-Ausschluss → Task 1 Step 5. ✓
- Nur Top-Level-SELECT (`isinstance(node, exp.Select)`) → Task 1 Step 6. ✓
- Route-JSON `suggestions` → Task 2 Step 3. ✓
- UI-Abschnitt nur wenn nicht leer, vor Warnungen, `.an-sugg` → Task 2 Steps 5/6. ✓
- Tests: 4 Heuristiken Positiv/Negativ + EXISTS-Negativ + Nicht-SELECT → Task 1 Step 1; Route-Test → Task 2 Step 1; Browser-Smoke → Task 2 Step 7. ✓
- Release inkl. TEST_COUNT, Übersichten namentlich, oberflaeche, gh-pages → Task 3. ✓

**Placeholder scan:** keine TBD/TODO; alle Code-Hunks vollständig. Task 3 Step 9 beschreibt eine Doku-Ergänzung in Prosa (kein Code-Hunk nötig — freier Fließtext im bestehenden Abschnitt), Stand-Marke konditional. ✓

**Type/Name-Konsistenz:** `AnalysisSuggestion(code, message)`, `suggestions`, `_optimization_suggestions(node)`, Codes `DISTINCT_WITH_GROUP_BY`/`ORDER_BY_NO_LIMIT`/`OR_IN_WHERE`/`SUBQUERY_IN_WHERE` — identisch in core, Tests, Route, Smoke. ✓
