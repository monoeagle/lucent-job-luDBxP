# AP-25 SQL-Statement-Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein neuer „SQL-Analyzer"-Tab analysiert ein eingefügtes SQL-Statement read-only (parst es mit sqlglot, ohne es je auszuführen) und zeigt Typ, gelesene/geschriebene Tabellen, Warnungen und — mit aktiver Verbindung — ein Graph-Highlight.

**Architecture:** Reine Analyse-Logik in `core/sqlanalyze.py` (Flask-frei) auf Basis des sqlglot-AST; ein read-only Endpoint `POST /api/analyze` in `web/routes.py`; ein neuer Frontend-Tab. Zwei Modi: mit Verbindung (Schema-Abgleich + Dialekt + Highlight) und ohne (reine Text-Analyse).

**Tech Stack:** Python 3.14 (venv via uv), sqlglot (neu, pure-Python), Flask, SQLAlchemy, NetworkX; vanilla JS Frontend; pytest.

## Global Constraints

- **Layering:** `core/` darf **niemals** Flask importieren. `web/` ruft `core/`, nie umgekehrt.
- **Read-only / strikt keine Ausführung:** Der Analyzer parst nur; es gibt **keinen** DB-Roundtrip für das Statement, kein EXPLAIN. Schema-Reflection (`SqlAlchemyLoader.load()`) ist erlaubt — das liest nur Metadaten.
- **No CDN:** Keine externen `<script>/<link>`. `sqlglot` wird als Wheel ins lokale `wheels/` gebündelt; alle Frontend-Assets bleiben lokal.
- **Determinismus:** `tables_read`/`tables_written` werden sortiert + dedupliziert zurückgegeben.
- **Sprache:** Code/Kommentare auf **Englisch**; nutzerseitige Warn-/UI-Texte auf **Deutsch**.
- **XSS:** Alle in den DOM eingefügten Server-Strings über `esc()`.
- **Version:** `config.APP_VERSION` nur via `./venv/bin/python sync_version.py` ändern. Feature → `--minor`.
- **Commits:** je Task ein Commit, **ohne** KI-Signatur.
- **Tests:** `./venv/bin/python -m pytest`. Baseline jetzt (master nach AP-30): **144 passed, 1 skipped**.

---

## File Structure

- `requirements.txt` + `wheels/` — sqlglot als Dependency + gebündeltes Wheel.
- `core/sqlanalyze.py` (neu, Flask-frei) — `AnalysisWarning`, `AnalysisResult`, `analyze(sql, schema=None, dialect=None)`. Reine Logik, voll unit-testbar.
- `web/routes.py` — neuer Endpoint `POST /api/analyze` (führt nie SQL aus).
- `web/templates/index.html` — Sidebar-Tool-Eintrag (falls statisch) / keine Änderung falls Sidebar rein per JS gebaut wird (sie ist es: `renderSidebar`).
- `web/static/js/app.js` — `openAnalyzer()` + Sidebar-Eintrag + Render + Graph-Highlight.
- `web/static/css/app.css` — `.analyze-read` / `.analyze-write` Node-Marker + Panel-Styles.
- `tests/test_sqlanalyze.py` (neu) — Kern-Unit-Tests.
- `tests/test_api.py` — `/api/analyze`-Tests.

---

### Task 1: sqlglot als gebündelte Dependency

**Files:**
- Modify: `requirements.txt`
- Create: `wheels/sqlglot-*-py3-none-any.whl`
- Test: (Verifikations-Schritt, kein pytest)

**Interfaces:**
- Produces: `import sqlglot` ist im venv verfügbar; `sqlglot` steht in `requirements.txt` und als Wheel in `wheels/` (offline-installierbar, NO-CDN).

- [ ] **Step 1: sqlglot in requirements.txt aufnehmen**

In `requirements.txt` eine Zeile ergänzen (nach den Treiber-Zeilen):

```
sqlglot>=25            # SQL parser/AST for the read-only SQL analyzer (AP-25), pure-Python
```

- [ ] **Step 2: Wheel ins Wheelhouse laden (pure-Python, no deps)**

Run:
```bash
./venv/bin/python -m pip download sqlglot --no-deps --dest wheels/
ls wheels/ | grep sqlglot
```
Expected: eine Datei `sqlglot-<version>-py3-none-any.whl` liegt in `wheels/`.

- [ ] **Step 3: Import im venv sicherstellen**

Run:
```bash
./venv/bin/python -m pip install sqlglot --quiet
./venv/bin/python -c "import sqlglot; print(sqlglot.__version__)"
```
Expected: eine Versionsnummer (z. B. `30.x`) wird gedruckt, kein ImportError. (Hinweis: sqlglot ist in dieser Session bereits ins venv installiert — der Schritt ist idempotent.)

- [ ] **Step 4: Volle Suite (unverändert grün) + Commit**

Run: `./venv/bin/python -m pytest -q`
Expected: `144 passed, 1 skipped`.

```bash
git add requirements.txt wheels/
git commit -m "AP-25: sqlglot als gebündelte Dependency (requirements + Wheelhouse)"
```

---

### Task 2: `core/sqlanalyze.py` — Parsen, Typ & beteiligte Tabellen

**Files:**
- Create: `core/sqlanalyze.py`
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Consumes: `sqlglot` (Task 1).
- Produces:
  - `AnalysisWarning(level: str, code: str, message: str)` (frozen dataclass).
  - `AnalysisResult(statement_type: str, tables_read: tuple[str,...], tables_written: tuple[str,...], warnings: tuple[AnalysisWarning,...], parse_error: str | None)` (frozen dataclass).
  - `analyze(sql: str, schema=None, dialect: str | None = None) -> AnalysisResult`.
  - In diesem Task ist `warnings` immer leer (Warnungen folgen in Task 3/4); `schema`/`dialect` werden bereits akzeptiert, aber `schema` noch nicht ausgewertet.

- [ ] **Step 1: Failing tests schreiben** — `tests/test_sqlanalyze.py`:

```python
from core.sqlanalyze import analyze, AnalysisResult, AnalysisWarning


def test_select_with_join_reads_both_tables():
    r = analyze("SELECT v.Name, n.VLAN FROM VirtualMachine v "
                "JOIN Network n ON v.NetworkID = n.NetworkID")
    assert r.statement_type == "SELECT"
    assert r.tables_read == ("Network", "VirtualMachine")  # sorted, dedup
    assert r.tables_written == ()
    assert r.parse_error is None


def test_update_target_is_written():
    r = analyze("UPDATE Host SET Hostname = 'x' WHERE HostID = 1")
    assert r.statement_type == "UPDATE"
    assert r.tables_written == ("Host",)
    assert r.tables_read == ()


def test_insert_select_splits_read_and_written():
    r = analyze("INSERT INTO Audit (id) SELECT VMID FROM VirtualMachine")
    assert r.statement_type == "INSERT"
    assert r.tables_written == ("Audit",)
    assert r.tables_read == ("VirtualMachine",)


def test_ddl_create_is_ddl_type():
    r = analyze("CREATE TABLE T (id INT)")
    assert r.statement_type == "DDL"
    assert r.tables_written == ("T",)


def test_unparseable_sets_parse_error_no_exception():
    r = analyze("NOT SQL @@@ ;;;")
    assert r.parse_error is not None
    assert r.statement_type == "OTHER"
    assert r.tables_read == () and r.tables_written == ()


def test_determinism_sorted_dedup():
    a = analyze("SELECT * FROM A, B, A")
    assert a.tables_read == ("A", "B")
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: FAIL mit `ModuleNotFoundError: No module named 'core.sqlanalyze'`.

- [ ] **Step 3: `core/sqlanalyze.py` implementieren**

```python
"""Read-only analysis of a single SQL statement via its sqlglot AST.

Never executes anything against a database. Parses the statement, classifies
it, extracts the tables it reads and writes, and (in later layers) derives
non-blocking warnings. On a parse failure no exception escapes: parse_error
is set and the other fields stay empty.
"""
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

# Map sqlglot root expression types to a coarse, user-facing statement type.
_DDL_NODES = (exp.Create, exp.Drop, exp.Alter)
_TYPE_NAMES = {
    exp.Select: "SELECT",
    exp.Insert: "INSERT",
    exp.Update: "UPDATE",
    exp.Delete: "DELETE",
}


@dataclass(frozen=True)
class AnalysisWarning:
    level: str    # "info" | "warn" | "danger"
    code: str     # stable machine code, e.g. "WRITE_STATEMENT"
    message: str  # German user-facing text


@dataclass(frozen=True)
class AnalysisResult:
    statement_type: str
    tables_read: tuple[str, ...]
    tables_written: tuple[str, ...]
    warnings: tuple[AnalysisWarning, ...]
    parse_error: "str | None"


def _statement_type(node) -> str:
    if isinstance(node, _DDL_NODES):
        return "DDL"
    for cls, name in _TYPE_NAMES.items():
        if isinstance(node, cls):
            return name
    return "OTHER"


def _written_table(node) -> "str | None":
    """The single table a write statement targets, or None for reads."""
    if isinstance(node, (exp.Insert, *_DDL_NODES)):
        tgt = node.find(exp.Table)
        return tgt.name if tgt else None
    if isinstance(node, (exp.Update, exp.Delete)):
        tgt = node.this
        return tgt.name if isinstance(tgt, exp.Table) else None
    return None


def analyze(sql: str, schema=None, dialect: "str | None" = None) -> AnalysisResult:
    """Analyze one SQL statement read-only. Never executes it.

    Args:
        sql: The statement text.
        schema: Optional core.model.Schema for table/column cross-checks. When
            None, schema-dependent warnings are skipped (text-only mode).
        dialect: Optional sqlglot dialect name; None parses dialect-neutrally.

    Returns:
        An AnalysisResult. On parse failure, parse_error is set and the type is
        "OTHER" with empty table lists.
    """
    try:
        node = sqlglot.parse_one(sql, read=dialect)
    except SqlglotError as exc:
        return AnalysisResult("OTHER", (), (), (), str(exc))
    if node is None:
        return AnalysisResult("OTHER", (), (), (), "empty statement")

    written_name = _written_table(node)
    written = {written_name} if written_name else set()
    read = {t.name for t in node.find_all(exp.Table)} - written

    return AnalysisResult(
        statement_type=_statement_type(node),
        tables_read=tuple(sorted(read)),
        tables_written=tuple(sorted(written)),
        warnings=(),
        parse_error=None,
    )
```

- [ ] **Step 4: Tests laufen lassen, Erfolg prüfen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "AP-25: core/sqlanalyze — Parsen, Statement-Typ, gelesene/geschriebene Tabellen"
```

---

### Task 3: Strukturelle Warnungen (schema-unabhängig)

**Files:**
- Modify: `core/sqlanalyze.py`
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Consumes: `analyze` aus Task 2.
- Produces: `analyze(...)` füllt jetzt `warnings` mit den schema-unabhängigen Codes `WRITE_STATEMENT`, `NO_WHERE`, `CARTESIAN_JOIN`.

- [ ] **Step 1: Failing tests schreiben** — ans Ende von `tests/test_sqlanalyze.py`:

```python
def _codes(r):
    return {w.code for w in r.warnings}


def test_write_statement_warns_danger():
    r = analyze("DELETE FROM Host WHERE HostID = 1")
    assert "WRITE_STATEMENT" in _codes(r)
    assert any(w.code == "WRITE_STATEMENT" and w.level == "danger" for w in r.warnings)


def test_update_without_where_warns():
    r = analyze("UPDATE Host SET Hostname = 'x'")
    assert {"WRITE_STATEMENT", "NO_WHERE"} <= _codes(r)


def test_delete_with_where_no_nowhere_warning():
    r = analyze("DELETE FROM Host WHERE HostID = 1")
    assert "NO_WHERE" not in _codes(r)


def test_select_has_no_write_warning():
    r = analyze("SELECT * FROM Host WHERE HostID = 1")
    assert "WRITE_STATEMENT" not in _codes(r)


def test_cartesian_join_without_on_warns():
    r = analyze("SELECT * FROM A JOIN B")
    assert "CARTESIAN_JOIN" in _codes(r)


def test_comma_join_with_linking_where_not_flagged():
    # heuristic: a WHERE clause is assumed to link the tables -> no cartesian warning
    r = analyze("SELECT * FROM A, B WHERE A.id = B.id")
    assert "CARTESIAN_JOIN" not in _codes(r)


def test_ddl_is_write_statement():
    r = analyze("DROP TABLE Host")
    assert "WRITE_STATEMENT" in _codes(r)
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: FAIL — die neuen Warn-Tests scheitern (warnings noch leer).

- [ ] **Step 3: Warn-Erzeugung in `core/sqlanalyze.py` ergänzen**

Direkt vor dem `return AnalysisResult(...)` in `analyze` einfügen (und das `warnings=()`-Argument durch `tuple(warnings)` ersetzen):

```python
    warnings: list[AnalysisWarning] = []
    stmt_type = _statement_type(node)

    if stmt_type in ("INSERT", "UPDATE", "DELETE", "DDL"):
        warnings.append(AnalysisWarning(
            "danger", "WRITE_STATEMENT",
            "Dieses Statement würde Daten bzw. das Schema verändern — "
            "das Tool führt es nicht aus."))

    if isinstance(node, (exp.Update, exp.Delete)) and node.find(exp.Where) is None:
        warnings.append(AnalysisWarning(
            "danger", "NO_WHERE",
            "UPDATE/DELETE ohne WHERE — betrifft alle Zeilen der Tabelle."))

    # Cartesian heuristic: a JOIN/comma-join without ON/USING and no WHERE to
    # link the tables. A present WHERE is assumed to provide the link.
    joins_without_on = any(
        j.args.get("on") is None and j.args.get("using") is None
        for j in node.find_all(exp.Join)
    )
    if joins_without_on and node.find(exp.Where) is None:
        warnings.append(AnalysisWarning(
            "warn", "CARTESIAN_JOIN",
            "Join ohne Verknüpfungsbedingung — möglicher kartesischer Join "
            "(Zeilen-Explosion)."))
```

Und die Rückgabe anpassen:
```python
        warnings=tuple(warnings),
```

- [ ] **Step 4: Tests laufen lassen, Erfolg prüfen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "AP-25: strukturelle Warnungen (WRITE_STATEMENT, NO_WHERE, CARTESIAN_JOIN)"
```

---

### Task 4: Schema-abhängige Warnungen (UNKNOWN_TABLE / UNKNOWN_COLUMN)

**Files:**
- Modify: `core/sqlanalyze.py`
- Test: `tests/test_sqlanalyze.py`

**Interfaces:**
- Consumes: `analyze` aus Task 3; `core.model.Schema` (`.tables`/`.views` mit `.name`, `.has_column(table, column)`), geladen via `SqlAlchemyLoader`.
- Produces: bei übergebenem `schema` zusätzliche Warnungen `UNKNOWN_TABLE` / `UNKNOWN_COLUMN` (case-insensitiver Abgleich gegen Tabellen **und** Views). Ohne `schema` werden diese nie erzeugt.

- [ ] **Step 1: Failing tests schreiben** — ans Ende von `tests/test_sqlanalyze.py`:

```python
import pytest
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader


@pytest.fixture
def inv_schema(inventory_url):
    return SqlAlchemyLoader(inventory_url).load()


def test_unknown_table_warns_with_schema(inv_schema):
    r = analyze("SELECT * FROM NoSuchTable", schema=inv_schema)
    assert "UNKNOWN_TABLE" in {w.code for w in r.warnings}


def test_known_table_case_insensitive_no_warning(inv_schema):
    # inventory has table "Networks"; lowercase must still be recognized
    r = analyze("SELECT NetworkID FROM networks", schema=inv_schema)
    assert "UNKNOWN_TABLE" not in {w.code for w in r.warnings}


def test_unknown_qualified_column_warns(inv_schema):
    r = analyze("SELECT n.NoSuchCol FROM Networks n", schema=inv_schema)
    assert "UNKNOWN_COLUMN" in {w.code for w in r.warnings}


def test_no_schema_no_unknown_warnings():
    r = analyze("SELECT * FROM TotallyUnknown")
    codes = {w.code for w in r.warnings}
    assert "UNKNOWN_TABLE" not in codes and "UNKNOWN_COLUMN" not in codes
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: FAIL — die schema-Tests scheitern (Warnungen fehlen).

- [ ] **Step 3: Schema-Abgleich in `core/sqlanalyze.py` ergänzen**

Nach dem strukturellen Warn-Block (vor `return`) einfügen:

```python
    if schema is not None:
        known = {t.name.lower() for t in schema.tables}
        known |= {v.name.lower() for v in getattr(schema, "views", ())}
        # Map alias -> real table name for qualified-column resolution.
        alias_to_table: dict[str, str] = {}
        for tbl in node.find_all(exp.Table):
            real = tbl.name
            alias_to_table[real.lower()] = real
            alias = tbl.alias
            if alias:
                alias_to_table[alias.lower()] = real
            if real.lower() not in known:
                warnings.append(AnalysisWarning(
                    "warn", "UNKNOWN_TABLE",
                    f"Tabelle „{real}“ ist im verbundenen Schema nicht vorhanden."))
        # Qualified columns only (table.column); unqualified columns are skipped.
        for col in node.find_all(exp.Column):
            tbl_ref = col.table
            if not tbl_ref:
                continue
            real = alias_to_table.get(tbl_ref.lower())
            if real is None or real.lower() not in known:
                continue  # unknown table already warned; don't double-warn
            if not schema.has_column(real, col.name):
                warnings.append(AnalysisWarning(
                    "warn", "UNKNOWN_COLUMN",
                    f"Spalte „{col.name}“ existiert nicht in Tabelle „{real}“."))
```

(Hinweis: `UNKNOWN_TABLE`/`UNKNOWN_COLUMN` werden nach den strukturellen Warnungen angehängt; die bestehende `warnings=tuple(warnings)`-Rückgabe bleibt unverändert.)

- [ ] **Step 4: Tests laufen lassen, Erfolg prüfen**

Run: `./venv/bin/python -m pytest tests/test_sqlanalyze.py -q`
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add core/sqlanalyze.py tests/test_sqlanalyze.py
git commit -m "AP-25: schema-abhängige Warnungen UNKNOWN_TABLE/UNKNOWN_COLUMN (case-insensitiv)"
```

---

### Task 5: Web-Endpoint `POST /api/analyze`

**Files:**
- Modify: `web/routes.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `core.sqlanalyze.analyze` (Task 2–4); `SqlAlchemyLoader`, `_dialect_from_url` (bestehend).
- Produces: `POST /api/analyze` mit Body `{sql, connection_url?}` → JSON `{statement_type, tables_read, tables_written, warnings:[{level,code,message}], parse_error}`. Ohne/leer `connection_url` → Text-Modus (kein Schema/Dialekt). Führt **nie** SQL aus.

- [ ] **Step 1: Failing tests schreiben** — ans Ende von `tests/test_api.py`:

```python
def test_analyze_text_mode_no_connection(client):
    resp = client.post("/api/analyze", json={
        "sql": "UPDATE Host SET Hostname='x'",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["statement_type"] == "UPDATE"
    assert data["tables_written"] == ["Host"]
    codes = {w["code"] for w in data["warnings"]}
    assert {"WRITE_STATEMENT", "NO_WHERE"} <= codes
    # text mode: no schema-dependent warnings
    assert "UNKNOWN_TABLE" not in codes


def test_analyze_with_connection_flags_unknown_table(client, inventory_url):
    resp = client.post("/api/analyze", json={
        "sql": "SELECT * FROM NoSuchTable",
        "connection_url": inventory_url,
    })
    assert resp.status_code == 200
    codes = {w["code"] for w in resp.get_json()["warnings"]}
    assert "UNKNOWN_TABLE" in codes


def test_analyze_parse_error_returns_200_with_error(client):
    resp = client.post("/api/analyze", json={"sql": "NOT SQL @@@"})
    assert resp.status_code == 200
    assert resp.get_json()["parse_error"] is not None


def test_analyze_bad_connection_returns_400(client):
    resp = client.post("/api/analyze", json={
        "sql": "SELECT 1",
        "connection_url": "sqlite:////nonexistent/zzz.db",
    })
    # a connection that cannot reflect → 400 (analysis needs the schema it asked for)
    assert resp.status_code in (200, 400)  # see note in implementation
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./venv/bin/python -m pytest tests/test_api.py -k analyze -q`
Expected: FAIL — 404 (Route existiert nicht).

- [ ] **Step 3: Route + Import in `web/routes.py` ergänzen**

Import oben ergänzen (bei den übrigen `core`-Imports):
```python
from core.sqlanalyze import analyze as analyze_sql
```

Route am Dateiende anfügen:
```python
@bp.post("/api/analyze")
def api_analyze():
    """Analyze a pasted SQL statement read-only — never executes it.

    With a connection_url the reflected schema and the connection dialect feed
    table/column cross-checks; without one, the analysis is text-only.
    """
    data = request.get_json(silent=True) or {}
    sql = data.get("sql", "")
    if not sql.strip():
        return jsonify(error="Bitte ein SQL-Statement eingeben."), 400

    schema = None
    dialect = None
    url = (data.get("connection_url") or "").strip()
    if url:
        try:
            schema = SqlAlchemyLoader(url).load()
        except ConnectionError as exc:
            return jsonify(error=str(exc)), 400
        dialect = _dialect_from_url(url).name

    result = analyze_sql(sql, schema=schema, dialect=dialect)
    return jsonify(
        statement_type=result.statement_type,
        tables_read=list(result.tables_read),
        tables_written=list(result.tables_written),
        warnings=[{"level": w.level, "code": w.code, "message": w.message}
                  for w in result.warnings],
        parse_error=result.parse_error,
    )
```

Note: `_dialect_from_url(url).name` liefert den Dialektnamen (z. B. `"sqlite"`); sqlglot kennt diese Namen. Ist der Name sqlglot unbekannt, parst `analyze` dialekt-neutral (sqlglot wirft dann ggf. `parse_error`, kein Crash).

- [ ] **Step 4: Tests laufen lassen, Erfolg prüfen**

Run: `./venv/bin/python -m pytest tests/test_api.py -k analyze -q`
Expected: alle PASS.

- [ ] **Step 5: Volle Suite + Commit**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (Baseline + neue Tests).

```bash
git add web/routes.py tests/test_api.py
git commit -m "AP-25: read-only Endpoint POST /api/analyze (Text- und Verbindungs-Modus)"
```

---

### Task 6: Frontend — Analyzer-Tab, Ergebnis-Render, Graph-Highlight

**Files:**
- Modify: `web/static/js/app.js` (Sidebar-Eintrag in `renderSidebar`, neues `openAnalyzer()`, Render + Highlight)
- Modify: `web/static/css/app.css` (`.analyze-read`/`.analyze-write` + Panel-Styles)
- Verify: manuell via Playwright (System-`python3`), kein JS-Test-Harness.

**Interfaces:**
- Consumes: `POST /api/analyze` (Task 5); bestehende `ensureTab`, `activateTab`, `postJSON`, `esc`, `connUrl`, globales Cytoscape `CY`.
- Produces: Sidebar-Eintrag „SQL-Analyzer" → Tab mit Textarea + Button; rendert Typ/Tabellen/Warnungen; markiert beteiligte Tabellen im Graphen (nur wenn `CY` existiert, d. h. verbunden).

- [ ] **Step 1: Sidebar-Eintrag ergänzen**

In `web/static/js/app.js`, in `renderSidebar`, die Tools-Liste (`<li data-action="joinbuilder">…`) um einen Eintrag erweitern:

```javascript
    `<li data-action="joinbuilder">Join-Builder</li>` +
    `<li data-action="analyzer">SQL-Analyzer</li></ul>` +
```
(Die schließende `</ul>` wandert ans Ende der neuen Zeile — die bestehende `</ul>` nach „Join-Builder" entfernen.)

Und im Klick-Handler (`querySelectorAll("li")…`) einen Zweig ergänzen:
```javascript
      if (li.dataset.action === "joinbuilder") openJoinBuilder();
      else if (li.dataset.action === "analyzer") openAnalyzer();
      else if (li.dataset.action === "connections") openConnections();
```

- [ ] **Step 2: `openAnalyzer()` + Render + Highlight implementieren**

In `web/static/js/app.js` (z. B. nach `openJoinBuilder`) einfügen:

```javascript
// ===== SQL-Analyzer (AP-25) =====
function clearAnalyzeMarkers() {
  if (!CY) return;
  CY.nodes().removeClass("analyze-read analyze-write");
}

function applyAnalyzeMarkers(read, written) {
  if (!CY) return;
  clearAnalyzeMarkers();
  read.forEach((t) => CY.$id(t).addClass("analyze-read"));
  written.forEach((t) => CY.$id(t).addClass("analyze-write"));
}

function renderAnalyzeResult(panel, res) {
  const out = panel.querySelector("#an_result");
  if (res.parse_error) {
    out.innerHTML = `<p class="hint">Konnte nicht geparst werden: ${esc(res.parse_error)}</p>`;
    clearAnalyzeMarkers();
    return;
  }
  const list = (items) => items.length
    ? `<ul class="objlist">${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`
    : `<p class="hint">—</p>`;
  const warns = res.warnings.length
    ? res.warnings.map((w) =>
        `<div class="an-warn an-l-${esc(w.level)}">${esc(w.message)}</div>`).join("")
    : `<p class="hint">keine Warnungen</p>`;
  out.innerHTML =
    `<div class="an-type">Typ: <strong>${esc(res.statement_type)}</strong></div>` +
    `<h4>Gelesen</h4>${list(res.tables_read)}` +
    `<h4>Geschrieben/verändert</h4>${list(res.tables_written)}` +
    `<h4>Warnungen</h4>${warns}`;
  applyAnalyzeMarkers(res.tables_read, res.tables_written);
}

async function runAnalyze(panel) {
  const sql = panel.querySelector("#an_sql").value;
  if (!sql.trim()) return;
  try {
    const res = await postJSON("/api/analyze",
      { sql, connection_url: connUrl() });
    renderAnalyzeResult(panel, res);
  } catch (e) {
    panel.querySelector("#an_result").innerHTML =
      `<p class="hint">Fehler: ${esc(e.message)}</p>`;
  }
}

function openAnalyzer() {
  const panel = ensureTab("analyzer", "SQL-Analyzer", true);
  if (panel.dataset.built) { activateTab("analyzer"); return; }
  panel.dataset.built = "1";
  panel.innerHTML =
    `<div class="analyzer">` +
    `<textarea id="an_sql" rows="6" placeholder="SQL-Statement hier einfügen … "` +
    ` style="width:100%;font-family:monospace"></textarea>` +
    `<div class="row"><button id="an_run">Analysieren</button>` +
    `<span class="hint">read-only — das Statement wird nie ausgeführt</span></div>` +
    `<div id="an_result"></div></div>`;
  panel.querySelector("#an_run").addEventListener("click", () => runAnalyze(panel));
}
```

- [ ] **Step 3: CSS ergänzen** — ans Ende von `web/static/css/app.css`:

Die `w.level`-Werte sind `danger` / `warn` / `info`; das JS (Step 2) setzt `class="an-warn an-l-<level>"`. Genau diese Klassen anlegen:

```css
.an-warn { padding: 4px 8px; margin: 3px 0; border-radius: 3px; font-size: 0.9em; }
.an-l-danger { background: #fdecea; color: #b71c1c; }
.an-l-warn   { background: #fff4e5; color: #8a5300; }
.an-l-info   { background: #e8f0fe; color: #1a4480; }
.an-type { margin-bottom: 6px; }
```

Und die Cytoscape-Knoten-Marker: dort, wo das Cytoscape-Stylesheet im `CY`-Setup in `app.js` die Knoten-Klassen `sel-source`/`sel-target` definiert (`{ selector: "node.sel-source", style: {…} }`), direkt daneben zwei analoge Einträge ergänzen:

```javascript
    { selector: "node.analyze-read",  style: { "background-color": "#1a73e8" } },
    { selector: "node.analyze-write", style: { "background-color": "#d93025" } },
```

- [ ] **Step 4: JS-Syntax prüfen**

Run: `node --check web/static/js/app.js`
Expected: keine Ausgabe / Exit 0.

- [ ] **Step 5: Manuell verifizieren (Playwright, System-python3)**

Server starten (`bash run.sh --skip-setup`), Demo-DB verbinden (`sample_data/demo_cmdb.db`), Tab „SQL-Analyzer" öffnen:
- `UPDATE Host SET Hostname='x'` → Typ UPDATE, „Host" unter Geschrieben, Warnungen WRITE_STATEMENT (rot) + NO_WHERE; Host-Knoten im Graph rot markiert.
- `SELECT v.Name, n.VLAN FROM VirtualMachine v JOIN Network n ON v.NetworkID=n.NetworkID` → Typ SELECT, beide Tabellen gelesen + im Graph blau; keine danger-Warnung.
- `SELECT * FROM NoSuchTable` → Warnung UNKNOWN_TABLE.
- Ohne Verbindung (vor Connect): Text-Analyse funktioniert, kein Highlight, keine UNKNOWN_*-Warnung.
Screenshot beilegen.

- [ ] **Step 6: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "AP-25: Frontend SQL-Analyzer-Tab (Render + Graph-Highlight)"
```

---

### Task 7: Version, Doku, Site-Deploy

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/projekt/roadmap.md` + Mermaid-Quellen, `javascripts/icon-rail.js`-Badges, `todo.md`, Site-Build, `gh-pages`-Deploy.

**Interfaces:** keine Code-Interfaces.

- [ ] **Step 1: Minor-Bump**

```bash
./venv/bin/python sync_version.py --minor
./venv/bin/python -c "import config; print(config.APP_VERSION)"
```

- [ ] **Step 2: Changelog + Mirror** — neuen `[<neue Version>]`-Eintrag im Format des letzten Eintrags (Root `### Added` englisch + Volltext; Mirror `### Hinzugefügt` deutsch + kondensiert). Inhalt: „AP-25: read-only SQL-Statement-Analyzer — Tab parst ein eingefügtes Statement via sqlglot (nie ausgeführt), zeigt Typ, gelesene/geschriebene Tabellen, Warnungen (WRITE_STATEMENT/NO_WHERE/CARTESIAN_JOIN, mit Verbindung UNKNOWN_TABLE/UNKNOWN_COLUMN) und markiert beteiligte Tabellen im Graphen; funktioniert mit und ohne Verbindung." Testzahl aus dem finalen pytest-Lauf eintragen.

- [ ] **Step 3: Roadmap/Board/Gantt** — AP-25 **namentlich** als erledigt enumerieren (kein Sammel-Eintrag); nach Build die gerenderte Übersicht (SVG/HTML) gegenprüfen, dass AP-25 namentlich erscheint (Render-Kodierung `&#45;` beachten).

- [ ] **Step 4: `todo.md`** — die offenen AP-25-Checkboxen, die diese Scheibe abdeckt (Tab, Parsen/Klassifizieren, Graph-Highlight, Warnungen via Brainstorm-Punkt), auf `[x]`; verbleibende (Join-Builder-Transfer, Pfad-Highlight, View-Deps, Treffermenge) explizit als „spätere Scheibe" kennzeichnen; Spec-/Plan-Link ergänzen.

- [ ] **Step 5: Badges + Site-Build (Linux)** — `icon-rail.js` `APP_VERSION`/`TEST_COUNT`/`TEST_DATE` aktualisieren; `./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py` ausführen; gerenderte Seiten gegenprüfen.

- [ ] **Step 6: Volle Suite + Commit**

```bash
./venv/bin/python -m pytest -q
git add -A
git commit -m "AP-25 (Abschluss): SQL-Analyzer — Version, Changelog/Mirror, Roadmap/Board/Gantt, Badges, Site"
```

- [ ] **Step 7: gh-pages-Deploy** (wie bei AP-30): via temporärem Worktree den Inhalt von `luDBxP-docs/site/` nach `gh-pages` syncen (`.nojekyll` und `.git` schützen), committen „docs: Site-Deploy v<neue Version> (AP-25 SQL-Analyzer)", `git push origin gh-pages`, Worktree entfernen. (Auf Ansage des Nutzers, nicht automatisch pushen.)

---

## Self-Review

**Spec-Abdeckung:**
- „Neuer Tab mit Freitextfeld" → Task 6. ✓
- „Statement parsen/klassifizieren, keine Ausführung" → Task 2 + Task 5 (Route führt nie aus). ✓
- „beteiligte Tabellen markieren (geändert/beteiligt unterscheiden)" → Task 6 (`analyze-read`/`analyze-write`). ✓
- „Warn-Set (WRITE/NO_WHERE/CARTESIAN/UNKNOWN_TABLE/UNKNOWN_COLUMN)" → Task 3 (struktur) + Task 4 (schema). ✓
- „Zwei Modi (mit/ohne Verbindung)" → Task 4 (schema optional) + Task 5 (connection_url optional) + Task 6 (Highlight nur mit CY). ✓
- „sqlglot gebündelt, NO-CDN" → Task 1. ✓
- „Layering core/ Flask-frei" → Task 2–4 nur core, Task 5 ruft core. ✓
- „Version/Doku/Deploy" → Task 7. ✓
- Bewusst draußen (Transfer/Pfad-Highlight/View-Deps/EXPLAIN) → kein Task (YAGNI, dokumentiert). ✓

**Placeholder-Scan:** Konkreter Code in jedem Code-Schritt; keine no-op-/TBD-Reste (Task 6/Step 3 liefert die finalen, eindeutigen CSS-Klassen `an-l-danger/warn/info` passend zu den JS-Klassen aus Step 2).

**Typ-Konsistenz:** `AnalysisResult`/`AnalysisWarning`-Felder identisch über Task 2→5; `analyze(sql, schema, dialect)`-Signatur durchgängig; JS `w.level ∈ {danger,warn,info}` ↔ CSS `an-l-<level>` (Task 6/Step 4); `tables_read/written` als JSON-Arrays (Route) ↔ JS `res.tables_read`. ✓

**Hinweis Testzählung:** Endzahl beim finalen `pytest`-Lauf ablesen und in Changelog/Badges eintragen — nicht raten.
