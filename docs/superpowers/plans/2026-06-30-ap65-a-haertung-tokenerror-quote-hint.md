# AP-65·A-Härtung — TokenError-Quote-Hinweis + Mark-Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analyzer-Fehleranzeige härten — bei nicht geschlossenem Anführungszeichen (TokenError) eine Position + ehrlichen Hinweis statt leerem Fallback zeigen, und die farbige Markierung exakt platzieren.

**Architecture:** Pure Helfer in `core/sqlanalyze.py`: `_unclosed_quote_offset(sql)` findet das am Statement-Ende offene Quote; `_parse_error_location` liefert zusätzlich `highlight_pos` (kontext-relativer Index für die Markierung) + `hint` (ehrlicher Zusatztext). Zwei neue `AnalysisResult`-Trailing-Felder, Route + Frontend ziehen sie durch. Read-only, keine Auto-Korrektur.

**Tech Stack:** Python (sqlglot-Exception-Introspektion + String-Scan), pytest (volle CI-Abdeckung, kein DB), Flask-Route, vanilla JS.

## Global Constraints

- **Read-only:** der Analyzer parst nur, führt/korrigiert nichts.
- **Layering:** `core/` importiert nie Flask; Helfer pur.
- **Rückwärtskompatibel:** `parse_error` (String) bleibt; neue Felder trailing mit Default; except-Zweig ergänzt sie per Keyword (5-positionale Konstruktion bleibt gültig).
- **Graceful Fallback:** `(None,None,"","",-1,"")` bei nicht extrahierbar; nie eine zweite Exception.
- **`col` 1-basiert.** **Ehrlichkeit:** bei verschobenen Quotes markiert wird das am Ende offene Quote + Hinweis „Ursache kann früher liegen" — keine fabrizierte Ursachen-Position.
- **No CDN.** Sprache: Deutsch. **Version-Bump nur via `sync_version.py`**, Ziel **v0.59.0** (`--minor`).
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14).

---

### Task 1: Core — `_unclosed_quote_offset` + 2 Felder + `_parse_error_location`-Erweiterung

**Files:**
- Modify: `core/sqlanalyze.py` (2 Felder nach `parse_error_highlight`; neuer Helfer; `_parse_error_location` → 6-Tupel; except-Zweig)
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Produces: `AnalysisResult.parse_error_highlight_pos: int = -1`, `AnalysisResult.parse_error_hint: str = ""`;
  `_unclosed_quote_offset(sql) -> int | None`; `_parse_error_location(exc, sql) -> (line, col, context, highlight, highlight_pos, hint)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_sqlanalyze.py` (ans Dateiende). Werte empirisch bestätigt:

```python
def test_unclosed_quote_offset_helper():
    from core.sqlanalyze import _unclosed_quote_offset
    assert _unclosed_quote_offset('SELECT a FROM t') is None          # balanciert
    assert _unclosed_quote_offset('SELECT "a FROM t') == 7            # ein offenes "
    assert _unclosed_quote_offset('SELECT * FROM main"."ResourcePool"') == 33


def test_parse_error_tokenerror_unclosed_quote_short():
    r = analyze('SELECT * FROM main"."ResourcePool"')
    assert r.parse_error is not None
    assert r.parse_error_line == 1
    assert r.parse_error_col == 34
    assert r.parse_error_highlight == '"'
    assert r.parse_error_highlight_pos >= 0
    assert r.parse_error_context[r.parse_error_highlight_pos] == '"'
    assert "Anführungszeichen" in r.parse_error_hint


def test_parse_error_tokenerror_unclosed_quote_multiline():
    # Reproduktion des Screenshot-Falls: fehlendes " in einer mittleren Zeile.
    sql = ('SELECT "a"\n'
           'FROM "t"\n'
           '    AND main"."x" = "main"."y";')
    r = analyze(sql)
    assert r.parse_error_line is not None
    assert r.parse_error_highlight == '"'
    assert r.parse_error_highlight_pos >= 0
    assert r.parse_error_context[r.parse_error_highlight_pos] == '"'
    assert "Anführungszeichen" in r.parse_error_hint


def test_parse_error_parseerror_has_highlight_pos_no_hint():
    r = analyze("SELECT a b c FROM t")
    assert r.parse_error_highlight_pos == 11        # len(start_context "SELECT a b ")
    assert r.parse_error_context[r.parse_error_highlight_pos] == "c"
    assert r.parse_error_hint == ""


def test_valid_sql_no_highlight_pos_no_hint():
    r = analyze("SELECT a FROM t")
    assert r.parse_error_highlight_pos == -1
    assert r.parse_error_hint == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -k "unclosed_quote or highlight_pos or tokenerror_unclosed" -v`
Expected: FAIL — `ImportError: cannot import name '_unclosed_quote_offset'` / `AttributeError: ... 'parse_error_highlight_pos'`.

- [ ] **Step 3: Add the two fields** to `core/sqlanalyze.py` `class AnalysisResult`, after `parse_error_highlight`:

```python
    parse_error_highlight: str = ""     # the offending token (for marking)
    parse_error_highlight_pos: int = -1 # context-relative index of the token; -1 = unknown
    parse_error_hint: str = ""          # honest extra note (e.g. unclosed quote)
```

- [ ] **Step 4: Add the scan helper** to `core/sqlanalyze.py` (above `_parse_error_location`):

```python
def _unclosed_quote_offset(sql):
    """Return the offset of the quote (" or ') left open at end of input, else
    None. Toggles quote state; a doubled quote ('' / "") is close+open = neutral,
    which matches SQL's escaped-quote convention. Pure, read-only."""
    q = None
    open_at = None
    for i, c in enumerate(sql):
        if q is None:
            if c in ('"', "'"):
                q = c
                open_at = i
        elif c == q:
            q = None
            open_at = None
    return open_at
```

- [ ] **Step 5: Extend `_parse_error_location`** to return a 6-tuple. Replace the current body:

```python
def _parse_error_location(exc, sql):
    """Extract (line, col, context, highlight, highlight_pos, hint) from a
    sqlglot parse/token error. ParseError carries structured ``.errors``;
    TokenError does not — an unclosed quote makes the tokenizer consume to EOF,
    so we locate the quote left open at end of input and flag it. Returns
    ``(None, None, "", "", -1, "")`` when nothing usable can be extracted."""
    errors = getattr(exc, "errors", None)
    if errors:
        e = errors[0]
        start = e.get("start_context") or ""
        highlight = e.get("highlight") or ""
        context = start + highlight + (e.get("end_context") or "")
        return e.get("line"), e.get("col"), context, highlight, len(start), ""
    # TokenError: prefer the unclosed-quote scan (the common, real case).
    off = _unclosed_quote_offset(sql)
    if off is not None:
        line = sql.count("\n", 0, off) + 1
        col = off - sql.rfind("\n", 0, off)          # rfind == -1 → col = off + 1
        highlight = sql[off]
        ctx_start = max(0, off - 30)
        context = sql[ctx_start:off + 10]
        hint = ("Nicht geschlossenes Anführungszeichen — markiert ist das am "
                "Statement-Ende offene Quote; bei verschobenen Quotes kann die "
                "eigentliche Ursache weiter oben liegen.")
        return line, col, context, highlight, off - ctx_start, hint
    # Balanced quotes, other tokenizer error: fall back to the message prefix.
    m = _TOKEN_ERR_RE.match(str(exc))
    if m:
        prefix = m.group(1)
        if sql.startswith(prefix):
            off = len(prefix)
            line = prefix.count("\n") + 1
            col = off - prefix.rfind("\n")
            highlight = sql[off] if off < len(sql) else ""
            ctx_start = max(0, off - 20)
            context = sql[ctx_start:off + 20]
            return line, col, context, highlight, off - ctx_start, ""
    return None, None, "", "", -1, ""
```

- [ ] **Step 6: Update the except branch** — unpack 6 values + pass the two new fields by keyword:

```python
        line, col, ctx, hl, hlpos, hint = _parse_error_location(exc, sql)
        return AnalysisResult(
            "OTHER", (), (), (), _ANSI_RE.sub("", str(exc)),
            parse_error_line=line, parse_error_col=col,
            parse_error_context=ctx, parse_error_highlight=hl,
            parse_error_highlight_pos=hlpos, parse_error_hint=hint,
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -v`
Expected: PASS (alle, inkl. der 5 neuen + die bestehenden AP-65·A-Tests unverändert grün).

- [ ] **Step 8: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "feat(sqlanalyze): unclosed-quote-Lokalisierung + highlight_pos + hint (AP-65·A-Härtung)"
```

---

### Task 2: Route — `parse_error_highlight_pos` + `parse_error_hint`

**Files:**
- Modify: `web/routes.py` (`api_analyze` `jsonify`, nach den bestehenden `parse_error_*`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `result.parse_error_highlight_pos`, `result.parse_error_hint` (Task 1).
- Produces: `/api/analyze`-JSON mit beiden neuen Feldern.

- [ ] **Step 1: Write the failing test** in `tests/test_api.py` (ans Dateiende):

```python
def test_analyze_exposes_highlight_pos_and_hint(client):
    data = client.post("/api/analyze", json={"sql": 'SELECT * FROM main"."ResourcePool"'}).get_json()
    assert data["parse_error"] is not None
    assert data["parse_error_highlight_pos"] >= 0
    assert "Anführungszeichen" in data["parse_error_hint"]


def test_analyze_valid_sql_highlight_pos_default(client):
    data = client.post("/api/analyze", json={"sql": "SELECT a FROM t"}).get_json()
    assert data["parse_error_highlight_pos"] == -1
    assert data["parse_error_hint"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "highlight_pos or hint" -v`
Expected: FAIL — `KeyError: 'parse_error_highlight_pos'`.

- [ ] **Step 3: Add serialization** in `web/routes.py` `api_analyze`, nach `parse_error_highlight=result.parse_error_highlight,`:

```python
        parse_error_highlight_pos=result.parse_error_highlight_pos,
        parse_error_hint=result.parse_error_hint,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "highlight_pos or hint" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(api): parse_error_highlight_pos + parse_error_hint in /api/analyze (AP-65·A-Härtung)"
```

---

### Task 3: Frontend — Mark über highlight_pos + Hint-Anzeige

**Files:**
- Modify: `web/static/js/app.js` (`renderAnalyzeResult`, der Positions-Zweig aus AP-65·A)
- Modify: das Analyzer-CSS (optionale `.an-err-hint`-Regel) — am echten Code prüfen, wo `.an-parse-error`/`.an-err-mark` definiert sind
- Test: Manueller Playwright-Smoke (System-`python3`, `page.route`-Injektion)

**Interfaces:**
- Consumes: `res.parse_error_highlight_pos`, `res.parse_error_hint` (Task 2).

- [ ] **Step 1: Update den Positions-Zweig** in `renderAnalyzeResult`. Heute (aus AP-65·A) baut der Zweig `i = hl ? ctx.indexOf(hl) : -1`. Ersetzen, sodass der gelieferte Index bevorzugt wird, und den Hint anhängen:

```javascript
    if (res.parse_error_line != null) {
      const ctx = res.parse_error_context || "";
      const hl = res.parse_error_highlight || "";
      const pos = (typeof res.parse_error_highlight_pos === "number")
        ? res.parse_error_highlight_pos : -1;
      const i = (pos >= 0) ? pos : (hl ? ctx.indexOf(hl) : -1);
      const ctxHtml = (i >= 0 && hl)
        ? esc(ctx.slice(0, i)) +
          `<span class="an-err-mark">${esc(ctx.slice(i, i + hl.length))}</span>` +
          esc(ctx.slice(i + hl.length))
        : esc(ctx);
      const hintHtml = res.parse_error_hint
        ? `<p class="hint an-err-hint">${esc(res.parse_error_hint)}</p>` : "";
      out.innerHTML =
        `<p class="hint">Parse-Fehler in Zeile ${esc(String(res.parse_error_line))}, ` +
        `Spalte ${esc(String(res.parse_error_col))}:</p>` +
        `<pre class="an-parse-error">${ctxHtml}</pre>` + hintHtml;
    } else {
      out.innerHTML = `<p class="hint">Konnte nicht geparst werden:</p>` +
        `<pre class="an-parse-error">${esc(res.parse_error)}</pre>`;
    }
```

(Hinweis: `ctx.slice(i, i + hl.length)` statt `esc(hl)` direkt — markiert exakt den Kontext-Teil an `pos`; falls `i` aus `indexOf` stammt ist das identisch zu `hl`.)

- [ ] **Step 2: Optionale CSS** `.an-err-hint` (dezent, z. B. kleinerer/grauer Text), neben `.an-err-mark`/`.an-parse-error`. Ort via `grep -rn "an-err-mark" web/` finden.

- [ ] **Step 3: App neu starten + Browser-Smoke.** Die App läuft ggf. schon auf 5057 (sonst `bash run.sh --skip-setup`). Neues `scratchpad/smoke_analyze_hint.py` (modelliert nach `scratchpad/smoke_seq_matview.py` für `page.route`; Analyzer-Tab öffnen, SQL eingeben, Analysieren klicken — oder `/api/analyze`-Antwort injizieren). Prüfen:
- Antwort mit `parse_error_line:1, parse_error_col:34, parse_error_context:'main"."ResourcePool"', parse_error_highlight:'"', parse_error_highlight_pos:20, parse_error_hint:'Nicht geschlossenes …'` → Ergebnis zeigt „Parse-Fehler in Zeile 1, Spalte 34", die `.an-err-mark` umschließt das Zeichen an Index 20 (das End-Quote), und der `.an-err-hint`-Text ist sichtbar.
- Zur Gegenprobe: ein `parse_error_highlight_pos` von z. B. 0 markiert das erste Zeichen → Markierung folgt dem Index, nicht `indexOf`.
Run: `python3 scratchpad/smoke_analyze_hint.py` → Erwartet `PASS`.

- [ ] **Step 4: Commit** (app.js + CSS; Smoke untracked):

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "feat(ui): Analyzer-Markierung über highlight_pos + Quote-Hinweis (AP-65·A-Härtung)"
```

---

### Task 4: Release v0.59.0 + Doku (am Code geprüft)

**Files:**
- Modify: via `sync_version.py`; Changelog (EN + DE-Mirror), Roadmap-Prosa + `.mmd`, `datenmodell.md`, `oberflaeche.md`, Kennzahlen, `zensical.toml`, Site, gh-pages.

**Interfaces:** keine (Release/Doku).

- [ ] **Step 1: Version-Bump**

```bash
./venv/bin/python sync_version.py --minor   # → v0.59.0
```

- [ ] **Step 2: Doku am echten Code geprüft nachziehen** (grep-belegt):
  - **Changelog EN + DE-Mirror:** v0.59.0 — Analyzer bei nicht geschlossenem Anführungszeichen: Position am offenen Quote + ehrlicher Hinweis; Markierung exakt platziert.
  - **Roadmap-Prosa + Diagramme** (`roadmap.md`, `projekt-roadmap-1.mmd`, `entwicklung-arbeitspakete-1.mmd`): AP-65·A-Härtung als erledigt, **einzeln enumeriert**; AP-65·B/C bleiben offen.
  - **`datenmodell.md`:** `AnalysisResult`-Felder `parse_error_highlight_pos`/`parse_error_hint`.
  - **`oberflaeche.md`:** Analyzer-Hint + korrekte Markierung.
  - **Kennzahlen** (`kennzahlen.md`): Version v0.59.0, Commits/Tests/Coverage **frisch erheben**
    (`git rev-list --count HEAD`, `pytest`, `pytest --cov=core --cov=web --cov=launcher --cov=config --cov=app`),
    Karten + Tabelle + **Per-Modul-Balken** (hartkodiert, je Release prüfen).
  - **`zensical.toml`** Versionsstring.
  - Mit `grep` gegenprüfen, dass `datenmodell.md`/`oberflaeche.md` die neuen Felder/den Hint nennen.

- [ ] **Step 3: Site bauen + verifizieren**

```bash
bash luDBxP-docs/run_luDBxP_docs.sh --build
```
grep: `v0.59.0` in gebauter Site; `parse_error_hint` in datenmodell; Gantt-SVG zeigt AP-65·A-Härtung.

- [ ] **Step 4: Voll-Suite + Commit + Deploy**

```bash
./venv/bin/python -m pytest -q   # grün
git add -A
git commit -m "release: v0.59.0 — AP-65·A-Härtung (TokenError-Quote-Hinweis + Mark-Fix)"
# FF-Merge nach master + Push + gh-pages-Worktree-Deploy (etabliertes Muster)
```

---

## Self-Review

**1. Spec coverage:**
- `_unclosed_quote_offset` (Quote-Scan, balanciert→None) → Task 1 ✓
- 2 Felder `highlight_pos`/`hint` (trailing) + 6-Tupel-Helfer + except-Keyword-Wiring → Task 1 ✓
- ParseError exakt + `highlight_pos=len(start_context)`, kein Hint → Task 1 ✓
- TokenError offenes Quote → Position+Hint; balanced→Präfix-Heuristik → Task 1 ✓
- Route 2 Felder → Task 2 ✓
- Frontend Mark über `highlight_pos` (nicht `indexOf`) + Hint-Anzeige + Fallback → Task 3 ✓
- Tests: Unit (Helfer/ParseError/TokenError-kurz+mehrzeilig/valide) + Route-Naht + JS-Smoke → Task 1/2/3 ✓
- Release/Doku inkl. Per-Modul-Balken → Task 4 ✓
- Read-only / Ehrlichkeit (offenes End-Quote + Hinweis statt fabrizierter Ursache) → Task 1 (Design) ✓

**2. Placeholder scan:** Helfer/Tests/JS konkret. Die „am echten Code prüfen"-Hinweise (CSS-Ort) betreffen bestehendes Styling.

**3. Type consistency:** `_parse_error_location(exc, sql) -> (line, col, context, highlight, highlight_pos, hint)` 6-Tupel identisch in def + except-Unpack; `_unclosed_quote_offset(sql) -> int|None`; Feldnamen `parse_error_highlight_pos`/`parse_error_hint` durchgängig Task 1/2/3; JS liest `res.parse_error_highlight_pos`/`res.parse_error_hint`.
