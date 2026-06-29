# AP-56c — Subset-IN-Listen (SQL-Export-Identität) — Design

**Datum:** 2026-06-29
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** S–M (reine Nachverarbeitung des Stufe-2-Dumps + ein pure-Core-Renderer; kein neues SQL gegen die DB)
**Vorgänger:** `docs/superpowers/specs/2026-06-29-ap56b-stufe2-subset-data-dump-design.md` (Stufe 2) · `…-ap56b-subset-live-count-design.md` (Stufe 1) · `…-ap56a-subset-footprint-design.md` (AP-56a) · Konzept `docs/concepts/2026-06-28-legacy-db-migration-tooling.md`

## Ziel

Aus dem Daten-Dump (AP-56b·Stufe 2) je Closure-Tabelle die **kompakte PK-Menge** als fertiges, self-contained `SELECT … WHERE pk IN (…)`-Statement materialisieren — die **referenzielle Export-Identität** zum Weiterreichen an die ETL-Schicht: „genau diese Zeilen gehören zum Subset", join-frei über konkrete Schlüssel ausgedrückt.

**Gestaffelt (Fortsetzung von AP-56a→56b):**
- **AP-56c (diese Spec):** PK-Mengen aus dem Dump ableiten und als **gerendertes SQL** (Download `.sql`) ausgeben.
- **Später (bei Bedarf):** JSON-Schlüsselmengen, dedizierte Key-only-SELECTs (eigener höherer Cap), Cross-Schema.

## Code-Befunde (Ist-Stand verifiziert)

- **`core/datapreview.py::dump_subset_rows(url, scripts, *, max_rows_per_table)`** (AP-56b·Stufe 2) liefert je Tabelle `{table, columns, rows, row_count, truncated, error}`. Aus `columns` + `rows` + `Table.primary_key` sind die PK-Tupel rein ableitbar — keine neue DB-Ausführung.
- **`core/model.py::Table.primary_key: tuple[str, ...]`** trägt die PK-Spaltennamen (auch Composite, z. B. Demo `ResourcePool` = `(ClusterID, PoolKey)`).
- **`core/sqlgen.Dialect`** (frozen) mit `quote(ident)` (Identifier, schließendes Zeichen verdoppelt) und `table_ref(table, schema)` — wie in `generate_subset_sql` genutzt.
- **`generate_subset_sql`** rendert `SELECT [DISTINCT] t0.* …` — Vorlage für Struktur/Quoting; AP-56c rendert stattdessen aus konkreten Schlüsseln.
- **`/api/subset/dump`** (Stufe 2, `web/routes.py`) ist die Endpoint-Vorlage: gleiche Validierung, Run-Dialekt aus URL, `incomplete`-Semantik. `/api/subset/inlists` spiegelt sie.
- **UI-Panel „Entität exportieren"** (`web/static/js/app.js`): `runSubset`/`runSubsetCount`/`runSubsetDump` + `SUB_LAST_PAYLOAD` + `_sanitizeFilePart`. Wird erweitert.

## 1. Core: SQL-Renderer (`core/subset.py`, pur)

```python
def subset_in_list_sql(table, pk_columns, columns, rows, *, dialect=SQLITE, schema_name="") -> str | None:
    """Render a self-contained read-only SELECT that reproduces exactly the
    subset rows of ``table`` by their concrete primary keys. Returns None when
    the table has no primary key or no rows. Executes nothing."""
```

- **Voraussetzungen:** `pk_columns` leer → `None`. `rows` leer → `None`. Eine PK-Spalte nicht in `columns` → `None` (defensiv; Dump projiziert `t0.*`, sollte nie eintreten).
- **Schlüssel-Extraktion:** je Zeile das Tupel `(row[idx] for pk col)` über die `columns`-Indizes; **ordnungserhaltend dedupliziert**.
- **Rendering:**
  - Single-PK: `SELECT * FROM <schema.>tab WHERE <pk> IN (l1, l2, …);`
  - Composite-PK: `SELECT * FROM <schema.>tab WHERE (<c1> = l11 AND <c2> = l12) OR (<c1> = l21 AND …);` — bewusst **OR-Form** (portabel über SQLite/PG/MySQL/MSSQL/Oracle), kein Row-Value-`(a,b) IN ((…))`.
  - Bei `None`-Wert in einem Schlüsselteil: `<c> IS NULL` statt `<c> = NULL`.
  - Identifier (`tab`, PK-Spalten) via `dialect.quote` / `dialect.table_ref`.
- **SQL-Literal-Helper** `_sql_literal(v, dialect) -> str` (pur):
  - `bool` → `"1"`/`"0"` (PKs praktisch nie boolesch; portabler als TRUE/FALSE).
  - `int`/`float` (und Decimal via `numbers.Number`) → `str(v)`.
  - `None` → `"NULL"` (der Aufrufer nutzt für Composite-Gleichheit `IS NULL`).
  - alles andere (`str` etc.) → `'` + `str(v)` mit verdoppeltem `'` + `'`.
- **Read-only:** reine String-Erzeugung, kein Flask, keine Ausführung.

## 2. Route `/api/subset/inlists` (POST, read-only)

- **Gleicher Payload** wie `/api/subset/dump`.
- Server: Schema laden → `compute_subset` → `generate_subset_sql(..., dialect=_dialect_from_url(url), schema_name=schema)` → `dump_subset_rows(url, scripts, max_rows_per_table=config.MAX_RESULT_ROWS)` → je `result.tables`-Eintrag `subset_in_list_sql(name, schema-PK, dump.columns, dump.rows, dialect=run_dialect, schema_name)`.
  - PK-Spalten aus dem geladenen Schema (`Table.primary_key`) per Tabellenname.
- Validierung identisch zu `/api/subset/dump`: leere URL → 400 (`_NO_URL_MSG`); `ConnectionError` beim Laden → 400; unbekannte Start-Tabelle/Spalte → 400; `ValueError` → 400.
- **Antwort:**
  ```json
  {
    "start": "...", "truncated": false, "incomplete": false, "row_cap": 5000,
    "tables": [
      {"name":"...", "kind":"root|child|parent", "via_table":"...|null", "depth":0,
       "pk_columns":["..."], "has_pk":true, "key_count":3,
       "sql":"SELECT * FROM ... WHERE ...;", "truncated":false, "error":null}
    ]
  }
  ```
  - `has_pk = bool(pk_columns)`. `sql` = der Renderer-String (oder `""` bei `None`). `key_count` = Anzahl deduplizierter Schlüssel (0 bei No-PK/keine Zeilen).
  - Fehlt eine Closure-Tabelle im Dump-Map → Fallback `{"error":"not dumped", …}` (erzwingt `incomplete`).
  - **`incomplete` = `result.truncated` OR irgendeine Tabelle `truncated` OR irgendein `error` OR irgendeine Tabelle `has_pk=false`** (ohne PK keine ausdrückbare Identität).

## 3. UI — Panel „Entität exportieren" erweitern (`web/static/js/app.js`)

- Neuer Button **„IN-Listen (SQL)"** im Ergebnisbereich neben „Daten-Dump (JSON)", aktiv sobald ein Footprint vorliegt.
- Klick → `POST /api/subset/inlists` mit `SUB_LAST_PAYLOAD` (Null-Guard „Erst Footprint bauen." wie bei `runSubsetCount`/`runSubsetDump`).
- Erfolg → die Tabellen zu **einem `.sql`-Text** zusammensetzen, je Tabelle:
  - Kopf-Kommentar `-- <name> (<key_count> Schlüssel)`; bei `has_pk=false`: `-- <name>: kein PK, keine IN-Liste`; bei `error`: `-- <name>: Fehler — <error>`; bei `truncated`: zusätzlich `-- <name>: abgeschnitten bei <row_cap> — Identität unvollständig`.
  - dann die `sql`-Zeile (falls vorhanden).
  - Reihenfolge = Bundle-Reihenfolge (topologische Closure-Ordnung).
- Download als **Blob** (`text/plain`/`application/sql`) → Datei `subset_<start>_<filter>_inlists.sql` (Werte via bestehendes `_sanitizeFilePart`).
- **Laute Unvollständigkeits-Warnung** im Status (`#sub_total`), wenn `incomplete`: „IN-Listen unvollständig — kein PK / abgeschnitten / Fehler bei: <Tabellen>". Sonst „IN-Listen: <n> Tabellen mit PK, <Summe key_count> Schlüssel".
- Read-only-Charakter: kein Schreiben; Panel-Hinweis nennt jetzt vier Aktionen (Footprint / Zählen / Dump / IN-Listen).

## 4. Tests

**`tests/test_subset.py` (Renderer, pur, ohne DB):**
- Single-PK: `subset_in_list_sql("T", ("id",), ["id","x"], [[1,"a"],[2,"b"]])` → `… WHERE "id" IN (1, 2);` (Dialekt-abhängiges Quoting beachten; Test gegen `SQLITE`).
- Composite-PK: `("ClusterID","PoolKey")`, rows `[[1,"P1"],[2,"P2"]]` → `… WHERE ("ClusterID" = 1 AND "PoolKey" = 'P1') OR ("ClusterID" = 2 AND "PoolKey" = 'P2');`.
- String-Escaping: Wert `O'Brien` → `'O''Brien'`.
- `None` in Single-PK → Literal `NULL` in der `IN`-Liste? Nein — Composite nutzt `IS NULL`; für Single-PK mit `None` ist der Schlüssel `NULL` (PKs sind NOT NULL, Edge): Test belegt das dokumentierte Verhalten (`IN (NULL)`), kein Crash.
- Dedup: doppelte Schlüssel erscheinen einmal, ordnungserhaltend.
- Kein PK (`pk_columns=()`) → `None`; keine Zeilen (`rows=[]`) → `None`.
- Schema-Qualifizierung: `schema_name="dbo"` → `FROM "dbo"."T"`.

**Route-Test** (`tests/test_api.py`, gegen `demo_url`):
- `Datacenter`/`DatacenterID=1` → `Datacenter`-Eintrag `has_pk=true`, `sql` enthält `WHERE "DatacenterID" IN (1)`, `key_count==1`.
- `ResourcePool` ist Composite-PK → sein `sql` enthält die `(… AND …) OR`-Form (für eine Start-Wahl, deren Hülle `ResourcePool` enthält, z. B. Start `ResourcePool` oder `Cluster`).
- Deterministischer Anker `DatacenterID=3` (DC-Empty) → Root `key_count==1`, Kinder `key_count==0`/`has_pk` je Tabelle.
- unbekannte Start-Tabelle → 400; leere URL → 400.

**Browser-Smoke** (Playwright, System-python3): Demo verbinden → „Entität exportieren" → Start `Datacenter`, Filter `DatacenterID = 1` → „Footprint bauen" → „IN-Listen (SQL)" → Download abfangen, `.sql` enthält `WHERE "DatacenterID" IN`. **App-Neustart** vor Smoke.

## 5. Scope-Cuts (bewusst)

- **Nur gerendertes SQL** (`.sql`) — kein JSON-Key-Set (Folge-AP bei Bedarf).
- **Aus dem Dump abgeleitet** → erbt Per-Tabelle-Cap (`MAX_RESULT_ROWS`) + Truncation-Flag (unvollständige Identität wird laut markiert); keine dedizierten Key-only-SELECTs mit eigenem Cap.
- **Composite-PK als OR-Form** (portabel) — kein Row-Value-`IN`.
- Kein Cross-Schema; `bool`-PKs als 1/0.
- **PK-Literale nehmen int/str/Decimal/bool an;** `datetime`/`date`/`bytes`-PKs rendern best-effort (datetime als gequoteter ISO-String, bytes als Python-Repr) — selten (PKs sind meist int/str/UUID/Decimal); typgerechtes Date/Hex-Rendering wäre ein Folge-AP.
- Kein `DELETE`/`INSERT`/DDL — reine `SELECT`-Identität (ETL-Schicht baut das Weitere).

## 6. Release / Doku (nach Implementierung)

- `sync_version.py --minor` (Feature) + icon-rail `APP_VERSION`/`TEST_COUNT`.
- Roadmap/Board/Gantt: AP-56c → erledigt; Wave-2-Migration (AP-54/55/56a/56b/56c) als abgeschlossen führen, AP-57 bleibt bedingt. Übersicht nach Build gegenprüfen.
- CLAUDE.md „Bekannte Einschränkungen": Subset-Block um die IN-Listen ergänzen; Kennzahlen-Seite (hartkodiert) mitziehen.
- Changelog EN + DE-Mirror, zensical, Site-Build, gh-pages.
- Deutsch / NO-CDN / SDD-Final-Review nicht weglassen.
