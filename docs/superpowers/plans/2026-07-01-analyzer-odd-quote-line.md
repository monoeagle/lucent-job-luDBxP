# Analyzer Pro-Zeile-Ungerade-Quote-Heuristik — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bei einem nicht geschlossenen Anführungszeichen die *echte* Fehlerzeile über eine Ungerade-Quote-Heuristik melden statt aufs Statement-Ende-Quote zu zeigen.

**Architecture:** Reiner Helper `_odd_quote_line(sql, q)` findet die einzige Zeile mit ungerader Zählung des unclosed Quote-Zeichens. Im `TokenError`-Zweig von `_parse_error_location` wird auf diese Zeile umgeleitet (ohne Spalte/Zeichen-Mark, da bei fehlendem Quote nicht bestimmbar), sonst bleibt das heutige EOF-Verhalten. Die UI lässt „, Spalte Y" weg, wenn keine Spalte vorliegt.

**Tech Stack:** Python 3.10+ (venv = 3.14), sqlglot, pytest; Vanilla-JS-Frontend.

## Global Constraints

- Read-only: kein DB-Zugriff, führt nichts aus.
- `core/` importiert **nie** Flask; Helper bleibt pur/stdlib-only.
- NO-CDN: keine externen Assets.
- Deutsch für alle user-facing Texte/Hints.
- Version **nie** von Hand editieren — `sync_version.py`.
- Kern-Verifikation: `./venv/bin/python -m pytest` (Baseline: 436 passed, 10 skipped).

---

### Task 1: Helper `_odd_quote_line`

**Files:**
- Modify: `core/sqlanalyze.py` (neuer Helper direkt nach `_unclosed_quote_offset`, ~Zeile 300)
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Produces: `_odd_quote_line(sql: str, quote_char: str) -> int | None` — 1-basierte
  Zeilennummer der einzigen Zeile mit ungerader `quote_char`-Anzahl, sonst `None`.

- [ ] **Step 1: Failing test schreiben** (ans Ende von `tests/test_sqlanalyze.py`)

```python
def test_odd_quote_line_helper():
    from core.sqlanalyze import _odd_quote_line
    assert _odd_quote_line('SELECT a FROM t', '"') is None          # keine Quotes
    assert _odd_quote_line('SELECT "a" FROM "t"', '"') is None      # balanciert (gerade)
    # unclosed in Zeile 1, balanciert in Zeile 3 → nur Zeile 1 ungerade
    assert _odd_quote_line('SELECT "a\nFROM t\nWHERE x = "b"', '"') == 1
    # verdoppeltes "" zählt gerade → neutral
    assert _odd_quote_line('SELECT "a""b" FROM t', '"') is None
    # zwei ungerade Zeilen → mehrdeutig → None
    assert _odd_quote_line('SELECT "a\nFROM "t', '"') is None
```

- [ ] **Step 2: Test läuft rot**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py::test_odd_quote_line_helper -v`
Expected: FAIL — `ImportError: cannot import name '_odd_quote_line'`

- [ ] **Step 3: Helper implementieren** (in `core/sqlanalyze.py`, direkt nach der Funktion `_unclosed_quote_offset`)

```python
def _odd_quote_line(sql, quote_char):
    """Return the 1-based line number of the sole line whose count of
    ``quote_char`` is odd, or None when zero or multiple lines qualify.
    A missing quote leaves exactly that line with an odd count; doubled
    ("") escapes and balanced quotes stay even. Pure, read-only."""
    odd = [i + 1 for i, line in enumerate(sql.split("\n"))
           if line.count(quote_char) % 2 == 1]
    return odd[0] if len(odd) == 1 else None
```

- [ ] **Step 4: Test läuft grün**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py::test_odd_quote_line_helper -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "feat(analyze): _odd_quote_line helper — Zeile mit ungerader Quote-Anzahl"
```

---

### Task 2: Redirect im TokenError-Zweig

**Files:**
- Modify: `core/sqlanalyze.py` — `_parse_error_location`, `if off is not None:`-Block (~Zeile 316-326)
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Consumes: `_odd_quote_line` (Task 1), `_unclosed_quote_offset` (vorhanden).
- Produces: unverändertes 6-Tupel `(line, col, context, highlight, highlight_pos, hint)`;
  im Redirect-Fall `col=None`, `highlight=""`, `highlight_pos=-1`.

- [ ] **Step 1: Failing test schreiben** (ans Ende von `tests/test_sqlanalyze.py`)

```python
def test_parse_error_redirect_to_odd_quote_line():
    # Unclosed " in Zeile 1; danach balancierte Quotes → echte Fehlerzeile = 1,
    # nicht die EOF-Zeile. Spalte ist bewusst None (fehlendes Quote hat keine Position).
    sql = 'SELECT "a\nFROM t\nWHERE x = "b"'
    r = analyze(sql)
    assert r.parse_error is not None            # es ist ein Parse-Fehler
    assert r.parse_error_line == 1              # umgeleitet auf die Ungerade-Zeile
    assert r.parse_error_col is None            # keine Spalte
    assert r.parse_error_highlight == ""        # kein Zeichen-Mark
    assert r.parse_error_highlight_pos == -1
    assert r.parse_error_context == 'SELECT "a' # der volle Zeilentext
    assert "Zeile 1" in r.parse_error_hint
    assert "Anführungszeichen" in r.parse_error_hint
```

- [ ] **Step 2: Test läuft rot**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py::test_parse_error_redirect_to_odd_quote_line -v`
Expected: FAIL — aktuell wird die EOF-Zeile (3) mit einer Spalte + Mark gemeldet.

- [ ] **Step 3: Redirect implementieren.** In `core/sqlanalyze.py::_parse_error_location` den Block `if off is not None:` ersetzen. Vorher:

```python
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
```

Nachher:

```python
    off = _unclosed_quote_offset(sql)
    if off is not None:
        q = sql[off]
        line = sql.count("\n", 0, off) + 1
        # Ungerade-Quote-Heuristik: die echte Fehlerzeile hat eine ungerade Anzahl
        # des offenen Quote-Zeichens. Weicht sie von der EOF-Zeile ab, dorthin
        # umleiten — ohne Spalte/Mark, da ein fehlendes Quote keine Position hat.
        odd_line = _odd_quote_line(sql, q)
        if odd_line is not None and odd_line != line:
            context = sql.split("\n")[odd_line - 1]
            hint = (f"Vermutlich fehlt ein {q} in Zeile {odd_line} — die genaue "
                    f"Position ist nicht bestimmbar (fehlendes Anführungszeichen).")
            return odd_line, None, context, "", -1, hint
        col = off - sql.rfind("\n", 0, off)          # rfind == -1 → col = off + 1
        highlight = sql[off]
        ctx_start = max(0, off - 30)
        context = sql[ctx_start:off + 10]
        hint = ("Nicht geschlossenes Anführungszeichen — markiert ist das am "
                "Statement-Ende offene Quote; bei verschobenen Quotes kann die "
                "eigentliche Ursache weiter oben liegen.")
        return line, col, context, highlight, off - ctx_start, hint
```

- [ ] **Step 4: Neuer Test grün + volle Suite grün (Nicht-Regression)**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -v`
Expected: PASS — insbesondere bleiben `test_parse_error_tokenerror_unclosed_quote_short`
und `_multiline` grün (dort ist die Ungerade-Zeile == EOF-Zeile → kein Redirect).

- [ ] **Step 5: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "feat(analyze): unclosed-Quote auf echte Fehlerzeile umleiten (Ungerade-Heuristik)"
```

---

### Task 3: UI — „, Spalte Y" weglassen wenn keine Spalte

**Files:**
- Modify: `web/static/js/app.js` — `renderAnalyzeResult`, ~Zeile 546-548
- Verifikation: manueller/Playwright-UI-Smoke (kein JS-Unit-Test-Setup im Projekt)

**Interfaces:**
- Consumes: `res.parse_error_col` (kann jetzt `null` sein, Task 2).

- [ ] **Step 1: JS anpassen.** In `web/static/js/app.js::renderAnalyzeResult` den Block ersetzen. Vorher:

```javascript
      out.innerHTML =
        `<p class="hint">Parse-Fehler in Zeile ${esc(String(res.parse_error_line))}, ` +
        `Spalte ${esc(String(res.parse_error_col))}:</p>` +
        `<pre class="an-parse-error">${ctxHtml}</pre>` + hintHtml;
```

Nachher:

```javascript
      const loc = (res.parse_error_col != null)
        ? `Zeile ${esc(String(res.parse_error_line))}, Spalte ${esc(String(res.parse_error_col))}`
        : `Zeile ${esc(String(res.parse_error_line))}`;
      out.innerHTML =
        `<p class="hint">Parse-Fehler in ${loc}:</p>` +
        `<pre class="an-parse-error">${ctxHtml}</pre>` + hintHtml;
```

- [ ] **Step 2: App neu starten** (Core-Änderung aus Task 2 braucht Neustart; JS ist live). Alte Instanz killen, neu hochziehen:

```bash
ss -ltnp | grep 5057    # PID der alten Instanz finden und beenden
bash run.sh --skip-setup &
```

- [ ] **Step 3: UI-Smoke.** Analyzer öffnen, dieses SQL analysieren:

```
SELECT "a
FROM t
WHERE x = "b"
```

Expected: Anzeige „**Parse-Fehler in Zeile 1:**" (ohne „, Spalte …", ohne „Spalte null"),
darunter die Zeile `SELECT "a` ohne Zeichen-Mark, Hint „Vermutlich fehlt ein " in Zeile 1 …".
Gegenprobe einzeilig `SELECT "a FROM t` zeigt weiterhin „Zeile 1, Spalte 8" mit Mark.

- [ ] **Step 4: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(ui): Analyzer-Parse-Fehler ohne Spalte anzeigen, wenn nicht bestimmbar"
```

---

### Task 4: Release v0.61.0 + Doku

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`), Changelog (EN + DE-Mirror),
  Roadmap-Prosa + `.mmd` (Board/Gantt), `CLAUDE.md` (Analyzer-Zeile), Kennzahlen-Dashboard
  (Headline + Per-Modul-Balken), Site-Build, gh-pages.

**Interfaces:**
- Consumes: fertige, getestete Änderungen aus Task 1-3.

- [ ] **Step 1: Version bumpen (minor — neues Feature)**

```bash
./venv/bin/python sync_version.py --minor   # 0.60.0 → 0.61.0
```

- [ ] **Step 2: Doku nachziehen (am echten Code geprüft, nicht geraten).** Changelog EN + DE-Mirror-Eintrag; Roadmap-Prosa + Board/Gantt-`.mmd` (AP-65 Pro-Zeile-Heuristik als done); `CLAUDE.md`-Analyzer-Absatz um die Ungerade-Quote-Zeilenlokalisierung ergänzen; Kennzahlen frisch erheben:

```bash
git rev-list --count HEAD
./venv/bin/python -m pytest -q | tail -1
```

Kennzahlen-Dashboard (Commits/Sessions/Tests/Coverage + **Per-Modul-Balken** hartkodiert) mitziehen. Danach je neuem Feature per `grep` gegenprüfen, dass Changelog/Roadmap/CLAUDE/Kennzahlen die Heuristik nennen.

- [ ] **Step 3: Volle Suite grün + Site bauen**

Run: `./venv/bin/python -m pytest`
Expected: PASS (438 passed erwartet: 436 + 2 neue), 10 skipped.
Danach Site-Build + gh-pages-Worktree-Deploy (siehe `ludbxp-release-deploy-steps`-Memory).

- [ ] **Step 4: Commit + Push**

```bash
git add -A
git commit -m "release: v0.61.0 — AP-65 Analyzer Pro-Zeile-Ungerade-Quote-Heuristik"
git push origin master
```
