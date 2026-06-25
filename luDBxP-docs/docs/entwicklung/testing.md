# Testing

## Übersicht

| Metrik | Wert (Stand v0.1.0) |
|---|---|
| Gesamt-Tests | **81** |
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

## Playwright-Verifikation

Ergänzend zur pytest-Suite wurde die UI manuell über Playwright-Snapshots
verifiziert (3-Panel-Layout, Graph-Rendering, Join-Builder-Flow,
Filter-Hinzufügen, Datenvorschau-Tab).

## Test-Fixtures (`conftest.py`)

- `test_schema` — minimales In-Memory-Schema (orders → customers, mit FKs)
- `app_client` — Flask-Testclient mit der App im Test-Modus
- `demo_db_path` — Pfad zur eingecheckten `demo_cmdb.db`

## Demo-CMDB — Test-Abdeckung

Die Demo-CMDB (`sample_data/build_demo_db.py`) ist gezielt auf Edge-Cases ausgelegt:

```
Diamant-Pfad:     A → B → D  und  A → C → D  (2 alternative Routen)
Zusammenges. FK:  (col1, col2) → ref_table(pk1, pk2)  — in v1 nur col1 genutzt
Selbstreferenz:   node.parent_id → node.id
Mehrfach-FK:      tabelle hat 2 FKs auf dieselbe Zieltabelle
Isolierte Tabelle: keine FKs (taucht im Graph als isolierter Knoten auf)
```
