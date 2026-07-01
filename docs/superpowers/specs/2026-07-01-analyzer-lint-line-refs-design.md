# Design — AP-65·C Lints mit Zeilenbezug

**Datum:** 2026-07-01
**Kontext:** LucentTools DB Explorer, AP-65 (Analyzer-Zeilen & Fehlerstelle). Stufe C des
Konzepts `docs/concepts/2026-06-29-analyzer-line-numbers-error-location.md`. Baut auf Stufe A/B
auf: Parse-Fehler tragen `parse_error_line`, und die Eingabe hat seit AP-65·B einen
Zeilennummern-Gutter mit `panel._gutter.setErrorLine(n)` (rote Zeilen-Markierung + Auto-Scroll).

## Problem

Die schema-freien Lints (`SELECT *`, `LIKE '%…'`, Funktion-auf-Spalte, verdächtiger Alias) und
Optimierungs-Vorschläge sowie die Schema-Warnungen (unbekannte Tabelle/Spalte) nennen **keine
Zeile**. Bei mehrzeiligem SQL muss der Nutzer die betroffene Stelle selbst suchen. Ziel: jede
knoten-spezifische Meldung nennt ihre Zeile und markiert sie per Klick im Eingabefeld.

## Machbarkeit (verifiziert)

sqlglot-Leaf-Knoten (`Identifier`, `Literal`, `Star`) tragen `meta` mit
`line`/`col`/`start`/`end`. Kompositknoten (`Table`, `Column`, `Or`, `Like`, `Join`) haben leeres
`meta`, ihre Nachfahren aber nicht. Ein Helfer, der den frühesten `meta['start']` unter den
Nachfahren nimmt und daraus die Zeile rechnet, liefert für alle Lint-auslösenden Knoten die
richtige Zeile (empirisch geprüft: `LIKE '%bad'`→Zeile 5, `OR`→4, `Table`→2/3, `SELECT *`→1).

## Datenmodell

`core/sqlanalyze.py`:
- `AnalysisWarning` erhält als **letztes** Feld `line: int | None = None`.
- `AnalysisSuggestion` erhält als **letztes** Feld `line: int | None = None`.

Beide sind frozen dataclasses; ein neues Feld mit Default `None` am Ende ist rückwärtskompatibel
mit allen bestehenden positionalen Konstruktionen.

## Helfer

```
_node_line(node, sql) -> int | None
```
Rein, read-only: sammelt `e.meta['start']` über `node.walk()` für alle Nachfahren mit gesetztem
`start`; nimmt das Minimum `off`; gibt `sql.count("\n", 0, off) + 1` zurück. Ohne positionierten
Nachfahren `None`.

## Zeilen-Fädelung

`analyze()` reicht `sql` an die Lint-Helfer weiter. Je Meldung:

| Meldung | Knoten für `_node_line` | Zeile? |
|---|---|---|
| `SELECT_STAR` | der `exp.Star`-Knoten | ja |
| `LEADING_WILDCARD` | der `exp.Like`-Knoten | ja |
| `FUNC_ON_COLUMN` | der `exp.Func`-Knoten in WHERE | ja |
| `SUSPICIOUS_ALIAS` | der `exp.Table`-Knoten (Alias) | ja |
| `CARTESIAN_JOIN` | der `exp.Join`-Knoten ohne ON | ja |
| `UNKNOWN_TABLE` | der `exp.Table`-Knoten | ja |
| `UNKNOWN_COLUMN` | der `exp.Column`-Knoten | ja |
| `OR_IN_WHERE` | der `exp.Or`-Knoten | ja |
| `SUBQUERY_IN_WHERE` | der Unter-`exp.Select`-Knoten | ja |
| `WRITE_STATEMENT` | — (Statement-Ebene) | `None` |
| `NO_WHERE` | — (Statement-Ebene) | `None` |
| `DISTINCT_WITH_GROUP_BY` | — (Statement-Ebene) | `None` |
| `ORDER_BY_NO_LIMIT` | — (Statement-Ebene) | `None` |

Signaturänderungen: `_static_lints(node, sql)` und `_optimization_suggestions(node, sql)`. Die
Schema-Warnungen (UNKNOWN_TABLE/COLUMN) und CARTESIAN_JOIN werden in `analyze()` gebildet, wo `sql`
bereits vorliegt.

## API

`web/routes.py::api_analyze` nimmt `line` in die serialisierten Dicts auf:
`{"level", "code", "message", "line"}` (Warnungen) und `{"code", "message", "line"}` (Vorschläge).

## Frontend

`web/static/js/app.js`:
- Beim Rendern einer Warnung/eines Vorschlags: hat das Objekt `line != null`, wird der Meldung ein
  **„Zeile N: "**-Präfix vorangestellt und das `<div>` erhält die Klasse `an-lint-clickable` +
  `data-line="N"`. Ohne `line` bleibt die Darstellung wie bisher.
- Ein **einmal** (in `openAnalyzer`) registrierter delegierter Klick-Listener auf `#an_result`:
  bei Klick auf ein Element mit `[data-line]` ruft er `panel._gutter.setErrorLine(Number(line))`.
  Das nutzt die bestehende rote `.an-line-error`-Markierung + Auto-Scroll aus AP-65·B.
- Der delegierte Listener wird bewusst **einmal** angehängt (nicht je `renderAnalyzeResult`), um
  kein Listener-Stacking zu erzeugen; `panel._gutter` wird zur Klickzeit gelesen.

`web/static/css/app.css`: `.an-lint-clickable { cursor: pointer; }` + dezenter Hover
(`text-decoration: underline` o. Ä.), abgesetzt, ohne die Level-Farben zu stören.

## Randbedingungen

- Read-only, NO-CDN, kein neues Core-Modul.
- Deutsch für user-sichtbaren Text („Zeile N: ").
- Die rote Markierung wird bewusst wiederverwendet (eine Markier-Mechanik); sie wird — wie bei
  Parse-Fehlern — bei jeder Eingabe (`input`) gelöscht.

## Tests

**Python (pytest, echte Unit-Tests, kein Browser):**
- `_node_line` gibt für konstruierte Knoten die richtige 1-basierte Zeile bzw. `None`.
- `SELECT_STAR` trägt die Zeile des `*`; `FUNC_ON_COLUMN` die Zeile der Funktion in WHERE;
  `LEADING_WILDCARD` die Zeile des `LIKE`; `UNKNOWN_TABLE` die Zeile der Tabelle.
- Statement-Ebene: `WRITE_STATEMENT`/`NO_WHERE` haben `line is None`.
- Rückwärtskompatibilität: eine Warnung ohne Zeile hat `line is None`.

**Frontend (Playwright-DOM-Smoke, System-`python3`):**
- Mehrzeiliges SQL mit `LIKE '%…'` in einer mittleren Zeile analysieren → die Warnmeldung beginnt
  mit „Zeile N:" und trägt `data-line=N`.
- Klick auf die Meldung → genau eine `.an-line-error` auf der Backdrop-Zeile N.

## Betroffene Dateien

- `core/sqlanalyze.py` — `line`-Felder, `_node_line`, Fädelung in `_static_lints` /
  `_optimization_suggestions` / `analyze` (CARTESIAN_JOIN, UNKNOWN_TABLE/COLUMN).
- `web/routes.py` — `line` in der Serialisierung.
- `web/static/js/app.js` — Präfix + `an-lint-clickable` + delegierter Klick-Listener.
- `web/static/css/app.css` — `.an-lint-clickable`.
- Tests: `tests/test_sqlanalyze.py` (+ ggf. `tests/test_api.py` für die Serialisierung).
