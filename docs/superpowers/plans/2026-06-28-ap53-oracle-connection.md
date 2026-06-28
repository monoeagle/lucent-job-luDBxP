# AP-53 — Verbindung gegen Oracle-DB: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Oracle als Verbindungs-Backend ergänzen (live verbinden + reflektieren) — Treiber `oracledb` Thin-Mode, Adressierung per Service-Name.

**Architecture:** `core/connection.build_url` bekommt einen Oracle-Zweig (`oracle+oracledb://…/?service_name=…`); der Loader filtert Oracle-System-Schemas; Routes/Frontend bekommen ein `service_name`-Feld. SQL-Generierung (ORACLE-Dialekt) existiert bereits und bleibt unverändert.

**Tech Stack:** Python 3.14 (venv), SQLAlchemy + python-oracledb (thin), Flask, vanilla JS, pytest.

## Global Constraints

- **Layering:** `core/` darf NIE Flask importieren. URL-Bau bleibt in `core/connection.py`.
- **Read-Only:** keine Schreiboperationen; nur Reflektion + read-only-SELECT.
- **Treiber:** `python-oracledb` **Thin-Mode** (kein Oracle Instant Client), SQLAlchemy-Prefix `oracle+oracledb`.
- **Adressierung:** nur **Service-Name** (kein SID/TNS/Easy-Connect).
- **Passwort:** wird NIE persistiert (`_CONN_FIELDS` enthält kein `password`).
- **NO-CDN/Offline:** Treiber als Wheel ins `wheels/`-Wheelhouse fürs Windows-Ziel (cp314/win_amd64), Linux-Online-Fallback wie bei psycopg2/pyodbc.
- **Version:** nur via `sync_version.py`; Feature=minor → v0.39.0.
- **Sprache:** Code-Kommentare englisch; CHANGELOG-Root englisch, Mirror deutsch; UI-Texte deutsch.
- **Tests:** Baseline 257 passed, 1 skipped muss grün bleiben.

---

### Task 1: Dependency + `build_url`-Oracle-Zweig (+ Unit-Tests)

**Files:**
- Modify: `requirements.txt`
- Create: `wheels/oracledb-*.whl` (Windows-Wheel; siehe Step)
- Modify: `core/connection.py`
- Test: `tests/test_connection.py`

**Interfaces:**
- Produces: `build_url({db_type:"oracle", host, port?, service_name, user?, password?})` → `oracle+oracledb://[user:pw@]host:port/?service_name=<service>` (Port-Default 1521).

- [ ] **Step 1: oracledb zu requirements.txt**

In `requirements.txt` nach der `pyodbc`-Zeile ergänzen:

```
oracledb>=2.0          # Oracle driver (python-oracledb, thin mode — no Instant Client)
```

- [ ] **Step 2: Treiber in das venv + Wheelhouse**

Lokal (Linux, online-Fallback wie die anderen Treiber) ins venv installieren:
```bash
./venv/bin/pip install "oracledb>=2.0"
./venv/bin/python -c "import oracledb; print('oracledb', oracledb.__version__)"
```
Windows-Offline-Wheel ins Wheelhouse laden (cp314/win_amd64):
```bash
./venv/bin/pip download oracledb --only-binary=:all: --no-deps -d wheels/ \
  --platform win_amd64 --python-version 314 --implementation cp --abi cp314
ls wheels/oracledb-*win_amd64*.whl
```
Expected: ein `oracledb-*-cp314-*win_amd64.whl` in `wheels/`. **Falls oracledb (noch) kein cp314/win_amd64-Wheel anbietet:** den Befehl mit `--abi none` / passender ABI erneut versuchen; bleibt es erfolglos, im Fix-/Task-Bericht als bekannte Wheelhouse-Lücke vermerken (Windows würde oracledb dann online nachladen) — **nicht blockieren**.

- [ ] **Step 3: Failing tests schreiben**

In `tests/test_connection.py` ans Dateiende anhängen:

```python
def test_oracle_url_with_service_name():
    url = build_url({
        "db_type": "oracle", "host": "h", "service_name": "XEPDB1",
        "user": "u", "password": "p"})
    assert url == "oracle+oracledb://u:p@h:1521/?service_name=XEPDB1"


def test_oracle_custom_port():
    url = build_url({
        "db_type": "oracle", "host": "h", "port": 1599,
        "service_name": "ORCLPDB1", "user": "u", "password": "p"})
    assert url == "oracle+oracledb://u:p@h:1599/?service_name=ORCLPDB1"


def test_oracle_missing_service_name_raises():
    with pytest.raises(ValueError):
        build_url({"db_type": "oracle", "host": "h", "user": "u", "password": "p"})
```

- [ ] **Step 4: Tests laufen lassen — müssen fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_connection.py::test_oracle_url_with_service_name -v`
Expected: FAIL — `ValueError: Unbekannter Datenbank-Typ: oracle` (oracle noch nicht in `_DRIVERS`).

- [ ] **Step 5: `connection.py` erweitern**

In `core/connection.py` die Maps ergänzen:

```python
_DRIVERS = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
    "oracle": "oracle+oracledb",
}

_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306, "mssql": 1433, "oracle": 1521}
```

Den Server-Teil von `build_url` (ab `host = (params.get("host") …`) durch diese
umstrukturierte Fassung ersetzen (Oracle-Zweig vor der `database`-Pflicht):

```python
    host = (params.get("host") or "").strip()
    if not host:
        raise ValueError("Host fehlt.")
    port = params.get("port") or _DEFAULT_PORTS[db_type]

    user = quote_plus(params.get("user") or "")
    password = quote_plus(params.get("password") or "")
    auth = f"{user}:{password}@" if user else ""

    if db_type == "oracle":
        # Oracle is addressed by service name, not a database path.
        service = (params.get("service_name") or "").strip()
        if not service:
            raise ValueError("Service-Name fehlt.")
        return (f"{_DRIVERS['oracle']}://{auth}{host}:{port}"
                f"/?service_name={quote_plus(service)}")

    database = (params.get("database") or "").strip()
    if not database:
        raise ValueError("Datenbankname fehlt.")
    url = f"{_DRIVERS[db_type]}://{auth}{host}:{port}/{database}"
    if db_type == "mssql":
        url += "?" + _mssql_query(params)
    return url
```

(Den `build_url`-Docstring um `oracle` / `service_name` ergänzen.)

- [ ] **Step 6: Tests laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_connection.py -v`
Expected: PASS (neue Oracle-Tests + bestehende pg/mysql/mssql/sqlite unverändert).

- [ ] **Step 7: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `259 passed, 1 skipped` (257 + 2 neu).

- [ ] **Step 8: Commit**

```bash
git add requirements.txt wheels/oracledb-*.whl core/connection.py tests/test_connection.py
git commit -m "feat: AP-53 oracle+oracledb URL building (service-name) + driver dep"
```
(Falls kein Wheel geladen wurde, `wheels/oracledb-*.whl` aus `git add` weglassen.)

---

### Task 2: Loader — Oracle-System-Schema-Filter

**Files:**
- Modify: `core/loaders/sqlalchemy_loader.py`
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: nichts.
- Produces: reine Hilfsfunktion `_user_schemas(names) -> tuple[str, ...]` (entfernt bekannte System-Schemas); `list_schemas` nutzt sie. Oracle-System-Schemas sind in `_SYSTEM_SCHEMAS`.

- [ ] **Step 1: Failing test schreiben**

In `tests/test_sqlalchemy_loader.py` ans Dateiende anhängen:

```python
def test_user_schemas_filters_oracle_system_schemas():
    from core.loaders.sqlalchemy_loader import _user_schemas
    names = ["SYS", "SYSTEM", "XDB", "CTXSYS", "HR", "APP_DATA"]
    assert _user_schemas(names) == ("HR", "APP_DATA")
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py::test_user_schemas_filters_oracle_system_schemas -v`
Expected: FAIL — `ImportError: cannot import name '_user_schemas'`.

- [ ] **Step 3: Filter-Helfer + Oracle-System-Schemas**

In `core/loaders/sqlalchemy_loader.py` das `_SYSTEM_SCHEMAS`-Set um die Oracle-
System-Schemas erweitern und einen reinen Helfer ergänzen, den `list_schemas`
nutzt. `_SYSTEM_SCHEMAS` neu:

```python
# Schemas that are infrastructure, not user data — hidden from the picker.
_SYSTEM_SCHEMAS = frozenset({
    # Postgres / MySQL / MSSQL
    "information_schema", "pg_catalog", "pg_toast",
    "sys", "INFORMATION_SCHEMA", "performance_schema", "mysql",
    # Oracle (uppercase, as Oracle reports them)
    "SYS", "SYSTEM", "XDB", "OUTLN", "DBSNMP", "APPQOSSYS", "CTXSYS",
    "MDSYS", "ORDSYS", "ORDDATA", "OLAPSYS", "WMSYS", "LBACSYS", "DVSYS",
    "AUDSYS", "GSMADMIN_INTERNAL", "DBSFWUSER", "REMOTE_SCHEDULER_AGENT",
    "SYS$UMF", "GGSYS", "ANONYMOUS", "XS$NULL", "OJVMSYS", "DGPDB_INT",
})


def _user_schemas(names) -> tuple:
    """Drop infrastructure schemas, keeping only user-facing ones."""
    return tuple(n for n in names if n not in _SYSTEM_SCHEMAS)
```

In `list_schemas` die Rückgabe auf den Helfer umstellen:

```python
    return _user_schemas(names)
```

- [ ] **Step 4: Tests laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: PASS (neuer Filter-Test + bestehende `list_schemas`-Tests grün, da `main` kein System-Schema ist).

- [ ] **Step 5: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `260 passed, 1 skipped` (259 + 1 neu).

- [ ] **Step 6: Commit**

```bash
git add core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat: AP-53 filter Oracle system schemas in list_schemas"
```

---

### Task 3: Routes (`service_name`) + Frontend-Formular

**Files:**
- Modify: `web/routes.py` (`_CONN_FIELDS`)
- Modify: `web/static/js/app.js`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `build_url` (Task 1).
- Produces: gespeicherte Oracle-Verbindung trägt `service_name`; Verbindungsformular bietet Oracle mit Service-Name-Feld.

- [ ] **Step 1: Failing test schreiben (service_name wird persistiert)**

In `tests/test_api.py` ans Dateiende anhängen (isolierte config via `LUCENT_CONFIG_DIR`, damit die echte `config.json` nicht berührt wird):

```python
def test_oracle_connection_persists_service_name(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    save = client.post("/api/connections", json={
        "name": "Ora", "db_type": "oracle", "host": "h", "port": 1521,
        "service_name": "XEPDB1", "user": "u",
    })
    assert save.status_code == 200
    got = client.get("/api/connections").get_json()["connections"]
    ora = next(c for c in got if c["name"] == "Ora")
    assert ora["db_type"] == "oracle"
    assert ora["service_name"] == "XEPDB1"
    assert "password" not in ora
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_oracle_connection_persists_service_name -v`
Expected: FAIL — `KeyError: 'service_name'` (Feld wird nicht gespeichert).

- [ ] **Step 3: `_CONN_FIELDS` erweitern**

In `web/routes.py` das Tupel `_CONN_FIELDS` um `service_name` ergänzen:

```python
_CONN_FIELDS = ("db_type", "host", "port", "database", "user", "filepath",
                "encrypt", "trust_server_certificate", "service_name")
```

- [ ] **Step 4: Test laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (neuer Test + bestehende API-Tests grün).

- [ ] **Step 5: Frontend — Oracle im Verbindungsformular**

In `web/static/js/app.js`:

`DB_TYPES` um Oracle ergänzen:
```javascript
const DB_TYPES = [
  { v: "sqlite", label: "SQLite (Datei)" },
  { v: "postgresql", label: "PostgreSQL" },
  { v: "mysql", label: "MySQL / MariaDB" },
  { v: "mssql", label: "MS SQL Server" },
  { v: "oracle", label: "Oracle" },
];
const PORT_DEFAULTS = { postgresql: 5432, mysql: 3306, mssql: 1433, oracle: 1521 };
```

`connFieldsHtml` so umbauen, dass Oracle ein **Service-Name**-Feld statt
„Datenbank" hat (Host/Port/User/Passwort bleiben gemeinsam):
```javascript
function connFieldsHtml(dbType, c) {
  c = c || {};
  if (dbType === "sqlite") {
    return `<div class="row"><label>Dateipfad</label>` +
      `<input id="cf_filepath" type="text" placeholder="/pfad/zur.db" ` +
      `value="${esc(c.filepath || "")}" style="flex:1"></div>`;
  }
  const port = c.port || PORT_DEFAULTS[dbType] || "";
  let html =
    `<div class="row"><label>Host</label><input id="cf_host" type="text" ` +
    `placeholder="localhost" value="${esc(c.host || "")}"></div>` +
    `<div class="row"><label>Port</label><input id="cf_port" type="number" ` +
    `value="${esc(port)}"></div>`;
  if (dbType === "oracle") {
    html += `<div class="row"><label>Service-Name</label><input id="cf_service_name" ` +
      `type="text" placeholder="XEPDB1" value="${esc(c.service_name || "")}"></div>`;
  } else {
    html += `<div class="row"><label>Datenbank</label><input id="cf_database" type="text" ` +
      `value="${esc(c.database || "")}"></div>`;
  }
  html +=
    `<div class="row"><label>Benutzer</label><input id="cf_user" type="text" ` +
    `value="${esc(c.user || "")}"></div>` +
    `<div class="row"><label>Passwort</label><input id="cf_password" type="password"></div>`;
  if (dbType === "mssql") {
    const tri = (id, label, val) => {
      const opt = (v, t) =>
        `<option value="${v}"${(val || "") === v ? " selected" : ""}>${t}</option>`;
      return `<div class="row"><label>${label}</label><select id="${id}">` +
        opt("", "Standard") + opt("yes", "ja") + opt("no", "nein") + `</select></div>`;
    };
    html += tri("cf_encrypt", "Verschlüsselung", c.encrypt) +
            tri("cf_trust", "Server-Zertifikat vertrauen", c.trust_server_certificate);
  }
  return html;
}
```

`formParams` so anpassen, dass Oracle `service_name` statt `database` liefert:
```javascript
function formParams() {
  const t = $("conn_type").value;
  if (t === "sqlite") return { db_type: t, filepath: $("cf_filepath").value };
  const p = {
    db_type: t, host: $("cf_host").value, port: $("cf_port").value,
    user: $("cf_user").value, password: $("cf_password").value,
  };
  if (t === "oracle") p.service_name = $("cf_service_name").value;
  else p.database = $("cf_database").value;
  if (t === "mssql") {
    p.encrypt = $("cf_encrypt") ? $("cf_encrypt").value : "";
    p.trust_server_certificate = $("cf_trust") ? $("cf_trust").value : "";
  }
  return p;
}
```
(Die bestehende `formParams`-Fassung vollständig durch obige ersetzen — sie endet derzeit nach dem mssql-Block mit `return p;`.)

- [ ] **Step 6: JS-Syntax + volle Suite**

Run:
```bash
node --check web/static/js/app.js
./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: `app.js` ok; `261 passed, 1 skipped` (260 + 1 neu).

- [ ] **Step 7: Manuell (kein pytest für JS)**

App über Tray neu starten (`bash run.sh --tray`), Verbindungs-Tab öffnen (Sidebar → Tools → Verbindungen), Typ „Oracle" wählen → Felder Host/Port(1521)/Service-Name/Benutzer/Passwort erscheinen (kein „Datenbank"). (Echte Oracle-Verbindung optional; Feld-Rendering ist der Prüfpunkt.)

- [ ] **Step 8: Commit**

```bash
git add web/routes.py web/static/js/app.js tests/test_api.py
git commit -m "feat: AP-53 Oracle in connection form (service-name) + persist field"
```

---

### Task 4: Skip-guarded Integrationstest + Doku & Release v0.39.0

**Files:**
- Create: `tests/test_oracle_integration.py`
- Modify: `CLAUDE.md`
- Modify (via `sync_version.py`): `config.py`, `lucent-hub.yml`
- Modify: `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`
- Modify: `luDBxP-docs/mermaid-sources/referenz-architektur-3.mmd`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: Release v0.39.0; skip-guarded Oracle-Integrationstest.

- [ ] **Step 1: Integrationstest anlegen (skip-guarded)**

Erstelle `tests/test_oracle_integration.py`:

```python
"""AP-53 — optional live Oracle integration test.

Runs only when ``LUCENT_ORACLE_TEST_URL`` points at a reachable Oracle instance;
otherwise it skips, so the suite stays green without an Oracle backend. Example::

    LUCENT_ORACLE_TEST_URL='oracle+oracledb://user:pw@localhost:1521/?service_name=XEPDB1' \
        ./venv/bin/python -m pytest tests/test_oracle_integration.py

URL-building is covered by unit tests in ``test_connection.py``.
"""
import os

import pytest
from sqlalchemy import create_engine, text

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader

_ORACLE_URL = os.environ.get("LUCENT_ORACLE_TEST_URL")
_PARENT = "lucent_it_parent"
_CHILD = "lucent_it_child"


@pytest.mark.skipif(
    not _ORACLE_URL,
    reason="set LUCENT_ORACLE_TEST_URL to a reachable Oracle URL to run the live "
           "integration test",
)
def test_oracle_live_reflection_with_fk():
    """Provision a Parent/Child schema on Oracle and reflect its FK via the loader."""
    pytest.importorskip("oracledb")
    try:
        engine = create_engine(_ORACLE_URL)
        conn = engine.connect()
    except Exception as exc:  # driver missing / instance unreachable → skip
        pytest.skip(f"Oracle not reachable or driver missing: {exc}")

    def _drop():
        for name in (_CHILD, _PARENT):
            try:
                conn.execute(text(f"DROP TABLE {name}"))
            except Exception:
                pass

    try:
        _drop()
        conn.execute(text(f"CREATE TABLE {_PARENT} (id NUMBER PRIMARY KEY, name VARCHAR2(50))"))
        conn.execute(text(
            f"CREATE TABLE {_CHILD} (id NUMBER PRIMARY KEY, parent_id NUMBER, "
            f"CONSTRAINT fk_lucent_it FOREIGN KEY (parent_id) REFERENCES {_PARENT}(id))"))
        conn.commit()

        schema = SqlAlchemyLoader(_ORACLE_URL).load()
        by_name = {t.name.lower(): t for t in schema.tables}
        assert _CHILD in by_name and _PARENT in by_name
        child = by_name[_CHILD]
        assert len(child.foreign_keys) == 1
        assert child.foreign_keys[0].ref_table.lower() == _PARENT
    finally:
        _drop()
        conn.commit()
        conn.close()
        engine.dispose()
```

- [ ] **Step 2: Suite zeigt den zusätzlichen Skip**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `261 passed, 2 skipped` (Oracle-Integration ohne `LUCENT_ORACLE_TEST_URL` übersprungen).

- [ ] **Step 3: CLAUDE.md — Oracle als verbindbar dokumentieren**

In `CLAUDE.md` im Abschnitt „Bekannte Einschränkungen" beim Datenbank-Backends-Punkt ergänzen:

```
**Oracle** ist seit AP-53 verbindbar (python-oracledb Thin-Mode, Adressierung per Service-Name) — mit optionalem, skip-guardetem Live-Integrationstest (`tests/test_oracle_integration.py`, `LUCENT_ORACLE_TEST_URL`).
```

- [ ] **Step 4: Version bumpen (minor)**

Run:
```bash
./venv/bin/python sync_version.py --minor
./venv/bin/python -c "import config; print(config.APP_VERSION)"
```
Expected: `0.39.0`.

- [ ] **Step 5: Changelog (Root englisch) + Mirror (deutsch)**

In `CHANGELOG.md` ganz oben (vor `## [0.38.0]`):

```markdown
## [0.39.0] — 2026-06-28

### Added
- Oracle database connections: connect to and reflect an Oracle database via
  python-oracledb (thin mode, no Instant Client), addressed by service name.
  System schemas are filtered from the schema picker. Optional skip-guarded
  live integration test (`LUCENT_ORACLE_TEST_URL`).
```

In `luDBxP-docs/docs/entwicklung/changelog.md` ganz oben:

```markdown
## [0.39.0] — 2026-06-28

### Hinzugefügt
- Oracle-Verbindungen: Verbinden/Reflektieren via python-oracledb (Thin-Mode,
  kein Instant Client), Adressierung per Service-Name; System-Schemas im
  Schema-Wähler gefiltert.
```

- [ ] **Step 6: Badges + zensical**

In `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION='0.39.0'`, `TEST_COUNT='261'`, `TEST_DATE='2026-06-28'`.
In `luDBxP-docs/zensical.toml` Zeile 3: site_description-Ende von `· v0.38.0` auf `· v0.39.0`.

- [ ] **Step 7: Architektur-Diagramm — Oracle am DB-Knoten**

In `luDBxP-docs/mermaid-sources/referenz-architektur-3.mmd` den DB-Knoten
ergänzen — aus
`DB[("5 · Datenbank\nSQLite · PostgreSQL · MySQL · MSSQL")]`
wird
`DB[("5 · Datenbank\nSQLite · PostgreSQL · MySQL · MSSQL · Oracle")]`.

- [ ] **Step 8: Site bauen + gegenprüfen**

Run:
```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
grep -rl "0.39.0" luDBxP-docs/site/index.html luDBxP-docs/site/javascripts/icon-rail.js
```
Expected: Build ohne Fehler; `0.39.0` + `261` im gebauten `site/`; „Oracle" im DB-Knoten der `referenz-architektur-3.svg`.

- [ ] **Step 9: SDD-Final-Review**

Gesamten AP-Diff gegen die Spec prüfen: Layering (`core/` Flask-frei), Read-Only unverändert, nur Service-Name (kein SID/TNS), Passwort weiterhin nicht persistiert, Oracle-System-Schema-Filter greift, Tests grün (261/2), keine Doku-Drift, Roadmap/Board/Gantt-Hinweis (siehe unten). Niemals weglassen.

- [ ] **Step 10: Roadmap/Board/Gantt + Commit**

Roadmap/Board/Gantt mitziehen (Konvention): in `luDBxP-docs/docs/projekt/roadmap.md` AP-53 unter „Erledigte Arbeitspakete" (v0.39.0) ergänzen; in `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd` einen `AP-53 — Oracle-Verbindung :done`-Eintrag in der v0.33–v0.39-Sektion; in `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd` Cluster C2 einen Knoten `V7["AP-53\nOracle"]` (Klasse `done`) ergänzen. Danach Site erneut bauen.

```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
git add -A
git commit -m "docs: Release v0.39.0 — AP-53 Oracle-Verbindung (Doku/Badges/Changelog/Roadmap/Site)"
```

- [ ] **Step 11: Push & gh-pages-Deploy — NUR auf Ansage des Nutzers**

Master-Push und der manuelle gh-pages-Deploy (Worktree, `.nojekyll` erhalten) erfolgen erst nach ausdrücklicher Freigabe.

---

## Self-Review (durchgeführt)

**Spec-Coverage:** Dependency+Wheelhouse+build_url+Unit-Tests (Task 1), Oracle-System-Schema-Filter (Task 2), `service_name`-Persistenz + Frontend-Formular (Task 3), skip-guarded Integrationstest + Doku/Release inkl. Roadmap/Board/Gantt + arch-3 (Task 4). Alle Spec-Abschnitte abgedeckt; Nicht-Ziele (kein SID/TNS, kein Thick-Mode, keine Generierungs-Änderung) respektiert.

**Placeholder-Scan:** Keine TBD/TODO; jeder Code-Schritt enthält vollständigen Code/Befehle mit erwarteter Ausgabe. Einzige bewusst offene Stelle: Verfügbarkeit eines oracledb-cp314-win_amd64-Wheels (Task 1 Step 2) — mit klarer Fallback-Anweisung, nicht-blockierend.

**Type-Consistency:** `service_name` durchgängig (build_url Task 1 → `_CONN_FIELDS` Task 3 → `cf_service_name`/`formParams` Task 3); `_user_schemas` (Task 2) konsistent benannt; `_DRIVERS["oracle"]="oracle+oracledb"`, Port 1521 überall gleich. Testzahlen kumulativ: 257 → 259 → 260 → 261 (+1 skipped).
