# AP-56b·Stufe 1 — Subset-Live-Walk (echte Zeilenzahlen) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den AP-56a-Subset-Footprint live ausführen — je Closure-Tabelle die echte Zeilenzahl (read-only COUNT) + Summe zeigen.

**Architecture:** Reine COUNT-Wrapper-Funktion in `core/subset.py` umhüllt jedes vorhandene AP-56a-Hüll-SELECT; ein Aggregator in `core/datapreview.py` führt sie read-only und resilient pro Tabelle via dem bestehenden `execute_select` aus; ein neuer Endpoint `/api/subset/run` spiegelt `/api/subset` und liefert Counts; das bestehende UI-Panel „Entität exportieren" bekommt einen Button + „Zeilen"-Spalte.

**Tech Stack:** Python 3.10+ (venv = 3.14), Flask, SQLAlchemy, vanilla JS; pytest; Playwright (System-python3) für Browser-Smoke.

## Global Constraints

- **Layering:** `core/` importiert **nie** Flask. `core/datapreview.py` darf SQLAlchemy importieren (tut es bereits). Web ruft Core, nie umgekehrt.
- **Read-only:** Es werden ausschließlich SELECT/COUNT ausgeführt, nie INSERT/UPDATE/DELETE/DDL.
- **Kein client-geliefertes SQL** wird ausgeführt — nur server-generierte `SubsetScript.sql` aus `generate_subset_sql`.
- **Run-Dialekt aus der URL** (`_dialect_from_url(url)`), nicht der Client-Anzeige-Dialekt — wie `/api/joinpath/run`.
- **NO CDN:** keine externen Assets; alles unter `web/`.
- **Sprache:** UI-Texte/Doku Deutsch.
- **Version:** nie `config.APP_VERSION` von Hand editieren — nur via `sync_version.py`.
- **Neustart-Reibung:** Route/Template/Python-Änderungen wirken erst nach App-Neustart; JS/CSS live.

---

### Task 1: Core — `count_sql` COUNT-Wrapper (pur)

**Files:**
- Modify: `core/subset.py` (neue Funktion am Dateiende, nach `generate_subset_sql`)
- Test: `tests/test_subset.py`

**Interfaces:**
- Consumes: nichts (reine String-Funktion).
- Produces: `count_sql(inner_sql: str) -> str` — wickelt ein SELECT in `SELECT COUNT(*) FROM (<inner ohne ;>) subset_cnt`.

- [ ] **Step 1: Write the failing test**

In `tests/test_subset.py` ans Dateiende anfügen (Import oben ergänzen: `from core.subset import compute_subset, generate_subset_sql, count_sql`):

```python
def test_count_sql_wraps_and_strips_semicolon():
    inner = "SELECT DISTINCT t0.*\nFROM Country t0\nWHERE t0.code = :root;"
    out = count_sql(inner)
    assert out.startswith("SELECT COUNT(*) FROM (")
    assert out.rstrip().endswith(") subset_cnt")
    assert ";" not in out                      # trailing ';' stripped before embedding
    assert "DISTINCT t0.*" in out              # inner SELECT (incl. DISTINCT) preserved
    assert " AS " not in out                   # alias without AS → Oracle-portable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_subset.py::test_count_sql_wraps_and_strips_semicolon -v`
Expected: FAIL with `ImportError: cannot import name 'count_sql'`

- [ ] **Step 3: Write minimal implementation**

In `core/subset.py` ans Dateiende:

```python
def count_sql(inner_sql: str) -> str:
    """Wrap a subset SELECT into a read-only row-count query.

    ``SELECT COUNT(*) FROM (<inner>) subset_cnt`` — the alias carries no ``AS``
    so it is valid across SQLite/PostgreSQL/MySQL/MSSQL and Oracle (Oracle
    forbids ``AS`` for a table alias; the others require an alias for the
    derived table). A trailing ';' is stripped before embedding.
    """
    inner = inner_sql.strip().rstrip(";").rstrip()
    return f"SELECT COUNT(*) FROM ({inner}) subset_cnt"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_subset.py::test_count_sql_wraps_and_strips_semicolon -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/subset.py tests/test_subset.py
git commit -m "feat(subset): count_sql COUNT-Wrapper für Live-Walk (AP-56b)"
```

---

### Task 2: Core — `count_subset_rows` Execution-Aggregator (resilient)

**Files:**
- Modify: `core/datapreview.py` (neue Funktion, nutzt vorhandenes `execute_select`)
- Test: `tests/test_subset.py`

**Interfaces:**
- Consumes: `core.subset.count_sql`, `core.datapreview.execute_select`, `SubsetScript` (hat `.table`, `.sql`, `.params`).
- Produces: `count_subset_rows(connection_url: str, scripts) -> list[dict]` — je Script `{"table": str, "count": int|None, "error": str|None}`, Reihenfolge = Eingaberei­henfolge. Resilient: pro Tabelle `ConnectionError` gefangen.

- [ ] **Step 1: Write the failing tests**

In `tests/test_subset.py` ans Dateiende (Imports oben ergänzen):

```python
import pytest
from sample_data.build_demo_db import build
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.datapreview import count_subset_rows, execute_select
from core.subset import SubsetScript


@pytest.fixture
def demo_url(tmp_path):
    db = tmp_path / "demo.db"
    build(str(db))
    return f"sqlite:///{db}"


def _demo_scripts(url, start, column, value):
    schema = SqlAlchemyLoader(url).load()
    result = compute_subset(schema, start)
    return schema, generate_subset_sql(
        schema, result, {"column": column, "op": "=", "value": value})


def test_count_subset_rows_matches_actual_rows(demo_url):
    # Cross-check: each table's COUNT must equal the real number of rows the
    # original (non-count) subset SELECT returns. Data-independent correctness.
    _, scripts = _demo_scripts(demo_url, "VirtualMachine", "VMID", 1)
    counts = count_subset_rows(demo_url, scripts)
    assert [c["table"] for c in counts] == [s.table for s in scripts]  # order preserved
    by_table = {c["table"]: c for c in counts}
    for s in scripts:
        actual = len(execute_select(demo_url, s.sql, s.params, max_rows=100000)["rows"])
        assert by_table[s.table]["count"] == actual
        assert by_table[s.table]["error"] is None


def test_count_subset_rows_empty_datacenter_is_one_total(demo_url):
    # DatacenterID=3 is "DC-Empty": no Cluster/Network/Host hang off it, so every
    # child count is 0 and only the root row itself counts.
    _, scripts = _demo_scripts(demo_url, "Datacenter", "DatacenterID", 3)
    counts = count_subset_rows(demo_url, scripts)
    by = {c["table"]: c for c in counts}
    assert by["Datacenter"]["count"] == 1
    assert sum(c["count"] for c in counts) == 1


def test_count_subset_rows_resilient_per_table(demo_url):
    # A script referencing a non-existent column fails only that table.
    good = SubsetScript("Datacenter",
                        "SELECT * FROM Datacenter WHERE DatacenterID = :root;",
                        {"root": 1})
    bad = SubsetScript("Bogus", "SELECT * FROM NoSuchTable;", {})
    counts = count_subset_rows(demo_url, [good, bad])
    by = {c["table"]: c for c in counts}
    assert by["Datacenter"]["count"] == 1
    assert by["Bogus"]["count"] is None
    assert by["Bogus"]["error"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_subset.py -k count_subset_rows -v`
Expected: FAIL with `ImportError: cannot import name 'count_subset_rows'`

- [ ] **Step 3: Write minimal implementation**

In `core/datapreview.py` ans Dateiende (Import oben ergänzen: `from core.subset import count_sql`):

```python
def count_subset_rows(connection_url: str, scripts) -> list:
    """Execute each subset SELECT as a read-only COUNT, resilient per table.

    For each ``SubsetScript`` the COUNT query (``count_sql``) is run via
    ``execute_select``. A per-table ``ConnectionError`` (permission, broken
    type, missing object) is caught and recorded as ``error`` with
    ``count=None`` so the remaining tables are still counted.

    Returns a list of ``{"table", "count": int|None, "error": str|None}`` in
    the same order as ``scripts``.
    """
    out = []
    for s in scripts:
        try:
            res = execute_select(connection_url, count_sql(s.sql), s.params, max_rows=1)
            count = res["rows"][0][0] if res["rows"] else 0
            out.append({"table": s.table, "count": count, "error": None})
        except ConnectionError as exc:
            out.append({"table": s.table, "count": None, "error": str(exc)})
    return out
```

Hinweis: `from core.subset import count_sql` am Kopf von `core/datapreview.py` ergänzen. (Kein Zyklus: `subset.py` importiert `datapreview` nicht.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_subset.py -k count_subset_rows -v`
Expected: PASS (3 Tests)

- [ ] **Step 5: Run the full subset test module**

Run: `./venv/bin/python -m pytest tests/test_subset.py -v`
Expected: PASS (alle bisherigen + neuen)

- [ ] **Step 6: Commit**

```bash
git add core/datapreview.py tests/test_subset.py
git commit -m "feat(subset): count_subset_rows — resilienter read-only Live-Count (AP-56b)"
```

---

### Task 3: Route — `POST /api/subset/run`

**Files:**
- Modify: `web/routes.py` (neue Route direkt nach `api_subset`, ~Z. 503)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `compute_subset`, `generate_subset_sql` (bereits importiert), `_dialect_from_url`, `count_subset_rows`.
- Produces: `POST /api/subset/run` → `{start, truncated, incomplete, total, tables:[{name,kind,via_table,depth,count,error}]}`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_api.py` nach den AP-56a-Subset-Tests (~Z. 1057) anfügen:

```python
def test_subset_run_returns_counts_and_total(client, demo_url):
    resp = client.post("/api/subset/run", json={
        "connection_url": demo_url, "start_table": "Datacenter",
        "root_filter": {"column": "DatacenterID", "op": "=", "value": 3}})
    data = resp.get_json()
    assert resp.status_code == 200
    by = {t["name"]: t for t in data["tables"]}
    assert by["Datacenter"]["count"] == 1          # DC-Empty: only the root row
    assert data["total"] == 1
    assert data["incomplete"] is False


def test_subset_run_unknown_table_returns_400(client, demo_url):
    resp = client.post("/api/subset/run", json={
        "connection_url": demo_url, "start_table": "Nope",
        "root_filter": {"column": "x", "op": "=", "value": 1}})
    assert resp.status_code == 400


def test_subset_run_missing_url_returns_400(client):
    resp = client.post("/api/subset/run", json={"start_table": "Datacenter",
        "root_filter": {"column": "DatacenterID", "op": "=", "value": 1}})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k subset_run -v`
Expected: FAIL mit 404 (Route existiert noch nicht) bzw. AssertionError

- [ ] **Step 3: Write minimal implementation**

In `web/routes.py` direkt nach der `api_subset`-Funktion (vor `@bp.post("/api/joinpath/run")`):

```python
@bp.post("/api/subset/run")
def api_subset_run():
    """AP-56b·Stufe 1: execute the AP-56a subset SELECTs read-only and return
    the real row count per closure table plus a total. Counts only — no data
    dump, no writes."""
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
    if not schema.has_column(start, rf.get("column", "")):
        return jsonify(error="unknown start table or column"), 400

    # Execution must use the connection's own dialect (not a client display
    # choice) so the quoted SQL actually runs — same rule as /api/joinpath/run.
    run_dialect = _dialect_from_url(url)
    try:
        max_depth = int(data.get("max_depth") or 5)
        result = compute_subset(schema, start, include_implied=include_implied,
                                max_depth=max_depth)
        scripts = generate_subset_sql(schema, result, rf,
                                      dialect=run_dialect, schema_name=schema_name)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    counts = {c["table"]: c for c in count_subset_rows(url, scripts)}
    tables = []
    for t in result.tables:
        c = counts.get(t.name, {"count": None, "error": "not counted"})
        tables.append({
            "name": t.name, "depth": t.depth,
            "kind": t.edge.kind if t.edge else "root",
            "via_table": t.edge.via_table if t.edge else None,
            "count": c["count"], "error": c["error"],
        })
    total = sum(t["count"] for t in tables if t["count"] is not None)
    incomplete = result.truncated or any(t["error"] for t in tables)
    return jsonify(start=result.start, truncated=result.truncated,
                   incomplete=incomplete, total=total, tables=tables)
```

Import oben in `web/routes.py` ergänzen (Z. 16):

```python
from core.datapreview import fetch_rows, execute_select, count_subset_rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k subset_run -v`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(subset): /api/subset/run — Live-Zeilenzahlen je Closure-Tabelle (AP-56b)"
```

---

### Task 4: UI — Button „Zeilen zählen (live)" + „Zeilen"-Spalte

**Files:**
- Modify: `web/static/js/app.js` (`runSubset`/`openSubset`, ~Z. 523–577)
- Smoke: Playwright (System-python3), kein JS-Unit-Framework im Projekt.

**Interfaces:**
- Consumes: `POST /api/subset/run` (Task 3), bestehende Helfer `postJSON`, `esc`, `connUrl`, `$`.
- Produces: gerenderte „Zeilen"-Spalte + Summen-Fußzeile im Subset-Panel.

- [ ] **Step 1: `runSubset` — Tabelle um leere „Zeilen"-Spalte + Zähl-Button erweitern**

In `web/static/js/app.js`, `runSubset()`: den Tabellenkopf um eine Spalte und den Ausgabe-Block um einen Button ergänzen. Ersetze den `rows`/`out.innerHTML`-Block durch:

```javascript
  const rows = res.tables.map((t) =>
    `<tr data-table="${esc(t.name)}"><td>${esc(t.name)}</td>` +
    `<td><span class="badge">${esc(t.kind)}</span></td>` +
    `<td>${esc(t.via_table || "")}</td><td>${t.depth}</td>` +
    `<td class="sub-count">—</td></tr>`).join("");
  const scripts = res.scripts.map((s) =>
    `<h4>${esc(s.table)}</h4><pre class="sql">${esc(s.sql)}</pre>`).join("");
  const trunc = res.truncated
    ? `<p class='hint'>Tiefenlimit erreicht — Hülle evtl. unvollständig.</p>` : "";
  out.innerHTML =
    `<p><button id="sub_count">Zeilen zählen (live)</button> ` +
    `<span id="sub_total" class="hint"></span></p>` +
    `<table class="subtbl cols"><thead><tr><th>Tabelle</th><th>Rolle</th>` +
    `<th>via</th><th>Tiefe</th><th>Zeilen</th></tr></thead><tbody>${rows}</tbody></table>` +
    trunc + `<h3>Export-Skelett (read-only SELECTs)</h3>${scripts}`;
  $("sub_count").addEventListener("click", runSubsetCount);
```

- [ ] **Step 2: `runSubsetCount` — Live-Count holen und Spalte füllen**

Neue Funktion direkt nach `runSubset()` einfügen:

```javascript
async function runSubsetCount() {
  const btn = $("sub_count");
  const total = $("sub_total");
  btn.disabled = true;
  total.textContent = "zähle…";
  const payload = {
    connection_url: connUrl(), start_table: $("sub_table").value,
    root_filter: { column: $("sub_col").value, op: $("sub_op").value,
                   value: $("sub_val").value },
    include_implied: $("sub_implied").checked,
  };
  let res;
  try { res = await postJSON("/api/subset/run", payload); }
  catch (e) { total.textContent = `Fehler: ${esc(String(e))}`; btn.disabled = false; return; }
  res.tables.forEach((t) => {
    const cell = document.querySelector(`tr[data-table="${CSS.escape(t.name)}"] .sub-count`);
    if (!cell) return;
    if (t.error) { cell.textContent = "Fehler"; cell.title = t.error; }
    else { cell.textContent = String(t.count); cell.title = ""; }
  });
  total.textContent = `Summe: ${res.total}` +
    (res.incomplete ? " · unvollständig (Tiefenlimit/Fehler)" : "");
  btn.disabled = false;
}
```

- [ ] **Step 3: Panel-Hinweis um Live-Count ergänzen**

In `openSubset()` den Hinweis-Absatz ersetzen:

```javascript
    `<p class="hint">Referenzielle FK-Hülle einer Start-Zeile (Kinder abwärts + ` +
    `Lookups aufwärts). „Footprint bauen" führt nichts aus; „Zeilen zählen (live)" ` +
    `führt read-only COUNT-Queries gegen die DB aus.</p>` +
```

- [ ] **Step 4: App neu starten + Browser-Smoke**

App neu starten (Route/JS-Änderung → JS live, aber Route 3 braucht Neustart):

```bash
pkill -f "run.sh|app.py|waitress" 2>/dev/null; sleep 1
bash run.sh --skip-setup &
sleep 3
```

Playwright-Smoke (System-python3) — Demo verbinden, Footprint bauen, zählen, Spalte + Summe prüfen. Skript unter `scratchpad/smoke_subset_count.py`:

```python
from playwright.sync_api import sync_playwright
import pathlib
DB = pathlib.Path("sample_data/demo_cmdb.db").resolve()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto("http://127.0.0.1:5057")
    pg.fill("#conn_filepath, input[name=filepath], #filepath", str(DB))  # passende Selektoren ggf. anpassen
    # … verbinden (Testen/Speichern je nach AP-64-UI), dann:
    # Sidebar → "Entität exportieren", Start-Tabelle "Datacenter", Filter DatacenterID = 3
    # "Footprint bauen" → "Zeilen zählen (live)"
    pg.click("#sub_count")
    pg.wait_for_selector("#sub_total:has-text('Summe')")
    print(pg.inner_text("#sub_total"))
    assert "Summe: 1" in pg.inner_text("#sub_total")
    b.close()
```

Run: `python3 scratchpad/smoke_subset_count.py`
Expected: Ausgabe enthält `Summe: 1`. (Selektoren der Verbindungs-/Sidebar-Schritte beim Schreiben an die laufende UI anpassen — der entscheidende Beweis ist die gefüllte „Zeilen"-Spalte + `Summe: 1`.)

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(subset): UI „Zeilen zählen (live)" — Live-Count-Spalte + Summe (AP-56b)"
```

---

### Task 5: Release & Doku

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), icon-rail/zensical, Changelog (EN + DE-Mirror), Roadmap/Board/Gantt, `CLAUDE.md`, Kennzahlen-Seite, Site-Build, gh-pages.

**Interfaces:** keine Code-Interfaces — Doku-/Release-Schritt.

- [ ] **Step 1: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (vorher 359 passed, 2 skipped → jetzt +7 neue Tests = 366 passed, 2 skipped).

- [ ] **Step 2: Version bump (Feature → minor)**

```bash
./venv/bin/python sync_version.py --minor   # v0.48.3 → v0.49.0
```

- [ ] **Step 3: Abgeleitete Versions-/Test-Zahlen nachziehen**

icon-rail `APP_VERSION`/`TEST_COUNT`, zensical-Badges, Kennzahlen-Seite (`docs/session-kennzahlen.md`, **hartkodiert**) auf neue Version + Testzahl. (Konkrete Dateien per `grep -rl "0.48.3" docs/ web/ *.toml *.yml` finden.)

- [ ] **Step 4: Changelog EN + DE-Mirror**

Eintrag `v0.49.0 — AP-56b·Stufe 1: Subset-Live-Zeilenzahlen` in beide Changelog-Dateien.

- [ ] **Step 5: Roadmap/Board/Gantt — AP-56b aufsplitten**

AP-56b → **AP-56b·Stufe 1 (erledigt)** + **AP-56b·Stufe 2 (offen: IN-Listen/Daten-Dump)**, jedes Item **namentlich** in Startseite/Board/Gantt enumeriert (keine Sammel-Chips). Gerenderte Übersicht nach Build gegenprüfen.

- [ ] **Step 6: CLAUDE.md „Bekannte Einschränkungen"**

Subset-Block (AP-56a) um den Live-Count ergänzen: „Live-Zeilenzahlen je Closure-Tabelle (AP-56b·Stufe 1, read-only COUNT); IN-Listen/Daten-Dump = Stufe 2 (offen)."

- [ ] **Step 7: Site-Build + gh-pages**

Site bauen, nach `origin/master` pushen, gh-pages-Worktree deployen (Schritte wie in den letzten Releases).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.49.0 — AP-56b·Stufe 1 (Subset-Live-Zeilenzahlen)"
```

---

## Self-Review (vom Plan-Autor durchgeführt)

- **Spec-Abdeckung:** §1 count_sql → Task 1; §2 count_subset_rows → Task 2; §3 Route → Task 3; §4 UI → Task 4; §5 Tests → in Tasks 1–4 verteilt (count_sql-Unit, Live-Count + Resilienz, Route-Test, Browser-Smoke); §6 Scope-Cuts → respektiert (kein Dump/IN-Listen/Timeout); §7 Release → Task 5. Keine Lücke.
- **Platzhalter:** keine TBD/„handle errors" — resiliente Fehlerbehandlung ist in Task 2 auscodiert.
- **Typkonsistenz:** `count_sql(inner_sql)->str`, `count_subset_rows(url, scripts)->list[{table,count,error}]`, Route-Response `{start,truncated,incomplete,total,tables[]}` durchgängig identisch in Tasks 1→2→3→4 verwendet.
- **Daten-Robustheit:** Live-Count-Test cross-checkt COUNT gegen `len(rows)` (datenunabhängig) + deterministischer Anker DatacenterID=3 (DC-Empty, total=1).
