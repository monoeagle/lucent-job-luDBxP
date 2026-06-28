# AP-56a — Subset-Footprint + Export-Skelett Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Schema-basiertes Database-Subsetting: aus (Start-Tabelle, Wurzel-Filter) die referenzielle FK-Hülle (down-then-up) berechnen und je Tabelle ein parametrisiertes SELECT erzeugen, das zur Wurzel zurück-joint. Führt nichts aus.

**Architecture:** Neues pures Modul `core/subset.py` baut gerichtete FK-Adjazenz aus dem `Schema`, berechnet die down-then-up-Closure als Ableitungsbaum (mit Zyklus-Schutz + Tiefenlimit) und rendert je Closure-Tabelle ein SELECT (Reuse `core.sqlgen.Dialect`). Ein read-only Endpoint `/api/subset` und ein UI-Modus „Entität exportieren" hängen sich an die bestehenden Muster an.

**Tech Stack:** Python 3.10+ (pures `core/`), Flask-Route, Vanilla JS, pytest + Playwright-Smoke.

**Spec:** `docs/superpowers/specs/2026-06-28-ap56a-subset-footprint-design.md`

## Global Constraints

- **Layering:** `core/` importiert **nie** Flask. `web/`→`core/`, nie umgekehrt.
- **Read-only:** AP-56a **führt nichts aus** — reine String-/Struktur-Erzeugung. Nie INSERT/UPDATE/DDL.
- **NO CDN:** keine externen `<script>`/`<link>`. UI nutzt bestehende CSS-Klassen, kein neues CSS außer minimal nötigem.
- **UI-Texte Deutsch.**
- **Version:** `config.APP_VERSION` nie von Hand — nur via `./venv/bin/python sync_version.py --minor`.
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14). Baseline vor Start: **338 passed, 2 skipped**.
- **Reuse:** SQL-Quoting/Qualifizierung über `core.sqlgen.Dialect` (`quote`/`table_ref`/`qualify`); Dialect-Auswahl wie `/api/joinpath` (`dialect_for(data["dialect"])` bzw. `_dialect_from_url(url)`).
- **Branch:** `ap-56a-subset` (bereits angelegt, Spec committet `ad0a5ea`).

---

### Task 1: Core — down-then-up-Closure (`core/subset.py`)

**Files:**
- Create: `core/subset.py`
- Test: `tests/test_subset.py`

**Interfaces:**
- Consumes: `core.model.Schema/Table/Column/ForeignKey`, `core.implied.find_implied_fks`.
- Produces:
  - `SubsetEdge(via_table, pairs, child_table, kind)` — `pairs: tuple[tuple[str,str],...]` = (child_local_col, parent_ref_col); `child_table` = welche der beiden Tabellen die FK-Seite hält; `kind ∈ {"child","parent","root"}`.
  - `SubsetTable(name, edge, depth)` — `edge: SubsetEdge | None` (None nur für root).
  - `SubsetResult(start, tables, truncated)` — `tables` topologisch sortiert (Eltern vor Kindern).
  - `compute_subset(schema, start_table, *, include_implied=False, max_depth=5) -> SubsetResult`.

- [ ] **Step 1: Failing-Tests schreiben**

Create `tests/test_subset.py`:
```python
from core.model import Schema, Table, Column, ForeignKey
from core.subset import compute_subset


def _t(name, cols, fks=(), pk=()):
    return Table(name, tuple(Column(c, "INTEGER") for c in cols), tuple(fks), primary_key=tuple(pk))


# Schema: Country<-Customer<-Order<-LineItem->Product ; plus lookups' other children
# that must NOT be pulled (no re-descent): Region (child of Country), Inventory (child of Product).
def _shop_schema(extra=()):
    tables = [
        _t("Country", ["code", "name"], pk=["code"]),
        _t("Customer", ["id", "country_code"],
           [ForeignKey.single("country_code", "Country", "code")], pk=["id"]),
        _t("Order", ["id", "customer_id"],
           [ForeignKey.single("customer_id", "Customer", "id")], pk=["id"]),
        _t("Product", ["id"], pk=["id"]),
        _t("LineItem", ["id", "order_id", "product_id"],
           [ForeignKey.single("order_id", "Order", "id"),
            ForeignKey.single("product_id", "Product", "id")], pk=["id"]),
        _t("Region", ["id", "country_code"],
           [ForeignKey.single("country_code", "Country", "code")], pk=["id"]),
        _t("Inventory", ["id", "product_id"],
           [ForeignKey.single("product_id", "Product", "id")], pk=["id"]),
    ]
    return Schema(tuple(tables) + tuple(extra))


def test_downward_collects_children_recursively():
    r = compute_subset(_shop_schema(), "Customer")
    names = {t.name for t in r.tables}
    assert {"Order", "LineItem"} <= names


def test_upward_collects_lookups_of_start_and_children():
    r = compute_subset(_shop_schema(), "Customer")
    by = {t.name: t for t in r.tables}
    assert by["Country"].edge.kind == "parent"   # lookup of Customer
    assert by["Product"].edge.kind == "parent"   # lookup of LineItem


def test_down_then_up_no_redescent():
    # Country and Product are lookups (upward); their OTHER children must NOT be pulled.
    r = compute_subset(_shop_schema(), "Customer")
    names = {t.name for t in r.tables}
    assert "Region" not in names
    assert "Inventory" not in names


def test_root_has_no_edge_and_child_kinds_recorded():
    r = compute_subset(_shop_schema(), "Customer")
    by = {t.name: t for t in r.tables}
    assert by["Customer"].edge is None
    assert by["Order"].edge.kind == "child" and by["Order"].edge.via_table == "Customer"
    assert by["LineItem"].edge.kind == "child" and by["LineItem"].edge.via_table == "Order"


def test_topological_order_parents_before_children():
    order = [t.name for t in compute_subset(_shop_schema(), "Customer").tables]
    assert order.index("Country") < order.index("Customer")
    assert order.index("Customer") < order.index("Order")
    assert order.index("Order") < order.index("LineItem")
    assert order.index("Product") < order.index("LineItem")


def test_cycle_terminates():
    schema = Schema((
        _t("A", ["id", "b_id"], [ForeignKey.single("b_id", "B", "id")], pk=["id"]),
        _t("B", ["id", "a_id"], [ForeignKey.single("a_id", "A", "id")], pk=["id"]),
    ))
    names = {t.name for t in compute_subset(schema, "A").tables}
    assert names == {"A", "B"}


def test_self_fk_terminates():
    schema = Schema((
        _t("Employee", ["id", "manager_id"],
           [ForeignKey.single("manager_id", "Employee", "id")], pk=["id"]),
    ))
    names = {t.name for t in compute_subset(schema, "Employee").tables}
    assert names == {"Employee"}


def test_depth_limit_truncates_downward():
    schema = Schema((
        _t("R", ["id"], pk=["id"]),
        _t("C1", ["id", "r_id"], [ForeignKey.single("r_id", "R", "id")], pk=["id"]),
        _t("C2", ["id", "c1_id"], [ForeignKey.single("c1_id", "C1", "id")], pk=["id"]),
        _t("C3", ["id", "c2_id"], [ForeignKey.single("c2_id", "C2", "id")], pk=["id"]),
    ))
    r = compute_subset(schema, "R", max_depth=2)
    names = {t.name for t in r.tables}
    assert "C3" not in names and "C2" in names
    assert r.truncated is True


def test_implied_only_with_toggle():
    # Order.kunde references Kunde by name (no declared FK).
    schema = Schema((
        _t("Kunde", ["id"], pk=["id"]),
        Table("Bestellung",
              (Column("id", "INTEGER"), Column("kunde_id", "INTEGER")),
              (), primary_key=("id",)),
    ))
    assert "Bestellung" not in {t.name for t in compute_subset(schema, "Kunde").tables}
    assert "Bestellung" in {t.name for t in compute_subset(schema, "Kunde", include_implied=True).tables}


def test_unknown_start_table_raises():
    import pytest
    with pytest.raises(ValueError):
        compute_subset(_shop_schema(), "Nope")
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_subset.py -q`
Expected: FAIL — `ModuleNotFoundError: core.subset`.

- [ ] **Step 3: `core/subset.py` schreiben (Closure-Teil)**

Create `core/subset.py`:
```python
"""Schema-level database subsetting (AP-56a): the referential footprint of an
entity. Pure schema logic — executes nothing. The live data-driven walk is AP-56b.

Closure rule (Jailer-style "down-then-up"): from the start table, collect
dependents downward via reverse foreign keys (children), then collect the
lookups those rows need upward via foreign keys (parents) WITHOUT descending
again — this keeps the subset referentially complete without exploding.
"""
import heapq
from collections import deque
from dataclasses import dataclass

from core.model import Schema


@dataclass(frozen=True)
class SubsetEdge:
    via_table: str                          # predecessor in the derivation tree
    pairs: tuple[tuple[str, str], ...]      # (child_local_col, parent_ref_col)
    child_table: str                        # which endpoint holds the FK (child side)
    kind: str                               # "child" | "parent" | "root"


@dataclass(frozen=True)
class SubsetTable:
    name: str
    edge: "SubsetEdge | None"               # None only for the root table
    depth: int


@dataclass(frozen=True)
class SubsetResult:
    start: str
    tables: tuple[SubsetTable, ...]         # topologically sorted (parents first)
    truncated: bool


def _adjacency(schema: Schema, include_implied: bool):
    """Directed FK adjacency. Returns (parents_of, children_of), each
    table -> list of (other_table, pairs) where pairs are (child_local, parent_ref)."""
    parents_of: dict[str, list] = {t.name: [] for t in schema.tables}
    children_of: dict[str, list] = {t.name: [] for t in schema.tables}

    def add(child: str, parent: str, pairs):
        parents_of.setdefault(child, []).append((parent, pairs))
        children_of.setdefault(parent, []).append((child, pairs))

    for t in schema.tables:
        for fk in t.foreign_keys:
            add(t.name, fk.ref_table, fk.column_pairs)
    if include_implied:
        from core.implied import find_implied_fks
        for ifk in find_implied_fks(schema):
            add(ifk.table, ifk.ref_table, ((ifk.column, ifk.ref_column),))
    return parents_of, children_of


def _toposort(names: set, parents_of) -> list:
    """Parents before children, stable by name; cycle leftovers appended by name."""
    indeg = {n: 0 for n in names}
    adj: dict[str, set] = {n: set() for n in names}
    for child in names:
        for parent, _ in parents_of.get(child, []):
            if parent in names and parent != child and child not in adj[parent]:
                adj[parent].add(child)
                indeg[child] += 1
    heap = [n for n in names if indeg[n] == 0]
    heapq.heapify(heap)
    order: list = []
    while heap:
        n = heapq.heappop(heap)
        order.append(n)
        for c in sorted(adj[n]):
            indeg[c] -= 1
            if indeg[c] == 0:
                heapq.heappush(heap, c)
    order.extend(sorted(n for n in names if n not in order))
    return order


def compute_subset(schema: Schema, start_table: str, *,
                   include_implied: bool = False, max_depth: int = 5) -> SubsetResult:
    """Compute the referential footprint of ``start_table`` (down-then-up)."""
    known = {t.name for t in schema.tables}
    if start_table not in known:
        raise ValueError(f"unknown table: {start_table}")
    parents_of, children_of = _adjacency(schema, include_implied)

    # table -> (edge | None, depth). Root first.
    deriv: dict[str, tuple] = {start_table: (None, 0)}
    truncated = False

    # Phase 1: downward (dependents) — depth-limited.
    dq = deque([(start_table, 0)])
    downward = [start_table]
    while dq:
        cur, d = dq.popleft()
        if d >= max_depth:
            if children_of.get(cur):
                truncated = True
            continue
        for child, pairs in children_of.get(cur, []):
            if child not in known or child in deriv:
                continue
            deriv[child] = (SubsetEdge(cur, pairs, child, "child"), d + 1)
            downward.append(child)
            dq.append((child, d + 1))

    # Phase 2: upward (lookups) from root ∪ downward — no re-descent, unbounded
    # (referential completeness; the visited guard keeps it finite).
    dq = deque((t, deriv[t][1]) for t in downward)
    while dq:
        cur, d = dq.popleft()
        for parent, pairs in parents_of.get(cur, []):
            if parent not in known or parent in deriv:
                continue
            deriv[parent] = (SubsetEdge(cur, pairs, cur, "parent"), d + 1)
            dq.append((parent, d + 1))

    order = _toposort(set(deriv), parents_of)
    tables = tuple(
        SubsetTable(name, deriv[name][0], deriv[name][1]) for name in order
    )
    return SubsetResult(start_table, tables, truncated)
```

- [ ] **Step 4: Tests laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_subset.py -q`
Expected: PASS (10 Tests).

- [ ] **Step 5: Volle Suite**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -1`
Expected: `348 passed, 2 skipped` (338 + 10 neue).

- [ ] **Step 6: Commit**

```bash
git add core/subset.py tests/test_subset.py
git commit -m "feat: AP-56a — down-then-up Subset-Closure (core/subset.py)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Core — SELECT-Skelett (`generate_subset_sql`)

**Files:**
- Modify: `core/subset.py` (anhängen)
- Test: `tests/test_subset.py` (anhängen)

**Interfaces:**
- Consumes: `SubsetResult`/`SubsetTable`/`SubsetEdge` (Task 1), `core.sqlgen.Dialect`/`SQLITE`.
- Produces:
  - `SubsetScript(table: str, sql: str, params: dict)`.
  - `generate_subset_sql(schema, result, root_filter, *, dialect=SQLITE, schema_name="") -> tuple[SubsetScript, ...]` — `root_filter` ist `{"column": str, "op": str, "value": object}`; `op ∈ {=,!=,<,>,<=,>=,IN}`.

- [ ] **Step 1: Failing-Tests anhängen**

Am Ende von `tests/test_subset.py` anhängen:
```python
from core.subset import generate_subset_sql
from core.sqlgen import SQLITE


def _scripts(start="Customer", **kw):
    r = compute_subset(_shop_schema(), start)
    flt = kw.pop("flt", {"column": "id", "op": "=", "value": 5})
    return {s.table: s for s in generate_subset_sql(_shop_schema(), r, flt, **kw)}


def test_root_select_filters_on_root():
    s = _scripts()["Customer"]
    assert "FROM" in s.sql and "Customer" in s.sql
    assert ":root" in s.sql and s.params == {"root": 5}
    assert "DISTINCT" not in s.sql            # root has no parent edge


def test_child_select_joins_back_to_root_no_distinct():
    s = _scripts()["Order"]
    assert "JOIN" in s.sql and "Customer" in s.sql
    assert "DISTINCT" not in s.sql            # pure downward path
    assert s.sql.rstrip().endswith(":root;") or ":root" in s.sql


def test_parent_lookup_select_is_distinct():
    s = _scripts()["Country"]                 # upward lookup of Customer
    assert s.sql.lstrip().startswith("SELECT DISTINCT")
    assert "Customer" in s.sql                # joins through Customer back to root


def test_schema_qualification_when_given():
    r = compute_subset(_shop_schema(), "Customer")
    s = {x.table: x for x in generate_subset_sql(
        _shop_schema(), r, {"column": "id", "op": "=", "value": 1},
        dialect=SQLITE, schema_name="dbo")}["Order"]
    assert '"dbo"."Order"' in s.sql


def test_in_operator_expands_params():
    r = compute_subset(_shop_schema(), "Customer")
    s = {x.table: x for x in generate_subset_sql(
        _shop_schema(), r, {"column": "id", "op": "IN", "value": [1, 2, 3]})}["Customer"]
    assert "IN (" in s.sql
    assert s.params == {"root0": 1, "root1": 2, "root2": 3}


def test_bad_operator_raises():
    import pytest
    r = compute_subset(_shop_schema(), "Customer")
    with pytest.raises(ValueError):
        generate_subset_sql(_shop_schema(), r, {"column": "id", "op": "DROP", "value": 1})
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_subset.py -q`
Expected: FAIL — `ImportError: cannot import name 'generate_subset_sql'`.

- [ ] **Step 3: `generate_subset_sql` an `core/subset.py` anhängen**

Oben in `core/subset.py` den Import ergänzen:
```python
from core.sqlgen import Dialect, SQLITE
```
Am Ende von `core/subset.py` anhängen:
```python
_ALLOWED_OPS = {"=", "!=", "<", ">", "<=", ">=", "IN"}


@dataclass(frozen=True)
class SubsetScript:
    table: str
    sql: str
    params: dict


def _chain(table: str, edges: dict) -> list:
    """Tables from ``table`` up to the root, following derivation edges."""
    chain = [table]
    while edges[chain[-1]] is not None:
        chain.append(edges[chain[-1]].via_table)
    return chain


def generate_subset_sql(schema: Schema, result: SubsetResult, root_filter: dict, *,
                        dialect: Dialect = SQLITE, schema_name: str = "") -> tuple:
    """Render one parameterised SELECT per closure table, joining back to the
    root table along its derivation path and filtering by ``root_filter``.
    Executes nothing."""
    op = root_filter["op"]
    if op not in _ALLOWED_OPS:
        raise ValueError(f"unsupported operator: {op}")
    col = dialect.quote(root_filter["column"])
    if op == "IN":
        vals = root_filter["value"]
        if not isinstance(vals, (list, tuple)) or not vals:
            raise ValueError("IN requires a non-empty list value")
        keys = [f"root{i}" for i in range(len(vals))]
        params_template = dict(zip(keys, vals))
        where_tail = "IN (" + ", ".join(f":{k}" for k in keys) + ")"
    else:
        params_template = {"root": root_filter["value"]}
        where_tail = f"{op} :root"

    edges = {t.name: t.edge for t in result.tables}
    scripts = []
    for st in result.tables:
        chain = _chain(st.name, edges)                 # [T, via, …, root]
        chain_edges = [edges[chain[i]] for i in range(len(chain) - 1)]
        distinct = any(e.kind == "parent" for e in chain_edges)
        alias = {i: f"t{i}" for i in range(len(chain))}

        joins = []
        for i, e in enumerate(chain_edges):
            a, b = chain[i], chain[i + 1]              # a.edge points to b (via)
            child_alias = alias[i] if e.child_table == a else alias[i + 1]
            parent_alias = alias[i + 1] if e.child_table == a else alias[i]
            conds = " AND ".join(
                f"{child_alias}.{dialect.quote(lc)} = {parent_alias}.{dialect.quote(rc)}"
                for lc, rc in e.pairs
            )
            joins.append(f"JOIN {dialect.table_ref(b, schema_name)} {alias[i + 1]} ON {conds}")

        root_alias = alias[len(chain) - 1]
        select = "SELECT DISTINCT t0.*" if distinct else "SELECT t0.*"
        lines = [select, f"FROM {dialect.table_ref(chain[0], schema_name)} t0"]
        lines += joins
        lines.append(f"WHERE {root_alias}.{col} {where_tail}")
        scripts.append(SubsetScript(st.name, "\n".join(lines) + ";", dict(params_template)))
    return tuple(scripts)
```

- [ ] **Step 4: Tests laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_subset.py -q`
Expected: PASS (16 Tests).

- [ ] **Step 5: Commit**

```bash
git add core/subset.py tests/test_subset.py
git commit -m "feat: AP-56a — generate_subset_sql (SELECT je Tabelle, zur Wurzel gejoint)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Route — `/api/subset`

**Files:**
- Modify: `web/routes.py`
- Test: `tests/test_api.py` (anhängen)

**Interfaces:**
- Consumes: `compute_subset`, `generate_subset_sql` (Tasks 1/2); bestehende `SqlAlchemyLoader`, `dialect_for`, `_dialect_from_url`.
- Produces: `POST /api/subset` → `{start, truncated, tables:[{name,kind,via_table,depth}], scripts:[{table,sql,params}]}`.

- [ ] **Step 1: Failing-Route-Test anhängen**

Am Ende von `tests/test_api.py`:
```python
def test_subset_endpoint_returns_tables_and_scripts(client, inventory_url):
    resp = client.post("/api/subset", json={
        "connection_url": inventory_url, "start_table": "OperatingSystems",
        "root_filter": {"column": "OSID", "op": "=", "value": 1}})
    data = resp.get_json()
    assert resp.status_code == 200
    names = {t["name"] for t in data["tables"]}
    assert "OperatingSystems" in names and "VirtualMachines" in names   # child via OSID
    assert any(s["table"] == "VirtualMachines" and ":root" in s["sql"] for s in data["scripts"])


def test_subset_unknown_table_returns_400(client, inventory_url):
    resp = client.post("/api/subset", json={
        "connection_url": inventory_url, "start_table": "Nope",
        "root_filter": {"column": "x", "op": "=", "value": 1}})
    assert resp.status_code == 400
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_subset_endpoint_returns_tables_and_scripts -q`
Expected: FAIL — 404 (Route fehlt).

- [ ] **Step 3: Endpoint ergänzen**

In `web/routes.py` bei den `core`-Imports ergänzen:
```python
from core.subset import compute_subset, generate_subset_sql
```
Nach dem `api_joinpath`-Block (vor `@bp.post("/api/joinpath/run")`) einfügen:
```python
@bp.post("/api/subset")
def api_subset():
    """AP-56a: schema-level referential footprint + per-table SELECT skeleton.
    Read-only — generates SQL strings, executes nothing."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400

    start = (data.get("start_table") or "").strip()
    rf = data.get("root_filter") or {}
    include_implied = bool(data.get("include_implied", False))
    max_depth = int(data.get("max_depth") or 5)
    if not schema.has_column(start, rf.get("column", "")):
        return jsonify(error="unknown start table or column"), 400

    dialect = (dialect_for(data["dialect"]) if data.get("dialect")
               else _dialect_from_url(url))
    try:
        result = compute_subset(schema, start, include_implied=include_implied,
                                max_depth=max_depth)
        scripts = generate_subset_sql(schema, result, rf,
                                      dialect=dialect, schema_name=schema_name)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(
        start=result.start,
        truncated=result.truncated,
        tables=[{"name": t.name, "depth": t.depth,
                 "kind": t.edge.kind if t.edge else "root",
                 "via_table": t.edge.via_table if t.edge else None}
                for t in result.tables],
        scripts=[{"table": s.table, "sql": s.sql, "params": s.params}
                 for s in scripts],
    )
```

- [ ] **Step 4: Tests laufen lassen, Erfolg bestätigen**

Run: `./venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat: AP-56a — /api/subset (read-only Footprint + SELECT-Skelett)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Frontend — Modus „Entität exportieren"

**Files:**
- Modify: `web/static/js/app.js` (Sidebar `renderSidebar` + neuer `openSubset`)
- Smoke: `.superpowers/sdd/verify_subset.py` (neu)

**Interfaces:**
- Consumes: `/api/subset` (Task 3); bestehende Helfer `ensureTab`, `activateTab`, `postJSON`, `esc`, `connUrl`, `SCHEMA`, `currentSchemaName()` (falls vorhanden; sonst `""`).
- Produces: Sidebar-Eintrag + `openSubset()` mit Formular + Ergebnis-Render.

- [ ] **Step 1: Failing Browser-Smoke schreiben**

Create `.superpowers/sdd/verify_subset.py`:
```python
"""Browser smoke for AP-56a: the 'Entität exportieren' mode lists the closure
tables (root/child/parent) and renders one SELECT per table joined back to root."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5057/"
DB = "/home/meagle/Dokumente/_Projects/lucent-job-luDBxP/sample_data/demo_cmdb.db"
BOOT = """async (d)=>{const r=await postJSON('/api/connect',{db_type:'sqlite',filepath:d});setCurrentUrl(r.connection_url);await doConnect();return 1;}"""

results = []
def check(n, ok, d=""):
    results.append((n, ok)); print(("PASS" if ok else "FAIL"), n, ("- " + d) if d else "")

def launch(p):
    last = None
    for kw in ({"executable_path": "/usr/bin/chromium"}, {"executable_path": "/usr/bin/google-chrome"}, {}):
        try: return p.chromium.launch(headless=True, **kw)
        except Exception as e: last = e
    raise last

with sync_playwright() as p:
    b = launch(p); page = b.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.evaluate(BOOT, DB)
    page.wait_for_function("SCHEMA && SCHEMA.tables && SCHEMA.tables.length > 0", timeout=8000)

    page.evaluate("openSubset()")
    page.wait_for_selector("#tabpanels .subset", timeout=5000)
    check("subset panel opens", True)

    # pick the first table + its first column, submit
    ok = page.evaluate("""async () => {
        const t = SCHEMA.tables[0];
        document.querySelector('#sub_table').value = t.name;
        document.querySelector('#sub_table').dispatchEvent(new Event('change'));
        document.querySelector('#sub_col').value = t.columns[0].name;
        document.querySelector('#sub_val').value = '1';
        await runSubset();
        return true;
    }""")
    page.wait_for_selector("#sub_result .subtbl", timeout=5000)
    txt = page.eval_on_selector("#sub_result", "el => el.textContent")
    check("closure table list rendered", "root" in txt)
    sql = page.eval_on_selector("#sub_result", "el => el.textContent")
    check("SELECT skeleton rendered", "SELECT" in sql and "WHERE" in sql)

    real = [e for e in errors if "favicon" not in e.lower()]
    check("no console errors", not real, "; ".join(real[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
```

- [ ] **Step 2: App neu starten + Smoke laufen lassen, Fehlschlag bestätigen**

```bash
LUCENT_PORT=5057 bash run.sh --skip-setup   # laufende Instanz vorher beenden
```
Run: `python3 .superpowers/sdd/verify_subset.py`
Expected: FAIL — `openSubset` existiert noch nicht.

- [ ] **Step 3: Sidebar-Eintrag + `openSubset` ergänzen**

In `web/static/js/app.js`, in `renderSidebar`, die Analyzer-Listenzeile
```js
    `<li data-action="analyzer">SQL-Analyzer</li></ul>` +
```
ersetzen durch (Eintrag ergänzen):
```js
    `<li data-action="analyzer">SQL-Analyzer</li>` +
    `<li data-action="subset">Entität exportieren</li></ul>` +
```
Im Klick-Handler von `renderSidebar`, nach dem `analyzer`-Zweig
```js
      else if (li.dataset.action === "analyzer") openAnalyzer();
```
ergänzen:
```js
      else if (li.dataset.action === "subset") openSubset();
```
Direkt **nach** der Funktion `openAnalyzer` (vor dem nächsten `function`) einfügen:
```js
async function runSubset() {
  const out = $("sub_result");
  const start = $("sub_table").value;
  const col = $("sub_col").value;
  const payload = {
    connection_url: connUrl(), start_table: start,
    root_filter: { column: col, op: $("sub_op").value, value: $("sub_val").value },
    include_implied: $("sub_implied").checked,
  };
  out.innerHTML = "<p class='hint'>berechne…</p>";
  let res;
  try { res = await postJSON("/api/subset", payload); }
  catch (e) { out.innerHTML = `<p class='hint'>Fehler: ${esc(String(e))}</p>`; return; }
  const rows = res.tables.map((t) =>
    `<tr><td>${esc(t.name)}</td><td><span class="badge">${esc(t.kind)}</span></td>` +
    `<td>${esc(t.via_table || "")}</td><td>${t.depth}</td></tr>`).join("");
  const scripts = res.scripts.map((s) =>
    `<h4>${esc(s.table)}</h4><pre class="sql">${esc(s.sql)}</pre>`).join("");
  const trunc = res.truncated
    ? `<p class='hint'>Tiefenlimit erreicht — Hülle evtl. unvollständig.</p>` : "";
  out.innerHTML =
    `<table class="subtbl cols"><thead><tr><th>Tabelle</th><th>Rolle</th>` +
    `<th>via</th><th>Tiefe</th></tr></thead><tbody>${rows}</tbody></table>` +
    trunc + `<h3>Export-Skelett (read-only SELECTs)</h3>${scripts}`;
}

function fillSubsetColumns() {
  const t = (SCHEMA.tables || []).find((x) => x.name === $("sub_table").value);
  $("sub_col").innerHTML = (t ? t.columns : [])
    .map((c) => `<option>${esc(c.name)}</option>`).join("");
}

function openSubset() {
  const panel = ensureTab("subset", "Entität exportieren", true);
  if (panel.dataset.built) { activateTab("subset"); return; }
  panel.dataset.built = "1";
  const opts = (SCHEMA.tables || []).map((t) => `<option>${esc(t.name)}</option>`).join("");
  const ops = ["=", "!=", "<", ">", "<=", ">=", "IN"]
    .map((o) => `<option>${o}</option>`).join("");
  panel.innerHTML =
    `<div class="subset"><h2>Entität exportieren (Subset-Footprint)</h2>` +
    `<p class="hint">Referenzielle FK-Hülle einer Start-Zeile (Kinder abwärts + ` +
    `Lookups aufwärts) als read-only SELECT-Skelett. Führt nichts aus.</p>` +
    `<div class="subform">` +
    `<label>Start-Tabelle <select id="sub_table">${opts}</select></label> ` +
    `<label>Filter <select id="sub_col"></select> <select id="sub_op">${ops}</select> ` +
    `<input id="sub_val" type="text" value="1"></label> ` +
    `<label><input type="checkbox" id="sub_implied"> implizite FKs</label> ` +
    `<button id="sub_run">Footprint bauen</button></div>` +
    `<div id="sub_result"></div></div>`;
  fillSubsetColumns();
  $("sub_table").addEventListener("change", fillSubsetColumns);
  $("sub_run").addEventListener("click", runSubset);
  activateTab("subset");
}
```

- [ ] **Step 4: Smoke laufen lassen, Erfolg bestätigen**

JS ist live (Reload reicht; App läuft seit Step 2).
Run: `python3 .superpowers/sdd/verify_subset.py`
Expected: `5/5 checks passed`.

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js .superpowers/sdd/verify_subset.py
git commit -m "feat: AP-56a — UI-Modus 'Entität exportieren' (Footprint-Vorschau + SELECT-Skelett)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Release v0.48.0 + Doku/Übersichten + Deploy

**Files:** `config.py`, `lucent-hub.yml` (sync_version); `luDBxP-docs/docs/javascripts/icon-rail.js`; `luDBxP-docs/zensical.toml`; `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`; `luDBxP-docs/docs/projekt/roadmap.md`; `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd` + `entwicklung-arbeitspakete-1.mmd`; `luDBxP-docs/docs/referenz/oberflaeche.md`; `CLAUDE.md`; `docs/projekt-kennzahlen.html` + `luDBxP-docs/docs/projekt/kennzahlen.md`; Site-Build.

- [ ] **Step 1: Version-Bump (MINOR)**

```bash
./venv/bin/python sync_version.py --minor      # 0.47.0 → 0.48.0
./venv/bin/python -m pytest -q 2>&1 | tail -1   # echte passed-Zahl (erwartet 356: 338 + 10 T1 + 6 T2 + 2 T3)
```

- [ ] **Step 2: icon-rail + zensical**

`luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` → `'0.48.0'`, `TEST_COUNT` → neue passed-Zahl (string), `TEST_DATE` bleibt `'2026-06-28'`.
`luDBxP-docs/zensical.toml`: `· v0.47.0` → `· v0.48.0`.

- [ ] **Step 3: Changelog EN** (`CHANGELOG.md` oben)

```markdown
## [0.48.0] — 2026-06-28

### Added
- Database subsetting — schema footprint + export skeleton (AP-56a): from a start
  table and a root filter, the tool computes the referential closure (dependent
  children downward, lookup parents upward, Jailer-style "down-then-up" without
  re-descent; cycle-safe, depth-limited) and generates one read-only SELECT per
  included table that joins back to the root. New mode "Entität exportieren" and
  read-only endpoint `/api/subset`. Executes nothing; the live data-driven walk
  with real row counts is the deferred AP-56b.
```

- [ ] **Step 4: Changelog-Mirror DE** (`luDBxP-docs/docs/entwicklung/changelog.md` oben)

```markdown
## [0.48.0] — 2026-06-28

### Hinzugefügt
- Database-Subsetting — Schema-Footprint + Export-Skelett (AP-56a): aus Start-Tabelle
  + Wurzel-Filter wird die referenzielle FK-Hülle berechnet (abhängige Kinder abwärts,
  Lookup-Eltern aufwärts; „down-then-up" ohne Re-Descent, zyklus-sicher, tiefenbegrenzt)
  und je einbezogener Tabelle ein read-only SELECT erzeugt, das zur Wurzel zurück-joint.
  Neuer Modus „Entität exportieren" + read-only Endpoint `/api/subset`. Führt nichts aus;
  der Live-Walk mit echten Zeilenzahlen ist das zurückgestellte AP-56b.
```

- [ ] **Step 5: roadmap.md — AP-56 aufsplitten**

In `luDBxP-docs/docs/projekt/roadmap.md`:
(a) In der „Legacy-DB-Migration"-Offen-Liste den `**AP-56**`-Bullet ersetzen durch einen offenen **AP-56b**-Bullet:
```markdown
- **AP-56b** — Subset-Export Live-Walk: datengetriebener read-only Walk gegen die DB (echte Zeilenzahlen, konkrete IN-Listen/Daten-Dump) auf Basis des AP-56a-Footprints. **Aufwand L.**
```
(b) Im Versionslog unter „## Erledigte Arbeitspakete" **vor** dem `**v0.47.0**`-Block einfügen:
```markdown
**v0.48.0** (2026-06-28):

- **AP-56a** — Subset-Footprint + Export-Skelett: `core/subset.py` berechnet die referenzielle FK-Hülle (down-then-up, zyklus-sicher, tiefenbegrenzt) und generiert je Tabelle ein read-only SELECT (zur Wurzel gejoint); `/api/subset` + UI-Modus „Entität exportieren". Führt nichts aus. **Aufwand M** — v0.48.0
```

- [ ] **Step 6: Gantt + Board**

Gantt `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd`:
- In der erledigt-Sektion nach der AP-55-Zeile einfügen: `    AP-56a — Subset-Footprint + Export-Skelett   :done, f22, 2026-06-28, 1d`
- Die `AP-56`-Zeile in „Legacy-DB-Migration (geplant)" zu `AP-56b — Subset-Export Live-Walk :p22, 2026-07-03, 1d` umbenennen.
- Sektions-Versionsspanne der erledigt-Sektion auf `v0.48.0` ziehen.

Board `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd`:
- `M3` (AP-56) umbenennen auf `M3["AP-56a\nSubset-Footprint"]`, von der `plan`-Klassenzeile herausnehmen und `class M3 done` ergänzen. Einen neuen Knoten `M3b["AP-56b\nSubset Live-Walk"]` in dieselbe Subgraph-Gruppe + `class M3b plan` ergänzen, Kette `~~~`/`-->` analog der Nachbarn anpassen.

- [ ] **Step 7: oberflaeche.md**

In `luDBxP-docs/docs/referenz/oberflaeche.md` einen Absatz zum neuen Modus „Entität exportieren" ergänzen: Start-Tabelle + Wurzel-Filter → referenzielle FK-Hülle (Rollen root/child/parent) + read-only SELECT-Skelett; führt nichts aus.

- [ ] **Step 8: Projekt-Kennzahlen mitziehen**

`docs/projekt-kennzahlen.html` UND `luDBxP-docs/docs/projekt/kennzahlen.md`: Headline-Zahlen aktualisieren — Version `v0.48.0`, Tests (neue passed-Zahl), Coverage (`./venv/bin/python -m pytest --cov=core --cov=web --cov=launcher --cov=config --cov=app -q | tail -3`), Commits (`git rev-list --count HEAD` nach den Task-Commits). Restliche Baseline-Werte unverändert lassen.

- [ ] **Step 9: Site bauen + gegenprüfen**

```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
cd luDBxP-docs/site && grep -o "v0.48.0" index.html | head -1 && grep -o "AP&#45;56a\|AP-56a" images/mermaid/projekt-roadmap-1.svg | head -1
```
Expected: `v0.48.0` + ein AP-56a-Treffer in der gerenderten Roadmap-SVG.

- [ ] **Step 10: SDD-Final-Review** (opus, über `git diff master...ap-56a-subset`): Layering, Read-only (kein execute im Subset-Pfad), NO-CDN, Doku-Vollständigkeit, keine Test-Regression.

- [ ] **Step 11: Commit Doku/Version**

```bash
git add -A
git commit -m "docs: Release v0.48.0 — Subset-Footprint + Export-Skelett (AP-56a)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 12: CLAUDE.md — Einschränkungen**

In `CLAUDE.md` unter „## Bekannte Einschränkungen" einen Blockquote ergänzen:
```markdown
> **Database-Subsetting (AP-56a, v0.48.0):** Aus Start-Tabelle + Wurzel-Filter wird die
> referenzielle FK-Hülle schema-basiert berechnet (down-then-up, zyklus-sicher,
> tiefenbegrenzt) und je Tabelle ein read-only SELECT erzeugt, das zur Wurzel zurück-joint
> (`/api/subset`, Modus „Entität exportieren"). Führt nichts aus. Der Live-datengetriebene
> Walk mit echten Zeilenzahlen/Daten-Dump ist das zurückgestellte AP-56b.
```
Dann: `git add CLAUDE.md && git commit -m "docs: CLAUDE.md — AP-56a Subset-Footprint in Einschränkungen"` (mit Co-Authored-By).

- [ ] **Step 13: Merge + Deploy** (nach Freigabe): ff-merge → master, push origin/master, gh-pages-Worktree-Deploy (`.nojekyll` erhalten), KPI-Zeile + Handoff separat.

---

## Self-Review

**Spec coverage:**
- §1 Closure (Adjazenz, down-then-up, Ableitungsbaum, Zyklus/Tiefe, topo) → Task 1 ✓
- §2 SELECT-Skelett (generate_subset_sql, Wurzel-Filter, DISTINCT-Regel, ON-Orientierung via child_table, Quoting/Schema, IN) → Task 2 ✓
- §3 Route `/api/subset` (read-only, Validierung→400) + UI-Modus → Task 3 + 4 ✓
- §4 Tests (Closure-Unit, SQL-Unit, Route, Smoke) → Task 1/2/3/4 ✓
- §5 Scope-Cuts (kein Live-Walk/Dump, Einzelprädikat, kein Jailer-Per-Assoziation) — eingehalten, in Changelog/CLAUDE.md als AP-56b dokumentiert ✓
- §6 Release/Doku → Task 5 ✓

**Placeholder scan:** keine TBD/TODO; alle Code-Hunks vollständig, Commands mit Expected.

**Type/Name-Konsistenz:** `SubsetEdge(via_table, pairs, child_table, kind)`, `SubsetTable(name, edge, depth)`, `SubsetResult(start, tables, truncated)`, `SubsetScript(table, sql, params)`, `compute_subset(schema, start_table, *, include_implied, max_depth)`, `generate_subset_sql(schema, result, root_filter, *, dialect, schema_name)` — identisch über Tasks 1–4. JSON-Keys `tables[].{name,kind,via_table,depth}` / `scripts[].{table,sql,params}` identisch in Route, Test, JS, Smoke. JS-IDs `sub_table/sub_col/sub_op/sub_val/sub_implied/sub_run/sub_result` durchgängig.
