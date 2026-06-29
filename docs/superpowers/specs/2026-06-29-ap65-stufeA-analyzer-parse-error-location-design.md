# AP-65·Stufe A — SQL-Analyzer: Parse-Fehler mit Position

**Datum:** 2026-06-29 · **Zielversion:** v0.58.0 (Minor) · **Typ:** Analyzer-Anreicherung (Fehler-Lokalisierung)

## Zweck

Der SQL-Analyzer (`core/sqlanalyze.py`, Tab „SQL-Analyzer") zeigt bei einem nicht parsbaren
Statement heute nur einen **gestrippten Fehler-String** ohne Zeile/Spalte. Stufe A übernimmt die
**strukturierte Positionsinfo** (Zeile/Spalte + Kontext-Ausschnitt + fehlerhafter Token) und zeigt
sie als „Parse-Fehler in Zeile N, Spalte M: …" mit farbig markierter Fehlerstelle. Read-only —
der Analyzer führt weiterhin nichts aus, korrigiert nichts.

## Code-Befund (verifiziert) — Abweichung vom Konzept

Das AP-65-Konzept nahm an, der Fehler trage immer `exc.errors[0]`. **Empirisch geprüft** mit der
installierten sqlglot-Version:

- **`ParseError`** (Parser-Stufe, z. B. `SELECT a b c FROM t`): trägt `.errors` — eine Liste von
  Dicts mit `description`, `line`, `col`, `start_context`, `highlight`, `end_context`, `into_expression`.
- **`TokenError`** (Tokenizer-Stufe — **das Auslöser-Beispiel**: `SELECT * FROM main"."ResourcePool"`
  mit fehlendem `"`): trägt **kein** `.errors`, keine `line`/`col`. Nur `args = (Error tokenizing '<prefix>',)`,
  wobei `<prefix>` der bis zum Fehler **konsumierte Präfix** des Original-SQL ist (echter Präfix).

`TokenError` ist eine Subklasse von `SqlglotError`. Der bestehende `except (SqlglotError, ValueError)`
fängt beide. Stufe A behandelt beide Fälle (ParseError exakt, TokenError best-effort).

## 1. Core — `core/sqlanalyze.py`

Vier neue **Trailing-Felder** an `AnalysisResult` (alle mit Default → die bestehenden 5-positionalen
`AnalysisResult("OTHER", (), (), (), <msg>)`-Konstruktionen im `except`/`empty`-Zweig bleiben gültig):

```python
parse_error_line: int | None = None
parse_error_col: int | None = None
parse_error_context: str = ""      # Ausschnitt um die Fehlerstelle (für die Anzeige)
parse_error_highlight: str = ""    # der fehlerhafte Token (zum farbigen Markieren)
```

Neuer reiner Helfer `_parse_error_location(exc, sql) -> tuple[int|None, int|None, str, str]`
(line, col, context, highlight):

- **ParseError mit `.errors`:** `e = exc.errors[0]`; `line = e["line"]`, `col = e["col"]`,
  `highlight = e.get("highlight") or ""`,
  `context = (e.get("start_context") or "") + highlight + (e.get("end_context") or "")`.
- **TokenError / kein `.errors`:** aus `str(exc)` per Regex `^Error tokenizing '(.*)'$` (DOTALL) den
  Präfix ziehen. Wenn `sql.startswith(prefix)`:
  `line = prefix.count("\n") + 1`, `col = len(prefix) - prefix.rfind("\n")` (1-basiert; `rfind`=-1 → `col = len(prefix)+1`),
  `highlight = sql[len(prefix)]` falls vorhanden, sonst `""`,
  `context` = Fenster `sql[max(0, off-20):off+20]` um `off = len(prefix)`.
  Schlägt die Extraktion fehl (kein Match / `startswith` falsch) → `(None, None, "", "")`.
- Jeder Zugriff defensiv (`.get`, Bounds) → nie eine zweite Exception; Fallback `(None, None, "", "")`.

Im `except`-Zweig: `line, col, ctx, hl = _parse_error_location(exc, sql)` und in den `AnalysisResult`
durchreichen (die übrigen Felder unverändert, inkl. des bestehenden ANSI-gestrippten `parse_error`).
Der `empty statement`-Zweig bleibt unverändert (Felder default).

## 2. Route — `web/routes.py::api_analyze`

Im `jsonify(...)` vier neue Felder nach `parse_error`:
```python
parse_error_line=result.parse_error_line,
parse_error_col=result.parse_error_col,
parse_error_context=result.parse_error_context,
parse_error_highlight=result.parse_error_highlight,
```

## 3. Frontend — `web/static/js/app.js::renderAnalyzeResult`

Den bestehenden `if (res.parse_error)`-Block erweitern:
- Wenn `res.parse_error_line` gesetzt: Überschrift „**Parse-Fehler in Zeile {line}, Spalte {col}:**"
  (esc'd) + den Kontext-Ausschnitt in `<pre class="an-parse-error">`, wobei der `highlight`-Token
  **farbig markiert** wird: Kontext am **ersten** Vorkommen von `highlight` splitten und das Stück in
  `<span class="an-err-mark">…</span>` wrappen — alle drei Teile (`esc`'d) zusammensetzen. Wenn
  `highlight` leer oder nicht im Kontext: Kontext unmarkiert anzeigen.
- Fehlt `parse_error_line` (Extraktion fehlgeschlagen): heutige Anzeige (Label + `parse_error`-String) als Fallback.
- Kleine CSS-Regel `.an-err-mark` (rot/unterstrichen) im bestehenden CSS, konsistent zu vorhandenen Markern.

## 4. Tests

- **Unit `tests/test_sqlanalyze.py` (CI, kein DB):**
  - ParseError `SELECT a b c FROM t`: `parse_error_line == 1`, `parse_error_col` > 0, `parse_error_highlight` nicht leer.
  - TokenError `SELECT * FROM main"."ResourcePool"`: `parse_error_line == 1`, `parse_error_col` zeigt nahe ans
    fehlende `"` (Spalte ≈ Länge des konsumierten Präfix), `parse_error_context` enthält den umliegenden Text.
  - Mehrzeilig (`"SELECT a,\n  b c d\nFROM t"`): `parse_error_line == 2`.
  - Valides SQL: alle vier Felder `None`/`""`.
  - `empty statement`: Felder default.
- **Route-Naht `tests/test_api.py`:** `/api/analyze` mit kaputtem SQL → die vier Felder im JSON, mit Werten.
- **JS-Smoke (`page.route`):** „Parse-Fehler in Zeile N, Spalte M" + `.an-err-mark` sichtbar.

## 5. Release (voller SDD-Zyklus)

`sync_version.py --minor` → **v0.58.0**. Doku am Code geprüft: Changelog EN + DE-Mirror, Roadmap-Prosa
+ Diagramme (AP-65·A done, enumeriert; AP-65·B/C bleiben offen), `datenmodell.md` (`AnalysisResult`-Felder
`parse_error_line/col/context/highlight`), `oberflaeche.md` (Analyzer-Fehleranzeige mit Position),
Kennzahlen frisch erhoben (inkl. Per-Modul-Balken), Site, gh-pages.

## Verifikation

- `./venv/bin/python -m pytest` grün (sqlanalyze-Unit + Route-Naht; JS-Smoke separat).
- Browser-Smoke: kaputtes SQL (ParseError + TokenError-Beispiel) zeigt Zeile/Spalte + markierte Stelle.

## Nicht-Scope (Stufe B/C, zurückgestellt)

- **Stufe B:** Zeilennummern-Gutter im Eingabe-Textarea + Fehlerzeile farbig hinterlegen.
- **Stufe C:** Lints/Warnungen mit Zeilenbezug (`AnalysisWarning.line`), Klick-auf-Meldung → Zeile markieren.
- Keine Auto-Korrektur, keine Mehrfachfehler-Aggregation (sqlglot meldet den ersten Fehler), read-only unberührt.

## Risiken / offene Punkte

- **TokenError best-effort ist heuristisch:** beruht auf dem Message-Format `Error tokenizing '<prefix>'`
  und darauf, dass `<prefix>` ein echter Präfix des SQL ist. Ändert sqlglot das Format, greift der
  Fallback (`None`/`""` → heutige String-Anzeige) — kein Crash, nur keine Position. Im Unit-Test gegen
  die installierte Version abgesichert; bei sqlglot-Upgrade neu prüfen.
- **`col` ist 1-basiert** und an die sqlglot-Konvention (ParseError) angelehnt; der TokenError-Pfad nutzt
  dieselbe 1-Basis für Konsistenz in der Anzeige.
