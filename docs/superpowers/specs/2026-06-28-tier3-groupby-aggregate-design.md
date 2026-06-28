# Design: Tier-3 — GROUP BY + Aggregate im SQL-Generator

**Datum:** 2026-06-28
**Status:** Genehmigt (Brainstorming abgeschlossen)
**Kontext:** Reflection-/Generator-Ausbau, nächster Tier nach Tier-2 (Tabellen-/Spaltenkommentare, v0.40.0).

## Ziel

Das Tool baut visuell Join-Pfade über eine reflektierte Fremd-Datenbank: man wählt Start-/Ziel-
**Spalten** plus optionale Filter und erhält daraus einen Join-Pfad und read-only SQL. Bisher
erzeugt der Generator (`core/sqlgen.py`) flache Zeilen-SELECTs (SELECT-Liste, JOINs, WHERE,
ORDER BY, DISTINCT, LIMIT). Eine sehr häufige Auswertungsfrage — *„wie viele/Summe/Durchschnitt
je Gruppe?"* — ist damit nicht ausdrückbar.

**Tier-3 erweitert den Generator um Aggregat-Funktionen pro Spalte und ein automatisch
abgeleitetes GROUP BY.** Damit wird z. B. „pro Kunde Anzahl Bestellungen" als ein Klick je
Spalte erzeugbar.

**Wichtige Klarstellung zum Ist-Stand:** Der *Analyzer* (`core/sqlanalyze.py`, AP-39) parst
GROUP BY/HAVING aus *bestehendem* SQL bereits read-only und zeigt „Aggregate"/„Gruppierung"-Pills
an. Das ist reine Analyse fremden SQLs — der *Generator* kann GROUP BY/Aggregate bislang **nicht
erzeugen**. Genau diese Lücke schließt Tier-3. Die Analyzer-Terminologie wird für die UI-Labels
wiederverwendet.

## Kernmodell: Auto-GROUP-BY

Jeder SELECT-Eintrag (Start-Spalte, Ziel-Spalte, jede Extra-Spalte) trägt ein **optionales
Aggregat** aus `{COUNT, SUM, AVG, MIN, MAX}`, jeweils als `func(Spalte)`. **GROUP BY wird
automatisch** aus allen *nicht*-aggregierten SELECT-Spalten abgeleitet — es gibt **keine**
separate, manuell gepflegte GROUP-BY-Liste. Mentales Modell: *jede Spalte in der SELECT-Liste
ist entweder Gruppenschlüssel oder Aggregat.*

Drei Fälle (alle valides Standard-SQL):

| Aggregate in der SELECT-Liste | Ergebnis |
|---|---|
| **keine** | kein GROUP BY → **bitidentisch zum heutigen Verhalten** (volle Rückwärtskompatibilität) |
| **manche** | `GROUP BY <alle nicht-aggregierten Spalten>` |
| **alle** | kein GROUP BY (gültige Ein-Zeilen-Aggregation, z. B. `SELECT COUNT(a), SUM(b) FROM …`) |

## Scope

**In Scope:**
- Aggregat-Funktionen `COUNT`, `SUM`, `AVG`, `MIN`, `MAX` — je als `func(Spalte)`.
- Automatisch abgeleitetes `GROUP BY` aus den nicht-aggregierten SELECT-Spalten.
- Aggregat-Auswahl an **Start-, Ziel- und jeder Extra-Spalte** (nicht nur Extra-Spalten —
  nötig für den häufigsten Fall „pro Kunde Anzahl Bestellungen": Start = Gruppenschlüssel,
  Ziel = `COUNT`).
- Klauselreihenfolge im erzeugten SQL: `WHERE → GROUP BY → ORDER BY → LIMIT`.
- Wirkt automatisch auch im read-only Ausführungspfad (`/api/joinpath/run` nutzt denselben
  Generator).

**Out of Scope (YAGNI / spätere Folge-Scheiben):**
- **HAVING** (Filter auf Aggregat-Ergebnisse) — eigene Folge-Scheibe. WHERE filtert weiter
  auf Roh-Zeilen wie bisher.
- **COUNT(\*)** und **COUNT(DISTINCT …)** — sprengen das „Aggregat pro Spalte"-Modell
  (eigener Sondereintrag); später nachrüstbar.
- **ORDER BY auf Aggregaten:** ORDER BY rendert weiter `t.c` auf Roh-Spalten. Sortiert der
  Nutzer bei aktivem GROUP BY auf einer nicht-gruppierten/nicht-aggregierten Spalte, meldet die
  DB einen Fehler — Verantwortung des Nutzers (read-only Tool, DB validiert). Wird als
  Einschränkung dokumentiert.
- **Keine harte Typprüfung** (z. B. SUM/AVG auf Text-Spalten). Das Tool validiert Spalten-Typen
  nicht; ein unsinniges Aggregat erzeugt einen DB-seitigen Fehler beim Ausführen. Konsistent mit
  der bestehenden read-only Philosophie.

## Komponenten & Änderungen

### 1. Generator — `core/sqlgen.py`
- `Selection` erhält ein Feld `agg: str = ""` (frozen dataclass, Default leer → bestehende
  Aufrufer/Tests unverändert gültig).
- Allowlist `_ALLOWED_AGGS = {"", "COUNT", "SUM", "AVG", "MIN", "MAX"}`. Unbekanntes Aggregat →
  `ValueError` (spiegelt die bestehende op-/direction-Validierung).
- SELECT-Liste: bei gesetztem `agg` → `AGG(<qualified>)` (z. B. `COUNT("orders"."id")`), sonst
  wie bisher der reine qualifizierte Spaltenausdruck.
- Neuer GROUP-BY-Block: erzeugt aus den SELECT-Einträgen mit `agg == ""`, eingefügt **nach**
  WHERE und **vor** ORDER BY. Steht identisch in `sql` *und* `sql_inline` (enthält keine
  Filterwerte/Parameter). Leerer Gruppenschlüssel (alle aggregiert) → kein GROUP BY emittiert.
- Dedup-Schlüssel der SELECT-Liste wird `(table, column, agg)` (heute `(table, column)`), damit
  dieselbe Spalte einmal als Gruppenschlüssel *und* einmal aggregiert koexistieren kann.

### 2. Route — `web/routes.py`
- `_parse_joinpath_params` liest `agg` aus `start`, `target` und jedem `extra_selects[]`-Eintrag;
  konstruiert `Selection(table, column, agg=…)`.
- `_make_path_gen` baut die deduplizierte SELECT-Liste wie bisher, jetzt agg-tragend.
- Spalten-Existenzprüfung (`schema.has_column`) und AP-30-`required_tables`-Weaving bleiben
  **unverändert** — ein Aggregat ändert die Spaltenreferenz nicht.
- Validierung des `agg`-Werts erfolgt im Generator (Single Source of Truth, Allowlist), die Route
  reicht ihn durch.

### 3. Frontend — `web/static/js/app.js`
- Kleines Aggregat-`<select>` (`—`/COUNT/SUM/AVG/MIN/MAX) neben `start_col`, neben `target_col`
  und in jeder per `addColRow()` erzeugten Extra-Spalten-Zeile.
- `collectJoinBody()` hängt `agg` an `start`, `target` und jeden `extra_selects`-Eintrag an
  (`agg: ""` wenn „—" gewählt).
- Labels/Terminologie konsistent mit der Analyzer-Anzeige („Aggregat", „Gruppierung").
- `swapStartTarget()` muss die Aggregat-Auswahl von Start/Ziel mit-swappen (analog zu
  table/column), damit der Swap-Komfort erhalten bleibt.

## Rückwärtskompatibilität

Ohne jedes Aggregat haben alle `Selection` `agg == ""` → kein GROUP BY → erzeugtes SQL ist
**zeichengleich** zu heute. Bestehende 272 Tests bleiben unverändert grün; `Selection`-Konstruktionen
ohne `agg`-Argument bleiben gültig.

## Edge Cases & Entscheidungen

- **Alle Spalten aggregiert** → kein GROUP BY (Ein-Zeilen-Aggregat). Generator gibt den
  GROUP-BY-Block nur aus, wenn mindestens ein nicht-aggregierter SELECT existiert.
- **Gleiche Spalte als Schlüssel und Aggregat** (z. B. `orders.id` als Gruppenschlüssel und
  `COUNT(orders.id)`): durch Dedup-Key `(table, column, agg)` koexistenzfähig.
- **DISTINCT + GROUP BY**: syntaktisch koexistent, bleibt unverändert erlaubt (harmlos).
- **ORDER BY bei aktivem GROUP BY**: unverändert; mögliche DB-Fehler bei nicht-gruppierter
  Sortierspalte sind Nutzer-Verantwortung (siehe Out of Scope).

## Teststrategie

- **`tests/test_sqlgen.py`** — Aggregat-Rendering pro Funktion; Auto-GROUP-BY für die drei Fälle
  (keine/manche/alle aggregiert); Dedup mit `agg`; korrekte Klauselreihenfolge
  (WHERE→GROUP BY→ORDER BY→LIMIT); Allowlist-`ValueError` bei unbekanntem Aggregat;
  Rückwärtskompatibilität (kein Aggregat ⇒ unverändertes SQL).
- **`tests/test_sqlgen_dialect.py`** — GROUP BY mit Identifier-Quoting und Schema-Qualifizierung
  je Dialekt (SQLite/Postgres/MySQL/MSSQL/Oracle).
- **`tests/test_api.py`** — Route parst `agg` aus start/target/extra_selects; GROUP BY landet im
  erzeugten SQL; der read-only Run-Pfad (`/api/joinpath/run`) führt das Aggregat-SQL aus und
  liefert Gruppen-Zeilen.

## Architektur-Diagramme

Kein neues Modul und kein neuer Endpoint → Architektur-/Komponenten-Diagramme bleiben unverändert.
Release umfasst Version-**Minor**-Bump, Changelog + Doc-Mirror, Roadmap/Board/Gantt, „Bekannte
Einschränkungen"-Block in CLAUDE.md (Tier-3 erledigt, HAVING/COUNT(\*)/Cross-Schema offen), Badge
(Test-Zahl) und Site-Build.
