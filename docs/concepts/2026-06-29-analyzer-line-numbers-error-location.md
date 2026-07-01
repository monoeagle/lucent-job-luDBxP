# Konzept & Arbeitspaket — SQL-Analyzer: Zeilennummern + Fehler-Lokalisierung (AP-65)

**Datum:** 2026-06-29
**Status:** Stufe A erledigt (v0.58.0) · Stufe A-Härtung erledigt (v0.59.0) · Stufe A-Härtung 2 — Unclosed-Quote echte Fehlerzeile via Ungerade-Heuristik erledigt (v0.61.0) · Stufe B — Zeilennummern-Gutter + Fehlerzeilen-Highlight erledigt (v0.62.0) · Stufe C offen (AP-65·C)
**Auslöser:** Beim Analysieren eines fehlerhaften Statements (einer JOIN-Tabelle fehlt ein `"`) meldet der Analyzer nur `Error tokenizing 'ePool"…'` — ohne **Zeile/Spalte** und ohne die fehlerhafte Stelle zu markieren. Der Nutzer kann die Fehlerstelle nicht zuordnen (die Meldung zeigt einen *Folge*-Token, nicht die Ursache `JOIN main"."ResourcePool"` mit dem fehlenden `"`).

## 1. Problem

Der SQL-Analyzer (`core/sqlanalyze.py`, Tab „SQL-Analyzer") parst read-only via **sqlglot** und zeigt Typ, Komplexität, Joins, Filter, gelesene/geschriebene Tabellen sowie Warnungen/Lints/Optimierungs-Vorschläge.

Zwei Lücken bei der **Fehler-/Meldungs-Verortung**:

1. **Parse-Fehler ohne Position.** Bei einem nicht parsbaren Statement wird nur ein **gestrippter Fehler-String** ausgegeben — ohne Zeilen-/Spaltenangabe und ohne Hervorhebung. Die Meldung kann (wie im Beispiel) auf einen Folge-Token zeigen statt auf die Ursache.
2. **Lints/Warnungen ohne Zeilenbezug.** Warnungen (`SELECT *`, `LIKE '%…'`, `SUSPICIOUS_ALIAS`, `UNKNOWN_COLUMN`, …) und Optimierungs-Vorschläge benennen Spalten/Tabellen, aber **nicht die Quellzeile**. Bei mehrzeiligen Statements ist unklar, *wo* die Meldung greift.

## 2. Code-Befund (Ist-Stand verifiziert)

- `core/sqlanalyze.py:291–295`: `sqlglot.parse_one(...)` in `try`; bei `(SqlglotError, ValueError)` wird **nur** `AnalysisResult("OTHER", …, _ANSI_RE.sub("", str(exc)))` zurückgegeben. Der String-Cast der Exception verwirft die **strukturierten** Fehlerinfos.
- sqlglots `ParseError`/`TokenizeError` tragen `exc.errors` — eine Liste von Dicts mit den Schlüsseln **`line`, `col`, `start_context`, `highlight`, `end_context`, `description`**. (Empirisch bestätigt mit der installierten sqlglot-Version.) Genau diese line/col/Kontext-Daten werden derzeit weggeworfen.
- Lints werden über den AST gebildet (`expr.find_all(...)`). sqlglot-Knoten/-Token tragen Positionsinfo (Token `line`/`col` bzw. `node.meta`), die heute nicht in die `AnalysisWarning` übernommen wird (`AnalysisWarning` hat nur `level/code/message`).

## 3. Was ich tun würde

**Stufe A — Parse-Fehler mit Position (Kern, kleinster Nutzen-Hebel):**
- Im `except`-Zweig `exc.errors[0]` auslesen und **strukturiert** ins Ergebnis übernehmen: neue Felder am `AnalysisResult`, z. B. `parse_error_line: int | None`, `parse_error_col: int | None`, `parse_error_context: str` (aus `start_context` + `highlight` + `end_context` zusammengesetzt). Rückwärtskompatibel: `parse_error` (String) bleibt für die Kurzanzeige.
- `/api/analyze` liefert die neuen Felder mit.
- UI: Meldung als **„Parse-Fehler in Zeile N, Spalte M: …"** + den Kontext-Ausschnitt mit der **markierten** Fehlerstelle (`highlight`) farbig hervorheben.

**Stufe B — Zeilennummern im Eingabefeld + Fehlerzeile markieren:**
- Das Analyzer-Eingabe-Textarea um eine **Zeilennummern-Spalte (Gutter)** ergänzen (reines Markup/CSS, keine externe Lib — NO-CDN) und die Fehlerzeile (aus Stufe A) **farbig hinterlegen**.

**Stufe C — Lints mit Zeilenbezug:**
- `AnalysisWarning`/`AnalysisSuggestion` um ein optionales `line: int | None` erweitern; beim Bilden einer Warnung die Quellzeile des auslösenden AST-Knotens/Tokens mitführen (sqlglot-Token-Position).
- UI: jede Meldung mit **„Zeile N:"** präfixen; Klick auf eine Meldung **markiert** die zugehörige Zeile im Eingabefeld.

## 4. Nicht-Scope

- **Keine Auto-Korrektur** des fehlerhaften SQL — reine Lokalisierung/Anzeige.
- Keine vollständige Fehler-Recovery (sqlglot meldet i. d. R. den ersten Fehler; Mehrfachfehler-Aggregation ist nicht Ziel).
- Read-only bleibt unberührt: der Analyzer führt weiterhin nichts aus.

## 5. Aufwand & Sequenzierung

- **Stufe A:** **S** — reine Datenweitergabe (sqlglot-`.errors` → Result → Anzeige), gut SQLite-/Unit-testbar (konstruierte kaputte Statements, Assert auf `parse_error_line`/`col`).
- **Stufe B:** **S–M** — Frontend-Gutter + Zeilen-Highlight.
- **Stufe C:** **M** — Token-Positions-Verdrahtung durch alle Lint-Heuristiken.

Empfohlen: **A zuerst** (größter Nutzen pro Aufwand — beantwortet „wo ist der Fehler?"), dann B (visuelle Verortung), C optional.
