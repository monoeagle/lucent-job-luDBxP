# AP-56b·Stufe 2 — Subset-Daten-Dump (JSON) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die AP-56a-Hüll-SELECTs read-only ausführen und je Closure-Tabelle die echten Zeilen als herunterladbares JSON-Bundle liefern (Daten-Dump für die ETL-Schicht).

**Architecture:** Ein Execution-Aggregator in `core/datapreview.py` führt die vorhandenen `SubsetScript`-SELECTs roh aus (statt COUNT-gewrappt wie Stufe 1), kappt je Tabelle bei `MAX_RESULT_ROWS` mit `cap+1`-Truncation-Erkennung und ist pro Tabelle resilient. Ein neuer Endpoint `/api/subset/dump` spiegelt `/api/subset/run` und gibt das JSON-Bundle; die UI baut daraus einen client-seitigen Blob-Download.

**Tech Stack:** Python 3.10+ (venv = 3.14), Flask, SQLAlchemy, vanilla JS; pytest; Playwright (System-python3) für Browser-Smoke.

## Global Constraints

- **Layering:** `core/` importiert **nie** Flask. `core/datapreview.py` darf SQLAlchemy importieren (tut es). Web ruft Core, nie umgekehrt.
- **Read-only:** nur SELECT, nie INSERT/UPDATE/DELETE/DDL.
- **Kein client-geliefertes SQL** wird ausgeführt — nur server-generierte `SubsetScript.sql` aus `generate_subset_sql`.
- **Run-Dialekt aus der URL** (`_dialect_from_url(url)`), nicht der Client-Anzeige-Dialekt — wie `/api/subset/run` und `/api/joinpath/run`.
- **Per-Tabelle-Cap = `config.MAX_RESULT_ROWS`** (= 5000); Truncation je Tabelle + Bundle laut geflaggt.
- **`incomplete` = Footprint-truncated OR irgendeine Tabelle truncated OR irgendein error.**
- **NO CDN:** keine externen Assets; Download client-seitig via Browser-nativem Blob.
- **Sprache:** UI-Texte/Doku Deutsch.
- **Version:** nie `config.APP_VERSION` von Hand editieren — nur via `sync_version.py`.
- **Neustart-Reibung:** Route/Template/Python-Änderungen wirken erst nach App-Neustart; JS/CSS live. Route-TESTS nutzen den Flask-Testclient (kein laufender Server nötig).

---

### Task 1: Core — `dump_subset_rows` Execution-Aggregator (resilient, truncation-aware)

**Files:**
- Modify: `core/datapreview.py` (neue Funktion nach `count_subset_rows`)
- Test: `tests/test_subset.py`

**Interfaces:**
- Consumes: `core.datapreview.execute_select`, `SubsetScript` (`.table`, `.sql`, `.params`), `compute_subset`/`generate_subset_sql` (für die Tests).
- Produces: `dump_subset_rows(connection_url, scripts, *, max_rows_per_table) -> list[dict]` — je Script `{"table","columns":[...],"rows":[[...]],"row_count":int,"truncated":bool,"error":str|None}`, Reihenfolge = Eingabereihenfolge.

- [ ] **Step 1: Write the failing tests**

In `tests/test_subset.py` ans Dateiende anfügen. Die Imports `compute_subset, generate_subset_sql, count_sql` und `from sample_data.build_demo_db import build`, `from core.loaders.sqlalchemy_loader import SqlAlchemyLoader`, `from core.subset import SubsetScript`, die `demo_url`-Fixture und die `_demo_scripts`-Helper EXISTIEREN bereits aus den Stufe-1-Tests in dieser Datei. Ergänze den Import `count_subset_rows, execute_select` um `dump_subset_rows`:

```python
from core.datapreview import count_subset_rows, execute_select, dump_subset_rows
```

Dann die Tests:

```python
def test_dump_subset_rows_matches_actual_rows(demo_url):
    # Cross-check: each table's dumped rows equal the rows the original subset
    # SELECT returns directly. Data-independent.
    _, scripts = _demo_scripts(demo_url, "VirtualMachine", "VMID", 1)
    dump = dump_subset_rows(demo_url, scripts, max_rows_per_table=5000)
    assert [d["table"] for d in dump] == [s.table for s in scripts]  # order preserved
    by = {d["table"]: d for d in dump}
    for s in scripts:
        direct = execute_select(demo_url, s.sql, s.params, max_rows=100000)
        assert by[s.table]["rows"] == direct["rows"]
        assert by[s.table]["columns"] == direct["columns"]
        assert by[s.table]["row_count"] == len(direct["rows"])
        assert by[s.table]["truncated"] is False
        assert by[s.table]["error"] is None


def test_dump_subset_rows_empty_datacenter(demo_url):
    # DatacenterID=3 = "DC-Empty": root has 1 row, every child has 0.
    _, scripts = _demo_scripts(demo_url, "Datacenter", "DatacenterID", 3)
    dump = dump_subset_rows(demo_url, scripts, max_rows_per_table=5000)
    by = {d["table"]: d for d in dump}
    assert by["Datacenter"]["row_count"] == 1
    assert sum(d["row_count"] for d in dump) == 1
    assert all(d["error"] is None and d["truncated"] is False for d in dump)


def test_dump_subset_rows_truncates_per_table(demo_url):
    # A tiny cap forces truncation on any table whose subset has >2 rows.
    _, scripts = _demo_scripts(demo_url, "Datacenter", "DatacenterID", 1)
    dump = dump_subset_rows(demo_url, scripts, max_rows_per_table=2)
    # At least one closure table of DC-Frankfurt has >2 rows (e.g. Host/VirtualMachine).
    truncated = [d for d in dump if d["truncated"]]
    assert truncated, "expected at least one truncated table with cap=2"
    for d in truncated:
        assert d["row_count"] == 2 and len(d["rows"]) == 2


def test_dump_subset_rows_resilient_per_table(demo_url):
    good = SubsetScript("Datacenter",
                        "SELECT * FROM Datacenter WHERE DatacenterID = :root;",
                        {"root": 1})
    bad = SubsetScript("Bogus", "SELECT * FROM NoSuchTable;", {})
    dump = dump_subset_rows(demo_url, [good, bad], max_rows_per_table=5000)
    by = {d["table"]: d for d in dump}
    assert by["Datacenter"]["row_count"] == 1
    assert by["Bogus"]["rows"] == [] and by["Bogus"]["error"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_subset.py -k dump_subset_rows -v`
Expected: FAIL with `ImportError: cannot import name 'dump_subset_rows'`

- [ ] **Step 3: Write minimal implementation**

In `core/datapreview.py` ans Dateiende (nach `count_subset_rows`):

```python
def dump_subset_rows(connection_url: str, scripts, *, max_rows_per_table: int) -> list:
    """Execute each subset SELECT read-only and capture its rows. Resilient per table.

    Fetches up to ``max_rows_per_table + 1`` rows to detect truncation: if more
    than the cap come back, the table is flagged ``truncated`` and the rows are
    cut to the cap. A per-table ``ConnectionError`` is caught and recorded as
    ``error`` (empty rows) so the remaining tables still dump.

    Returns a list of ``{"table","columns","rows","row_count","truncated","error"}``
    in the same order as ``scripts``.
    """
    out = []
    for s in scripts:
        try:
            res = execute_select(connection_url, s.sql, s.params,
                                 max_rows=max_rows_per_table + 1)
            rows = res["rows"]
            truncated = len(rows) > max_rows_per_table
            if truncated:
                rows = rows[:max_rows_per_table]
            out.append({"table": s.table, "columns": res["columns"], "rows": rows,
                        "row_count": len(rows), "truncated": truncated, "error": None})
        except ConnectionError as exc:
            out.append({"table": s.table, "columns": [], "rows": [], "row_count": 0,
                        "truncated": False, "error": str(exc)})
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_subset.py -k dump_subset_rows -v`
Expected: PASS (4 Tests)

- [ ] **Step 5: Run the full subset module**

Run: `./venv/bin/python -m pytest tests/test_subset.py -q`
Expected: PASS (alle bisherigen + 4 neue)

- [ ] **Step 6: Commit**

```bash
git add core/datapreview.py tests/test_subset.py
git commit -m "feat(subset): dump_subset_rows — read-only Zeilen-Dump je Tabelle, truncation-aware (AP-56b Stufe 2)"
```

---

### Task 2: Route — `POST /api/subset/dump`

**Files:**
- Modify: `web/routes.py` (neue Route nach `api_subset_run`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `compute_subset`, `generate_subset_sql` (bereits importiert), `_dialect_from_url`, `_NO_URL_MSG`, `SqlAlchemyLoader`, `schema.has_column`, `config.MAX_RESULT_ROWS`, `dump_subset_rows` (Task 1).
- Produces: `POST /api/subset/dump` → `{start, truncated, incomplete, row_cap, tables:[{name,kind,via_table,depth,columns,rows,row_count,truncated,error}]}`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_api.py` nach den AP-56b-`/api/subset/run`-Tests anfügen (`client` und `demo_url`-Fixtures existieren bereits):

```python
def test_subset_dump_returns_bundle(client, demo_url):
    resp = client.post("/api/subset/dump", json={
        "connection_url": demo_url, "start_table": "Datacenter",
        "root_filter": {"column": "DatacenterID", "op": "=", "value": 3}})
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["row_cap"] == 5000 and data["incomplete"] is False
    by = {t["name"]: t for t in data["tables"]}
    assert by["Datacenter"]["row_count"] == 1
    assert "columns" in by["Datacenter"] and "rows" in by["Datacenter"]
    assert len(by["Datacenter"]["rows"]) == 1
    # closure children of the empty datacenter are present but empty
    assert sum(t["row_count"] for t in data["tables"]) == 1


def test_subset_dump_unknown_table_returns_400(client, demo_url):
    resp = client.post("/api/subset/dump", json={
        "connection_url": demo_url, "start_table": "Nope",
        "root_filter": {"column": "x", "op": "=", "value": 1}})
    assert resp.status_code == 400


def test_subset_dump_missing_url_returns_400(client):
    resp = client.post("/api/subset/dump", json={"start_table": "Datacenter",
        "root_filter": {"column": "DatacenterID", "op": "=", "value": 1}})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k subset_dump -v`
Expected: FAIL mit 404 (Route fehlt) bzw. AssertionError

- [ ] **Step 3: Write minimal implementation**

Import auf `web/routes.py` Zeile 16 erweitern:

```python
from core.datapreview import fetch_rows, execute_select, count_subset_rows, dump_subset_rows
```

In `web/routes.py` direkt nach der `api_subset_run`-Funktion (vor `@bp.post("/api/joinpath/run")`):

```python
@bp.post("/api/subset/dump")
def api_subset_dump():
    """AP-56b·Stufe 2: execute the AP-56a subset SELECTs read-only and return the
    actual rows per closure table as a JSON bundle (data dump for the ETL layer).
    Read-only; per-table row cap with loud truncation flagging. No writes."""
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

    run_dialect = _dialect_from_url(url)
    try:
        max_depth = int(data.get("max_depth") or 5)
        result = compute_subset(schema, start, include_implied=include_implied,
                                max_depth=max_depth)
        scripts = generate_subset_sql(schema, result, rf,
                                      dialect=run_dialect, schema_name=schema_name)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    cap = config.MAX_RESULT_ROWS
    dumped = {d["table"]: d for d in dump_subset_rows(url, scripts, max_rows_per_table=cap)}
    tables = []
    for t in result.tables:
        d = dumped.get(t.name, {"columns": [], "rows": [], "row_count": 0,
                                "truncated": False, "error": "not dumped"})
        tables.append({
            "name": t.name, "depth": t.depth,
            "kind": t.edge.kind if t.edge else "root",
            "via_table": t.edge.via_table if t.edge else None,
            "columns": d["columns"], "rows": d["rows"], "row_count": d["row_count"],
            "truncated": d["truncated"], "error": d["error"],
        })
    incomplete = (result.truncated or any(t["truncated"] for t in tables)
                  or any(t["error"] for t in tables))
    return jsonify(start=result.start, truncated=result.truncated,
                   incomplete=incomplete, row_cap=cap, tables=tables)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k subset_dump -v`
Expected: PASS (3 Tests)

- [ ] **Step 5: Run the full api module**

Run: `./venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(subset): /api/subset/dump — JSON-Daten-Bundle der Closure (AP-56b Stufe 2)"
```

---

### Task 3: UI — Button „Daten-Dump (JSON)" + Blob-Download

**Files:**
- Modify: `web/static/js/app.js` (`runSubset` Button-Zeile ~551, neue `runSubsetDump` nach `runSubsetCount` ~578, `openSubset`-Hinweis ~595)
- Smoke: Playwright (System-python3).

**Interfaces:**
- Consumes: `POST /api/subset/dump` (Task 2), bestehende Helfer `postJSON`, `esc`, `$`, Modul-Var `SUB_LAST_PAYLOAD` (aus Stufe 1).
- Produces: ein Browser-Download des JSON-Bundles + Status/Warnung im Panel.

- [ ] **Step 1: Button neben „Zeilen zählen (live)" ergänzen**

In `web/static/js/app.js`, `runSubset()`, den `out.innerHTML`-Kopf (aktuell Zeile ~550–552) ändern — den Dump-Button + eine Status-Zeile ergänzen:

```javascript
  out.innerHTML =
    `<p><button id="sub_count">Zeilen zählen (live)</button> ` +
    `<button id="sub_dump">Daten-Dump (JSON)</button> ` +
    `<span id="sub_total" class="hint"></span></p>` +
    `<table class="subtbl cols"><thead><tr><th>Tabelle</th><th>Rolle</th>` +
    `<th>via</th><th>Tiefe</th><th>Zeilen</th></tr></thead><tbody>${rows}</tbody></table>` +
    trunc + `<h3>Export-Skelett (read-only SELECTs)</h3>${scripts}`;
  $("sub_count").addEventListener("click", runSubsetCount);
  $("sub_dump").addEventListener("click", runSubsetDump);
```

- [ ] **Step 2: `runSubsetDump` — Bundle holen, als Datei herunterladen**

Neue Funktion direkt nach `runSubsetCount()` einfügen:

```javascript
function _sanitizeFilePart(s) {
  return String(s).replace(/[^A-Za-z0-9._-]/g, "_").slice(0, 60);
}

async function runSubsetDump() {
  const btn = $("sub_dump");
  const total = $("sub_total");
  if (!SUB_LAST_PAYLOAD) { total.textContent = "Erst Footprint bauen."; return; }
  btn.disabled = true;
  total.textContent = "Daten-Dump läuft…";
  const payload = { ...SUB_LAST_PAYLOAD };
  let res;
  try { res = await postJSON("/api/subset/dump", payload); }
  catch (e) { total.textContent = `Fehler: ${esc(String(e))}`; btn.disabled = false; return; }

  // Build a client-side download (browser-native Blob, no CDN, no server file).
  const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
  const fp = payload.root_filter || {};
  const fname = `subset_${_sanitizeFilePart(payload.start_table)}_` +
    `${_sanitizeFilePart(fp.column)}${_sanitizeFilePart(fp.op)}${_sanitizeFilePart(fp.value)}.json`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fname;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);

  const totalRows = res.tables.reduce((n, t) => n + (t.row_count || 0), 0);
  if (res.incomplete) {
    const bad = res.tables.filter((t) => t.truncated || t.error).map((t) => t.name);
    total.textContent = `Export unvollständig — abgeschnitten/Fehler bei: ${esc(bad.join(", "))}`;
  } else {
    total.textContent = `Dump: ${res.tables.length} Tabellen, ${totalRows} Zeilen`;
  }
  btn.disabled = false;
}
```

- [ ] **Step 3: Panel-Hinweis um den Dump ergänzen**

In `openSubset()` den Hinweis-Absatz (aktuell ~595–597) ersetzen:

```javascript
    `<p class="hint">Referenzielle FK-Hülle einer Start-Zeile (Kinder abwärts + ` +
    `Lookups aufwärts). „Footprint bauen" führt nichts aus; „Zeilen zählen (live)" ` +
    `führt read-only COUNT-Queries aus; „Daten-Dump (JSON)" lädt die Zeilen der Hülle ` +
    `read-only als JSON herunter.</p>` +
```

- [ ] **Step 4: App neu starten + Browser-Smoke**

App neu starten (Route 2 braucht Neustart):

```bash
pkill -f "run.sh|app.py|waitress" 2>/dev/null; sleep 1
bash run.sh --skip-setup &
sleep 3
```

Demo-DB sicherstellen (falls fehlend):
`./venv/bin/python -c "from sample_data.build_demo_db import build; build('sample_data/demo_cmdb.db')"`

Playwright-Smoke (System-python3) nach `scratchpad/smoke_subset_dump.py` — Demo verbinden, „Entität exportieren", Start `Datacenter`, Filter `DatacenterID = 3`, „Footprint bauen", dann den **Download abfangen**:

```python
from playwright.sync_api import sync_playwright
import json, pathlib
DB = pathlib.Path("sample_data/demo_cmdb.db").resolve()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto("http://127.0.0.1:5057")
    # ... echte Verbindungs-/Sidebar-Selektoren aus app.js/templates verwenden
    #     (SQLite + Filepath setzen → verbinden → Sidebar „Entität exportieren")
    #     Start-Tabelle „Datacenter", Filter DatacenterID = 3, „Footprint bauen"
    with pg.expect_download() as dl_info:
        pg.click("#sub_dump")
    dl = dl_info.value
    path = dl.path()
    bundle = json.loads(pathlib.Path(path).read_text())
    print("start:", bundle["start"], "row_cap:", bundle["row_cap"])
    by = {t["name"]: t for t in bundle["tables"]}
    assert bundle["start"] == "Datacenter"
    assert by["Datacenter"]["row_count"] == 1
    print("PASS")
    b.close()
```

Run: `python3 scratchpad/smoke_subset_dump.py`
Expected: Ausgabe enthält `PASS` und ein heruntergeladenes Bundle mit `start: Datacenter`. (Verbindungs-/Sidebar-Selektoren beim Schreiben an die laufende UI anpassen — der Beweis ist das abgefangene Download-Bundle.)

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(subset): UI „Daten-Dump (JSON)" — Blob-Download der Closure-Zeilen (AP-56b Stufe 2)"
```

---

### Task 4: Release & Doku

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`, `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/docs/projekt/kennzahlen.md`, `docs/projekt-kennzahlen.html`, `CLAUDE.md`; dann Site-Build.

**Interfaces:** keine Code-Interfaces — Release-/Doku-Schritt.

- [ ] **Step 1: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (366 passed + 7 neue = 373 passed, 2 skipped).

- [ ] **Step 2: Version bump (Feature → minor)**

```bash
./venv/bin/python sync_version.py --minor   # v0.49.0 → v0.50.0
```

- [ ] **Step 3: icon-rail + zensical + Kennzahlen nachziehen**

- `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` `0.49.0`→`0.50.0`, `TEST_COUNT` `366`→`373`, `TEST_DATE` auf `2026-06-29`.
- `luDBxP-docs/zensical.toml`: `v0.49.0`→`v0.50.0`.
- `luDBxP-docs/docs/projekt/kennzahlen.md` **und** `docs/projekt-kennzahlen.html`: Version `v0.49.0`→`v0.50.0`, Tests `366`→`373` (je 2 Stellen, wie im v0.49.0-Release).

- [ ] **Step 4: Changelog EN + DE-Mirror**

Eintrag `## [0.50.0] — 2026-06-29` ganz oben in `CHANGELOG.md` (EN) und `luDBxP-docs/docs/entwicklung/changelog.md` (DE): „Subset data dump (AP-56b·Stage 2): read-only JSON bundle of the closure rows via `/api/subset/dump`, per-table row cap with loud truncation flag, client-side Blob download." / DE-Mirror analog.

- [ ] **Step 5: Roadmap — AP-56b·Stufe 2 nach Erledigt**

In `luDBxP-docs/docs/projekt/roadmap.md`: den offenen `AP-56b · Stufe 2`-Eintrag aus dem Offen-Abschnitt entfernen; im Erledigt-Abschnitt eine neue `**v0.50.0** (2026-06-29):`-Gruppe mit AP-56b·Stufe 2 (Daten-Dump) **vor** der `v0.49.0`-Gruppe einfügen. Das verbleibende **IN-Listen-Folge-AP** namentlich im Offen-Abschnitt führen (z. B. „AP-56c — Subset-IN-Listen (PK-Mengen je Tabelle als Export-Identität)"). Gerenderte Übersicht nach Build gegenprüfen.

- [ ] **Step 6: CLAUDE.md „Bekannte Einschränkungen"**

Den Subset-Block um den Daten-Dump ergänzen: „Daten-Dump (AP-56b·Stufe 2, v0.50.0): `/api/subset/dump` liefert die Closure-Zeilen read-only als JSON-Bundle (`core/datapreview.py::dump_subset_rows`, Per-Tabelle-Cap `MAX_RESULT_ROWS`, lautes Truncation-Flag). IN-Listen bleiben offen."

- [ ] **Step 7: Site-Build**

```bash
cd luDBxP-docs && ./run_luDBxP_docs.sh --build
```
Danach prüfen, dass keine alte `0.49.0` außerhalb von Changelog/Roadmap/Handoffs verbleibt und die Site `0.50.0` + `373` zeigt.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.50.0 — AP-56b·Stufe 2 (Subset-Daten-Dump JSON)"
```

(Merge nach master, Push, gh-pages-Deploy erfolgen nach dem finalen Whole-Branch-Review durch den Controller.)

---

## Self-Review (vom Plan-Autor durchgeführt)

- **Spec-Abdeckung:** §1 `dump_subset_rows` → Task 1; §2 Route → Task 2; §3 UI/Blob-Download → Task 3; §4 Tests → in Tasks 1–3 verteilt (Cross-Check, Anker, Truncation, Resilienz, Route, Smoke); §5 Scope-Cuts → respektiert (nur JSON, keine IN-Listen/CSV/Streaming); §6 Release → Task 4. Keine Lücke.
- **Platzhalter:** keine TBD/„handle errors" — Resilienz + Truncation sind auscodiert.
- **Typkonsistenz:** `dump_subset_rows(url, scripts, *, max_rows_per_table)->list[{table,columns,rows,row_count,truncated,error}]` identisch in Task 1→2→3; Route-Response `{start,truncated,incomplete,row_cap,tables[]}` durchgängig; UI liest `row_count`/`truncated`/`error`/`incomplete` exakt so.
- **Daten-Robustheit:** Dump-Test cross-checkt gegen `execute_select` (datenunabhängig); deterministischer Anker DatacenterID=3; Truncation via Mini-Cap real erzwungen.
