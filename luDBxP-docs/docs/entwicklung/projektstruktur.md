# Projektstruktur

```
lucent-job-luDBxP/
│
├── app.py                    # Flask-App-Factory (create_app)
├── config.py                 # Konstanten: APP_NAME, APP_VERSION, Pfade, Ports
├── config.json               # Laufzeit-Einstellungen (default_connection, gespeicherte Verbindungen)
├── run.sh                    # Interaktives Menü + direkte Flags (Linux/macOS)
├── run.ps1                   # Gleiches Menü für Windows PowerShell
├── strings.py                # Benutzer-seitige Texte / Fehlermeldungen
├── sync_version.py           # Versions-Bump: config.py + alle Stellen synchron
│
├── core/                     # Reine Business-Logik (kein Flask-Import)
│   ├── model.py              # Schema, Table, Column, ForeignKey, View
│   ├── schema_loader.py      # Abstrakte Loader-Schnittstelle
│   ├── graph.py              # build_graph() → NetworkX DiGraph
│   ├── pathfinder.py         # find_paths() — k-kürzeste Pfade
│   ├── sqlgen.py             # generate_sql() — parametrisiertes SELECT+JOIN
│   ├── implied.py            # guess_implicit_fks() — Heuristik
│   ├── connection.py         # build_url() — SQLAlchemy-URL-Konstruktor
│   ├── datapreview.py        # fetch_rows() — erste N Zeilen
│   ├── ddl.py                # table_ddl() — rekonstruiertes CREATE TABLE
│   ├── settings.py           # Settings.load/save (config.json)
│   ├── log.py                # Logging-Setup
│   ├── sqlanalyze.py         # analyze() — read-only SQL-Analyzer (AP-25, sqlglot)
│   ├── userpaths.py          # Pro-Nutzer-Pfade + dynamischer Port + Migration (AP-31)
│   └── loaders/
│       ├── sqlalchemy_loader.py   # Haupt-Loader (SQLAlchemy inspect)
│       ├── manual_loader.py       # Manuell definiertes Schema (Tests)
│       ├── ddl_loader.py          # Schema aus DDL-Text parsen
│       └── schemaspy_loader.py    # Schema aus SchemaSpy-Output (experimentell)
│
├── web/                      # Flask-Schicht
│   ├── routes.py             # Blueprint: alle /api/*-Endpoints + index-Route
│   └── __init__.py
│
├── launcher/                 # Tray-Icon-Launcher (AP-34, pystray/Pillow)
│   ├── core.py               # LauncherCore: Port + app.py-Prozess + Auto-Browser + sauberes Beenden
│   ├── tray.py               # pystray-Icon + Menü (Im Browser öffnen / Info / Beenden)
│   ├── about.py              # Info-Dialog (Tkinter, eigener Prozess, primär-Monitor-zentriert)
│   └── __main__.py           # Einstieg: python -m launcher (Windows fensterlos via pythonw)
│
├── tests/                    # pytest-Tests (232 gesamt)
│   ├── conftest.py           # Fixtures (Test-Schema, Flask-Client)
│   ├── test_api.py           # HTTP-API-Tests (via Flask-Testclient)
│   ├── test_smoke.py         # Smoke-Tests
│   ├── test_graph.py         # FK-Graph-Aufbau
│   ├── test_pathfinder.py    # Pfadfindung
│   ├── test_sqlgen.py        # SQL-Generierung
│   ├── test_implied.py       # Implizite-FK-Heuristik
│   ├── test_demo_db_cases.py # Integrationstests gegen Demo-CMDB
│   └── ...                   # weitere Unit-Tests
│
├── sample_data/
│   ├── demo_cmdb.db          # Mitgelieferte Demo-CMDB (SQLite, eingecheckt)
│   ├── demo_cmdb_nofk.db     # Demo-CMDB ohne FK-Constraints (für implizite FKs)
│   └── build_demo_db.py      # Generator für beide Demo-DBs
│
├── web/static/
│   ├── js/app.js             # Frontend-Logik (3-Panel-UI, Graph, SQL-Builder)
│   ├── css/style.css         # App-Styles
│   └── lib/
│       └── cytoscape.min.js  # Cytoscape.js 3.30.2 (lokal gebundelt)
│
├── luDBxP-docs/              # Dokumentation (Zensical/MkDocs)
│   ├── zensical.toml
│   ├── build_docs.py
│   ├── run_luDBxP_docs.sh
│   ├── docs/
│   └── tools/
│
└── lucent-hub.yml            # Hub-Registrierung (Port 5057, Docs 8046)
```
