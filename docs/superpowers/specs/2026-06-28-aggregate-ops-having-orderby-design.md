# Design: Aggregat-Operationen — HAVING + ORDER BY auf Aggregaten

**Datum:** 2026-06-28
**Status:** Genehmigt (Brainstorming abgeschlossen)
**Kontext:** Direkte Folge-Stufe nach Tier-3 (GROUP BY/Aggregate, v0.41.0). Schließt die zwei in
Tier-3 bewusst ausgeklammerten Aggregat-Bedienungen, die Nutzer unmittelbar nach „GROUP BY +
COUNT" brauchen.

## Ziel

Tier-3 (v0.41.0) brachte Aggregate (`COUNT/SUM/AVG/MIN/MAX`) pro SELECT-Spalte mit
automatischem GROUP BY. Zwei naheliegende Operationen auf diesen Aggregaten fehlen noch:

1. **ORDER BY auf Aggregaten** — gruppierte Ergebnisse nach dem Aggregat sortieren
   („Top-Hosts nach VM-Anzahl": `ORDER BY COUNT(...) DESC`). Heute rendert ORDER BY nur
   Roh-Spalten, ein aggregiertes Sortierkriterium ist nicht ausdrückbar.
2. **HAVING** — Gruppen nach ihrem Aggregat-Ergebnis filtern (`HAVING COUNT(*) > 5`). Der
   Generator kennt HAVING gar nicht (der read-only *Analyzer* parst es seit AP-39 bereits, das
   ist getrennte Funktionalität).

Beide operieren auf demselben Aggregat-Begriff und nutzen dieselbe `_ALLOWED_AGGS`-Allowlist aus
Tier-3. Sie werden als **ein AP** gebündelt (ein Minor-Release).

## Scope

**In Scope:**
- ORDER BY-Eintrag trägt optional ein Aggregat (`COUNT/SUM/AVG/MIN/MAX`) → rendert `AGG(col) DIR`.
- HAVING-Bedingungen: `AGG(col) <op> <wert>`, mit Aggregat **verpflichtend**.
- HAVING-Operatoren: nur Skalar-Vergleiche `=, !=, <, >, <=, >=`.
- HAVING-Werte parametrisiert (`:h0, :h1, …`) — eigener Placeholder-Namespace, kollidiert nicht
  mit WHERE (`:p0`). Plus inline-Literal-Variante für die Copy/Display-SQL.
- Klauselreihenfolge im erzeugten SQL: `WHERE → GROUP BY → HAVING → ORDER BY → LIMIT`.
- Wirkt automatisch im read-only Run-Pfad (`/api/joinpath/run` nutzt denselben Generator).
- HAVING-Tabellen werden ins AP-30-`required_tables`-Weaving aufgenommen.

**Out of Scope (YAGNI / spätere Folge-Scheiben):**
- HAVING mit `IN`/`BETWEEN`/`LIKE`/`IS (NOT) NULL` auf Aggregaten (SQL-gültig, aber exotisch).
- HAVING ohne Aggregat (Filter auf reinen Gruppenschlüssel) — gehört konzeptuell in WHERE
  (vor der Gruppierung).
- `COUNT(*)` / `COUNT(DISTINCT col)` — eigenes Folge-AP.
- Harte Typprüfung (z. B. `SUM`/`AVG` auf Textspalten) — read-only, DB meldet den Fehler.

## Entscheidungen

- **ORDER-BY-Aggregat ist frei:** Es muss kein im SELECT vorhandenes Aggregat spiegeln. Standard-SQL
  erlaubt `ORDER BY AGG(col)` unabhängig von der SELECT-Liste; eine sinnwidrige Kombination bei
  aktivem GROUP BY meldet die DB (Nutzer-Verantwortung, read-only).
- **HAVING immer parametrisiert:** Werte gehen wie WHERE-Werte als benannte Platzhalter in `params`
  — kein String-Konkatenations-Injection-Vektor. Die inline-Variante (für Copy) rendert Literale
  über denselben `_inline_literal`-Pfad wie WHERE.
- **HAVING-Aggregat verpflichtend:** jede HAVING-Zeile ist `AGG(col) op wert`. Macht „Filter auf
  Aggregat-Ergebnis" eindeutig und die UI/Validierung einfach.

## Komponenten & Änderungen

### 1. Generator — `core/sqlgen.py`
- **ORDER BY:** `order_by`-Element wird ein optionales 4. Feld `agg`. Generator liest
  `agg = entry[3] if len(entry) > 3 else ""` → **bestehende 3-Tupel-Aufrufe bleiben gültig**.
  Bei gesetztem `agg` (validiert gegen `_ALLOWED_AGGS`): `AGG(<qualified>) DIR`, sonst wie bisher
  `<qualified> DIR`.
- **HAVING:** neue frozen dataclass `Having(table: str, column: str, agg: str, op: str, value: object)`
  und neuer Parameter `having: tuple[Having, ...] = ()` in `generate_sql`.
  - Allowlist `_ALLOWED_HAVING_OPS = frozenset({"=","!=","<",">","<=",">="})`. Unbekannter Op →
    `ValueError`. `agg` muss in `_ALLOWED_AGGS` (nicht-leer) sein, sonst `ValueError`.
  - Rendering: pro Bedingung `AGG(<qualified>) <op> :h{i}`; Werte nach `params["h{i}"]`. Mehrere
    Bedingungen als HAVING-Block analog zum WHERE-Block (`HAVING …` erste Zeile, `  AND …` weitere).
    Inline-Variante mit `_inline_literal(value)`.
- **Klauselzusammenbau:** `lines + where_param + group_lines + having_param + tail` (und die
  inline-Pendants). HAVING steht zwischen GROUP BY und ORDER BY/LIMIT.

### 2. Route — `web/routes.py`
- `_parse_joinpath_params`:
  - ORDER BY: zusätzlich `agg = ob.get("agg", "")` lesen → 4-Tupel `(tbl, col, direction, agg)`.
  - HAVING: `data.get("having", [])` → `Having(table, column, agg, op, value)`. Spalten-Existenz
    via `schema.has_column` prüfen (unbekannt → `ValueError`/400).
  - `required_tables` erweitern um `[h.table for h in having]` (order-preserving dedup), damit die
    HAVING-Tabelle in den Join-Pfad gewoben wird.
- `_make_path_gen` erhält Parameter `having` und reicht ihn an `generate_sql` durch.
- Bad HAVING-Op/-Aggregat → `ValueError` aus dem Generator → bestehendes `try/except → 400`.

### 3. Frontend — `web/static/js/app.js`
- **ORDER BY:** Aggregat-`<select>` `.ob-agg` (`aggOptions()` aus Tier-3) zwischen `.ob-col` und
  `.ob-dir` in `addOrderByRow`; `collectOrderBy` ergänzt `agg`. Live-Rebuild beibehalten.
- **HAVING:** neuer Container `#havings` + Button „HAVING +" (neben „Filter +"/„Sortierung +"/
  „Spalten +"). `addHavingRow()`: Aggregat-Dropdown + Tabellen-Select + Spalten-Select +
  Skalar-Op-Dropdown (`= != < > <= >=`) + Wertfeld + ✕. `collectHaving()` liefert
  `{table, column, agg, op, value}` nur bei vollständiger Zeile (Wert ≠ leer). `collectJoinBody()`
  ergänzt `having: collectHaving()`. Live-Rebuild über das bestehende `_rebuildIfBuilt`-Muster.

## Rückwärtskompatibilität

Ohne ORDER-BY-Aggregat und ohne HAVING ist das erzeugte SQL **zeichengleich** zu v0.41.0:
`order_by`-3-Tupel werden weiter akzeptiert (`agg` defaultet auf `""`), `having=()` erzeugt keinen
Block. Bestehende 282 Tests bleiben grün; `generate_sql`-Aufrufe ohne `having` bleiben gültig.

## Edge Cases

- **HAVING ohne GROUP BY / ohne SELECT-Aggregat:** SQL behandelt die Gesamtmenge als eine Gruppe
  (`SELECT … HAVING COUNT(col) > 5`), gültig. Dokumentierte Nutzer-Verantwortung.
- **ORDER BY AGG(col) bei aktivem GROUP BY:** gültig; sortiert nach dem Aggregat. Sortieren nach
  einer nicht-gruppierten Roh-Spalte bleibt (wie in Tier-3) ein DB-seitiger Nutzerfehler.
- **Mehrere HAVING-Bedingungen:** mit `AND` verknüpft, je eigener Platzhalter.

## Teststrategie

- **`tests/test_sqlgen.py`** — ORDER BY rendert `AGG(col) DIR`; HAVING rendert
  `HAVING AGG(col) op :h0` + korrekte `params`; Klauselreihenfolge
  WHERE→GROUP BY→HAVING→ORDER BY→LIMIT (Index-Vergleich mit einem Filter, einem Aggregat, HAVING,
  ORDER BY und LIMIT in einem Statement); mehrere HAVING-Bedingungen via `AND`; Allowlist-`ValueError`
  (unbekannter HAVING-Op; leeres/unbekanntes HAVING-Aggregat); Rückwärtskompat (3-Tupel-ORDER BY,
  kein HAVING ⇒ unverändertes SQL); HAVING-Wert nie inline im parametrisierten `sql`.
- **`tests/test_sqlgen_dialect.py`** — HAVING und ORDER-BY-Aggregat mit Identifier-Quoting und
  Schema-Qualifizierung je Dialekt (mind. MSSQL-Brackets + Schema).
- **`tests/test_api.py`** — Route parst ORDER-BY-`agg` und `having`; HAVING-Tabelle wird ins
  `required_tables`-Weaving aufgenommen (Off-Path-HAVING erscheint im Join); unbekannter HAVING-Op
  → 400; read-only Run-Pfad (`/api/joinpath/run`) führt ein HAVING-Statement aus und liefert nur die
  passenden Gruppen.

## Architektur-Diagramme

Kein neues Modul und kein neuer Endpoint → Architektur-/Komponenten-Diagramme bleiben unverändert.
Release: Version-**Minor**-Bump (0.41.0 → 0.42.0), Changelog + Doc-Mirror, Roadmap/Board/Gantt
(neues AP namentlich enumeriert), „Bekannte Einschränkungen" in CLAUDE.md (HAVING erledigt; offen:
`COUNT(*)`/`COUNT(DISTINCT)`, Cross-Schema-Joins), Test-Badge, Site-Build + gh-pages-Deploy.
