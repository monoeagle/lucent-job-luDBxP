# AP-56b·Stufe 1 — Subset-Live-Walk (echte Zeilenzahlen) — Design

**Datum:** 2026-06-29
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** S–M (erste, ehrliche Scheibe von AP-56b; Daten-Dump/IN-Listen = AP-56b·Stufe 2)
**Vorgänger:** `docs/superpowers/specs/2026-06-28-ap56a-subset-footprint-design.md` · Konzept `docs/concepts/2026-06-28-legacy-db-migration-tooling.md` (Abschnitt AP-56)

## Ziel

AP-56a berechnet die referenzielle FK-Hülle einer Start-Zeile **schema-basiert** und rendert je Closure-Tabelle ein read-only SELECT, das zur Wurzel zurück-joint — **führt aber nichts aus**. AP-56b macht aus dem Bauplan einen **datengetriebenen Live-Walk** gegen die echte DB.

**Gestaffelt (wie AP-54→56a):**
- **AP-56b·Stufe 1 (diese Spec):** die AP-56a-Hüll-SELECTs **read-only ausführen** und je Tabelle die **echte Zeilenzahl** + Summe liefern. Beantwortet „Wie groß ist mein Export?" / „Ist die Hülle plausibel?". Reuse von `generate_subset_sql` + `execute_select`.
- **AP-56b·Stufe 2 (später):** konkrete Schlüssel materialisieren (IN-Listen als Export-Identität) + Roh-Daten-Dump (CSV/JSON).

## Code-Befunde (Ist-Stand verifiziert)

- **`core/subset.py`** liefert bereits `SubsetResult` (topologisch sortierte Closure) und `generate_subset_sql(...) -> tuple[SubsetScript, ...]` mit `SubsetScript(table, sql, params)`. Jedes `sql` ist `SELECT [DISTINCT] t0.* FROM … WHERE tN.<col> <op> :root;` — bei Lookup-Tabellen mit `DISTINCT`, sodass COUNT genau die Export-Zeilenmenge zählt.
- **Read-only Ausführung existiert:** `core/datapreview.py::execute_select(url, sql, params, max_rows)` (parametrisiert, harter Row-Cap, `engine.dispose()` im finally). `core/datapreview.py` importiert SQLAlchemy, **kein Flask** → Execution-Helfer dürfen hier liegen (Layering ok).
- **Run-Dialekt vs. Anzeige-Dialekt:** `/api/joinpath/run` (`web/routes.py:558`) führt bewusst mit `_dialect_from_url(url)` aus, nicht mit der Client-Anzeigewahl — damit das gequotete SQL real läuft. AP-56b/`/api/subset/run` übernimmt dieses Muster.
- **`/api/subset`** (`web/routes.py:463`) bleibt unverändert (generiert nur SQL).
- **UI-Panel „Entität exportieren"** existiert (`web/static/js/app.js::openSubset/runSubset`, ~Z. 523–577): Footprint-Tabelle + SQL-Skelette. Wird erweitert, nicht ersetzt.

## 1. Core: COUNT-Wrapper (`core/subset.py`, pur)

Reine String-Funktion, kein Flask, keine Ausführung — unit-testbar:
```python
def count_sql(inner_sql: str) -> str:
    """Wickelt ein Hüll-SELECT in eine Zähl-Query. Strippt das abschließende ';'."""
    # SELECT COUNT(*) FROM (<inner>) subset_cnt
```
- Abschließendes `;` (und Whitespace) wird entfernt, bevor die Subquery eingebettet wird.
- **Alias ohne `AS`** (`… ) subset_cnt`) → portabel über SQLite/PostgreSQL/MySQL/MSSQL/**Oracle** (Oracle verbietet `AS` für Tabellen-Aliasse; PG/MySQL/MSSQL verlangen einen Alias für die abgeleitete Tabelle — die Form ohne `AS` erfüllt beides).
- Die `params` der `SubsetScript` bleiben unverändert (dieselben `:root`-Binds gelten in der Subquery).
- `DISTINCT t0.*` der Lookup-SELECTs bleibt in der Subquery erhalten → `COUNT(*)` zählt die distinkten Export-Zeilen.

## 2. Execution-Aggregator (`core/datapreview.py`)

```python
def count_subset_rows(connection_url, scripts, *, per_query_max_rows=1) -> list[dict]:
    """Führt je SubsetScript die COUNT-Query read-only aus. Resilient pro Tabelle."""
    # für jedes script:
    #   try: res = execute_select(url, count_sql(script.sql), script.params, max_rows=1)
    #        count = res["rows"][0][0]
    #   except ConnectionError as exc: count=None, error=str(exc)
    # -> [{"table": ..., "count": int|None, "error": str|None}, ...]
```
- **Resilient pro Tabelle:** ein `ConnectionError` (Permission, kaputter Typ, fehlendes Objekt) wird je Tabelle gefangen → `count=None, error=<msg>`; die übrigen Tabellen werden weiter gezählt.
- Reihenfolge = Reihenfolge der `scripts` (= topologische Closure-Ordnung aus AP-56a).
- Reuse von `execute_select` (eine Zeile, `max_rows=1`); kein neuer Engine-/Connection-Code.

## 3. Route `/api/subset/run` (POST, read-only Ausführung)

- **Gleicher Payload** wie `/api/subset`: `{connection_url, schema, start_table, root_filter:{column,op,value}, include_implied, max_depth?, dialect?}`.
- Server: Schema laden → `compute_subset(...)` → `generate_subset_sql(..., dialect=_dialect_from_url(url), schema_name=schema)` → `count_subset_rows(url, scripts)`.
  - **Run-Dialekt aus der URL** (nicht Anzeige-Dialekt), wie `/api/joinpath/run`.
- Validierung wie `/api/subset`: leere URL → 400 (`_NO_URL_MSG`); unbekannte Start-Tabelle/Spalte → 400; `compute_subset`/`generate_subset_sql`-`ValueError` → 400; `ConnectionError` beim Schema-Laden → 400.
- **Antwort:**
  ```json
  {
    "start": "...",
    "truncated": false,
    "incomplete": false,
    "total": 1234,
    "tables": [
      {"name":"...", "kind":"root|child|parent", "via_table":"...|null",
       "depth":0, "count":123, "error":null}
    ]
  }
  ```
  - `total` = Summe der erfolgreichen `count`s (Tabellen mit `error` zählen nicht mit).
  - `incomplete = truncated OR any(t.error)` → die Summe ist evtl. unvollständig.

## 4. UI — Panel „Entität exportieren" erweitern (`web/static/js/app.js`)

- Nach „Footprint bauen" (bestehend) ein **zweiter Button „Zeilen zählen (live)"** im Ergebnisbereich, aktiv sobald ein Footprint vorliegt.
- Klick → `POST /api/subset/run` mit demselben Payload wie `runSubset()`.
- Ergebnis: füllt eine **Spalte „Zeilen"** in der bestehenden Hüll-Tabelle (`count` bzw. bei `error` die Zelle „Fehler" mit `title=`Meldung), plus **Fußzeile „Summe: N"** — bei `incomplete` ergänzt um „· unvollständig (Tiefenlimit/Fehler)".
- **Hinweis-Text** des Panels ergänzen: Footprint-Bau führt nichts aus; „Zeilen zählen" führt **read-only `COUNT`-Queries** gegen die DB aus.
- Read-only-Charakter bleibt: keine Schreiboperation, kein Daten-Dump in dieser Stufe.

## 5. Tests

**`tests/test_subset.py`** (Core, ohne DB):
- `count_sql`: wickelt korrekt (`SELECT COUNT(*) FROM (…) subset_cnt`), strippt abschließendes `;`, Alias ohne `AS`, lässt Innen-SQL inkl. `DISTINCT` intakt.

**`tests/test_subset.py` / Integration gegen Demo-CMDB (SQLite):**
- `count_subset_rows` gegen die Demo-DB: Counts je Tabelle = handgeprüfte Erwartung aus den gesäten Zeilen; `total` korrekt; topologische Reihenfolge erhalten.
- **Resilienz-Pfad:** ein `SubsetScript` mit ungültiger Referenz (nicht existente Spalte/Tabelle) → `execute_select` wirft `ConnectionError` → als `error` erfasst, `count=None`, übrige Counts intakt, `incomplete` reflektiert.

**Route-Test** (`tests/test_api.py`): `POST /api/subset/run` gegen `inventory_url` (Demo) liefert `tables` mit `count` + `total`; unbekannte Start-Tabelle → 400; leere URL → 400.

**Browser-Smoke** (Playwright, System-python3): Demo verbinden → „Entität exportieren" → Footprint bauen → „Zeilen zählen (live)" → „Zeilen"-Spalte + „Summe"-Fußzeile gerendert. **App-Neustart** vor Smoke (Route/Template/Python-Änderung).

## 6. Scope-Cuts (bewusst, → AP-56b·Stufe 2)

- **Keine** materialisierten Schlüssel / IN-Listen, **kein** Roh-Daten-Dump (CSV/JSON).
- **Kein** per-Statement-Timeout (portabel treiberspezifisch; read-only COUNT, Tabellenzahl durch `max_depth` begrenzt) — bewusst zurückgestellt.
- Einzel-Wurzel-Prädikat (kein Multi-Filter) — wie AP-56a.
- Keine Anonymisierung / kein Insert-/DDL-Skript (ETL-Schicht).

## 7. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`.
- Roadmap/Board/Gantt: AP-56b → AP-56b·Stufe 1 (erledigt) + Stufe 2 (offen) aufsplitten, jedes Item namentlich.
- CLAUDE.md „Bekannte Einschränkungen": Subset-Block um den Live-Count ergänzen; Kennzahlen-Seite (hartkodiert) mitziehen.
- Changelog EN + DE-Mirror, zensical, Site-Build, gh-pages.
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen.
