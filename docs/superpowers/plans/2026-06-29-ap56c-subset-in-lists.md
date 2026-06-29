# AP-56c — Subset-IN-Listen (SQL-Export-Identität) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aus dem AP-56b·Stufe-2-Dump je Closure-Tabelle die PK-Menge als self-contained `SELECT * FROM tab WHERE <pk-identity>;` rendern und als `.sql` herunterladbar machen (referenzielle Export-Identität für die ETL-Schicht).

**Architecture:** Ein reiner Core-Renderer in `core/subset.py` extrahiert deduplizierte PK-Tupel aus den Dump-Zeilen und rendert ein portables WHERE-Prädikat (Single-PK → `IN (…)`, Composite → `(a=… AND b=…) OR …`). Ein neuer Endpoint `/api/subset/inlists` spiegelt `/api/subset/dump`, ruft `dump_subset_rows` intern und rendert je Tabelle; die UI setzt die Blöcke zu einer `.sql` zusammen und lädt sie als Browser-Blob herunter.

**Tech Stack:** Python 3.10+ (venv = 3.14), Flask, SQLAlchemy, vanilla JS; pytest; Playwright (System-python3) für Browser-Smoke.

## Global Constraints

- **Layering:** `core/` importiert **nie** Flask. Web ruft Core. Der Renderer ist pur (kein DB-Zugriff).
- **Read-only:** der Renderer erzeugt nur Strings; nichts wird ausgeführt. Datenbeschaffung ausschließlich über das bestehende read-only `dump_subset_rows`.
- **Run-Dialekt aus der URL** (`_dialect_from_url(url)`), nicht der Client-Anzeige-Dialekt — wie `/api/subset/dump`.
- **Per-Tabelle-Cap = `config.MAX_RESULT_ROWS`** (aus dem Dump geerbt); Truncation je Tabelle + Bundle laut geflaggt.
- **`incomplete` = Footprint-truncated OR irgendeine Tabelle truncated OR irgendein error OR irgendeine Tabelle `has_pk=false`.**
- **Composite-PK als OR-Form** (`(a=… AND b=…) OR …`), portabel — kein Row-Value-`IN`. `None`-Schlüsselteil → `IS NULL`.
- **NO CDN:** Download client-seitig via Browser-nativem Blob.
- **Sprache:** UI-Texte/Doku Deutsch.
- **Version:** nie `config.APP_VERSION` von Hand editieren — nur via `sync_version.py`.
- **Neustart-Reibung:** Route/Python-Änderungen wirken erst nach App-Neustart; JS/CSS live. Route-TESTS nutzen den Flask-Testclient.

---

### Task 1: Core — `subset_keys` + `subset_in_list_sql` Renderer (pur)

**Files:**
- Modify: `core/subset.py` (neue Funktionen am Dateiende; `import numbers` am Kopf)
- Test: `tests/test_subset.py`

**Interfaces:**
- Consumes: `core.sqlgen.Dialect`, `SQLITE` (bereits in `subset.py` importiert).
- Produces:
  - `subset_keys(pk_columns, columns, rows) -> list[tuple]` — ordnungserhaltend deduplizierte PK-Tupel; `[]` wenn kein PK, eine PK-Spalte fehlt, oder keine Zeilen.
  - `subset_in_list_sql(table, pk_columns, columns, rows, *, dialect=SQLITE, schema_name="") -> str | None` — self-contained `SELECT * FROM <tab> WHERE <pk-identity>;` oder `None`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_subset.py` ans Dateiende. Ergänze den Import oben (`from core.subset import compute_subset, generate_subset_sql, count_sql, SubsetScript`) um `subset_keys, subset_in_list_sql`:

```python
from core.subset import (compute_subset, generate_subset_sql, count_sql,
                          SubsetScript, subset_keys, subset_in_list_sql)
```

(Falls die bestehende Import-Zeile anders gruppiert ist, nur `subset_keys, subset_in_list_sql` ergänzen — nicht die vorhandenen Namen entfernen.) Dann die Tests:

```python
def test_subset_keys_dedup_order_preserving():
    keys = subset_keys(("id",), ["id", "x"], [[1, "a"], [1, "b"], [2, "c"], [1, "d"]])
    assert keys == [(1,), (2,)]


def test_subset_keys_empty_cases():
    assert subset_keys((), ["id"], [[1]]) == []          # no PK
    assert subset_keys(("id",), ["id"], []) == []        # no rows
    assert subset_keys(("missing",), ["id"], [[1]]) == []  # PK col absent


def test_in_list_sql_single_pk():
    sql = subset_in_list_sql("T", ("id",), ["id", "x"], [[1, "a"], [2, "b"]])
    assert sql == 'SELECT * FROM "T" WHERE "id" IN (1, 2);'


def test_in_list_sql_composite_pk_or_form():
    sql = subset_in_list_sql("RP", ("ClusterID", "PoolKey"),
                             ["ClusterID", "PoolKey", "Name"],
                             [[1, "P1", "a"], [2, "P2", "b"]])
    assert sql == ('SELECT * FROM "RP" WHERE '
                   '("ClusterID" = 1 AND "PoolKey" = \'P1\') OR '
                   '("ClusterID" = 2 AND "PoolKey" = \'P2\');')


def test_in_list_sql_escapes_string_literals():
    sql = subset_in_list_sql("T", ("name",), ["name"], [["O'Brien"]])
    assert "'O''Brien'" in sql


def test_in_list_sql_composite_none_uses_is_null():
    sql = subset_in_list_sql("T", ("a", "b"), ["a", "b"], [[1, None]])
    assert sql == 'SELECT * FROM "T" WHERE ("a" = 1 AND "b" IS NULL);'


def test_in_list_sql_none_when_no_pk_or_no_rows():
    assert subset_in_list_sql("T", (), ["id"], [[1]]) is None
    assert subset_in_list_sql("T", ("id",), ["id"], []) is None


def test_in_list_sql_schema_qualified():
    sql = subset_in_list_sql("T", ("id",), ["id"], [[1]], schema_name="dbo")
    assert sql.startswith('SELECT * FROM "dbo"."T" WHERE')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_subset.py -k "subset_keys or in_list_sql" -v`
Expected: FAIL with `ImportError: cannot import name 'subset_keys'`

- [ ] **Step 3: Write minimal implementation**

In `core/subset.py`: am Dateikopf `import numbers` ergänzen (neben den bestehenden Imports). Dann ans Dateiende:

```python
def subset_keys(pk_columns, columns, rows) -> list:
    """Order-preserving deduplicated primary-key tuples from dump rows.

    Returns [] when the table has no primary key, a PK column is absent from
    ``columns``, or there are no rows.
    """
    if not pk_columns:
        return []
    try:
        idx = [columns.index(c) for c in pk_columns]
    except ValueError:
        return []
    seen = set()
    out = []
    for r in rows:
        k = tuple(r[i] for i in idx)
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _sql_literal(v, dialect: Dialect) -> str:
    """Render a Python value as a SQL literal for a read-only artifact.

    Numbers are emitted raw; strings are single-quoted with ' doubled; None
    becomes NULL; bool becomes 1/0 (portable). The result is never executed
    by this tool — it is generated for external inspection/use.
    """
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, numbers.Number):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def subset_in_list_sql(table, pk_columns, columns, rows, *,
                       dialect: Dialect = SQLITE, schema_name: str = "") -> "str | None":
    """Render a self-contained read-only SELECT reproducing exactly the subset
    rows of ``table`` by their concrete primary keys. None when there is no PK
    or no rows. Composite keys use the portable ``(a=… AND b=…) OR …`` form.
    Executes nothing.
    """
    keys = subset_keys(pk_columns, columns, rows)
    if not keys:
        return None
    tref = dialect.table_ref(table, schema_name)
    if len(pk_columns) == 1:
        col = dialect.quote(pk_columns[0])
        lits = ", ".join(_sql_literal(k[0], dialect) for k in keys)
        where = f"{col} IN ({lits})"
    else:
        qcols = [dialect.quote(c) for c in pk_columns]
        terms = []
        for k in keys:
            parts = [
                f"{qc} IS NULL" if val is None else f"{qc} = {_sql_literal(val, dialect)}"
                for qc, val in zip(qcols, k)
            ]
            terms.append("(" + " AND ".join(parts) + ")")
        where = " OR ".join(terms)
    return f"SELECT * FROM {tref} WHERE {where};"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_subset.py -k "subset_keys or in_list_sql" -v`
Expected: PASS (8 Tests)

- [ ] **Step 5: Run the full subset module**

Run: `./venv/bin/python -m pytest tests/test_subset.py -q`
Expected: PASS (alle bisherigen + 8 neue)

- [ ] **Step 6: Commit**

```bash
git add core/subset.py tests/test_subset.py
git commit -m "feat(subset): subset_keys + subset_in_list_sql — PK-IN-Listen-Renderer (AP-56c)"
```

---

### Task 2: Route — `POST /api/subset/inlists`

**Files:**
- Modify: `web/routes.py` (neue Route nach `api_subset_dump`; Import auf Zeile 20 erweitern)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `compute_subset`, `generate_subset_sql`, `subset_in_list_sql`, `subset_keys` (Task 1), `dump_subset_rows`, `_dialect_from_url`, `_NO_URL_MSG`, `SqlAlchemyLoader`, `schema.has_column`, `Table.primary_key`, `config.MAX_RESULT_ROWS`.
- Produces: `POST /api/subset/inlists` → `{start, truncated, incomplete, row_cap, tables:[{name,kind,via_table,depth,pk_columns,has_pk,key_count,sql,truncated,error}]}`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_api.py` nach den AP-56b-`/api/subset/dump`-Tests anfügen (`client`/`demo_url` existieren):

```python
def test_subset_inlists_single_pk(client, demo_url):
    resp = client.post("/api/subset/inlists", json={
        "connection_url": demo_url, "start_table": "Datacenter",
        "root_filter": {"column": "DatacenterID", "op": "=", "value": 1}})
    data = resp.get_json()
    assert resp.status_code == 200 and data["row_cap"] == 5000
    by = {t["name"]: t for t in data["tables"]}
    dc = by["Datacenter"]
    assert dc["has_pk"] is True and dc["pk_columns"] == ["DatacenterID"]
    assert dc["key_count"] == 1
    assert 'WHERE "DatacenterID" IN (1)' in dc["sql"]


def test_subset_inlists_composite_pk(client, demo_url):
    # ResourcePool has a composite PK (ClusterID, PoolKey).
    resp = client.post("/api/subset/inlists", json={
        "connection_url": demo_url, "start_table": "ResourcePool",
        "root_filter": {"column": "ClusterID", "op": "=", "value": 1}})
    data = resp.get_json()
    assert resp.status_code == 200
    rp = {t["name"]: t for t in data["tables"]}["ResourcePool"]
    assert rp["pk_columns"] == ["ClusterID", "PoolKey"]
    assert '("ClusterID" = ' in rp["sql"] and ' AND "PoolKey" = ' in rp["sql"]


def test_subset_inlists_deterministic_anchor(client, demo_url):
    resp = client.post("/api/subset/inlists", json={
        "connection_url": demo_url, "start_table": "Datacenter",
        "root_filter": {"column": "DatacenterID", "op": "=", "value": 3}})
    data = resp.get_json()
    by = {t["name"]: t for t in data["tables"]}
    assert by["Datacenter"]["key_count"] == 1


def test_subset_inlists_unknown_table_returns_400(client, demo_url):
    resp = client.post("/api/subset/inlists", json={
        "connection_url": demo_url, "start_table": "Nope",
        "root_filter": {"column": "x", "op": "=", "value": 1}})
    assert resp.status_code == 400


def test_subset_inlists_missing_url_returns_400(client):
    resp = client.post("/api/subset/inlists", json={"start_table": "Datacenter",
        "root_filter": {"column": "DatacenterID", "op": "=", "value": 1}})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k subset_inlists -v`
Expected: FAIL mit 404 (Route fehlt) bzw. AssertionError

- [ ] **Step 3: Write minimal implementation**

Import auf `web/routes.py` Zeile 20 erweitern:

```python
from core.subset import compute_subset, generate_subset_sql, subset_in_list_sql, subset_keys
```

In `web/routes.py` direkt nach der `api_subset_dump`-Funktion (vor `@bp.post("/api/joinpath/run")`):

```python
@bp.post("/api/subset/inlists")
def api_subset_inlists():
    """AP-56c: derive the primary-key IN-list per closure table from the
    AP-56b·Stufe-2 dump and render a self-contained read-only SELECT
    (export identity). Read-only — no writes."""
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
    pk_by_table = {t.name: tuple(t.primary_key) for t in schema.tables}
    tables = []
    for t in result.tables:
        d = dumped.get(t.name, {"columns": [], "rows": [], "row_count": 0,
                               "truncated": False, "error": "not dumped"})
        pk = pk_by_table.get(t.name, ())
        keys = subset_keys(pk, d["columns"], d["rows"])
        sql = subset_in_list_sql(t.name, pk, d["columns"], d["rows"],
                                 dialect=run_dialect, schema_name=schema_name) or ""
        tables.append({
            "name": t.name, "depth": t.depth,
            "kind": t.edge.kind if t.edge else "root",
            "via_table": t.edge.via_table if t.edge else None,
            "pk_columns": list(pk), "has_pk": bool(pk), "key_count": len(keys),
            "sql": sql, "truncated": d["truncated"], "error": d["error"],
        })
    incomplete = (result.truncated or any(t["truncated"] for t in tables)
                  or any(t["error"] for t in tables)
                  or any(not t["has_pk"] for t in tables))
    return jsonify(start=result.start, truncated=result.truncated,
                   incomplete=incomplete, row_cap=cap, tables=tables)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k subset_inlists -v`
Expected: PASS (5 Tests)

- [ ] **Step 5: Run the full api module**

Run: `./venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(subset): /api/subset/inlists — PK-IN-Listen je Closure-Tabelle (AP-56c)"
```

---

### Task 3: UI — Button „IN-Listen (SQL)" + `.sql`-Download

**Files:**
- Modify: `web/static/js/app.js` (`runSubset` Button-Zeile ~551–558, neue `runSubsetInlists` nach `runSubsetDump`, `openSubset`-Hinweis)
- Smoke: Playwright (System-python3).

**Interfaces:**
- Consumes: `POST /api/subset/inlists` (Task 2), bestehende Helfer `postJSON`, `esc`, `$`, `_sanitizeFilePart`, Modul-Var `SUB_LAST_PAYLOAD`.
- Produces: ein `.sql`-Browser-Download + Status/Warnung im Panel.

- [ ] **Step 1: Button neben „Daten-Dump (JSON)" ergänzen**

In `web/static/js/app.js`, `runSubset()`, die Button-Zeile + Listener erweitern (aktuell ~551–558):

```javascript
  out.innerHTML =
    `<p><button id="sub_count">Zeilen zählen (live)</button> ` +
    `<button id="sub_dump">Daten-Dump (JSON)</button> ` +
    `<button id="sub_inlists">IN-Listen (SQL)</button> ` +
    `<span id="sub_total" class="hint"></span></p>` +
    `<table class="subtbl cols"><thead><tr><th>Tabelle</th><th>Rolle</th>` +
    `<th>via</th><th>Tiefe</th><th>Zeilen</th></tr></thead><tbody>${rows}</tbody></table>` +
    trunc + `<h3>Export-Skelett (read-only SELECTs)</h3>${scripts}`;
  $("sub_count").addEventListener("click", runSubsetCount);
  $("sub_dump").addEventListener("click", runSubsetDump);
  $("sub_inlists").addEventListener("click", runSubsetInlists);
```

- [ ] **Step 2: `runSubsetInlists` — Bundle holen, `.sql` zusammensetzen, herunterladen**

Neue Funktion direkt nach `runSubsetDump()` einfügen:

```javascript
async function runSubsetInlists() {
  const btn = $("sub_inlists");
  const total = $("sub_total");
  if (!SUB_LAST_PAYLOAD) { total.textContent = "Erst Footprint bauen."; return; }
  btn.disabled = true;
  total.textContent = "IN-Listen werden erzeugt…";
  const payload = { ...SUB_LAST_PAYLOAD };
  let res;
  try { res = await postJSON("/api/subset/inlists", payload); }
  catch (e) { total.textContent = `Fehler: ${esc(String(e))}`; btn.disabled = false; return; }

  // Assemble one .sql text: per table a comment header + the SELECT (if any).
  const lines = [`-- Subset-IN-Listen (Export-Identität) — Start: ${payload.start_table}`,
                 `-- Cap je Tabelle: ${res.row_cap}`, ""];
  res.tables.forEach((t) => {
    if (!t.has_pk) { lines.push(`-- ${t.name}: kein PK, keine IN-Liste`); }
    else if (t.error) { lines.push(`-- ${t.name}: Fehler — ${t.error}`); }
    else { lines.push(`-- ${t.name} (${t.key_count} Schlüssel)`); }
    if (t.truncated) { lines.push(`-- ${t.name}: abgeschnitten bei ${res.row_cap} — Identität unvollständig`); }
    if (t.sql) { lines.push(t.sql); }
    lines.push("");
  });
  const blob = new Blob([lines.join("\n")], { type: "application/sql" });
  const fp = payload.root_filter || {};
  const fname = `subset_${_sanitizeFilePart(payload.start_table)}_` +
    `${_sanitizeFilePart(fp.column)}${_sanitizeFilePart(fp.op)}${_sanitizeFilePart(fp.value)}_inlists.sql`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fname;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);

  const withPk = res.tables.filter((t) => t.has_pk);
  const totalKeys = withPk.reduce((n, t) => n + (t.key_count || 0), 0);
  if (res.incomplete) {
    const bad = res.tables.filter((t) => !t.has_pk || t.truncated || t.error).map((t) => t.name);
    total.textContent = `IN-Listen unvollständig — kein PK/abgeschnitten/Fehler bei: ${esc(bad.join(", "))}`;
  } else {
    total.textContent = `IN-Listen: ${withPk.length} Tabellen mit PK, ${totalKeys} Schlüssel`;
  }
  btn.disabled = false;
}
```

- [ ] **Step 3: Panel-Hinweis um die IN-Listen ergänzen**

In `openSubset()` den Hinweis-Absatz ersetzen (die vier Aktionen nennen):

```javascript
    `<p class="hint">Referenzielle FK-Hülle einer Start-Zeile (Kinder abwärts + ` +
    `Lookups aufwärts). „Footprint bauen" führt nichts aus; „Zeilen zählen (live)" ` +
    `führt read-only COUNT-Queries aus; „Daten-Dump (JSON)" lädt die Zeilen read-only ` +
    `herunter; „IN-Listen (SQL)" erzeugt je Tabelle die PK-Identität als WHERE-SELECT.</p>` +
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

Playwright-Smoke nach `scratchpad/smoke_subset_inlists.py` (Verbindungs-/Sidebar-Selektoren aus dem bestehenden `scratchpad/smoke_subset_dump.py` übernehmen): Demo verbinden → „Entität exportieren" → Start `Datacenter`, Filter `DatacenterID = 1` → „Footprint bauen" → Download von `#sub_inlists` abfangen, `.sql`-Text lesen:

```python
from playwright.sync_api import sync_playwright
import pathlib
DB = pathlib.Path("sample_data/demo_cmdb.db").resolve()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto("http://127.0.0.1:5057")
    # ... echte Verbindungs-/Sidebar-Schritte wie in smoke_subset_dump.py ...
    # Start "Datacenter", Filter DatacenterID = 1, "Footprint bauen"
    with pg.expect_download() as dl_info:
        pg.click("#sub_inlists")
    text = pathlib.Path(dl_info.value.path()).read_text()
    assert 'WHERE "DatacenterID" IN' in text
    print("PASS"); b.close()
```

Run: `python3 scratchpad/smoke_subset_inlists.py`
Expected: Ausgabe enthält `PASS`; das `.sql` enthält `WHERE "DatacenterID" IN`. (Selektoren der Connect-/Sidebar-Schritte an die laufende UI anpassen — der Beweis ist das abgefangene `.sql`.)

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(subset): UI „IN-Listen (SQL)" — .sql-Download der PK-Identität (AP-56c)"
```

---

### Task 4: Release & Doku

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`, `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/docs/projekt/kennzahlen.md`, `docs/projekt-kennzahlen.html`, `CLAUDE.md`; dann Site-Build.

**Interfaces:** keine Code-Interfaces — Release-/Doku-Schritt.

- [ ] **Step 1: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (373 passed + 13 neue = 386 passed, 2 skipped).

- [ ] **Step 2: Version bump (Feature → minor)**

```bash
./venv/bin/python sync_version.py --minor   # v0.50.0 → v0.51.0
```

- [ ] **Step 3: icon-rail + zensical + Kennzahlen nachziehen**

- `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` `0.50.0`→`0.51.0`, `TEST_COUNT` `373`→`386`, `TEST_DATE` `2026-06-29`.
- `luDBxP-docs/zensical.toml`: `v0.50.0`→`v0.51.0`.
- `luDBxP-docs/docs/projekt/kennzahlen.md` **und** `docs/projekt-kennzahlen.html`: Version `v0.50.0`→`v0.51.0`, Tests `373`→`386` (je 2 Stellen, wie im v0.50.0-Release).

- [ ] **Step 4: Changelog EN + DE-Mirror**

Eintrag `## [0.51.0] — 2026-06-29` ganz oben in `CHANGELOG.md` (EN) und `luDBxP-docs/docs/entwicklung/changelog.md` (DE): „Subset IN-lists (AP-56c): per closure table the primary-key set as a self-contained `SELECT * FROM tab WHERE pk IN (…)` (composite PKs via portable `(a=… AND b=…) OR …`), derived from the Stage-2 dump, downloadable as `.sql` via `/api/subset/inlists`." / DE-Mirror analog.

- [ ] **Step 5: Roadmap — AP-56c nach Erledigt**

In `luDBxP-docs/docs/projekt/roadmap.md`: den offenen `AP-56c`-Eintrag aus dem Offen-Abschnitt entfernen; im Erledigt-Abschnitt eine neue `**v0.51.0** (2026-06-29):`-Gruppe mit AP-56c **vor** der `v0.50.0`-Gruppe einfügen. Wave-2-Migration (AP-54/55/56a/56b·1+2/56c) als abgeschlossen führen; AP-57 (Cross-Schema-Joins) bleibt bedingt/zurückgestellt. Gerenderte Übersicht nach Build gegenprüfen (jedes Item namentlich).

- [ ] **Step 6: CLAUDE.md „Bekannte Einschränkungen"**

Den Subset-Block um die IN-Listen ergänzen: „Subset-IN-Listen (AP-56c, v0.51.0): `/api/subset/inlists` leitet je Closure-Tabelle die PK-Menge aus dem Stufe-2-Dump ab und rendert read-only `SELECT * FROM tab WHERE pk IN (…)` (Composite-PK als portable OR-Form; `core/subset.py::subset_in_list_sql`); UI-Button „IN-Listen (SQL)" lädt als `.sql`. No-PK-Tabellen werden laut markiert."

- [ ] **Step 7: Site-Build**

```bash
cd luDBxP-docs && ./run_luDBxP_docs.sh --build
```
Danach prüfen, dass keine alte `0.50.0` außerhalb von Changelog/Roadmap/Handoffs verbleibt und die Site `0.51.0` + `386` zeigt.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.51.0 — AP-56c (Subset-IN-Listen SQL-Export-Identität)"
```

(Merge nach master, Push, gh-pages-Deploy erfolgen nach dem finalen Whole-Branch-Review durch den Controller.)

---

## Self-Review (vom Plan-Autor durchgeführt)

- **Spec-Abdeckung:** §1 Renderer (`subset_keys`+`subset_in_list_sql`+`_sql_literal`) → Task 1; §2 Route → Task 2; §3 UI/.sql-Download → Task 3; §4 Tests → in Tasks 1–3 verteilt (Renderer single/composite/escaping/None/dedup/no-pk/schema, Route single+composite+anchor+400, Smoke); §5 Scope-Cuts → respektiert (nur SQL, aus Dump, OR-Form); §6 Release → Task 4. Keine Lücke.
- **Platzhalter:** keine TBD/„handle errors" — Renderer-Edge-Cases (None/no-PK/dedup) auscodiert.
- **Typkonsistenz:** `subset_keys(pk_columns,columns,rows)->list[tuple]` und `subset_in_list_sql(...)->str|None` identisch in Task 1→2; Route-Response `{start,truncated,incomplete,row_cap,tables[{…,pk_columns,has_pk,key_count,sql,…}]}` durchgängig; UI liest `has_pk`/`key_count`/`sql`/`truncated`/`error`/`incomplete` exakt so.
- **Daten-Robustheit:** Renderer-Tests sind reine Funktionstests (datenunabhängig); Route-Tests nutzen den deterministischen Composite-PK (`ResourcePool`) + DC-Empty-Anker; Smoke fängt den echten `.sql`-Download ab.
