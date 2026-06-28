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

## Version Management
Version lives in `config.APP_VERSION`. **Never edit it by hand.** Use `sync_version.py` which updates `config.py` and `lucent-hub.yml` in lockstep:
```bash
./venv/bin/python sync_version.py --patch   # 0.1.0 → 0.1.1
./venv/bin/python sync_version.py --minor   # 0.1.0 → 0.2.0
./venv/bin/python sync_version.py --major   # 0.1.0 → 1.0.0
./venv/bin/python sync_version.py --set 1.2.3
```
