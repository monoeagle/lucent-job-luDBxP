# AP-65·Stufe A — Analyzer Parse-Fehler mit Position Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beim SQL-Analyzer einen Parse-Fehler mit Zeile/Spalte + markierter Fehlerstelle anzeigen statt nur einem positionslosen String.

**Architecture:** Ein reiner Helfer in `core/sqlanalyze.py` zieht aus der sqlglot-Exception die Position (ParseError exakt via `.errors[0]`, TokenError best-effort aus dem konsumierten Message-Präfix); vier neue Trailing-Felder am `AnalysisResult` tragen sie; Route serialisiert sie; Frontend zeigt „Parse-Fehler in Zeile N, Spalte M" + farbig markierten Token. Read-only, keine Auto-Korrektur.

**Tech Stack:** Python/sqlglot (Exception-Introspektion), pytest (volle CI-Abdeckung, kein DB), Flask-Route, vanilla JS.

## Global Constraints

- **Read-only:** der Analyzer parst nur, führt nichts aus, korrigiert nichts.
- **Layering:** `core/` importiert nie Flask; der Helfer ist pur.
- **Rückwärtskompatibel:** `parse_error` (String) bleibt; neue Felder sind Trailing mit Default (die bestehenden 5-positionalen `AnalysisResult("OTHER", (), (), (), msg)`-Konstruktionen bleiben gültig — Felder per Keyword ergänzen).
- **Graceful Fallback:** schlägt die Positions-Extraktion fehl → `(None, None, "", "")`, nie eine zweite Exception.
- **`col` 1-basiert.**
- **No CDN.** Sprache: Deutsch (Commits/Doku/UI).
- **Version-Bump nur via `sync_version.py`**, Ziel **v0.58.0** (`--minor`).
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14).

---

### Task 1: Core — `_parse_error_location` + `AnalysisResult`-Felder + except-Verdrahtung

**Files:**
- Modify: `core/sqlanalyze.py` (Felder nach `suggestions` ~Z.74; neuer Helfer + Regex; except-Zweig ~Z.295)
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Produces: `AnalysisResult` mit vier neuen Feldern `parse_error_line: int|None=None`,
  `parse_error_col: int|None=None`, `parse_error_context: str=""`, `parse_error_highlight: str=""`.
  Helfer `_parse_error_location(exc, sql) -> tuple[int|None, int|None, str, str]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_sqlanalyze.py` (ans Dateiende). Werte sind empirisch gegen die installierte sqlglot-Version bestätigt:

```python
def test_parse_error_location_parseerror():
    r = analyze("SELECT a b c FROM t")
    assert r.parse_error is not None
    assert r.parse_error_line == 1
    assert r.parse_error_col == 12
    assert r.parse_error_highlight == "c"
    assert "c" in r.parse_error_context


def test_parse_error_location_tokenerror_missing_quote():
    # Das AP-Auslöser-Beispiel: fehlendes schließendes Anführungszeichen → TokenError.
    r = analyze('SELECT * FROM main"."ResourcePool"')
    assert r.parse_error is not None
    assert r.parse_error_line == 1
    assert r.parse_error_col == 34
    assert r.parse_error_highlight == '"'
    assert "ResourcePool" in r.parse_error_context


def test_parse_error_location_multiline():
    r = analyze("SELECT a,\n  b c d\nFROM t")
    assert r.parse_error_line == 2
    assert r.parse_error_col == 7
    assert r.parse_error_highlight == "d"


def test_valid_sql_has_no_parse_error_location():
    r = analyze("SELECT a FROM t")
    assert r.parse_error is None
    assert r.parse_error_line is None
    assert r.parse_error_col is None
    assert r.parse_error_context == ""
    assert r.parse_error_highlight == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -k "parse_error_location or no_parse_error_location" -v`
Expected: FAIL — `AttributeError: 'AnalysisResult' object has no attribute 'parse_error_line'`.

- [ ] **Step 3: Add the four fields** to `core/sqlanalyze.py` `class AnalysisResult`, after the `suggestions` field (~Z.74):

```python
    suggestions: tuple[AnalysisSuggestion, ...] = ()  # AP-F: Optimierungs-Vorschläge
    # AP-65·A — parse-error location (None/"" when the statement parses).
    parse_error_line: "int | None" = None
    parse_error_col: "int | None" = None
    parse_error_context: str = ""       # excerpt around the offending token
    parse_error_highlight: str = ""     # the offending token (for marking)
```

- [ ] **Step 4: Add the helper + regex** to `core/sqlanalyze.py`. Place the regex near `_ANSI_RE` (~Z.37) and the helper just above the `analyze` function:

```python
_TOKEN_ERR_RE = re.compile(r"^Error tokenizing '(.*)'$", re.DOTALL)


def _parse_error_location(exc, sql):
    """Extract (line, col, context, highlight) from a sqlglot parse/token error.

    ParseError carries structured ``.errors`` (line/col/start_context/highlight/
    end_context). TokenError does not — its message embeds the consumed prefix,
    which is a true prefix of the input, so the failure sits just past it.
    Returns ``(None, None, "", "")`` when nothing usable can be extracted.
    """
    errors = getattr(exc, "errors", None)
    if errors:
        e = errors[0]
        highlight = e.get("highlight") or ""
        context = (e.get("start_context") or "") + highlight + (e.get("end_context") or "")
        return e.get("line"), e.get("col"), context, highlight
    m = _TOKEN_ERR_RE.match(str(exc))
    if m:
        prefix = m.group(1)
        if sql.startswith(prefix):
            off = len(prefix)
            line = prefix.count("\n") + 1
            col = off - prefix.rfind("\n")          # rfind == -1 → col = off + 1
            highlight = sql[off] if off < len(sql) else ""
            context = sql[max(0, off - 20):off + 20]
            return line, col, context, highlight
    return None, None, "", ""
```

- [ ] **Step 5: Wire the except branch.** Replace the current return at ~Z.295:

```python
    except (SqlglotError, ValueError) as exc:
        # sqlglot underlines the offending token with ANSI escape codes; strip
        # them so the browser shows clean text, not "□[4m…□[0m" garbage.
        line, col, ctx, hl = _parse_error_location(exc, sql)
        return AnalysisResult(
            "OTHER", (), (), (), _ANSI_RE.sub("", str(exc)),
            parse_error_line=line, parse_error_col=col,
            parse_error_context=ctx, parse_error_highlight=hl,
        )
```

(Der `empty statement`-Zweig bleibt unverändert — die neuen Felder defaulten dort auf `None`/`""`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -v`
Expected: PASS (alle, inkl. der 4 neuen).

- [ ] **Step 7: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "feat(sqlanalyze): Parse-Fehler-Position (ParseError exakt, TokenError best-effort) (AP-65·A)"
```

---

### Task 2: Route — vier Felder in `/api/analyze`

**Files:**
- Modify: `web/routes.py` (`api_analyze` `jsonify`, nach `parse_error=...`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `result.parse_error_line/col/context/highlight` (Task 1).
- Produces: `/api/analyze`-JSON mit `parse_error_line`, `parse_error_col`, `parse_error_context`, `parse_error_highlight`.

- [ ] **Step 1: Write the failing test** in `tests/test_api.py` (ans Dateiende):

```python
def test_analyze_exposes_parse_error_location(client):
    data = client.post("/api/analyze", json={"sql": "SELECT a b c FROM t"}).get_json()
    assert data["parse_error"] is not None
    assert data["parse_error_line"] == 1
    assert data["parse_error_col"] == 12
    assert data["parse_error_highlight"] == "c"
    assert "c" in data["parse_error_context"]


def test_analyze_valid_sql_no_parse_error_location(client):
    data = client.post("/api/analyze", json={"sql": "SELECT a FROM t"}).get_json()
    assert data["parse_error"] is None
    assert data["parse_error_line"] is None
    assert data["parse_error_highlight"] == ""
```

(Falls `/api/analyze` einen anderen Request-Key als `sql` erwartet, an die bestehenden analyze-Tests in `tests/test_api.py` anlehnen — am echten Code prüfen.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "parse_error_location" -v`
Expected: FAIL — `KeyError: 'parse_error_line'`.

- [ ] **Step 3: Add serialization** in `web/routes.py` `api_analyze`, im `jsonify(...)` direkt nach `parse_error=result.parse_error,`:

```python
        parse_error=result.parse_error,
        parse_error_line=result.parse_error_line,
        parse_error_col=result.parse_error_col,
        parse_error_context=result.parse_error_context,
        parse_error_highlight=result.parse_error_highlight,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "parse_error_location" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(api): Parse-Fehler-Position in /api/analyze (AP-65·A)"
```

---

### Task 3: Frontend — Positions-Anzeige + markierter Token

**Files:**
- Modify: `web/static/js/app.js` (`renderAnalyzeResult`, der `if (res.parse_error)`-Block ~Z.532–538)
- Modify: das Analyzer-CSS (Regel `.an-err-mark` neben `.an-parse-error`) — am echten Code prüfen, wo `.an-parse-error` definiert ist
- Test: Manueller Playwright-Smoke (System-`python3`, `page.route`-Injektion)

**Interfaces:**
- Consumes: `res.parse_error_line/col/context/highlight` (Task 2).

- [ ] **Step 1: Update `renderAnalyzeResult`.** Aktuell:
```javascript
  if (res.parse_error) {
    out.innerHTML = `<p class="hint">Konnte nicht geparst werden:</p>` +
      `<pre class="an-parse-error">${esc(res.parse_error)}</pre>`;
    clearAnalyzeMarkers();
    return;
  }
```
Ersetzen durch (Positions-Variante mit markiertem Token; Fallback = heutige Anzeige):
```javascript
  if (res.parse_error) {
    if (res.parse_error_line != null) {
      const ctx = res.parse_error_context || "";
      const hl = res.parse_error_highlight || "";
      const i = hl ? ctx.indexOf(hl) : -1;
      const ctxHtml = (i >= 0)
        ? esc(ctx.slice(0, i)) +
          `<span class="an-err-mark">${esc(hl)}</span>` +
          esc(ctx.slice(i + hl.length))
        : esc(ctx);
      out.innerHTML =
        `<p class="hint">Parse-Fehler in Zeile ${esc(String(res.parse_error_line))}, ` +
        `Spalte ${esc(String(res.parse_error_col))}:</p>` +
        `<pre class="an-parse-error">${ctxHtml}</pre>`;
    } else {
      out.innerHTML = `<p class="hint">Konnte nicht geparst werden:</p>` +
        `<pre class="an-parse-error">${esc(res.parse_error)}</pre>`;
    }
    clearAnalyzeMarkers();
    return;
  }
```

- [ ] **Step 2: Add CSS** `.an-err-mark` neben `.an-parse-error` (rot + unterstrichen, konsistent zu vorhandenen Markern). Den richtigen CSS-Ort am echten Code finden (`grep -rn "an-parse-error" web/`). Beispielregel:
```css
.an-err-mark { color: #d93025; text-decoration: underline; font-weight: 600; }
```

- [ ] **Step 3: App neu starten + Browser-Smoke.** Die App läuft ggf. schon auf 5057 (sonst `bash run.sh --skip-setup`). Neues `scratchpad/smoke_analyze_error.py` (modelliert nach `scratchpad/smoke_seq_matview.py` für den `page.route`-Teil; öffnet den Analyzer-Tab, gibt SQL ein, klickt Analysieren — oder injiziert die `/api/analyze`-Antwort via `page.route`). Prüfen:
- Bei injizierter Antwort mit `parse_error_line:1, parse_error_col:34, parse_error_context:'…main"."ResourcePool"', parse_error_highlight:'"'` zeigt das Ergebnis „Parse-Fehler in Zeile 1, Spalte 34" und ein `.an-err-mark`-Element.
- Bei `parse_error` ohne `parse_error_line` (null) erscheint die Fallback-Anzeige „Konnte nicht geparst werden".
Run: `python3 scratchpad/smoke_analyze_error.py` → Erwartet `PASS`.

- [ ] **Step 4: Commit** (app.js + CSS; Smoke bleibt untracked):

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat(ui): Analyzer-Parse-Fehler mit Zeile/Spalte + markiertem Token (AP-65·A)"
```

---

### Task 4: Release v0.58.0 + Doku (am Code geprüft)

**Files:**
- Modify: via `sync_version.py`; Changelog (EN + DE-Mirror), Roadmap-Prosa + `.mmd`, `datenmodell.md`, `oberflaeche.md`, Kennzahlen, `zensical.toml`, Site, gh-pages.

**Interfaces:** keine (Release/Doku).

- [ ] **Step 1: Version-Bump**

```bash
./venv/bin/python sync_version.py --minor   # → v0.58.0
```

- [ ] **Step 2: Doku am echten Code geprüft nachziehen** (grep-belegt):
  - **Changelog EN + DE-Mirror:** v0.58.0 — Analyzer zeigt Parse-Fehler mit Zeile/Spalte + markierter Stelle (ParseError exakt, TokenError best-effort).
  - **Roadmap-Prosa + Diagramme** (`roadmap.md`, `projekt-roadmap-1.mmd` Gantt, `entwicklung-arbeitspakete-1.mmd` Board): AP-65·A erledigt, **einzeln enumeriert**; AP-65·B/C bleiben offen.
  - **`datenmodell.md`:** `AnalysisResult`-Felder `parse_error_line/col/context/highlight`.
  - **`oberflaeche.md`:** Analyzer-Fehleranzeige mit Position + markiertem Token.
  - **Kennzahlen** (`kennzahlen.md`): Version v0.58.0, Commits/Tests/Coverage **frisch erheben**
    (`git rev-list --count HEAD`, `pytest`, `pytest --cov=core --cov=web --cov=launcher --cov=config --cov=app`),
    Karten + Tabelle + **Per-Modul-Balken** (core/web/launcher/GUI — hartkodiert, je Release prüfen).
  - **`zensical.toml`** Versionsstring.
  - Mit `grep` gegenprüfen, dass `datenmodell.md`/`oberflaeche.md` die neuen Felder/Anzeige nennen.

- [ ] **Step 3: Site bauen + verifizieren**

```bash
bash luDBxP-docs/run_luDBxP_docs.sh --build
```
grep: `v0.58.0` in gebauter Site; `parse_error_line` in datenmodell; Gantt-SVG zeigt AP-65·A.

- [ ] **Step 4: Voll-Suite + Commit + Deploy**

```bash
./venv/bin/python -m pytest -q   # grün
git add -A
git commit -m "release: v0.58.0 — AP-65·A (Analyzer Parse-Fehler mit Position)"
# FF-Merge nach master + Push + gh-pages-Worktree-Deploy (etabliertes Muster)
```

---

## Self-Review

**1. Spec coverage:**
- `_parse_error_location` (ParseError `.errors` exakt; TokenError best-effort aus Präfix; graceful `(None,None,"","")`) → Task 1 ✓
- 4 Trailing-Felder an `AnalysisResult` + except-Verdrahtung per Keyword (5-positionale Konstruktion bleibt) → Task 1 ✓
- `parse_error`-String rückwärtskompatibel → Task 1 (unverändert) ✓
- Route 4 Felder → Task 2 ✓
- Frontend Positions-Anzeige + markierter Token + Fallback + CSS → Task 3 ✓
- Tests: sqlanalyze-Unit (ParseError/TokenError/mehrzeilig/valide, CI) + Route-Naht + JS-Smoke → Task 1/2/3 ✓
- Release/Doku inkl. Per-Modul-Balken → Task 4 ✓
- Read-only / keine Auto-Korrektur → Helfer liest nur die Exception, nichts ausgeführt ✓

**2. Placeholder scan:** Helfer-Code, Tests (mit empirisch bestätigten Werten), JS konkret. Die „am echten Code prüfen"-Hinweise (analyze-Request-Key in Task 2; CSS-Ort in Task 3) betreffen bestehende Strukturen, keine zu erfindende Logik.

**3. Type consistency:** `_parse_error_location(exc, sql) -> (line, col, context, highlight)` identisch in Task 1 (def + Aufruf); Feldnamen `parse_error_line/col/context/highlight` durchgängig in Task 1/2/3; JS liest `res.parse_error_line/col/context/highlight` passend zur Route-Serialisierung.
