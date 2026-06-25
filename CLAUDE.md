# Lucent DB Explorer — CLAUDE.md

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
```
Server listens at `http://127.0.0.1:5057`.

## How to Test
```bash
./venv/bin/python -m pytest          # full suite
./venv/bin/python -m pytest -v       # verbose
```

## Bekannte Einschränkungen (v1)

- **Composite foreign keys:** Schemas with multi-column FKs are joined on only the first column pair in v1; single-column FKs are fully supported.
- **Database backends:** Postgres support is implemented via SQLAlchemy but is only covered by automated tests against SQLite in v1.

## Version Management
Version lives in `config.APP_VERSION`. **Never edit it by hand.** Use `sync_version.py` which updates `config.py` and `lucent-hub.yml` in lockstep:
```bash
./venv/bin/python sync_version.py --patch   # 0.1.0 → 0.1.1
./venv/bin/python sync_version.py --minor   # 0.1.0 → 0.2.0
./venv/bin/python sync_version.py --major   # 0.1.0 → 1.0.0
./venv/bin/python sync_version.py --set 1.2.3
```
