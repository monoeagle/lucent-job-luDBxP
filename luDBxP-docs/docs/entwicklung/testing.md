# Testing

## Übersicht

| Metrik | Wert (Stand v0.34.1) |
|---|---|
| Gesamt-Tests | **232** (+ 1 skipped: optionaler MSSQL-Live-Test) |
| Framework | pytest |
| Laufzeit | < 10 s |
| Abdeckung | Unit + Integrationstests |

## Tests ausführen

```bash
bash run.sh --tests
# oder direkt:
./venv/bin/python -m pytest
# mit Details:
./venv/bin/python -m pytest -v
```

## Test-Dateien

| Datei | Inhalt |
|---|---|
| `test_api.py` | HTTP-Endpoints (Flask-Testclient): schema, joinpath, graph, data, connect, connections |
| `test_smoke.py` | App-Start, Index-Route, `/api/info` |
| `test_graph.py` | `build_graph()` — Knoten, Kanten, implied-Flag |
| `test_pathfinder.py` | `find_paths()` — direkte Pfade, mehrstufige Pfade, kein Pfad, k-Pfade |
| `test_sqlgen.py` | `generate_sql()` — SELECT, JOIN, WHERE, Platzhalter |
| `test_implied.py` | `guess_implicit_fks()` — Name-Matching, Typ-Kompatibilität |
| `test_demo_db_cases.py` | Integrationstests gegen `demo_cmdb.db`: Diamant-Pfade, zusammengesetzte FKs, Selbstreferenz, isolierte Tabelle |
| `test_sqlalchemy_loader.py` | `SqlAlchemyLoader` — Tabellen, Views, FKs, Primärschlüssel |
| `test_datapreview.py` | `fetch_rows()` — Rückgabeformat, Validierung Objektname |
| `test_ddl.py` | `table_ddl()` — DDL-Rekonstruktion |
| `test_connection.py` | `build_url()` — alle vier DB-Typen, Fehlerfall |
| `test_model.py` | `Schema.has_column()` |
| `test_index_page.py` | Startseite lädt, enthält erwartete HTML-Strukturen |
| `test_sync_version.py` | `sync_version.py` — Versions-Bump-Logik |
| `test_loader_interface.py` | Abstrakte Loader-Schnittstelle |
| `test_log.py` | `init_logging()` — Rotation, Level/Pfad via ENV, Request-Logging (AP-33) |
| `test_sqlanalyze.py` | `analyze()` — read-only SQL-Analyzer: Typ/Tabellen/Spalten, Lints, Komplexität (AP-25) |
| `test_sqlgen_dialect.py` | dialekt-spezifisches SQL-Rendering (SQLite/PostgreSQL/MySQL/MSSQL/Oracle, AP-29) |
| `test_userpaths.py` | Pro-Nutzer-Pfade, `pick_port`/`resolve_port`, Migration (AP-31) |
| `test_launcher.py` | Tray-Launcher-Kern: Port-Handoff, Readiness, sauberes Beenden, Info-Dialog/Primärmonitor (AP-34) |

## Playwright-Verifikation

Ergänzend zur pytest-Suite wurde die UI manuell über Playwright-Snapshots
verifiziert (3-Panel-Layout, Graph-Rendering, Join-Builder-Flow,
Filter-Hinzufügen, Datenvorschau-Tab).

## Test-Fixtures (`conftest.py`)

- `inventory_url` — datei-basierte SQLite-URL aus dem Inventory-Schema (Reflection sieht FKs)
- `inventory_nofk_url` — gleiche Form ohne deklarierte FKs (für Implied-FK-Tests)
- `sqlite_engine` — SQLAlchemy-Engine auf `inventory_url`

(Der Flask-Testclient `client` und die `demo_url`-Fixture werden lokal in den
jeweiligen Testdateien definiert, z. B. `test_api.py`.)

## Demo-CMDB — Test-Abdeckung

Die Demo-CMDB (`sample_data/build_demo_db.py`) ist gezielt auf Edge-Cases ausgelegt:

```
Diamant-Pfad:     A → B → D  und  A → C → D  (2 alternative Routen)
Zusammenges. FK:  (col1, col2) → ref_table(pk1, pk2)  — seit AP-11 voll: ON a.x=b.x AND a.y=b.y
Selbstreferenz:   node.parent_id → node.id
Mehrfach-FK:      tabelle hat 2 FKs auf dieselbe Zieltabelle
Isolierte Tabelle: keine FKs (taucht im Graph als isolierter Knoten auf)
```
