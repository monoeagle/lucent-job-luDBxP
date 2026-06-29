# AP-65·A-Härtung — TokenError-Quote-Hinweis + Mark-Fix

**Datum:** 2026-06-30 · **Zielversion:** v0.59.0 (Minor) · **Typ:** Analyzer-Fehleranzeige härten (Folgescheibe zu AP-65·A)

## Zweck & Befund

AP-65·A (v0.58.0) zeigt Parse-Fehler mit Position. Zwei reale Lücken, durch einen Live-Test
(mehrzeiliges Statement mit fehlendem Anführungszeichen) aufgedeckt:

1. **TokenError mit nicht geschlossenem Anführungszeichen liefert KEINE Position.** Ein fehlendes/
   verschobenes `"` mitten im Statement verschiebt alle folgenden Quote-Paare; der sqlglot-Tokenizer
   bleibt scheinbar balanciert und **konsumiert bis zum Dateiende**, wo erst das letzte `"` unpaarig
   bleibt. sqlglots Fehlermeldung ist dann ein **Tail-Fenster** (kein Präfix ab Position 0), und die
   bestehende `sql.startswith(prefix)`-Heuristik schlägt fehl → `(None, None, "", "")` → Fallback auf
   die rohe Meldung, die irreführend ans Statement-**Ende** zeigt. **Empirisch bestätigt** mit der
   installierten sqlglot-Version.
2. **Markierung sitzt am falschen Token.** Wo eine Position gezeigt wird, nutzt das Frontend
   `ctx.indexOf(highlight)` und markiert das **erste** Vorkommen des Zeichens (bei `main"."ResourcePool"`
   das `main"`-Quote statt des End-Quotes). Das Zeile/Spalte-Label ist korrekt, nur die Markierung nicht.

**Ehrlichkeits-Grenze (Design-Annahme):** Bei verschobenen Quotes kann sqlglot die *echte* Ursache
prinzipiell nicht lokalisieren (es weiß nicht, wo das Quote hätte schließen sollen). Das Maximum, das
verlässlich geht: das **am Ende offene Quote** finden + einen Hinweis, dass die Ursache früher liegen kann.

## 1. Core — `core/sqlanalyze.py`

### Neue `AnalysisResult`-Felder (trailing, Default)
```python
parse_error_highlight_pos: int = -1   # context-relativer Index der Fehlerstelle (für die Markierung); -1 = unbekannt
parse_error_hint: str = ""            # ehrlicher Zusatzhinweis (z. B. nicht geschlossenes Quote)
```

### Neuer reiner Helfer `_unclosed_quote_offset(sql) -> int | None`
SQL zeichenweise scannen, Quote-Status togglen (`"` und `'`); gibt den Offset des Quotes zurück, das
am Ende **offen** bleibt, sonst `None`. (Toggle behandelt `''`/`""`-Escapes korrekt als close+open = neutral.)
```python
def _unclosed_quote_offset(sql):
    q = None; open_at = None
    for i, c in enumerate(sql):
        if q is None:
            if c in ('"', "'"):
                q = c; open_at = i
        elif c == q:
            q = None; open_at = None
    return open_at
```

### `_parse_error_location(exc, sql)` → 6-Tupel `(line, col, context, highlight, highlight_pos, hint)`
- **ParseError** (`.errors` vorhanden): wie bisher; zusätzlich `highlight_pos = len(start_context or "")`,
  `hint = ""`.
- **TokenError** (kein `.errors`):
  1. `off = _unclosed_quote_offset(sql)`.
  2. **`off is not None`** (offenes Quote gefunden — der Hauptfall):
     - `line = sql.count("\n", 0, off) + 1`, `col = off - sql.rfind("\n", 0, off)` (1-basiert; `rfind`=-1 → `off+1`),
     - `highlight = sql[off]` (das offene Quote-Zeichen),
     - `context = sql[max(0, off-30):off+10]`, `highlight_pos = off - max(0, off-30)`,
     - `hint = "Nicht geschlossenes Anführungszeichen — markiert ist das am Statement-Ende offene "
       "Quote; bei verschobenen Quotes kann die eigentliche Ursache weiter oben liegen."`
  3. **`off is None`** (Quotes balanciert, anderer Tokenizer-Fehler): die bisherige Message-Präfix-
     Heuristik (`_TOKEN_ERR_RE` + `startswith`), erweitert um `highlight_pos = off_prefix - max(0, off_prefix-20)`;
     `hint = ""`. Schlägt auch das fehl → alle Defaults.
- Sonst: `(None, None, "", "", -1, "")`.

### except-Zweig
6-Tupel entpacken, neue Felder per Keyword durchreichen (5-positionale Konstruktion bleibt gültig).
`parse_error` (String, ANSI-gestrippt) bleibt unverändert.

## 2. Route — `web/routes.py::api_analyze`

Nach den bestehenden `parse_error_*`-Feldern:
```python
parse_error_highlight_pos=result.parse_error_highlight_pos,
parse_error_hint=result.parse_error_hint,
```

## 3. Frontend — `web/static/js/app.js::renderAnalyzeResult`

- **Mark-Fix:** statt `ctx.indexOf(hl)` den gelieferten Index verwenden:
  `const i = (res.parse_error_highlight_pos >= 0) ? res.parse_error_highlight_pos : (hl ? ctx.indexOf(hl) : -1);`
  (Rest der Split/Wrap-Logik unverändert — `ctx.slice(0,i)` + `<span class="an-err-mark">esc(hl)</span>` + `ctx.slice(i+hl.length)`.)
- **Hint:** wenn `res.parse_error_hint` gesetzt, eine zusätzliche Zeile unter „Zeile N, Spalte M:"
  rendern: `<p class="hint an-err-hint">${esc(res.parse_error_hint)}</p>`. (Kleine optionale CSS-Regel
  `.an-err-hint` — dezent, am echten Code prüfen wo `.hint` definiert ist.)
- Fallback (`parse_error_line == null`): heutige String-Anzeige unverändert.

## 4. Tests

- **Unit `tests/test_sqlanalyze.py` (CI, kein DB):**
  - Mehrzeiliges offenes Quote (reproduziertes Screenshot-Beispiel): `parse_error_line` gesetzt (zeigt aufs
    am Ende offene Quote), `parse_error_highlight == '"'`, `parse_error_hint` enthält „Anführungszeichen",
    `parse_error_highlight_pos >= 0` und `context[highlight_pos] == '"'`.
  - Kurzes offenes Quote `SELECT * FROM main"."ResourcePool"`: `parse_error_col == 34`, Hint gesetzt.
  - ParseError `SELECT a b c FROM t`: `parse_error_highlight_pos == 11` (= `len(start_context)`),
    `context[11] == 'c'`, `parse_error_hint == ""`.
  - `_unclosed_quote_offset`: balanciertes SQL → `None`; ein offenes `"` → korrekter Offset.
  - Valides SQL: alle Felder Default (`-1`/`""`/`None`).
- **Route-Naht `tests/test_api.py`:** `/api/analyze` mit offenem Quote → `parse_error_highlight_pos` + `parse_error_hint` im JSON.
- **JS-Smoke (`page.route`):** Markierung sitzt am gelieferten `highlight_pos` (nicht am ersten Vorkommen); Hint sichtbar.

## 5. Release (voller SDD-Zyklus)

`sync_version.py --minor` → **v0.59.0**. Doku am Code geprüft: Changelog EN + DE-Mirror, Roadmap-Prosa
+ Diagramme (AP-65·A-Härtung erledigt, enumeriert; B/C bleiben offen), `datenmodell.md` (`AnalysisResult`-
Felder `parse_error_highlight_pos`/`parse_error_hint`), `oberflaeche.md` (Analyzer-Hint + korrekte Markierung),
Kennzahlen frisch (inkl. Per-Modul-Balken), Site, gh-pages.

## Verifikation

- `./venv/bin/python -m pytest` grün.
- Browser-Smoke: das mehrzeilige Screenshot-Beispiel zeigt jetzt Position + Hint + Markierung am offenen Quote.

## Nicht-Scope

- **Echte Ursachen-Lokalisierung bei verschobenen Quotes** (sqlglot-Grenze, s. o.) — bewusst nicht;
  stattdessen offenes End-Quote + ehrlicher Hinweis.
- **Stufe B** (Zeilennummern-Gutter im Eingabefeld) + **Stufe C** (Lints mit Zeilenbezug) bleiben Backlog.
- Keine Auto-Korrektur, read-only unberührt.
