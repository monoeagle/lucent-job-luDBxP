# Tier-3 — GROUP BY + Aggregate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the read-only SQL generator to emit aggregate functions per SELECT column with an automatically derived GROUP BY, surfaced in the Join-Builder UI.

**Architecture:** Each `Selection` carries an optional aggregate (`COUNT/SUM/AVG/MIN/MAX`). The generator wraps aggregated columns as `FUNC(col)` and derives `GROUP BY` from the *non*-aggregated SELECT columns (clause order `WHERE → GROUP BY → ORDER BY → LIMIT`). The route parses an `agg` field on start/target/extra-selects; the frontend adds an aggregate dropdown to every SELECT-list entry. The read-only run endpoint reuses the same generator, so grouped queries execute unchanged.

**Tech Stack:** Python 3.14 (venv), Flask, SQLAlchemy, sqlglot (analyzer only), vanilla JS, pytest.

## Global Constraints

- **Layering:** `core/` must never import Flask. `web/` calls `core/`, never the reverse.
- **Read-only:** the tool only generates/executes SELECTs; never INSERT/UPDATE/DELETE/DDL.
- **No CDN:** all JS/CSS/fonts stay bundled under `web/` — never add `<script src="https://…">`.
- **Language:** all user-facing copy and commit messages in German.
- **Version:** never edit `config.APP_VERSION` by hand — use `./venv/bin/python sync_version.py --minor` at release time (a feature ⇒ MINOR bump).
- **Tests:** run with `./venv/bin/python -m pytest`. Baseline before starting: **272 passed, 2 skipped**.
- **Backward compatibility:** with no aggregate anywhere, generated SQL must be byte-identical to today. `Selection("t","c")` (no agg arg) must stay valid.
- **Aggregate allowlist (verbatim):** `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`. Empty string `""` means "no aggregate".
- **Out of scope (do NOT build):** HAVING, `COUNT(*)`, `COUNT(DISTINCT …)`, ORDER BY on aggregates, column-type validation.

---

## Task 1: Generator — aggregates + auto GROUP BY

**Files:**
- Modify: `core/sqlgen.py` (`Selection` dataclass ~`106-110`; SELECT-list loop ~`182-191`; final assembly ~`276-280`)
- Test: `tests/test_sqlgen.py`, `tests/test_sqlgen_dialect.py`

**Interfaces:**
- Consumes: existing `generate_sql(path, selects, filters, *, distinct, order_by, limit, join_types, dialect, schema)` and `JoinPath`/`JoinStep`.
- Produces:
  - `Selection(table: str, column: str, agg: str = "")` — `agg` is `""` or one of the allowlist.
  - `core.sqlgen._ALLOWED_AGGS: set[str]` = `{"COUNT","SUM","AVG","MIN","MAX"}`.
  - `generate_sql` raises `ValueError` on an unsupported aggregate; emits `GROUP BY` only when at least one select is aggregated **and** at least one is not.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_sqlgen.py` (reuse the module's existing `_path()` helper):

```python
def test_aggregate_wraps_column_and_groups_by_rest():
    # COUNT on the target column -> GROUP BY the non-aggregated select column.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert '"Networks"."VLAN"' in g.sql
    assert 'GROUP BY "Networks"."VLAN"' in g.sql
    # GROUP BY is identical in the copy/inline variant (no filter values in it).
    assert 'GROUP BY "Networks"."VLAN"' in g.sql_inline


def test_no_aggregate_emits_no_group_by_unchanged():
    # Backward compatibility: without any aggregate the SQL has no GROUP BY.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID")))
    assert "GROUP BY" not in g.sql


def test_all_columns_aggregated_emits_no_group_by():
    # Every select aggregated -> single-row aggregate, no GROUP BY.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN", agg="MIN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'MIN("Networks"."VLAN")' in g.sql
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert "GROUP BY" not in g.sql


def test_group_by_clause_order_before_order_by_and_limit():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     order_by=(("Networks", "VLAN", "ASC"),),
                     limit=10)
    # WHERE -> GROUP BY -> ORDER BY -> LIMIT
    assert g.sql.index("GROUP BY") < g.sql.index("ORDER BY") < g.sql.index("LIMIT")


def test_same_column_as_key_and_aggregate_coexist():
    # A column may appear once plain (group key) and once aggregated.
    g = generate_sql(_path(),
                     selects=(Selection("VMwareCluster", "ClusterID"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert 'GROUP BY "VMwareCluster"."ClusterID"' in g.sql


def test_unsupported_aggregate_raises_value_error():
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN", agg="MEDIAN"),))
```

Add to `tests/test_sqlgen_dialect.py` (import `generate_sql, Selection` and a path helper consistent with that file's existing imports):

```python
def test_group_by_quotes_and_qualifies_per_dialect():
    from core.sqlgen import MSSQL
    path = JoinPath(tables=("Host", "VirtualMachine"),
                    steps=(JoinStep("Host", "VirtualMachine", (("HostID", "HostID"),)),))
    g = generate_sql(path,
                     selects=(Selection("Host", "Hostname"),
                              Selection("VirtualMachine", "VMID", agg="COUNT")),
                     dialect=MSSQL, schema="dbo")
    # MSSQL bracket-quotes and schema-qualifies the GROUP BY column too.
    assert "GROUP BY [dbo].[Host].[Hostname]" in g.sql
    assert "COUNT([dbo].[VirtualMachine].[VMID])" in g.sql
```

> If `tests/test_sqlgen_dialect.py` does not already import `JoinPath`/`JoinStep`, add `from core.pathfinder import JoinPath, JoinStep` and `from core.sqlgen import generate_sql, Selection` at the top to match the helper usage above.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -k "aggregate or group_by or no_aggregate" tests/test_sqlgen_dialect.py -k "group_by" -v`
Expected: FAIL — `Selection(...)` raises `TypeError: __init__() got an unexpected keyword argument 'agg'`.

- [ ] **Step 3: Add the `agg` field to `Selection`**

In `core/sqlgen.py`, change the `Selection` dataclass:

```python
@dataclass(frozen=True)
class Selection:
    table: str
    column: str
    agg: str = ""   # "" = plain column; else one of _ALLOWED_AGGS -> FUNC(col)
```

- [ ] **Step 4: Add the aggregate allowlist constant**

In `core/sqlgen.py`, next to the existing `_ALLOWED_OPS` / `_ALLOWED_DIRECTIONS` constants:

```python
# Tier-3: aggregate functions allowed on a Selection. Empty agg = no aggregate.
_ALLOWED_AGGS = frozenset({"COUNT", "SUM", "AVG", "MIN", "MAX"})
```

- [ ] **Step 5: Wrap aggregated columns in the SELECT-list loop**

In `generate_sql`, replace the existing SELECT-list loop:

```python
    for k, s in enumerate(selects):
        comma = "," if k < len(selects) - 1 else ""
        lines.append(f"    {dialect.qualify(s.table, s.column, schema)}{comma}")
```

with:

```python
    for k, s in enumerate(selects):
        comma = "," if k < len(selects) - 1 else ""
        expr = dialect.qualify(s.table, s.column, schema)
        if s.agg:
            if s.agg not in _ALLOWED_AGGS:
                raise ValueError(f"Unsupported aggregate: {s.agg!r}")
            expr = f"{s.agg}({expr})"
        lines.append(f"    {expr}{comma}")
```

- [ ] **Step 6: Build the GROUP BY block and insert it into the final assembly**

In `generate_sql`, just before the final `sql = "\n".join(...)` assembly (after `where_param`/`where_inline` are computed and `tail` is built), add:

```python
    # Tier-3 auto-GROUP-BY: group by every non-aggregated select, but only when
    # at least one select IS aggregated (else this is a plain row query). All
    # columns aggregated -> empty group_cols -> single-row aggregate, no GROUP BY.
    group_lines: list[str] = []
    has_agg = any(s.agg for s in selects)
    group_cols = [s for s in selects if not s.agg]
    if has_agg and group_cols:
        parts = [dialect.qualify(s.table, s.column, schema) for s in group_cols]
        group_lines.append("GROUP BY " + ", ".join(parts))
```

Then change the two assembly lines to splice `group_lines` between WHERE and `tail`:

```python
    sql = "\n".join(lines + where_param + group_lines + tail)
    sql_inline = "\n".join(lines + where_inline + group_lines + tail) + ";"
```

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlgen.py -k "aggregate or group_by or no_aggregate" tests/test_sqlgen_dialect.py -k "group_by" -v`
Expected: PASS (all 7 new tests green).

- [ ] **Step 8: Run the full suite to confirm no regression**

Run: `./venv/bin/python -m pytest -q`
Expected: previous count + 7 new passes, still 2 skipped (e.g. `279 passed, 2 skipped`).

- [ ] **Step 9: Commit**

```bash
git add core/sqlgen.py tests/test_sqlgen.py tests/test_sqlgen_dialect.py
git commit -m "feat: Tier-3 Generator — Aggregate (COUNT/SUM/AVG/MIN/MAX) + Auto-GROUP-BY

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Route — parse `agg` and thread it through

**Files:**
- Modify: `web/routes.py` (`_parse_joinpath_params` extra-selects build ~`257-261`; `_make_path_gen` select dedup loop ~`328-336`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Selection(table, column, agg="")` from Task 1; existing `_parse_joinpath_params` / `_make_path_gen` helpers; `/api/joinpath` and `/api/joinpath/run` already wrap `generate_sql` in `try/except ValueError -> 400`.
- Produces: request JSON now accepts an optional `agg` string on `start`, `target`, and each `extra_selects[]` item. SELECT-list dedup key becomes `(table, column, agg)` so a plain and an aggregated copy of one column coexist.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py` (uses the existing `client`, `inventory_url`, and `demo_url` fixtures):

```python
def test_joinpath_aggregate_emits_group_by(client, inventory_url):
    """An agg on the target column produces FUNC(col) + GROUP BY on the rest."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "filters": [],
    })
    assert resp.status_code == 200
    sql = resp.get_json()["paths"][0]["sql"]
    assert 'COUNT("VMwareCluster"."ClusterID")' in sql
    assert 'GROUP BY "Networks"."VLAN"' in sql


def test_joinpath_unknown_aggregate_returns_400(client, inventory_url):
    """An unsupported aggregate is rejected with 400 (ValueError from generator)."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "MEDIAN"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_run_executes_grouped_aggregate(client, demo_url):
    """Read-only run path executes a grouped COUNT and returns grouped rows.

    Host 1-N VirtualMachine (VM.HostID -> Host): count VMs per host.
    """
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "VirtualMachine", "column": "VMID", "agg": "COUNT"},
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "GROUP BY" in data["sql"]
    assert isinstance(data["rows"], list) and len(data["rows"]) >= 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "aggregate or grouped" -v`
Expected: FAIL — `test_joinpath_aggregate_emits_group_by` finds no `COUNT(...)` (agg ignored), and the run test finds no `GROUP BY` in `data["sql"]`.

- [ ] **Step 3: Parse `agg` for extra selects**

In `web/routes.py`, in `_parse_joinpath_params`, change the extra-selects build:

```python
    # --- Extra SELECT columns ---
    extra_selections = tuple(
        Selection(es["table"], es["column"], es.get("agg", ""))
        for es in data.get("extra_selects", [])
    )
```

- [ ] **Step 4: Parse `agg` for start/target and dedup including agg**

In `web/routes.py`, in `_make_path_gen`, change the select-collection loop:

```python
    seen: set[tuple[str, str, str]] = set()
    selects_for_path: list[Selection] = []
    for sel in (Selection(start["table"], start["column"], start.get("agg", "")),
                Selection(target["table"], target["column"], target.get("agg", "")),
                *extra_selections):
        key = (sel.table, sel.column, sel.agg)
        if key not in seen:
            seen.add(key)
            selects_for_path.append(sel)
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "aggregate or grouped" -v`
Expected: PASS (3 new tests green).

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `./venv/bin/python -m pytest -q`
Expected: prior count + 3 new passes, still 2 skipped (e.g. `282 passed, 2 skipped`).

- [ ] **Step 7: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat: Tier-3 Route — agg auf start/target/extra_selects, GROUP-BY im Run-Pfad

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Frontend — aggregate dropdowns in the Join-Builder

**Files:**
- Modify: `web/static/js/app.js` (`openJoinBuilder` markup ~`291-298`; `addColRow` ~`643-661`; `collectExtraSelects` ~`663-671`; `collectJoinBody` ~`692-707`; `swapStartTarget` ~`678-690`)
- Test: manual browser verification (no JS unit harness in this project — UI is verified by driving the app; see memory note "JS-UI via Playwright verifizieren").

**Interfaces:**
- Consumes: the `/api/joinpath` request body now honoring `agg` on `start`, `target`, and `extra_selects[]` (Task 2).
- Produces: an aggregate `<select>` (`—`/COUNT/SUM/AVG/MIN/MAX) next to `start_col`, next to `target_col`, and in every extra-column row; `collectJoinBody()` includes the chosen `agg` (empty string when `—`).

- [ ] **Step 1: Add a shared aggregate-options helper**

In `web/static/js/app.js`, near `optionList` (~line 78), add:

```javascript
// Tier-3: aggregate <option>s for a SELECT column. Empty value = no aggregate.
const AGG_FUNCS = ["COUNT", "SUM", "AVG", "MIN", "MAX"];
function aggOptions() {
  return `<option value="">—</option>` +
    AGG_FUNCS.map((f) => `<option value="${f}">${f}</option>`).join("");
}
```

- [ ] **Step 2: Add aggregate selects to the Start and Ziel rows**

In `openJoinBuilder`, change the Start and Ziel row markup so each carries an aggregate select:

```javascript
    `<div class="row"><label>Start</label>` +
    `<select id="start_table"></select> . <select id="start_col"></select>` +
    `<select id="start_agg" class="jb-agg" title="Aggregatfunktion">${aggOptions()}</select></div>` +
    `<div class="row"><label>Ziel</label>` +
    `<select id="target_table"></select> . <select id="target_col"></select>` +
    `<select id="target_agg" class="jb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<button id="btn_swap" class="jb-swap" type="button" title="Start und Ziel vertauschen" ` +
    `aria-label="Start und Ziel vertauschen">⇅</button></div>` +
```

- [ ] **Step 3: Add an aggregate select to each extra-column row**

In `addColRow`, add the aggregate select to the row markup:

```javascript
  row.innerHTML =
    `<select class="c-table">${optionList(names)}</select>` +
    `<select class="c-col"></select>` +
    `<select class="c-agg jb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<button type="button" class="c-del">✕</button>`;
```

- [ ] **Step 4: Collect `agg` from extra rows and from start/target**

In `collectExtraSelects`, include the chosen aggregate:

```javascript
function collectExtraSelects() {
  const out = [];
  document.querySelectorAll("#extra_cols .col-row").forEach((row) => {
    const table = row.querySelector(".c-table").value;
    const column = row.querySelector(".c-col").value;
    const agg = row.querySelector(".c-agg").value;
    if (table && column) out.push({ table, column, agg });
  });
  return out;
}
```

In `collectJoinBody`, attach `agg` to start and target:

```javascript
    start: { table: $("start_table").value, column: $("start_col").value,
             agg: $("start_agg") ? $("start_agg").value : "" },
    target: { table: $("target_table").value, column: $("target_col").value,
              agg: $("target_agg") ? $("target_agg").value : "" },
```

- [ ] **Step 5: Swap the aggregate too in `swapStartTarget`**

In `swapStartTarget`, after the existing table/column swap lines and before the graph-marker block, add:

```javascript
  if ($("start_agg") && $("target_agg")) {
    const sa = $("start_agg").value;
    $("start_agg").value = $("target_agg").value;
    $("target_agg").value = sa;
  }
```

- [ ] **Step 6: Manual browser verification**

Start the app and drive the Join-Builder:

```bash
bash run.sh --tray   # or: LUCENT_PORT=5057 bash run.sh --skip-setup
```

Verify in the browser (connect to the bundled demo DB):
1. Open **Join-Builder**. Start = `Host.Hostname`, Ziel = `VirtualMachine.VMID`, set the **Ziel** aggregate to `COUNT`. Click **Join-Pfad bauen**.
   Expected SQL contains `COUNT("VirtualMachine"."VMID")` and `GROUP BY "Host"."Hostname"`.
2. Click **Aktualisieren** (run) — the result table shows one row per host with a count column (read-only execution succeeded).
3. Set the aggregate back to `—` on both → rebuild → SQL has **no** `GROUP BY` (unchanged behavior).
4. Click **⇅ (swap)** with an aggregate set on Ziel → the aggregate moves to Start along with the column.

Confirm no console errors (no CDN requests; all assets local).

- [ ] **Step 7: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: Tier-3 UI — Aggregat-Dropdown an Start/Ziel/Extra-Spalten (Auto-GROUP-BY)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Release — version, docs, badge, site

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py` — never by hand), `CHANGELOG.md` (+ doc mirror), `CLAUDE.md` (Bekannte Einschränkungen block), roadmap/board/Gantt + site source, test-count badge.
- Test: full suite + site build.

**Interfaces:**
- Consumes: the completed Tasks 1-3 (generator, route, UI) on a clean tree, full suite green.
- Produces: a tagged MINOR release documenting Tier-3 as done and HAVING/`COUNT(*)`/Cross-Schema as still open.

- [ ] **Step 1: Confirm the full suite is green**

Run: `./venv/bin/python -m pytest -q`
Expected: `285 passed, 2 skipped` (272 baseline + 7 + 3 + 3 new; adjust if counts differ — record the real number).

- [ ] **Step 2: Bump the version (MINOR — this is a feature)**

Run: `./venv/bin/python sync_version.py --minor`
Expected: `config.py` + `lucent-hub.yml` updated in lockstep (e.g. `0.40.0 → 0.41.0`). Note the new version.

- [ ] **Step 3: Update the changelog (and its doc mirror)**

Add a `0.41.0` section to `CHANGELOG.md` (and the mirrored copy under `docs/` if present) describing: Tier-3 GROUP BY + aggregates (COUNT/SUM/AVG/MIN/MAX, auto-GROUP-BY), generated SQL gains GROUP BY, read-only run executes grouped queries; HAVING / `COUNT(*)` / Cross-Schema remain open.

- [ ] **Step 4: Update CLAUDE.md "Bekannte Einschränkungen"**

In `CLAUDE.md`, update the Tier-2 note's "Still open" line: Tier-3 (GROUP BY/Aggregate) is now **done**; only HAVING, `COUNT(*)`/`COUNT(DISTINCT)`, and Cross-Schema-Joins remain open.

- [ ] **Step 5: Update roadmap / board / Gantt + test-count badge**

Move Tier-3 to done across the roadmap, start-page board, and Gantt source (enumerate the item by name — no umbrella entry). Update the test-count badge to the real number from Step 1. Rebuild the site per the project's site-build step.

- [ ] **Step 6: Verify the rendered overview lists Tier-3 and rebuild the suite**

Grep the rendered site/overview for the Tier-3 item by name (mind HTML entity encoding) to confirm it is present and marked done. Then:
Run: `./venv/bin/python -m pytest -q`
Expected: same green count as Step 1.

- [ ] **Step 7: Commit the release**

```bash
git add -A
git commit -m "docs: Release v0.41.0 — Tier-3 GROUP BY/Aggregate (Changelog/CLAUDE/Roadmap/Site)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Pushing to `origin/master` and the `gh-pages` deploy are a separate, user-confirmed step (see release-/deploy memory) — do not push without confirmation.

---

## Self-Review

**Spec coverage:**
- Auto-GROUP-BY model (3 cases) → Task 1 Steps 5-6 + tests in Step 1. ✓
- Standard-5 aggregates as `func(col)` → Task 1 Steps 3-5. ✓
- Aggregate on start/target/extra → Task 2 Steps 3-4 (route), Task 3 Steps 2-4 (UI). ✓
- Clause order WHERE→GROUP BY→ORDER BY→LIMIT → Task 1 Step 6 + `test_group_by_clause_order...`. ✓
- Dedup `(table, column, agg)` → Task 2 Step 4 + `test_same_column_as_key_and_aggregate_coexist`. ✓
- Allowlist ValueError → Task 1 Step 5 + Task 2 `test_joinpath_unknown_aggregate_returns_400`. ✓
- Read-only run executes grouped SQL → Task 2 `test_joinpath_run_executes_grouped_aggregate`. ✓
- Backward compatibility (no agg ⇒ unchanged SQL) → `test_no_aggregate_emits_no_group_by_unchanged`. ✓
- Swap handling → Task 3 Step 5. ✓
- Out of scope (HAVING/COUNT(*)/ORDER BY agg/type-check) → not built; recorded in Global Constraints + Task 4 docs. ✓
- Release (MINOR bump, changelog/CLAUDE/roadmap/board/badge/site) → Task 4. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** `Selection(table, column, agg="")`, `_ALLOWED_AGGS` (frozenset of 5), dedup key `(table, column, agg)`, `aggOptions()` / `AGG_FUNCS`, request field `agg` — names consistent across Tasks 1-3. ✓
