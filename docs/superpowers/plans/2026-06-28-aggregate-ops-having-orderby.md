# Aggregat-Operationen (HAVING + ORDER BY auf Aggregaten) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the read-only SQL generator order grouped results by an aggregate (`ORDER BY COUNT(...) DESC`) and filter groups by an aggregate (`HAVING COUNT(*) > 5`), wired into the Join-Builder UI.

**Architecture:** Extend Tier-3. `order_by` entries gain an optional 4th `agg` element (3-tuples stay valid). A new `Having(table, column, agg, op, value)` dataclass plus a `having` parameter on `generate_sql` renders a parametrised `HAVING` block in clause order `WHERE → GROUP BY → HAVING → ORDER BY → LIMIT`. The route parses `agg` on order_by and a `having` list, weaving HAVING tables into the join path; the frontend adds an aggregate dropdown to order-by rows and a new HAVING block. The read-only run endpoint reuses the same generator.

**Tech Stack:** Python 3.14 (venv), Flask, SQLAlchemy, vanilla JS, pytest.

## Global Constraints

- **Layering:** `core/` must never import Flask. `web/` calls `core/`, never the reverse.
- **Read-only:** the tool only generates/executes SELECTs; never INSERT/UPDATE/DELETE/DDL.
- **No CDN:** all JS/CSS/fonts stay bundled under `web/` — never add `<script src="https://…">`.
- **Language:** all user-facing copy and commit messages in German.
- **Version:** never edit `config.APP_VERSION` by hand — use `./venv/bin/python sync_version.py --minor` at release time (a feature ⇒ MINOR bump, 0.41.0 → 0.42.0).
- **Tests:** run with `./venv/bin/python -m pytest`. Baseline before starting: **282 passed, 2 skipped**.
- **Backward compatibility:** with no order-by aggregate and no HAVING, generated SQL must be byte-identical to v0.41.0. Existing `order_by` 3-tuples and `generate_sql` calls without `having` must stay valid.
- **HAVING is parametrised:** values become named placeholders `:h0, :h1, …` (separate namespace from WHERE's `:p0`) plus a literal inline variant for the copy/display SQL. Never string-concatenate a HAVING value into `sql`.
- **HAVING aggregate is mandatory; HAVING operators are scalar comparisons only:** `=, !=, <, >, <=, >=`.
- **Aggregate allowlist (from Tier-3, reused verbatim):** `COUNT, SUM, AVG, MIN, MAX` (`core.sqlgen._ALLOWED_AGGS`).
- **Out of scope (do NOT build):** HAVING with IN/BETWEEN/LIKE/IS NULL, HAVING without an aggregate, COUNT(*)/COUNT(DISTINCT), column-type validation.

---

## Task 1: Generator — ORDER BY aggregate + HAVING

**Files:**
- Modify: `core/sqlgen.py` (allowlists near `_ALLOWED_DIRECTIONS` ~`17-20`; `Filter` dataclass region ~`112-118`; `generate_sql` signature ~`130-138`; ORDER BY loop ~`269-276`; final assembly ~`288-299`)
- Test: `tests/test_sqlgen.py`, `tests/test_sqlgen_dialect.py`

**Interfaces:**
- Consumes: existing `generate_sql(...)`, `Selection(table, column, agg="")`, `_ALLOWED_AGGS`, `_inline_literal`, `dialect.qualify`.
- Produces:
  - `Having(table: str, column: str, agg: str, op: str, value: object)` — frozen dataclass.
  - `core.sqlgen._ALLOWED_HAVING_OPS` = `frozenset({"=","!=","<",">","<=",">="})`.
  - `generate_sql(..., having: tuple[Having, ...] = ())` — appends a `HAVING` block between GROUP BY and ORDER BY; HAVING values go into `params` as `h0, h1, …`.
  - ORDER BY entries may be 3-tuples `(table, col, dir)` or 4-tuples `(table, col, dir, agg)`; a set `agg` renders `AGG(col) DIR`.
  - `generate_sql` raises `ValueError` on an unsupported HAVING op, a HAVING entry whose `agg` is not in `_ALLOWED_AGGS`, or an unsupported ORDER BY aggregate.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_sqlgen.py` (it already imports `generate_sql, Selection, Filter` and has `_path()`; extend the import line to also import `Having`):

```python
def test_order_by_aggregate_renders_func():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     order_by=(("VMwareCluster", "ClusterID", "DESC", "COUNT"),))
    assert 'ORDER BY COUNT("VMwareCluster"."ClusterID") DESC' in g.sql


def test_order_by_three_tuple_still_works():
    # Backward compatibility: a 3-tuple order_by renders a raw column, no aggregate.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("Networks", "VLAN", "ASC"),))
    assert 'ORDER BY "Networks"."VLAN" ASC' in g.sql


def test_having_renders_parametrised():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">", 5),))
    assert 'HAVING COUNT("VMwareCluster"."ClusterID") > :h0' in g.sql
    assert g.params["h0"] == 5
    assert "> 5" not in g.sql            # value never inlined into the executed SQL
    assert "> 5" in g.sql_inline          # but inlined in the copy/display variant


def test_having_clause_order():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     filters=(Filter("VirtualMachines", "OSID", "=", 7),),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">=", 2),),
                     order_by=(("Networks", "VLAN", "ASC"),),
                     limit=10)
    s = g.sql
    assert s.index("WHERE") < s.index("GROUP BY") < s.index("HAVING") < s.index("ORDER BY") < s.index("LIMIT")


def test_multiple_having_anded():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">", 1),
                             Having("VMwareCluster", "ClusterID", "COUNT", "<", 9)))
    assert 'HAVING COUNT("VMwareCluster"."ClusterID") > :h0' in g.sql
    assert '  AND COUNT("VMwareCluster"."ClusterID") < :h1' in g.sql
    assert g.params == {"h0": 1, "h1": 9}


def test_having_unsupported_op_raises():
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     having=(Having("Networks", "VLAN", "COUNT", "LIKE", "x"),))


def test_having_requires_aggregate_raises():
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     having=(Having("Networks", "VLAN", "", ">", 1),))


def test_no_having_no_orderby_agg_unchanged():
    # Backward compatibility: omit having and order-by aggregates -> no HAVING clause.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert "HAVING" not in g.sql
```

Add to `tests/test_sqlgen_dialect.py` (import `Having` alongside the existing `generate_sql, Selection`; ensure `JoinPath, JoinStep` are imported as in Task structure of the Tier-3 work):

```python
def test_having_and_order_by_agg_quoted_per_dialect():
    from core.sqlgen import MSSQL
    path = JoinPath(tables=("Host", "VirtualMachine"),
                    steps=(JoinStep("Host", "VirtualMachine", (("HostID", "HostID"),)),))
    g = generate_sql(path,
                     selects=(Selection("Host", "Hostname"),
                              Selection("VirtualMachine", "VMID", agg="COUNT")),
                     having=(Having("VirtualMachine", "VMID", "COUNT", ">", 3),),
                     order_by=(("VirtualMachine", "VMID", "DESC", "COUNT"),),
                     dialect=MSSQL, schema="dbo")
    assert "HAVING COUNT([dbo].[VirtualMachine].[VMID]) > :h0" in g.sql
    assert "ORDER BY COUNT([dbo].[VirtualMachine].[VMID]) DESC" in g.sql
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -k "having or order_by_aggregate or order_by_three" tests/test_sqlgen_dialect.py -k "having" -v`
Expected: FAIL — `ImportError`/`NameError` for `Having` (not yet defined).

- [ ] **Step 3: Add the `Having` dataclass and HAVING-op allowlist**

In `core/sqlgen.py`, next to `_ALLOWED_DIRECTIONS` add:

```python
# Aggregate comparison operators allowed inside a HAVING clause (scalar only).
_ALLOWED_HAVING_OPS = frozenset({"=", "!=", "<", ">", "<=", ">="})
```

And next to the `Filter` dataclass add:

```python
@dataclass(frozen=True)
class Having:
    table: str
    column: str
    agg: str       # required; one of _ALLOWED_AGGS
    op: str        # one of _ALLOWED_HAVING_OPS
    value: object  # scalar; rendered as a named placeholder :h{i}
```

- [ ] **Step 4: Add the `having` parameter to `generate_sql`**

In `core/sqlgen.py`, add `having` to the signature (after `order_by`):

```python
                 order_by: tuple[tuple, ...] = (),
                 having: tuple[Having, ...] = (),
                 limit: "int | None" = None,
```

- [ ] **Step 5: Render aggregates in the ORDER BY loop**

Replace the ORDER BY loop:

```python
    if order_by:
        ob_parts = []
        for tbl, col, direction in order_by:
            direction_upper = direction.upper()
            if direction_upper not in _ALLOWED_DIRECTIONS:
                raise ValueError(f"Unsupported ORDER BY direction: {direction!r}")
            ob_parts.append(f"{dialect.qualify(tbl, col, schema)} {direction_upper}")
        tail.append("ORDER BY " + ", ".join(ob_parts))
```

with (tolerates 3- and 4-element entries):

```python
    if order_by:
        ob_parts = []
        for entry in order_by:
            tbl, col, direction = entry[0], entry[1], entry[2]
            agg = entry[3] if len(entry) > 3 else ""
            direction_upper = direction.upper()
            if direction_upper not in _ALLOWED_DIRECTIONS:
                raise ValueError(f"Unsupported ORDER BY direction: {direction!r}")
            expr = dialect.qualify(tbl, col, schema)
            if agg:
                if agg not in _ALLOWED_AGGS:
                    raise ValueError(f"Unsupported aggregate: {agg!r}")
                expr = f"{agg}({expr})"
            ob_parts.append(f"{expr} {direction_upper}")
        tail.append("ORDER BY " + ", ".join(ob_parts))
```

- [ ] **Step 6: Build the HAVING block and splice it into the assembly**

In `core/sqlgen.py`, after the `group_lines` block and before the final `sql = "\n".join(...)`, add:

```python
    # HAVING: filter groups by an aggregate. Mandatory aggregate, scalar ops,
    # parametrised value (:h{i}) in its own namespace so it never collides with
    # WHERE's :p{i}. Clause order: after GROUP BY, before ORDER BY/LIMIT.
    having_clauses = []
    having_inline = []
    for i, h in enumerate(having):
        if h.op not in _ALLOWED_HAVING_OPS:
            raise ValueError(f"Unsupported HAVING operator: {h.op}")
        if h.agg not in _ALLOWED_AGGS:
            raise ValueError(f"HAVING requires an aggregate, got: {h.agg!r}")
        expr = f"{h.agg}({dialect.qualify(h.table, h.column, schema)})"
        key = f"h{i}"
        having_clauses.append(f"{expr} {h.op} :{key}")
        having_inline.append(f"{expr} {h.op} {_inline_literal(h.value)}")
        params[key] = h.value

    def _having_block(cls):
        return [(f"HAVING {c}" if k == 0 else f"  AND {c}")
                for k, c in enumerate(cls)]

    having_param = _having_block(having_clauses) if having_clauses else []
    having_inline_block = _having_block(having_inline) if having_inline else []
```

Then change the two assembly lines to splice HAVING between GROUP BY and `tail`:

```python
    sql = "\n".join(lines + where_param + group_lines + having_param + tail)
    sql_inline = "\n".join(lines + where_inline + group_lines + having_inline_block + tail) + ";"
```

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -k "having or order_by_aggregate or order_by_three" tests/test_sqlgen_dialect.py -k "having" -v`
Expected: PASS (8 new sqlgen tests + 1 dialect test green).

- [ ] **Step 8: Run the full suite to confirm no regression**

Run: `./venv/bin/python -m pytest -q`
Expected: `291 passed, 2 skipped` (282 + 9 new).

- [ ] **Step 9: Commit**

```bash
git add core/sqlgen.py tests/test_sqlgen.py tests/test_sqlgen_dialect.py
git commit -m "feat: Aggregat-Ops Generator — ORDER BY auf Aggregaten + HAVING (parametrisiert)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Route — parse order-by `agg` and `having`, weave HAVING tables

**Files:**
- Modify: `web/routes.py` (import ~`13`; `_parse_joinpath_params` order-by parse ~`276-286`, required_tables ~`296-303`, return ~`304-305`; `_make_path_gen` signature ~`314-322` + generate_sql call ~`348-354`; three unpack sites + three `_make_path_gen` calls — see Step 3)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Having` and the extended `generate_sql(..., having=...)` from Task 1; the existing `try/except ValueError -> 400` around the generator in all three routes.
- Produces: request JSON now accepts `agg` on each `order_by[]` item and a top-level `having` list of `{table, column, agg, op, value}`. `_parse_joinpath_params` returns a 9-element tuple ending `(..., order_by_validated, having_validated, required_tables)`; HAVING tables are woven via `required_tables`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py` (uses existing `client`, `inventory_url`, `demo_url` fixtures):

```python
def test_joinpath_order_by_aggregate_in_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "order_by": [{"table": "VMwareCluster", "column": "ClusterID", "dir": "DESC", "agg": "COUNT"}],
        "filters": [],
    })
    assert resp.status_code == 200
    assert 'ORDER BY COUNT("VMwareCluster"."ClusterID") DESC' in resp.get_json()["paths"][0]["sql"]


def test_joinpath_having_emits_clause(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "having": [{"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT", "op": ">", "value": 1}],
        "filters": [],
    })
    assert resp.status_code == 200
    sql = resp.get_json()["paths"][0]["sql"]
    assert 'HAVING COUNT("VMwareCluster"."ClusterID") > :h0' in sql


def test_joinpath_having_unknown_op_returns_400(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "having": [{"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT", "op": "LIKE", "value": "x"}],
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_having_table_woven_into_path(client, demo_url):
    """A HAVING on a table off the start/target path is woven in (required_tables)."""
    resp = client.post("/api/joinpath", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "Host", "column": "HostID"},
        "having": [{"table": "VirtualMachine", "column": "VMID", "agg": "COUNT", "op": ">=", "value": 1}],
        "filters": [],
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    for p in paths:
        assert "VirtualMachine" in p["tables"]
        assert 'HAVING COUNT("VirtualMachine"."VMID") >=' in p["sql"]


def test_joinpath_run_executes_having(client, demo_url):
    """Read-only run executes a grouped query with HAVING and returns grouped rows."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "VirtualMachine", "column": "VMID", "agg": "COUNT"},
        "having": [{"table": "VirtualMachine", "column": "VMID", "agg": "COUNT", "op": ">=", "value": 1}],
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "HAVING" in data["sql"]
    assert isinstance(data["rows"], list) and len(data["rows"]) >= 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "order_by_aggregate or having" -v`
Expected: FAIL — order-by `agg` ignored (no `COUNT(...)` in ORDER BY) and `having` ignored (no `HAVING` in SQL); the weave test finds no `VirtualMachine` in tables.

- [ ] **Step 3: Import `Having` and parse order-by `agg` + `having`**

In `web/routes.py`, extend the import:

```python
from core.sqlgen import generate_sql, Selection, Filter, Having, dialect_for, SQLITE
```

In `_parse_joinpath_params`, change the ORDER BY parse to carry `agg` (4-tuple):

```python
    raw_order_by = data.get("order_by", [])
    order_by_validated: list[tuple] = []
    for ob in raw_order_by:
        tbl = ob.get("table", "")
        col = ob.get("column", "")
        direction = (ob.get("dir") or "ASC").upper()
        agg = ob.get("agg", "")
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"invalid ORDER BY direction: {direction!r}")
        if not schema.has_column(tbl, col):
            raise ValueError(f"unknown column: {tbl}.{col}")
        order_by_validated.append((tbl, col, direction, agg))
```

Immediately after that loop, add the HAVING parse:

```python
    # --- HAVING: filter groups by an aggregate (scalar comparison, parametrised) ---
    raw_having = data.get("having", [])
    having_validated: list[Having] = []
    for h in raw_having:
        tbl = h.get("table", "")
        col = h.get("column", "")
        if not schema.has_column(tbl, col):
            raise ValueError(f"unknown column: {tbl}.{col}")
        having_validated.append(
            Having(tbl, col, h.get("agg", ""), h.get("op", ""), h.get("value")))
    having = tuple(having_validated)
```

- [ ] **Step 4: Weave HAVING tables into required_tables and return them**

In `_parse_joinpath_params`, update `required_tables` (note the order_by entries are now 4-tuples — index by `e[0]`):

```python
    required_tables = tuple(dict.fromkeys(
        [f.table for f in filters]
        + [s.table for s in extra_selections]
        + [e[0] for e in order_by_validated]
        + [h.table for h in having_validated]
    ))
    return (start, target, filters, extra_selections,
            distinct, limit, order_by_validated, having, required_tables)
```

- [ ] **Step 5: Thread `having` through `_make_path_gen` and all three call sites**

In `_make_path_gen`, add a `having` keyword parameter and pass it to `generate_sql`:

```python
def _make_path_gen(p, start: dict, target: dict,
                   extra_selections: tuple,
                   filters: tuple,
                   distinct: bool,
                   limit,
                   order_by_validated: list,
                   dialect=SQLITE,
                   join_types: tuple = (),
                   schema: str = "",
                   having: tuple = ()):
```

and in its `return generate_sql(...)` add `having=having`:

```python
    return generate_sql(p, tuple(selects_for_path), filters,
                        distinct=distinct,
                        order_by=order_by_for_path,
                        having=having,
                        limit=limit,
                        join_types=tuple(join_types),
                        dialect=dialect,
                        schema=schema)
```

Now update the THREE `_parse_joinpath_params` unpack sites and THREE `_make_path_gen` calls. Find them with:
`grep -n "_parse_joinpath_params(data, schema)\|_make_path_gen(" web/routes.py`
They are in `api_joinpath`, `api_joinpath_run`, and `api_orphan_check`.

At each unpack site, add `having` before `required_tables`, e.g.:

```python
        (start, target, filters, extra_selections,
         distinct, limit, order_by_validated, having,
         required_tables) = _parse_joinpath_params(data, schema)
```

At each `_make_path_gen(...)` call, pass `having=having` as a keyword argument (alongside the existing `dialect`, `join_types=`, `schema=` arguments). For example in `api_joinpath`:

```python
            gen = _make_path_gen(p, start, target, extra_selections, filters,
                                 distinct, limit, order_by_validated, dialect,
                                 join_types=join_types, schema=schema_name,
                                 having=having)
```

Apply the analogous `having=having` addition to the `api_joinpath_run` and `api_orphan_check` calls.

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "order_by_aggregate or having" -v`
Expected: PASS (5 new tests green).

- [ ] **Step 7: Run the full suite to confirm no regression**

Run: `./venv/bin/python -m pytest -q`
Expected: `296 passed, 2 skipped` (291 + 5 new).

- [ ] **Step 8: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat: Aggregat-Ops Route — order_by agg + having parsen, HAVING-Tabellen ins Weaving

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Frontend — ORDER BY aggregate dropdown + HAVING block

**Files:**
- Modify: `web/static/js/app.js` (`openJoinBuilder` controls/containers ~`299-305` + listener wiring ~`337-339`; `addOrderByRow` ~`611-639`; `collectOrderBy` ~`632`; add `addHavingRow`/`collectHaving`; `collectJoinBody` ~`692-707`)
- Test: manual browser verification (controller drives the app — no JS unit harness; see memory note "JS-UI via Playwright verifizieren").

**Interfaces:**
- Consumes: the request contract from Task 2 — `agg` on each `order_by[]` item, and a top-level `having: [{table, column, agg, op, value}]`.
- Produces: an aggregate `<select>` `.ob-agg` on each order-by row; a new `#havings` container with `HAVING +` rows (`.h-agg/.h-table/.h-col/.h-op/.h-val`); `collectJoinBody()` includes `order_by[].agg` and `having`.

- [ ] **Step 1: Add the HAVING-operator constant**

In `web/static/js/app.js`, near the `AGG_FUNCS` constant added in Tier-3, add:

```javascript
// Aggregat-Ops: scalar comparison operators allowed in a HAVING row.
const HAVING_OPS = ["=", "!=", "<", ">", "<=", ">="];
```

- [ ] **Step 2: Add the aggregate select to order-by rows**

In `addOrderByRow`, change the row markup to insert `.ob-agg` before the direction select:

```javascript
  row.innerHTML =
    `<select class="ob-table">${optionList(names)}</select>` +
    `<select class="ob-col"></select>` +
    `<select class="ob-agg jb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<select class="ob-dir"><option>ASC</option><option>DESC</option></select>` +
    `<button type="button" class="ob-del">✕</button>`;
```

- [ ] **Step 3: Collect the order-by aggregate**

Replace `collectOrderBy` with a version that carries `agg`:

```javascript
function collectOrderBy() {
  const out = [];
  document.querySelectorAll("#order_bys .orderby-row").forEach((row) => {
    const table = row.querySelector(".ob-table").value;
    const column = row.querySelector(".ob-col").value;
    const dir = row.querySelector(".ob-dir").value;
    const agg = row.querySelector(".ob-agg").value;
    if (table && column) out.push({ table, column, dir, agg });
  });
  return out;
}
```

> If the existing `collectOrderBy` body differs, preserve its existing field names (`table`, `column`, `dir`) and only add the `agg` read + property.

- [ ] **Step 4: Add the HAVING container, button, and listener**

In `openJoinBuilder`, add a `#havings` container next to the other row containers (after `#extra_cols`):

```javascript
    `<div class="filters" id="extra_cols"></div>` +
    `<div class="filters" id="havings"></div>` +
```

Add a `HAVING +` button next to the existing add buttons:

```javascript
    `<button id="btn_add_col" title="Weitere SELECT-Spalte hinzufügen">Spalten +</button>` +
    `<button id="btn_add_having" title="Gruppen nach Aggregat filtern (HAVING)">HAVING +</button>` +
```

And wire it where the other add buttons are wired:

```javascript
  $("btn_add_col").addEventListener("click", addColRow);
  $("btn_add_having").addEventListener("click", addHavingRow);
```

- [ ] **Step 5: Implement `addHavingRow` and `collectHaving`**

Add these two functions (place them near `addColRow`/`collectExtraSelects`):

```javascript
function addHavingRow() {
  if (!SCHEMA.tables.length) return;
  const row = document.createElement("div");
  row.className = "having-row";
  const names = SCHEMA.tables.map((t) => t.name);
  row.innerHTML =
    `<select class="h-agg jb-agg" title="Aggregatfunktion">` +
    AGG_FUNCS.map((f) => `<option value="${f}">${f}</option>`).join("") + `</select>` +
    `<select class="h-table">${optionList(names)}</select>` +
    `<select class="h-col"></select>` +
    `<select class="h-op">${HAVING_OPS.map((o) => `<option>${o}</option>`).join("")}</select>` +
    `<input class="h-val" type="text" placeholder="Wert">` +
    `<button type="button" class="h-del">✕</button>`;
  const fillHcol = () => {
    const t = tableByName(row.querySelector(".h-table").value);
    row.querySelector(".h-col").innerHTML =
      optionList(t ? t.columns.map((c) => c.name) : []);
  };
  fillHcol();
  row.querySelector(".h-table").addEventListener("change", fillHcol);
  row.querySelector(".h-val").addEventListener("change", _rebuildIfBuilt);
  row.querySelector(".h-agg").addEventListener("change", _rebuildIfBuilt);
  row.querySelector(".h-op").addEventListener("change", _rebuildIfBuilt);
  row.querySelector(".h-del").addEventListener("click", () => { row.remove(); _rebuildIfBuilt(); });
  $("havings").appendChild(row);
}

function collectHaving() {
  const out = [];
  document.querySelectorAll("#havings .having-row").forEach((row) => {
    const table = row.querySelector(".h-table").value;
    const column = row.querySelector(".h-col").value;
    const agg = row.querySelector(".h-agg").value;
    const op = row.querySelector(".h-op").value;
    const value = row.querySelector(".h-val").value;
    if (table && column && agg && op && value !== "") {
      out.push({ table, column, agg, op, value });
    }
  });
  return out;
}
```

Note: the `.h-agg` dropdown has NO empty `—` option (the aggregate is mandatory for HAVING); it defaults to `COUNT`.

- [ ] **Step 6: Include `having` in the request body**

In `collectJoinBody`, add the `having` field (order_by already comes from `collectOrderBy()` which now carries `agg`):

```javascript
    order_by: collectOrderBy(),
    having: collectHaving(),
```

- [ ] **Step 7: Validate JS syntax**

Run: `node --check web/static/js/app.js`
Expected: exit 0, no output.

- [ ] **Step 8: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: Aggregat-Ops UI — ORDER-BY-Aggregat + HAVING-Block im Join-Builder

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Browser verification (start the app, set Start `Host.Hostname` + Ziel `VirtualMachine.VMID` COUNT, add a HAVING `COUNT VirtualMachine.VMID >= 2`, add an ORDER BY on `VirtualMachine.VMID` COUNT DESC, build → SQL shows `HAVING COUNT(...) >= :h0` and `ORDER BY COUNT(...) DESC`; run returns grouped rows) is performed by the controller after this task, not by the implementer.

---

## Task 4: Release — version, docs, badge, site

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md` (+ mirror `luDBxP-docs/docs/entwicklung/changelog.md`), `CLAUDE.md` (Bekannte Einschränkungen), `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd` + `entwicklung-arbeitspakete-1.mmd`, `luDBxP-docs/docs/javascripts/icon-rail.js` (TEST_COUNT), site rebuild.
- Reference: the previous release commit `b655902` ("docs: Release v0.41.0 — Tier-3 …") — mirror its file set.

**Interfaces:**
- Consumes: completed Tasks 1-3 on a clean tree, full suite green.
- Produces: a tagged MINOR release documenting HAVING + ORDER-BY-aggregate as done.

- [ ] **Step 1: Confirm the full suite is green**

Run: `./venv/bin/python -m pytest -q`
Expected: `296 passed, 2 skipped` (record the real number if it differs).

- [ ] **Step 2: Bump the version (MINOR)**

Run: `./venv/bin/python sync_version.py --minor`
Expected: `config.py` + `lucent-hub.yml` go `0.41.0 → 0.42.0`.

- [ ] **Step 3: Update the changelog (root + mirror)**

Add a `[0.42.0] — 2026-06-28` "Added" section to `CHANGELOG.md` and the mirror `luDBxP-docs/docs/entwicklung/changelog.md`: ORDER BY may sort by an aggregate (`ORDER BY COUNT(...) DESC`); HAVING filters groups by an aggregate (scalar comparison, parametrised); clause order WHERE→GROUP BY→HAVING→ORDER BY→LIMIT; read-only run executes HAVING; still open: COUNT(*)/COUNT(DISTINCT), Cross-Schema joins.

- [ ] **Step 4: Update CLAUDE.md "Bekannte Einschränkungen"**

In the Tier-3 note, update the "Still open" line: HAVING is now done; remaining open = `COUNT(*)`/`COUNT(DISTINCT)`, Cross-Schema-Joins. (Optionally add a one-line note that ORDER BY/HAVING now accept aggregates.)

- [ ] **Step 5: Update roadmap / board / Gantt + test-count badge**

Add the new item BY NAME (e.g. "Aggregat-Operationen — HAVING + ORDER BY auf Aggregaten — v0.42.0") to `luDBxP-docs/docs/projekt/roadmap.md` and add an item to BOTH mermaid sources (`projekt-roadmap-1.mmd` gantt line `:done, …, 2026-06-28, 1d`; `entwicklung-arbeitspakete-1.mmd` an `E13` node modeled on `E12`, with Tier-2/Tier-3 still present). Set `icon-rail.js` `TEST_COUNT` to the real count from Step 1 (`296`).

- [ ] **Step 6: Build the site and verify the overview**

Run: `cd luDBxP-docs && ./run_luDBxP_docs.sh --build`
Expected: mermaid SVGs regenerate, static site builds with no errors. Then grep `luDBxP-docs/site/` for the new item and `HAVING` to confirm it rendered (mind HTML entity encoding); confirm Tier-2, Tier-3, and the new item all appear by name. Then re-run `./venv/bin/python -m pytest -q` (still `296 passed, 2 skipped`).

- [ ] **Step 7: Commit the release**

```bash
git add -A
git commit -m "docs: Release v0.42.0 — Aggregat-Operationen (HAVING + ORDER BY auf Aggregaten)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Pushing to `origin/master` and the `gh-pages` deploy are a separate, user-confirmed step — do not push without confirmation.

---

## Self-Review

**Spec coverage:**
- ORDER BY on aggregates → Task 1 Step 5 + `test_order_by_aggregate_renders_func`; route Task 2 Step 3; UI Task 3 Steps 2-3. ✓
- HAVING (mandatory agg, scalar ops, parametrised) → Task 1 Steps 3-6 + having tests; route Task 2 Step 3; UI Task 3 Step 5. ✓
- Clause order WHERE→GROUP BY→HAVING→ORDER BY→LIMIT → Task 1 Step 6 + `test_having_clause_order`. ✓
- Separate `:h{i}` placeholder namespace → Task 1 Step 6 + `test_multiple_having_anded`. ✓
- HAVING value never inlined into executed SQL → `test_having_renders_parametrised`. ✓
- HAVING tables woven via required_tables → Task 2 Step 4 + `test_joinpath_having_table_woven_into_path`. ✓
- Bad HAVING op / missing aggregate → ValueError/400 → Task 1 Steps 5-6 + `test_having_unsupported_op_raises`, `test_having_requires_aggregate_raises`, `test_joinpath_having_unknown_op_returns_400`. ✓
- Read-only run executes HAVING → `test_joinpath_run_executes_having`. ✓
- Backward compatibility (3-tuple order_by, no having) → `test_order_by_three_tuple_still_works`, `test_no_having_no_orderby_agg_unchanged`. ✓
- Out of scope (HAVING IN/BETWEEN/NULL, HAVING without agg, COUNT(*)/DISTINCT, type-check) → not built; recorded in Global Constraints + Task 4 docs. ✓
- Release MINOR 0.42.0 + docs/badge/site → Task 4. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** `Having(table, column, agg, op, value)`, `_ALLOWED_HAVING_OPS` (6 ops), `having: tuple[Having,...]=()`, order_by 4-tuple `(table, col, dir, agg)`, request fields `order_by[].agg` + `having[]`, `_parse_joinpath_params` 9-tuple return with `having` before `required_tables`, `_make_path_gen(..., having=())`, JS `HAVING_OPS`/`collectHaving`/`.h-*`/`.ob-agg` — consistent across Tasks 1-3. ✓
