# AP-52 — Multi-Schema-Reflection (ein wählbares Schema): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein wählbares DB-Schema reflektieren und schema-qualifizierte, lauffähige SQL erzeugen — Tabellen außerhalb des Default-Schemas werden erreichbar.

**Architecture:** Das gewählte Schema ist ein Request-Parameter, der durch Reflection (`load(schema)`) und SQL-Erzeugung (`generate_sql(schema=...)`, `fetch_rows(schema=...)`) fließt. Weil immer nur EIN Schema aktiv ist (keine Namenskollisionen), bleiben `core/model.py`, `core/graph.py`, `core/pathfinder.py` unverändert.

**Tech Stack:** Python 3.14 (venv), SQLAlchemy (Reflection), Flask, vanilla JS, pytest.

## Global Constraints

- **Layering:** `core/` darf NIE Flask importieren. `core/model.py`, `core/graph.py`, `core/pathfinder.py` bleiben in dieser AP UNVERÄNDERT.
- **Read-Only:** nur Schema-Metadaten lesen; read-only-Ausführung unverändert.
- **Version Management:** Version nur via `sync_version.py`; Feature=minor → v0.38.0.
- **Sprache:** Code-Kommentare englisch; CHANGELOG-Root `### Added` englisch, Mirror `### Hinzugefügt` deutsch; UI-Texte deutsch.
- **NO-CDN:** keine neuen externen Frontend-Assets.
- **Qualifizierungs-Regel:** `schema` ist ein String; nicht-leer → jede Tabellenreferenz wird schema-qualifiziert; leer/None → exakt heutige Ausgabe (keine Regression).
- **`schema`-Param-Konvention in Routes:** `schema_name = (data.get("schema") or "").strip()`; an Loader `load(schema_name or None)`, an sqlgen/datapreview den String `schema_name`.
- **Tests:** Baseline 248 passed, 1 skipped muss grün bleiben; neue Tests kommen hinzu.

---

### Task 1: Loader — schema-Parameter + Schema-Listing

**Files:**
- Modify: `core/loaders/sqlalchemy_loader.py`
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: nichts.
- Produces:
  - `SqlAlchemyLoader.load(self, schema=None)` — reflektiert das benannte Schema (`None` = Default).
  - `list_schemas(connection_url: str) -> tuple[str, ...]` — verfügbare Schemas ohne bekannte System-Schemas.

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_sqlalchemy_loader.py` ans Dateiende anhängen:

```python
def test_load_with_explicit_default_schema_matches(inventory_url):
    # SQLite's real default schema is "main"; reflecting it explicitly must
    # yield the same tables as the no-arg default.
    default = {t.name for t in SqlAlchemyLoader(inventory_url).load().tables}
    explicit = {t.name for t in SqlAlchemyLoader(inventory_url).load(schema="main").tables}
    assert explicit == default and "VirtualMachines" in explicit


def test_list_schemas_includes_main_and_filters_system(inventory_url):
    from core.loaders.sqlalchemy_loader import list_schemas
    schemas = list_schemas(inventory_url)
    assert "main" in schemas
    assert not ({"information_schema", "pg_catalog", "sys"} & set(schemas))
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py::test_list_schemas_includes_main_and_filters_system -v`
Expected: FAIL — `ImportError: cannot import name 'list_schemas'`.

- [ ] **Step 3: `load(schema=...)` + `list_schemas` implementieren**

In `core/loaders/sqlalchemy_loader.py` die `load`-Signatur und alle Inspector-Aufrufe um `schema=` erweitern. `load(self)` → `load(self, schema=None)`; dann in den Schleifen:
- `insp.get_table_names()` → `insp.get_table_names(schema=schema)`
- `insp.get_columns(tname)` → `insp.get_columns(tname, schema=schema)`
- `insp.get_foreign_keys(tname)` → `insp.get_foreign_keys(tname, schema=schema)`
- `insp.get_pk_constraint(tname)` → `insp.get_pk_constraint(tname, schema=schema)`
- `insp.get_unique_constraints(tname)` → `insp.get_unique_constraints(tname, schema=schema)`
- `insp.get_indexes(tname)` → `insp.get_indexes(tname, schema=schema)`
- `insp.get_view_names()` → `insp.get_view_names(schema=schema)`
- `insp.get_columns(vname)` → `insp.get_columns(vname, schema=schema)`
- `insp.get_view_definition(vname)` → `insp.get_view_definition(vname, schema=schema)`

Am Dateiende die reine Listing-Funktion ergänzen:

```python
# Schemas that are infrastructure, not user data — hidden from the picker.
_SYSTEM_SCHEMAS = frozenset({
    "information_schema", "pg_catalog", "pg_toast",
    "sys", "INFORMATION_SCHEMA", "performance_schema", "mysql",
})


def list_schemas(connection_url: str) -> tuple:
    """Return the connectable, user-facing schema names (system schemas removed).

    Raises:
        ConnectionError: If the database is unreachable or the URL is invalid.
    """
    try:
        engine = create_engine(connection_url)
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not create engine: {exc}") from exc
    try:
        names = inspect(engine).get_schema_names()
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not list schemas: {exc}") from exc
    finally:
        engine.dispose()
    return tuple(n for n in names if n not in _SYSTEM_SCHEMAS)
```

- [ ] **Step 4: Tests laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: PASS (alle Loader-Tests inkl. der zwei neuen).

- [ ] **Step 5: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `250 passed, 1 skipped` (248 + 2 neu).

- [ ] **Step 6: Commit**

```bash
git add core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat: AP-52 loader reflects a named schema + list_schemas()"
```

---

### Task 2: SQL-Qualifizierung (sqlgen + datapreview)

**Files:**
- Modify: `core/sqlgen.py`
- Modify: `core/datapreview.py`
- Test: `tests/test_sqlgen_dialect.py`, `tests/test_datapreview.py` (neu)

**Interfaces:**
- Consumes: nichts (reine String-Logik).
- Produces:
  - `Dialect.table_ref(self, table, schema="")` und `Dialect.qualify(self, table, column, schema="")`.
  - `generate_sql(..., schema="")` — qualifiziert alle Tabellenreferenzen bei nicht-leerem `schema`.
  - `fetch_rows(connection_url, object_name, valid_names, limit=100, schema="")` — qualifiziert das Objekt bei nicht-leerem `schema`.

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_sqlgen_dialect.py` ans Dateiende anhängen:

```python
def test_generate_sql_qualifies_with_schema():
    g = generate_sql(_path(), selects=_sel(), schema="sales")
    assert 'FROM "sales"."VirtualMachine"' in g.sql
    assert 'JOIN "sales"."Host"' in g.sql
    assert '    "sales"."VirtualMachine"."VMID"' in g.sql
    assert '    ON "sales"."VirtualMachine"."HostID" = "sales"."Host"."HostID"' in g.sql


def test_generate_sql_without_schema_is_unqualified():
    g = generate_sql(_path(), selects=_sel())
    assert 'FROM "VirtualMachine"' in g.sql
    assert '"sales".' not in g.sql
```

Erstelle `tests/test_datapreview.py`:

```python
from core.datapreview import fetch_rows


def test_fetch_rows_with_schema_runs(inventory_url):
    # SQLite's real schema is "main"; a schema-qualified preview must execute.
    res = fetch_rows(inventory_url, "VirtualMachines",
                     {"VirtualMachines"}, limit=5, schema="main")
    assert "columns" in res and "rows" in res
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `./venv/bin/python -m pytest tests/test_sqlgen_dialect.py::test_generate_sql_qualifies_with_schema tests/test_datapreview.py -v`
Expected: FAIL — `TypeError: generate_sql() got an unexpected keyword argument 'schema'` bzw. `fetch_rows() got an unexpected keyword argument 'schema'`.

- [ ] **Step 3: Dialect-Helfer + generate_sql-Schema**

In `core/sqlgen.py` die `Dialect`-Methoden erweitern. Die bestehende `qualify` (aktuell):

```python
    def qualify(self, table: str, column: str) -> str:
        """Render a quoted ``table.column`` reference."""
        return f"{self.quote(table)}.{self.quote(column)}"
```

ersetzen durch:

```python
    def table_ref(self, table: str, schema: str = "") -> str:
        """Quoted table reference, schema-qualified when ``schema`` is non-empty."""
        return f"{self.quote(schema)}.{self.quote(table)}" if schema else self.quote(table)

    def qualify(self, table: str, column: str, schema: str = "") -> str:
        """Render a quoted ``[schema.]table.column`` reference."""
        return f"{self.table_ref(table, schema)}.{self.quote(column)}"
```

In `generate_sql` die Signatur um `schema: str = ""` ergänzen (z. B. nach `dialect: Dialect = SQLITE`) und die Tabellenreferenzen qualifizieren:
- SELECT-Spalte: `dialect.qualify(s.table, s.column)` → `dialect.qualify(s.table, s.column, schema)`
- FROM: `dialect.quote(path.tables[0])` → `dialect.table_ref(path.tables[0], schema)`
- JOIN: `dialect.quote(step.right_table)` → `dialect.table_ref(step.right_table, schema)`
- ON-Paare: `dialect.qualify(step.left_table, lc)` → `dialect.qualify(step.left_table, lc, schema)` und `dialect.qualify(step.right_table, rc)` → `dialect.qualify(step.right_table, rc, schema)`
- WHERE: `dialect.qualify(flt.table, flt.column)` → `dialect.qualify(flt.table, flt.column, schema)`
- ORDER BY: `dialect.qualify(tbl, col)` → `dialect.qualify(tbl, col, schema)`

- [ ] **Step 4: datapreview-Schema**

In `core/datapreview.py` die `fetch_rows`-Signatur auf `def fetch_rows(connection_url: str, object_name: str, valid_names: set, limit: int = 100, schema: str = "") -> dict:` ändern und die Quotierung (aktuell `quoted = '"' + object_name.replace('"', '""') + '"'`) ersetzen durch:

```python
            def _q(ident: str) -> str:
                return '"' + ident.replace('"', '""') + '"'
            quoted = f"{_q(schema)}.{_q(object_name)}" if schema else _q(object_name)
```

- [ ] **Step 5: Tests laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py tests/test_sqlgen_dialect.py tests/test_datapreview.py -v`
Expected: PASS (neue Tests grün; bestehende sqlgen-Tests unverändert grün, da `schema=""` Default).

- [ ] **Step 6: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `253 passed, 1 skipped` (250 + 3 neu).

- [ ] **Step 7: Commit**

```bash
git add core/sqlgen.py core/datapreview.py tests/test_sqlgen_dialect.py tests/test_datapreview.py
git commit -m "feat: AP-52 schema-qualified SQL in sqlgen + datapreview"
```

---

### Task 3: Routes — /api/schemas + reflektierende Endpoints

**Files:**
- Modify: `web/routes.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `list_schemas` (Task 1), `load(schema=...)` (Task 1), `fetch_rows(..., schema=...)` (Task 2).
- Produces: `POST /api/schemas` → `{"schemas": [...]}`; `/api/schema`, `/api/graph`, `/api/data` akzeptieren optional `schema`.

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_api.py` ans Dateiende anhängen:

```python
def test_schemas_endpoint_lists_main(client, inventory_url):
    resp = client.post("/api/schemas", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    assert "main" in resp.get_json()["schemas"]


def test_data_endpoint_with_schema_returns_rows(client, inventory_url):
    resp = client.post("/api/data", json={
        "connection_url": inventory_url, "object": "VirtualMachines",
        "schema": "main",
    })
    assert resp.status_code == 200
    assert "columns" in resp.get_json()
```

- [ ] **Step 2: Tests laufen lassen — `/api/schemas` schlägt fehl (404)**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_schemas_endpoint_lists_main -v`
Expected: FAIL — 404 (Endpoint existiert nicht).

- [ ] **Step 3: Import + neuer Endpoint**

In `web/routes.py` den Loader-Import um `list_schemas` erweitern:

```python
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader, list_schemas
```

Den neuen Endpoint ergänzen (z. B. direkt nach `api_schema`):

```python
@bp.post("/api/schemas")
def api_schemas():
    """List the database's user-facing schema names for the schema picker."""
    data = request.get_json(silent=True) or {}
    url = (data.get("connection_url") or "").strip()
    if not url:
        return jsonify(error=_NO_URL_MSG), 400
    try:
        schemas = list_schemas(url)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(schemas=list(schemas))
```

- [ ] **Step 4: schema in die reflektierenden Endpoints fädeln**

In `api_schema`, `api_graph`, `api_data` jeweils direkt nach dem `url`-Lesen `schema_name` bestimmen und an `load` (und in `api_data` zusätzlich an `fetch_rows`) übergeben:

```python
    schema_name = (data.get("schema") or "").strip()
```
- `api_schema`: `SqlAlchemyLoader(url).load()` → `SqlAlchemyLoader(url).load(schema_name or None)`
- `api_graph`: `SqlAlchemyLoader(url).load()` → `SqlAlchemyLoader(url).load(schema_name or None)`
- `api_data`: `SqlAlchemyLoader(url).load()` → `SqlAlchemyLoader(url).load(schema_name or None)`; und `fetch_rows(url, obj, valid)` → `fetch_rows(url, obj, valid, schema=schema_name)`

- [ ] **Step 5: Tests laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (neue + bestehende API-Tests grün).

- [ ] **Step 6: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `255 passed, 1 skipped` (253 + 2 neu).

- [ ] **Step 7: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat: AP-52 /api/schemas + schema param on reflect endpoints"
```

---

### Task 4: Routes — schema durch die SQL-erzeugenden Endpoints

**Files:**
- Modify: `web/routes.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `generate_sql(..., schema=...)` (Task 2), `load(schema=...)` (Task 1).
- Produces: `/api/joinpath`, `/api/joinpath/run`, `/api/distinct`, `/api/orphan_check` qualifizieren erzeugte SQL mit dem gewählten Schema.

- [ ] **Step 1: Failing tests schreiben**

In `tests/test_api.py` ans Dateiende anhängen:

```python
def test_joinpath_with_schema_qualifies_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VirtualMachines", "column": "VMID"},
        "filters": [], "schema": "main",
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert '"main"."Networks"' in p["sql"]


def test_joinpath_run_with_schema_executes(client, inventory_url):
    resp = client.post("/api/joinpath/run", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VirtualMachines", "column": "VMID"},
        "filters": [], "schema": "main", "path_index": 0,
    })
    assert resp.status_code == 200
    assert "columns" in resp.get_json()
```

- [ ] **Step 2: Tests laufen lassen — Qualifizierung fehlt**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_joinpath_with_schema_qualifies_sql -v`
Expected: FAIL — `assert '"main"."Networks"' in p["sql"]` schlägt fehl (SQL noch unqualifiziert).

- [ ] **Step 3: `_make_path_gen` um schema erweitern**

In `web/routes.py` die `_make_path_gen`-Signatur um `schema: str = ""` ergänzen (z. B. nach `dialect`) und den `generate_sql`-Aufruf darin um `schema=schema` erweitern:

```python
    return generate_sql(p, tuple(selects_for_path), filters,
                        distinct=distinct, order_by=order_by_validated,
                        limit=limit, join_types=join_types,
                        dialect=dialect, schema=schema)
```
(Die bestehenden Keyword-Argumente unverändert lassen — nur `schema=schema` ergänzen; falls der Aufruf positionale Argumente nutzt, `schema=schema` am Ende anhängen.)

- [ ] **Step 4: schema in joinpath / joinpath_run / orphan_check / distinct fädeln**

Jeweils `schema_name = (data.get("schema") or "").strip()` direkt nach dem `url`-Lesen bestimmen.

- `api_joinpath`: `load()` → `load(schema_name or None)`; der `_make_path_gen(...)`-Aufruf (im Pfad-Loop) erhält zusätzlich `schema=schema_name`.
- `api_joinpath_run`: `load()` → `load(schema_name or None)`; der `_make_path_gen(...)`-Aufruf erhält `schema=schema_name`.
- `api_orphan_check`: `load()` → `load(schema_name or None)`; der `_make_path_gen(...)`-Aufruf in `row_count` erhält `schema=schema_name`.
- `api_distinct`: `load()` → `load(schema_name or None)`; die SQL-Konstruktion qualifizieren:
  ```python
        col = dialect.qualify(table, column, schema_name)
        sql = (f"SELECT DISTINCT {col} FROM {dialect.table_ref(table, schema_name)}\n"
               f"WHERE {col} IS NOT NULL\nORDER BY {col}")
  ```

- [ ] **Step 5: Tests laufen lassen — bestehen**

Run: `./venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (neue + bestehende grün).

- [ ] **Step 6: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: `257 passed, 1 skipped` (255 + 2 neu).

- [ ] **Step 7: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat: AP-52 thread schema through joinpath/distinct/orphan SQL"
```

---

### Task 5: Frontend — Schema-Dropdown

**Files:**
- Modify: `web/templates/index.html`
- Modify: `web/static/js/app.js`

**Interfaces:**
- Consumes: `POST /api/schemas` (Task 3); alle reflektierenden Endpoints akzeptieren `schema` (Tasks 3–4).
- Produces: ein Schema-Dropdown; alle Requests mit `connection_url` tragen automatisch das gewählte Schema.

**Hinweis:** Reine JS/Template-Änderung → live ohne App-Neustart. Keine pytest-Abdeckung; Verifikation manuell bzw. via Playwright (System-`python3`) — Backend ist durch Tasks 1–4 voll getestet.

- [ ] **Step 1: Dropdown ins Template**

In `web/templates/index.html` in der `topbar` (nach Zeile 18, dem `btn_connections`-Button) ein Schema-Dropdown ergänzen:

```html
    <select id="schema_select" class="topbar-conn" title="Schema wählen" style="display:none">
      <option value="">— Standard-Schema —</option>
    </select>
```

- [ ] **Step 2: Schema-State + Auto-Inject in postJSON**

In `web/static/js/app.js` oben bei den Modul-Variablen ergänzen:

```javascript
let SELECTED_SCHEMA = "";  // empty = default schema
```

In `postJSON(url, body)` (ab Zeile 45) das gewählte Schema automatisch in jeden Request mit `connection_url` einfügen — direkt am Funktionsanfang, vor dem `fetch`:

```javascript
  if (SELECTED_SCHEMA && body && body.connection_url !== undefined
      && body.schema === undefined) {
    body = { ...body, schema: SELECTED_SCHEMA };
  }
```

- [ ] **Step 3: Schemas nach dem Verbinden laden + Wechsel verdrahten**

In `app.js` eine Funktion ergänzen, die das Dropdown füllt, und sie in `doConnect()` **vor** dem `/api/schema`-Laden aufrufen. In `doConnect` (ab Zeile 1380) vor `SCHEMA = await postJSON("/api/schema", …)` einfügen:

```javascript
  await populateSchemas();
```

Und die Funktion selbst (z. B. nahe `doConnect`):

```javascript
async function populateSchemas() {
  const sel = $("schema_select");
  try {
    const res = await postJSON("/api/schemas", { connection_url: connUrl() });
    const list = (res && res.schemas) || [];
    sel.innerHTML = '<option value="">— Standard-Schema —</option>'
      + list.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
    sel.value = SELECTED_SCHEMA;
    sel.style.display = list.length ? "" : "none";
  } catch (_e) {
    sel.style.display = "none";
  }
}
```

Den Change-Handler einmalig registrieren (bei der übrigen Event-Verdrahtung, z. B. im Init-Block, wo `btn_load` o. Ä. gebunden wird):

```javascript
  $("schema_select").addEventListener("change", (e) => {
    SELECTED_SCHEMA = e.target.value;
    doConnect();
  });
```

- [ ] **Step 4: Manuell verifizieren**

App starten (`bash run.sh --skip-setup`), gegen die Demo-DB verbinden. Erwartet: Das Schema-Dropdown erscheint (bei SQLite „main"); Auswahl von „main" lädt neu und das generierte SELECT zeigt `"main"."…"`-qualifizierte Namen; „— Standard-Schema —" liefert unqualifizierte SQL wie bisher. (Optional Playwright-Check mit System-`python3`.)

- [ ] **Step 5: Commit**

```bash
git add web/templates/index.html web/static/js/app.js
git commit -m "feat: AP-52 schema picker in the topbar (auto-applied to requests)"
```

---

### Task 6: Doku & Release v0.38.0

**Files:**
- Modify: `CLAUDE.md`
- Modify (via `sync_version.py`): `config.py`, `lucent-hub.yml`
- Modify: `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`
- Modify: `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`
- Modify: `luDBxP-docs/mermaid-sources/referenz-architektur-3.mmd`

**Interfaces:**
- Consumes: fertige Implementierung aus Tasks 1–5.
- Produces: Release v0.38.0, konsistente Doku, gebaute Site.

- [ ] **Step 1: CLAUDE.md — Schema-Fähigkeit dokumentieren**

In `CLAUDE.md` im Abschnitt „Bekannte Einschränkungen" beim Datenbank-Backends-Punkt einen Satz ergänzen:

```
Ein einzelnes, wählbares Schema ist reflektierbar (AP-52): `/api/schemas` listet die Schemas, der gewählte Name wird durch Reflection und SQL-Erzeugung (`schema.table`) gefädelt. Gleichzeitiges Multi-Schema und Cross-Schema-Joins sind noch nicht unterstützt.
```

- [ ] **Step 2: Version bumpen (minor)**

Run:
```bash
./venv/bin/python sync_version.py --minor
./venv/bin/python -c "import config; print(config.APP_VERSION)"
```
Expected: `0.38.0`.

- [ ] **Step 3: Changelog (Root englisch) + Mirror (deutsch)**

In `CHANGELOG.md` ganz oben (vor `## [0.37.0]`):

```markdown
## [0.38.0] — 2026-06-27

### Added
- Multi-schema support: a schema picker lets you reflect and query any one
  database schema. The chosen schema is threaded through reflection and SQL
  generation, so the generated SQL is schema-qualified (`schema.table`) and
  runs regardless of the search path. New `/api/schemas` endpoint.
```

In `luDBxP-docs/docs/entwicklung/changelog.md` ganz oben:

```markdown
## [0.38.0] — 2026-06-27

### Hinzugefügt
- Multi-Schema: ein Schema-Wähler reflektiert/abfragt jedes einzelne Schema;
  erzeugte SQL ist schema-qualifiziert (`schema.table`). Neues `/api/schemas`.
```

- [ ] **Step 4: Badges + zensical nachziehen**

In `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION='0.38.0'`, `TEST_COUNT='257'`, `TEST_DATE='2026-06-27'`.
In `luDBxP-docs/zensical.toml` Zeile 3: site_description-Ende von `· v0.37.0` auf `· v0.38.0`.

- [ ] **Step 5: Architektur-Diagramm `-3.mmd` ergänzen**

In `luDBxP-docs/mermaid-sources/referenz-architektur-3.mmd` das neue `/api/schemas`-Endpoint in der Komponenten/Endpoints-Karte ergänzen (neben den übrigen `/api/*`-Endpoints, gleiche Notation wie die Nachbarn). `-1.mmd` und `-2.mmd` unverändert lassen.

- [ ] **Step 6: Site bauen + gegenprüfen**

Run:
```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
```
Expected: Build ohne Fehler; danach gegenprüfen, dass `0.38.0`, `257` und das neue `/api/schemas` auftauchen:
```bash
grep -rl "0.38.0" luDBxP-docs/site/index.html luDBxP-docs/site/javascripts/icon-rail.js
grep -rl "/api/schemas" luDBxP-docs/site/ | head -1
```

- [ ] **Step 7: SDD-Final-Review**

Gesamten AP-Diff gegen die Spec prüfen: Layering (`core/` Flask-frei; Model/Graph/Pathfinder unverändert), Read-Only unverändert, Tests grün (257/1), `schema=""`/None → keine Regression an unqualifizierter SQL, keine Doku-Drift, Grenzen (kein gleichzeitiges Multi-Schema/Cross-Join, keine Persistenz) korrekt dokumentiert. Niemals weglassen.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.38.0 — AP-52 Multi-Schema-Reflection (Doku/Badges/Changelog/Site)"
```

- [ ] **Step 9: Push & gh-pages-Deploy — NUR auf Ansage des Nutzers**

Master-Push und der manuelle gh-pages-Deploy (Worktree, `.nojekyll` erhalten) erfolgen erst nach ausdrücklicher Freigabe. Nicht automatisch ausführen.

---

## Self-Review (durchgeführt)

**Spec-Coverage:** Loader schema-Param + `list_schemas` (Task 1), SQL-Qualifizierung sqlgen+datapreview (Task 2), `/api/schemas` + reflect-Endpoints (Task 3), SQL-Gen-Endpoints (Task 4), Frontend-Dropdown (Task 5), Doku/Release inkl. `-3.mmd` + Final-Review (Task 6). Alle Spec-Abschnitte abgedeckt; Nicht-Ziele (kein gleichzeitiges Multi-Schema, keine Cross-Schema-Joins, keine Persistenz, Model/Graph/Pathfinder unverändert) respektiert.

**Placeholder-Scan:** Keine TBD/TODO; jeder Code-Schritt enthält vollständigen Code bzw. exakte Edit-Anweisungen mit Kontext; Befehle mit erwarteter Ausgabe. Task 5 (Frontend) ist bewusst manuell/Playwright-verifiziert — Backend ist voll pytest-getestet.

**Type-Consistency:** `load(schema=None)` (Task 1) → `generate_sql(..., schema="")` / `Dialect.table_ref`/`qualify(...schema)` / `fetch_rows(..., schema="")` (Task 2) → `_make_path_gen(..., schema="")` + `schema_name`-Konvention in Routes (Tasks 3–4) → `SELECTED_SCHEMA`/`postJSON`-Injection (Task 5) durchgängig konsistent. Testzahlen kumulativ: 248 → 250 → 253 → 255 → 257.
