# LucentTools DB Explorer — CLAUDE.md

## Project Purpose
Visual join-path builder: reflects a live database schema, builds a directed FK-graph, and generates read-only parameterised SQL from a start/target column selection plus optional filters. No data is written or mutated.

## Stack
- **Backend:** Python 3.10+, Flask (web layer), SQLAlchemy (reflection + engine), NetworkX (graph + path-finding)
- **Frontend:** Jinja2 templates, vanilla JS — all assets bundled locally under `web/assets/`
- **Config:** `config.py` — single source of truth for version, paths, port

## Layering Rule
`core/` contains pure business logic and **must never import Flask**. The web layer (`web/`) calls `core/` — never the other way around.

```
web/ (Flask routes, templates, assets)
  └── calls →
core/ (graph, pathfinder, sqlgen, loader, settings, log)
  └── uses →
config.py (constants only)
```

## Read-Only Constraint
The tool only reads schema metadata and generates SQL strings. It never executes INSERT/UPDATE/DELETE/DDL against any database. Loaders open engines with read-only intent. Generated SQL must be inspected/run externally.

## No CDN Rule
All JavaScript, CSS, and font dependencies are bundled locally under `web/assets/`. Never add `<script src="https://...">` or `<link href="https://...">` to templates.

## How to Run
```bash
bash run.sh            # creates venv if needed, installs deps, starts server
bash run.sh --version  # print current version
bash run.sh --skip-setup  # skip venv/dep check, just launch (for hub use)
bash run.sh --debug    # Flask debug mode (LUCENT_DEBUG=1); combine with --start/--skip-setup
bash run.sh --tray     # Tray-Icon-Launcher (App + Auto-Browser); Windows: run.ps1 -Action tray
```
Tray-Menü (Öffnen/Info/Beenden): Windows nativ. **Linux** braucht das AppIndicator/GTK-Backend —
`sudo apt install libgirepository1.0-dev gobject-introspection libcairo2-dev` + `pip install -r requirements-tray-linux.txt`
(sonst nur Icon ohne Menü → Xorg-Fallback). `launcher/core.py` ist stdlib-only + getestet; die GUI (`tray.py`/`about.py`) nicht headless-testbar.

Server listens at `http://127.0.0.1:5057`.
Normalbetrieb läuft auf dem waitress-WSGI-Server; `--debug` nutzt den Werkzeug-Dev-Server mit Auto-Reload.

## How to Test
```bash
./venv/bin/python -m pytest          # full suite
./venv/bin/python -m pytest -v       # verbose
```

**Optional MSSQL integration test** (`tests/test_mssql_integration.py`) runs only when
a reachable instance is provided; otherwise it skips:
```bash
LUCENT_MSSQL_TEST_URL='mssql+pyodbc://user:pw@host:1433/db?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes' \
  ./venv/bin/python -m pytest tests/test_mssql_integration.py
```

**Optional PostgreSQL integration test** (`tests/test_pg_integration.py`, AP-63·S2b) verifies sequence + materialized-view reflection — runs only with `LUCENT_PG_TEST_URL`, else skips:
```bash
LUCENT_PG_TEST_URL='postgresql+psycopg://user:pw@host:5432/db' \
  ./venv/bin/python -m pytest tests/test_pg_integration.py
```

## Logging
`core/log.py::init_logging` writes to stdout + a rotating `app.log`. Overridable per environment:
- `LUCENT_LOG_DIR` — log directory (else per-user OS path, see below)
- `LUCENT_LOG_LEVEL` — `DEBUG`/`INFO`/… (`LUCENT_DEBUG` truthy implies `DEBUG`)

Request logging (method · path · status · duration) lives in the `web/` app factory — `core/` stays Flask-free.

## Per-Nutzer-Pfade & Port (AP-31 Kern, v0.33.0)
`core/userpaths.py` (pur, stdlib-only, kein Flask/`config`-Import) löst pro Nutzer auf:
- **config.json + Logs** im OS-Nutzerverzeichnis (Slug `luDBxP`): Linux `~/.config/luDBxP/` bzw. `~/.local/state/luDBxP/logs/` (XDG), Windows `%LOCALAPPDATA%\luDBxP\`. Overrides: `LUCENT_CONFIG_DIR`, `LUCENT_LOG_DIR`. Eine alte App-Verzeichnis-`config.json` wird beim ersten Start einmalig übernommen.
- **Port pro Session:** ohne `LUCENT_PORT` erst 5057 (Hub-reserviert), sonst ein freier Port; `LUCENT_PORT=<n>` erzwingt fest, `=0` immer dynamisch. Die tatsächliche URL gibt `app.py` beim Start aus. Bind nur `127.0.0.1`. `run.sh`/`run.ps1` brechen bei belegtem Port nicht mehr ab.
- **Offen (Rest von AP-31):** Idle-Shutdown/sauberer Stop (lokaler WSGI-Server via waitress erledigt), Deployment-Packaging via AppImage.

## Bekannte Einschränkungen

- **Database backends:** PostgreSQL/MySQL support is implemented via SQLAlchemy but is only covered by automated tests against SQLite. **MS SQL Server** has an optional, skip-guarded live integration test (`tests/test_mssql_integration.py`, set `LUCENT_MSSQL_TEST_URL`) verified against SQL Server 2022. **Oracle** ist seit AP-53 verbindbar (python-oracledb Thin-Mode, Adressierung per Service-Name) — mit optionalem, skip-guardetem Live-Integrationstest (`tests/test_oracle_integration.py`, `LUCENT_ORACLE_TEST_URL`).
  Ein einzelnes, wählbares Schema ist reflektierbar (AP-52): `/api/schemas` listet die Schemas, der gewählte Name wird durch Reflection und SQL-Erzeugung (`schema.table`) gefädelt. Gleichzeitiges Multi-Schema und Cross-Schema-Joins sind noch nicht unterstützt.

> **Composite foreign keys** are fully supported since AP-11 (v0.5.0): a multi-column FK is carried as one `ForeignKey` with all `(local, ref)` column pairs and emitted as `JOIN … ON a.x = b.x AND a.y = b.y`. Two *separate* single-column FKs between the same tables stay distinct alternative join routes.

> **One-to-one detection (AP-50/51):** a descending FK whose child columns are themselves UNIQUE (constraint or PK) is treated as 1-1, not 1-N — no false fan-out warning. Uniqueness backed by a UNIQUE index (full-column, non-partial) is detected too (AP-51); only partial and expression unique indexes are deliberately ignored.

> **Table and column comments (Tier-2, v0.40.0):** Table and column comments are read during schema reflection and surfaced in the UI (detail column list + UML cards) as hover tooltips (`title`). The generated SQL is unchanged.

> **Indizes + Check-Constraints (AP-63·S1, v0.52.0):** Im Tabellen-Detail („Definition") werden alle Indizes (Name/Spalten/unique) + Check-Constraints (Name/Ausdruck) read-only via SQLAlchemy-Reflection angezeigt (`get_indexes`/`get_check_constraints`, alle Engines inkl. SQLite; Model `Index`/`CheckConstraint`). Nur Anzeige — kein DDL/Join-Pfad; Expression-/Funktions-Indizes übersprungen.

> **Trigger-Sidebar-Kategorie (AP-63·S2, v0.53.0):** Trigger werden read-only als eigene Sidebar-Kategorie reflektiert (Name/Tabelle/Quelltext) — **nur SQLite** via `sqlite_master`-Katalog-SQL (`core/loaders/sqlalchemy_loader.py::_reflect_triggers`, Model `Trigger`); andere Dialekte liefern noch `()` (PG/Oracle-Trigger = Fast-Follow). Kategorie nur bei N>0; schlankes Trigger-Detail ohne Daten-Tab; Trigger werden nie ausgeführt, keine Join-Teilnahme.

> **Sequences + Materialized-View-Kategorien (AP-63·S2b, v0.54.0):** Sequenzen (nur Name) + Materialized Views (Spalten + Definition, Matviews reusen das `View`-Model) werden read-only als je eigene Sidebar-Kategorie reflektiert (`get_sequence_names`/`get_materialized_view_names`, Model `Sequence`); echte Werte **nur PG/Oracle** (SQLite/MSSQL → leer). Display-only (kein Daten-Tab), Kategorie nur bei N>0, keine Join-Teilnahme. Optionaler Live-Test `tests/test_pg_integration.py` (`LUCENT_PG_TEST_URL`).

> **Routinen- und Synonym-Kategorien (AP-63·S3, v0.55.0):** Stored Procedures, Functions, Oracle
> Packages und Oracle Synonyme werden read-only als je eigene Sidebar-Kategorie reflektiert — via
> Pro-Dialekt-Katalog-SQL (`pg_proc` PG; `all_objects`/`all_source` Oracle; `sys.objects`/`sys.sql_modules`
> MSSQL; Synonyme `all_synonyms` Oracle-only). Model `Routine(name, kind, sql)` (kind ∈ procedure/function/package)
> + `Synonym(name, target)` + `Schema.routines`/`Schema.synonyms`; `/api/schema` liefert
> `procedures`/`functions`/`packages`/`synonyms`. Kategorie nur bei N>0, kein Daten-Tab, keine
> Join-Teilnahme. Skip-guarded Live-Tests (PG/Oracle/MSSQL); SQLite/andere → leer.

> **GROUP BY / Aggregates (Tier-3, v0.41.0):** Each SELECT column may carry an aggregate (COUNT/SUM/AVG/MIN/MAX); GROUP BY is auto-derived from the non-aggregated columns. The generated SQL gains GROUP BY and the read-only run path executes grouped queries.

> **Aggregat-Operationen — HAVING + ORDER BY auf Aggregaten (v0.42.0):** ORDER BY may sort by an aggregate (`ORDER BY COUNT(...) DESC`) and a new HAVING clause filters groups by an aggregate (scalar comparison, parametrised). Clause order: WHERE → GROUP BY → HAVING → ORDER BY → LIMIT.

> **COUNT(*) + COUNT(DISTINCT) (v0.43.0):** COUNT(*) counts rows per group (column-ignored; the entry's table is still joined) and COUNT(DISTINCT col) counts distinct values. Both work across SELECT, HAVING, and ORDER BY. Still open: Cross-Schema-Joins.

> **Implied-FK-Schärfung (AP-55, v0.47.0):** Implied-FKs werden neben dem exakten
> PK-Namen-Match auch über Suffix→Tabellenname (Groß/Klein-, Trenner-, Plural-
> normalisiert, Ziel-PK = generische ID-Form) erkannt; jeder Treffer trägt eine
> Confidence-Stufe (hoch/mittel/niedrig) und erscheint read-only im Info-Panel.
> Es werden keine FKs angelegt; Cross-Schema-Implied-Matching bleibt zurückgestellt
> (braucht Multi-Schema-Reflection, Gate wie AP-57).

> **Database-Subsetting (AP-56a, v0.48.0):** Aus Start-Tabelle + Wurzel-Filter wird die
> referenzielle FK-Hülle schema-basiert berechnet (down-then-up, zyklus-sicher,
> tiefenbegrenzt) und je Tabelle ein read-only SELECT erzeugt, das zur Wurzel zurück-joint
> (`/api/subset`, Modus „Entität exportieren"). Führt nichts aus.

> **Subset-Live-Zeilenzahlen (AP-56b·Stufe 1, v0.49.0):** Die AP-56a-Hüll-SELECTs werden
> read-only ausgeführt (`SELECT COUNT(*) FROM (<Hüll-SELECT>)`, `core/subset.py::count_sql`
> → `core/datapreview.py::count_subset_rows`, resilient pro Tabelle) und je Closure-Tabelle
> die echte Zeilenzahl + Summe geliefert (`/api/subset/run`, UI-Button „Zeilen zählen (live)").
> Nur Zählung, kein Schreiben.

> **Subset-Daten-Dump (AP-56b·Stufe 2, v0.50.0):** `/api/subset/dump` führt die AP-56a-Hüll-SELECTs
> read-only aus (`core/datapreview.py::dump_subset_rows`) und liefert die echten Zeilen je Closure-Tabelle
> als JSON-Bundle; die UI lädt es client-seitig (Browser-Blob) herunter. Per-Tabelle-Cap `MAX_RESULT_ROWS`
> mit lautem Truncation-Flag (`cap+1`-Erkennung), resilient pro Tabelle. Kein Schreiben, kein CSV/INSERT.

> **Subset-IN-Listen (AP-56c, v0.51.0):** `/api/subset/inlists` leitet je Closure-Tabelle die PK-Menge
> aus dem Stufe-2-Dump ab und rendert read-only `SELECT * FROM tab WHERE pk IN (…);` (Composite-PK als
> portable `(a=… AND b=…) OR …`-Form, `core/subset.py::subset_keys`/`subset_in_list_sql`); UI-Button
> „IN-Listen (SQL)" lädt als `.sql`. No-PK-Tabellen werden laut markiert (`incomplete`). PK-Literale
> nehmen int/str/Decimal/bool an; datetime/bytes-PKs rendern best-effort. Damit ist Wave 2 (Migration)
> abgeschlossen; Cross-Schema-Joins (AP-57) bleiben bedingt.

## Version Management
Version lives in `config.APP_VERSION`. **Never edit it by hand.** Use `sync_version.py` which updates `config.py` and `lucent-hub.yml` in lockstep:
```bash
./venv/bin/python sync_version.py --patch   # 0.1.0 → 0.1.1
./venv/bin/python sync_version.py --minor   # 0.1.0 → 0.2.0
./venv/bin/python sync_version.py --major   # 0.1.0 → 1.0.0
./venv/bin/python sync_version.py --set 1.2.3
```
