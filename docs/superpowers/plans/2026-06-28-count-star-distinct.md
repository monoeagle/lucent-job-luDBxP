# COUNT(*) + COUNT(DISTINCT) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `COUNT(*)` (row count, column-ignored) and `COUNT(DISTINCT col)` as aggregate options that thread automatically through SELECT, HAVING, and ORDER BY.

**Architecture:** Two new tokens (`COUNT*`, `COUNT DISTINCT`) join the existing `_ALLOWED_AGGS` allowlist. A single `_render_agg(agg, expr)` helper replaces the three identical `f"{agg}({expr})"` render sites in `core/sqlgen.py`, so both new aggregates work everywhere with no other generator change and no route change. The frontend adds the two options (with value≠label) and disables the column picker when `COUNT(*)` is chosen.

**Tech Stack:** Python 3.14 (venv), Flask, SQLAlchemy, vanilla JS, pytest.

## Global Constraints

- **Layering:** `core/` must never import Flask. `web/` calls `core/`, never the reverse.
- **Read-only:** the tool only generates/executes SELECTs; never INSERT/UPDATE/DELETE/DDL.
- **No CDN:** all JS/CSS/fonts stay bundled under `web/` — never add `<script src="https://…">`.
- **Language:** all user-facing copy and commit messages in German.
- **Version:** never edit `config.APP_VERSION` by hand — use `./venv/bin/python sync_version.py --minor` at release time (a feature ⇒ MINOR bump, 0.42.0 → 0.43.0).
- **Tests:** run with `./venv/bin/python -m pytest`. Baseline before starting: **296 passed, 2 skipped**.
- **Backward compatibility:** without the new tokens, generated SQL must be byte-identical to v0.42.0. The render helper falls back to `f"{agg}({expr})"` for the five existing tokens.
- **New aggregate tokens (verbatim):** `COUNT*` renders `COUNT(*)` (column ignored); `COUNT DISTINCT` renders `COUNT(DISTINCT <col>)`. Allowlist becomes `{COUNT, SUM, AVG, MIN, MAX, COUNT*, COUNT DISTINCT}`.
- **Route is UNCHANGED:** `agg` flows through verbatim; `schema.has_column` validates the (column-ignored-but-still-selected) column; the generator validates the allowlist. Do NOT edit `web/routes.py`.
- **COUNT(*) is table-bound, not column-bound:** the column is ignored at render time but the entry's table still goes into AP-30 `required_tables` weaving (intended).
- **Out of scope (do NOT build):** `SUM(DISTINCT)`/`AVG(DISTINCT)` etc., multi-column `COUNT(DISTINCT a, b)`, column-type validation.

---

## Task 1: Generator — COUNT(*) + COUNT(DISTINCT) via render helper

**Files:**
- Modify: `core/sqlgen.py` (`_ALLOWED_AGGS` ~`26`; add `_render_agg` near the module helpers ~after `_inline_literal`; SELECT render site ~`208-211`; ORDER BY render site ~`291-294`; HAVING render site ~`323-325`)
- Test: `tests/test_sqlgen.py`, `tests/test_sqlgen_dialect.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: existing `generate_sql(...)`, `Selection(table, column, agg="")`, `Having(table, column, agg, op, value)`, order_by 4-tuples `(table, col, dir, agg)`, `_ALLOWED_AGGS`, `dialect.qualify`.
- Produces:
  - `_ALLOWED_AGGS` includes `"COUNT*"` and `"COUNT DISTINCT"`.
  - `core.sqlgen._render_agg(agg: str, expr: str) -> str` — `COUNT*`→`COUNT(*)`, `COUNT DISTINCT`→`COUNT(DISTINCT <expr>)`, else `f"{agg}({expr})"`.
  - SELECT/HAVING/ORDER BY all render the two new tokens; the route (unchanged) accepts them as `agg` on start/target/extra, order_by, and having.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_sqlgen.py` (it already imports `generate_sql, Selection, Filter, Having` and has `_path()`):

```python
def test_count_star_renders_ignoring_column():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT*")))
    assert "COUNT(*)" in g.sql
    # the column attached to the COUNT* selection is ignored in the rendered expr
    assert 'COUNT(*)("' not in g.sql and 'COUNT("VMwareCluster"."ClusterID")' not in g.sql
    # group by the non-aggregated select
    assert 'GROUP BY "Networks"."VLAN"' in g.sql


def test_count_distinct_renders_with_column():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT DISTINCT")))
    assert 'COUNT(DISTINCT "VMwareCluster"."ClusterID")' in g.sql
    assert 'GROUP BY "Networks"."VLAN"' in g.sql


def test_count_star_in_having_and_order_by():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT*")),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT*", ">", 5),),
                     order_by=(("VMwareCluster", "ClusterID", "DESC", "COUNT*"),))
    assert "HAVING COUNT(*) > :h0" in g.sql
    assert "ORDER BY COUNT(*) DESC" in g.sql


def test_count_distinct_in_having_and_order_by():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT DISTINCT", ">", 2),),
                     order_by=(("VMwareCluster", "ClusterID", "ASC", "COUNT DISTINCT"),))
    assert 'HAVING COUNT(DISTINCT "VMwareCluster"."ClusterID") > :h0' in g.sql
    assert 'ORDER BY COUNT(DISTINCT "VMwareCluster"."ClusterID") ASC' in g.sql


def test_existing_aggregates_unchanged():
    # Backward compat: the five original tokens still render func(col).
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert "COUNT(*)" not in g.sql
    assert "DISTINCT" not in g.sql
```

Add to `tests/test_sqlgen_dialect.py` (already imports `JoinPath, JoinStep, generate_sql, Selection`; add `MSSQL` import in-test as the existing dialect tests do):

```python
def test_count_distinct_and_star_quoted_per_dialect():
    from core.sqlgen import MSSQL
    path = JoinPath(tables=("Host", "VirtualMachine"),
                    steps=(JoinStep("Host", "VirtualMachine", (("HostID", "HostID"),)),))
    g = generate_sql(path,
                     selects=(Selection("Host", "Hostname"),
                              Selection("VirtualMachine", "VMID", agg="COUNT DISTINCT"),
                              Selection("VirtualMachine", "VMID", agg="COUNT*")),
                     dialect=MSSQL, schema="dbo")
    assert "COUNT(DISTINCT [dbo].[VirtualMachine].[VMID])" in g.sql
    assert "COUNT(*)" in g.sql            # COUNT(*) is dialect-independent
```

Add to `tests/test_api.py` (uses existing `client`, `inventory_url`, `demo_url` fixtures; route is unchanged so these confirm passthrough):

```python
def test_joinpath_count_distinct_in_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT DISTINCT"},
        "filters": [],
    })
    assert resp.status_code == 200
    assert 'COUNT(DISTINCT "VMwareCluster"."ClusterID")' in resp.get_json()["paths"][0]["sql"]


def test_joinpath_run_executes_count_star(client, demo_url):
    """COUNT(*) per host over the joined VirtualMachine rows, read-only run."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "VirtualMachine", "column": "VMID", "agg": "COUNT*"},
        "having": [{"table": "VirtualMachine", "column": "VMID", "agg": "COUNT*", "op": ">=", "value": 1}],
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "COUNT(*)" in data["sql"]
    assert "HAVING COUNT(*) >=" in data["sql"]
    assert isinstance(data["rows"], list) and len(data["rows"]) >= 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -k "count_star or count_distinct or existing_aggregates" tests/test_sqlgen_dialect.py -k "count_distinct_and_star" tests/test_api.py -k "count_distinct or count_star" -v`
Expected: FAIL — `COUNT*` / `COUNT DISTINCT` is not in `_ALLOWED_AGGS`, so `generate_sql` raises `ValueError: Unsupported aggregate` (the route tests get HTTP 400, the sqlgen tests raise).

- [ ] **Step 3: Extend the aggregate allowlist**

In `core/sqlgen.py`, change `_ALLOWED_AGGS`:

```python
_ALLOWED_AGGS = frozenset({"COUNT", "SUM", "AVG", "MIN", "MAX", "COUNT*", "COUNT DISTINCT"})
```

- [ ] **Step 4: Add the `_render_agg` helper**

In `core/sqlgen.py`, add this module-level function near the other helpers (e.g. right after `_inline_literal`):

```python
def _render_agg(agg: str, expr: str) -> str:
    """Render an aggregate over a qualified column expression.

    COUNT* ignores the column and renders COUNT(*); COUNT DISTINCT dedups the
    column; every other token renders the plain FUNC(col) form.
    """
    if agg == "COUNT*":
        return "COUNT(*)"
    if agg == "COUNT DISTINCT":
        return f"COUNT(DISTINCT {expr})"
    return f"{agg}({expr})"
```

- [ ] **Step 5: Route the three render sites through the helper**

In `core/sqlgen.py`, SELECT-list render site — replace:

```python
        if s.agg:
            if s.agg not in _ALLOWED_AGGS:
                raise ValueError(f"Unsupported aggregate: {s.agg!r}")
            expr = f"{s.agg}({expr})"
```

with:

```python
        if s.agg:
            if s.agg not in _ALLOWED_AGGS:
                raise ValueError(f"Unsupported aggregate: {s.agg!r}")
            expr = _render_agg(s.agg, expr)
```

ORDER BY render site — replace:

```python
            if agg:
                if agg not in _ALLOWED_AGGS:
                    raise ValueError(f"Unsupported aggregate: {agg!r}")
                expr = f"{agg}({expr})"
```

with:

```python
            if agg:
                if agg not in _ALLOWED_AGGS:
                    raise ValueError(f"Unsupported aggregate: {agg!r}")
                expr = _render_agg(agg, expr)
```

HAVING render site — replace:

```python
        if h.agg not in _ALLOWED_AGGS:
            raise ValueError(f"HAVING requires an aggregate, got: {h.agg!r}")
        expr = f"{h.agg}({dialect.qualify(h.table, h.column, schema)})"
```

with:

```python
        if h.agg not in _ALLOWED_AGGS:
            raise ValueError(f"HAVING requires an aggregate, got: {h.agg!r}")
        expr = _render_agg(h.agg, dialect.qualify(h.table, h.column, schema))
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -k "count_star or count_distinct or existing_aggregates" tests/test_sqlgen_dialect.py -k "count_distinct_and_star" tests/test_api.py -k "count_distinct or count_star" -v`
Expected: PASS (7 new tests green).

- [ ] **Step 7: Run the full suite to confirm no regression**

Run: `./venv/bin/python -m pytest -q`
Expected: `303 passed, 2 skipped` (296 + 7 new).

- [ ] **Step 8: Commit**

```bash
git add core/sqlgen.py tests/test_sqlgen.py tests/test_sqlgen_dialect.py tests/test_api.py
git commit -m "feat: COUNT(*) + COUNT(DISTINCT) im Generator (Render-Helfer, Route unverändert)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Frontend — two new aggregate options + COUNT(*) column-disable

**Files:**
- Modify: `web/static/js/app.js` (`AGG_FUNCS`/`aggOptions` ~`81-86`; `addHavingRow` aggregate `<select>` build ~`697-700`; `openJoinBuilder` start/target wiring ~after `334`; `addColRow` ~`643-661`; `addOrderByRow` ~`611-639`; `addHavingRow` ~`688-731`)
- Test: manual browser verification (controller drives the app after this task — no JS unit harness; see memory note "JS-UI via Playwright verifizieren").

**Interfaces:**
- Consumes: the backend contract from Task 1 — `agg` may be `COUNT*` or `COUNT DISTINCT` on any SELECT column, order_by entry, or HAVING row.
- Produces: aggregate dropdowns offer `COUNT(*)` (value `COUNT*`) and `COUNT(DISTINCT)` (value `COUNT DISTINCT`); selecting `COUNT(*)` disables the row's column `<select>` (value still submitted, render ignores it).

- [ ] **Step 1: Replace `AGG_FUNCS` with a value/label list and a tag helper**

In `web/static/js/app.js`, replace the `AGG_FUNCS` const + `aggOptions` function:

```javascript
// Tier-3: aggregate <option>s for a SELECT column. Empty value = no aggregate.
const AGG_FUNCS = ["COUNT", "SUM", "AVG", "MIN", "MAX"];
function aggOptions() {
  return `<option value="">—</option>` +
    AGG_FUNCS.map((f) => `<option value="${f}">${f}</option>`).join("");
}
```

with (value ≠ label for the two new tokens):

```javascript
// Aggregate options. value = token sent in the request; label = shown to the user.
// COUNT* renders COUNT(*) (column ignored); "COUNT DISTINCT" renders COUNT(DISTINCT col).
const AGG_OPTIONS = [
  { v: "COUNT", l: "COUNT" },
  { v: "COUNT*", l: "COUNT(*)" },
  { v: "COUNT DISTINCT", l: "COUNT(DISTINCT)" },
  { v: "SUM", l: "SUM" },
  { v: "AVG", l: "AVG" },
  { v: "MIN", l: "MIN" },
  { v: "MAX", l: "MAX" },
];
function aggOptionTags() {
  return AGG_OPTIONS.map((o) => `<option value="${o.v}">${o.l}</option>`).join("");
}
function aggOptions() {              // SELECT/ORDER BY: optional aggregate ("—" first)
  return `<option value="">—</option>` + aggOptionTags();
}
```

- [ ] **Step 2: Use the shared tag helper in the HAVING row (mandatory aggregate)**

In `addHavingRow`, replace the aggregate `<select>` build (currently using `AGG_FUNCS.map(...)`):

```javascript
    `<select class="h-agg jb-agg" title="Aggregatfunktion">` +
    AGG_FUNCS.map((f) => `<option value="${f}">${f}</option>`).join("") + `</select>` +
```

with:

```javascript
    `<select class="h-agg jb-agg" title="Aggregatfunktion">` +
    aggOptionTags() + `</select>` +
```

- [ ] **Step 3: Add the column-disable helper**

In `web/static/js/app.js`, add near `aggOptions` (top-of-file helpers):

```javascript
// COUNT(*) ignores the column — disable the paired column <select> when chosen
// (its value is still submitted and ignored server-side). Other aggregates keep it.
function wireAggColDisable(aggSel, colSel) {
  if (!aggSel || !colSel) return;
  const sync = () => { colSel.disabled = (aggSel.value === "COUNT*"); };
  aggSel.addEventListener("change", sync);
  sync();
}
```

- [ ] **Step 4: Wire the helper for Start and Ziel**

In `openJoinBuilder`, after the start/target listeners are registered (near the existing `$("start_table").addEventListener(...)` / `$("target_table").addEventListener(...)` block), add:

```javascript
  wireAggColDisable($("start_agg"), $("start_col"));
  wireAggColDisable($("target_agg"), $("target_col"));
```

- [ ] **Step 5: Wire the helper for extra-column rows**

In `addColRow`, after the row is built and its other listeners are wired (before `$("extra_cols").appendChild(row);`), add:

```javascript
  wireAggColDisable(row.querySelector(".c-agg"), row.querySelector(".c-col"));
```

- [ ] **Step 6: Wire the helper for ORDER BY rows**

In `addOrderByRow`, before `$("order_bys").appendChild(row);`, add:

```javascript
  wireAggColDisable(row.querySelector(".ob-agg"), row.querySelector(".ob-col"));
```

- [ ] **Step 7: Wire the helper for HAVING rows**

In `addHavingRow`, before `$("havings").appendChild(row);`, add:

```javascript
  wireAggColDisable(row.querySelector(".h-agg"), row.querySelector(".h-col"));
```

- [ ] **Step 8: Validate JS syntax**

Run: `node --check web/static/js/app.js`
Expected: exit 0, no output.

- [ ] **Step 9: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: COUNT(*) + COUNT(DISTINCT) im Join-Builder (Dropdown + Spalten-Disable bei COUNT(*))

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Browser verification (start the app, pick Ziel `VirtualMachine.VMID` with `COUNT(*)` → column picker disables, SQL shows `COUNT(*)` + `GROUP BY Host.Hostname`; pick `COUNT(DISTINCT)` → column stays active, SQL shows `COUNT(DISTINCT ...)`; HAVING/ORDER BY rows offer both) is performed by the controller after this task, not by the implementer.

---

## Task 3: Release — version, docs, badge, site

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md` (+ mirror `luDBxP-docs/docs/entwicklung/changelog.md`), `CLAUDE.md` (Bekannte Einschränkungen), `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd` + `entwicklung-arbeitspakete-1.mmd`, `luDBxP-docs/docs/javascripts/icon-rail.js` (TEST_COUNT), site rebuild.
- Reference: the previous release commit `7c44075` ("docs: Release v0.42.0 — Aggregat-Operationen …") — mirror its file set.

**Interfaces:**
- Consumes: completed Tasks 1-2 on a clean tree, full suite green.
- Produces: a tagged MINOR release documenting COUNT(*) + COUNT(DISTINCT) as done.

- [ ] **Step 1: Confirm the full suite is green**

Run: `./venv/bin/python -m pytest -q`
Expected: `303 passed, 2 skipped` (record the real number if it differs).

- [ ] **Step 2: Bump the version (MINOR)**

Run: `./venv/bin/python sync_version.py --minor`
Expected: `config.py` + `lucent-hub.yml` go `0.42.0 → 0.43.0`.

- [ ] **Step 3: Update the changelog (root + mirror)**

Add a `[0.43.0] — 2026-06-28` "Added" section to `CHANGELOG.md` and the mirror `luDBxP-docs/docs/entwicklung/changelog.md`: `COUNT(*)` (row count per group, column-ignored, also usable in HAVING/ORDER BY) and `COUNT(DISTINCT col)` as new aggregate options across SELECT/HAVING/ORDER BY; no route or core-module change; still open: Cross-Schema joins.

- [ ] **Step 4: Update CLAUDE.md "Bekannte Einschränkungen"**

In the Aggregat-Operationen / Tier-3 note(s), update the "Still open" line: `COUNT(*)`/`COUNT(DISTINCT)` is now done; remaining open = Cross-Schema-Joins.

- [ ] **Step 5: Update roadmap / board / Gantt + test-count badge**

Add the new item BY NAME (e.g. "COUNT(*) + COUNT(DISTINCT) — v0.43.0") to `luDBxP-docs/docs/projekt/roadmap.md` and add an item to BOTH mermaid sources (`projekt-roadmap-1.mmd` gantt line `:done, f11, 2026-06-28, 1d`; `entwicklung-arbeitspakete-1.mmd` an `E14` node modeled on `E13`, keeping Tier-2/Tier-3/Aggregat-Operationen present). Set `icon-rail.js` `TEST_COUNT` to the real count from Step 1 (`303`).

- [ ] **Step 6: Build the site and verify the overview**

Run: `cd luDBxP-docs && ./run_luDBxP_docs.sh --build`
Expected: mermaid SVGs regenerate, static site builds with no errors. Then grep `luDBxP-docs/site/` for the new item name and `COUNT(DISTINCT)` to confirm it rendered (mind HTML entity encoding); confirm Tier-2, Tier-3, Aggregat-Operationen, and the new item all appear by name. Then re-run `./venv/bin/python -m pytest -q` (still `303 passed, 2 skipped`).

- [ ] **Step 7: Commit the release**

```bash
git add -A
git commit -m "docs: Release v0.43.0 — COUNT(*) + COUNT(DISTINCT)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Pushing to `origin/master` and the `gh-pages` deploy are a separate, user-confirmed step — do not push without confirmation.

---

## Self-Review

**Spec coverage:**
- `COUNT*` → `COUNT(*)` (column ignored) → Task 1 Steps 3-5 + `test_count_star_renders_ignoring_column`. ✓
- `COUNT DISTINCT` → `COUNT(DISTINCT col)` → Task 1 Steps 3-5 + `test_count_distinct_renders_with_column`. ✓
- Both in SELECT/HAVING/ORDER BY → Task 1 + `test_count_star_in_having_and_order_by`, `test_count_distinct_in_having_and_order_by`. ✓
- Route unchanged (passthrough verified) → Task 1 API tests `test_joinpath_count_distinct_in_sql`, `test_joinpath_run_executes_count_star`; no `web/routes.py` edit. ✓
- UI options with value≠label → Task 2 Steps 1-2. ✓
- COUNT(*) column-disable at 5 sites → Task 2 Steps 3-7. ✓
- COUNT(*) table still woven (table-bound) → covered by `test_joinpath_run_executes_count_star` (VirtualMachine woven, rows returned); documented in Global Constraints. ✓
- GROUP BY derivation with COUNT(*) → `test_count_star_renders_ignoring_column` asserts `GROUP BY "Networks"."VLAN"`. ✓
- Backward compatibility → `test_existing_aggregates_unchanged`. ✓
- Dialect quoting → `test_count_distinct_and_star_quoted_per_dialect`. ✓
- Out of scope (SUM/AVG DISTINCT, multi-col DISTINCT, type-check) → not built; recorded in Global Constraints. ✓
- Release MINOR 0.43.0 + docs/badge/site → Task 3. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** tokens `"COUNT*"` / `"COUNT DISTINCT"` identical across `_ALLOWED_AGGS`, `_render_agg`, tests, and JS `AGG_OPTIONS` values; `_render_agg(agg, expr)` signature stable; JS `AGG_OPTIONS`/`aggOptionTags`/`aggOptions`/`wireAggColDisable` names consistent across Task 2 steps. ✓
