# AP-63·Stufe 2b — Sequences + Materialized Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sequences (Name) und Materialized Views (Spalten + Definition) als je eigene read-only Sidebar-Kategorie reflektieren + anzeigen, auf dem AP-63·S2-Muster.

**Architecture:** Der Loader reflektiert via SQLAlchemy-nativ `get_sequence_names`/`get_materialized_view_names` (+ columns/definition); ein neues `Sequence`-Model + `Schema.sequences`/`Schema.materialized_views` (Matviews reusen `View`) tragen sie; `/api/schema` serialisiert sie; die Sidebar bekommt zwei conditional Kategorien und `openDetail` zwei display-only Zweige (kein Daten-Tab). Echte Werte nur PG/Oracle (skip-guarded); SQLite → leer.

**Tech Stack:** Python 3.10+ (venv = 3.14), Flask, SQLAlchemy (Reflection), vanilla JS; pytest; Playwright (System-python3) für Browser-Smoke.

## Global Constraints

- **Layering:** `core/` importiert **nie** Flask. Model = reine frozen Dataclasses. Web ruft Core.
- **Read-only:** nur Inspector-Reflektion + Anzeige; nichts wird ausgeführt.
- **Model-Erweiterung am Ende:** `Schema.sequences` + `Schema.materialized_views` mit Default `()` nach `triggers`.
- **Matviews reusen `View`** (name/columns/definition) — kein neues Matview-Model.
- **Display-only:** kein Daten-Tab für `sequence`/`matview` (`hasData` bleibt `table||view`).
- **Sidebar-Kategorien nur sichtbar bei N>0.** Echte Reflektion nur PG/Oracle; SQLite/MSSQL → `()`.
- **NO CDN.** **Sprache:** UI/Doku Deutsch. **Version:** nur via `sync_version.py`.
- **Neustart-Reibung:** Route/Python erst nach App-Neustart; JS/CSS live. Tests nutzen Flask-Testclient bzw. `page.route`.

---

### Task 1: Model + Loader — Sequences + Materialized Views reflektieren

**Files:**
- Modify: `core/model.py` (`Sequence`-Dataclass + zwei `Schema`-Felder)
- Modify: `core/loaders/sqlalchemy_loader.py` (Reflektion + Import + `Schema(...)`-Aufruf)
- Create: `tests/test_pg_integration.py` (skip-guarded Live-Test)
- Test: `tests/test_sqlalchemy_loader.py` (Leer-Pfad gegen SQLite)

**Interfaces:**
- Produces:
  - `core.model.Sequence(name: str)`
  - `Schema.sequences: tuple[Sequence,...] = ()`, `Schema.materialized_views: tuple[View,...] = ()`
  - Loader füllt beide (SQLite → `()`).

- [ ] **Step 1: Write the failing empty-path test**

In `tests/test_sqlalchemy_loader.py` anfügen (`SqlAlchemyLoader` + `inventory_url` vorhanden):

```python
def test_loader_sequences_and_matviews_empty_on_sqlite(inventory_url):
    schema = SqlAlchemyLoader(inventory_url).load()
    assert schema.sequences == ()
    assert schema.materialized_views == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -k "sequences_and_matviews" -v`
Expected: FAIL — `AttributeError: 'Schema' object has no attribute 'sequences'`.

- [ ] **Step 3: Add the model**

In `core/model.py`, add after the `View` class (before `Trigger`/`Schema`):

```python
@dataclass(frozen=True)
class Sequence:
    name: str
```

In the `Schema` dataclass, add two fields after `triggers`:

```python
    sequences: tuple[Sequence, ...] = ()
    materialized_views: tuple[View, ...] = ()   # Matviews reusen das View-Shape
```

- [ ] **Step 4: Add reflection in the loader**

In `core/loaders/sqlalchemy_loader.py`, extend the model import (line 5) to add `Sequence`:
```python
from core.model import Column, ForeignKey, Index, CheckConstraint, Table, View, Schema, Trigger, Sequence
```
Then, in `load()`, right before the `return Schema(...)` line, add:
```python
            try:
                sequences = tuple(
                    Sequence(n) for n in insp.get_sequence_names(schema=schema)
                )
            except (SQLAlchemyError, NotImplementedError):
                sequences = ()
            try:
                mv_names = insp.get_materialized_view_names(schema=schema)
            except (SQLAlchemyError, NotImplementedError):
                mv_names = []
            matviews = []
            for mvname in mv_names:
                try:
                    mvcols = tuple(
                        Column(c["name"], str(c["type"]))
                        for c in insp.get_columns(mvname, schema=schema)
                    )
                except SQLAlchemyError:
                    mvcols = ()
                try:
                    mvdef = insp.get_view_definition(mvname, schema=schema) or ""
                except (SQLAlchemyError, NotImplementedError):
                    mvdef = ""
                matviews.append(View(mvname, mvcols, mvdef))
```
And change the return (currently `return Schema(tuple(tables), tuple(views), _reflect_triggers(engine))`) to:
```python
            return Schema(tuple(tables), tuple(views), _reflect_triggers(engine),
                          sequences, tuple(matviews))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -k "sequences_and_matviews" -v`
Expected: PASS

- [ ] **Step 6: Add the skip-guarded PG live test**

Create `tests/test_pg_integration.py`:

```python
"""AP-63·S2b — optional live PostgreSQL integration test.

Runs only when LUCENT_PG_TEST_URL points at a reachable PostgreSQL with write
access; otherwise it skips, so the suite stays green without a PG instance.
Provisions a sequence + a materialized view, reflects them through the app's
loader, and asserts both are captured — the real reflect path only PG can
verify. Example::

    LUCENT_PG_TEST_URL='postgresql+psycopg://user:pw@localhost:5432/db' \
        ./venv/bin/python -m pytest tests/test_pg_integration.py
"""
import os

import pytest
from sqlalchemy import create_engine, text

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader

_PG_URL = os.environ.get("LUCENT_PG_TEST_URL")
pytestmark = pytest.mark.skipif(not _PG_URL, reason="LUCENT_PG_TEST_URL not set")

_SEQ = "_lucent_it_seq"
_MV = "_lucent_it_mv"


@pytest.fixture
def pg_objects():
    engine = create_engine(_PG_URL)
    ddl = [
        f"DROP MATERIALIZED VIEW IF EXISTS {_MV}",
        f"DROP SEQUENCE IF EXISTS {_SEQ}",
        f"CREATE SEQUENCE {_SEQ}",
        f"CREATE MATERIALIZED VIEW {_MV} AS SELECT 1 AS n",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    yield
    with engine.begin() as conn:
        conn.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {_MV}"))
        conn.execute(text(f"DROP SEQUENCE IF EXISTS {_SEQ}"))
    engine.dispose()


def test_pg_reflects_sequence_and_matview(pg_objects):
    schema = SqlAlchemyLoader(_PG_URL).load()
    assert _SEQ in {s.name for s in schema.sequences}
    mv = {m.name: m for m in schema.materialized_views}
    assert _MV in mv
    assert "n" in {c.name for c in mv[_MV].columns}
```

- [ ] **Step 7: Run the full suite**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (395 + 1 neuer CI-Test = 396 passed, 3 skipped — der PG-Test skippt ohne `LUCENT_PG_TEST_URL`). Falls abweichend, gilt die reale Zahl.

- [ ] **Step 8: Commit**

```bash
git add core/model.py core/loaders/sqlalchemy_loader.py tests/test_pg_integration.py tests/test_sqlalchemy_loader.py
git commit -m "feat(model): Sequences + Materialized Views reflektieren + im Schema tragen (AP-63·S2b)"
```

---

### Task 2: Endpoint — `/api/schema` serialisiert Sequences + Matviews

**Files:**
- Modify: `web/routes.py` (`api_schema`-Response)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Schema.sequences`, `Schema.materialized_views` (Task 1).
- Produces: Response-Felder `sequences:[{name}]`, `materialized_views:[{name, columns:[{name,type}], definition}]`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_api.py` anfügen (`client`/`inventory_url` vorhanden; baue das konstruierte Schema-Szenario per monkeypatch):

```python
def test_schema_exposes_sequences_and_matviews(client, inventory_url, monkeypatch):
    import web.routes as routes_mod
    from core.model import Schema, View, Sequence, Column

    fake = Schema(
        tables=(), views=(), triggers=(),
        sequences=(Sequence("seq_orders"),),
        materialized_views=(View("mv_sales", (Column("total", "INTEGER"),), "SELECT 1 AS total"),),
    )
    monkeypatch.setattr(routes_mod.SqlAlchemyLoader, "load", lambda self, schema=None: fake)
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    assert data["sequences"] == [{"name": "seq_orders"}]
    mv = {m["name"]: m for m in data["materialized_views"]}
    assert mv["mv_sales"]["columns"] == [{"name": "total", "type": "INTEGER"}]
    assert "SELECT 1" in mv["mv_sales"]["definition"]


def test_schema_sequences_matviews_empty_on_sqlite(client, inventory_url):
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    assert data["sequences"] == []
    assert data["materialized_views"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "sequences_and_matviews or sequences_matviews_empty" -v`
Expected: FAIL with `KeyError: 'sequences'`

- [ ] **Step 3: Add the serialization**

In `web/routes.py`, in the `api_schema` `jsonify(...)` call (after the `triggers=[...]` block), add:

```python
        sequences=[{"name": s.name} for s in schema.sequences],
        materialized_views=[
            {"name": mv.name,
             "columns": [{"name": c.name, "type": c.type} for c in mv.columns],
             "definition": mv.definition}
            for mv in schema.materialized_views
        ],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "sequences_and_matviews or sequences_matviews_empty" -v`
Expected: PASS (2 Tests)

- [ ] **Step 5: Run the full api module**

Run: `./venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(subset): /api/schema liefert Sequences + Materialized Views (AP-63·S2b)"
```

---

### Task 3: Sidebar-Kategorien + Detail-Zweige + Smoke

**Files:**
- Modify: `web/static/js/app.js` (`renderSidebar` + `openDetail`)
- Smoke: Playwright (System-python3, via `page.route`)

**Interfaces:**
- Consumes: `/api/schema` `sequences`/`materialized_views` (Task 2); `SCHEMA.sequences`/`SCHEMA.materialized_views`.
- Produces: zwei Sidebar-Kategorien + `sequence`/`matview` Detail-Zweige (display-only).

- [ ] **Step 1: Add the two sidebar categories**

In `web/static/js/app.js`, `renderSidebar()`, nach der Trigger-Kategorie (dem `((SCHEMA.triggers && …) ? … : "") +`-Block) und **vor** `<div class="sidebar-bottom">` einfügen:

```javascript
    ((SCHEMA.sequences && SCHEMA.sequences.length)
      ? `<h3>Sequences (${SCHEMA.sequences.length})</h3>` +
        `<ul class="objlist">${objList(SCHEMA.sequences, "sequence")}</ul>`
      : "") +
    ((SCHEMA.materialized_views && SCHEMA.materialized_views.length)
      ? `<h3>Materialized Views (${SCHEMA.materialized_views.length})</h3>` +
        `<ul class="objlist">${objList(SCHEMA.materialized_views, "matview")}</ul>`
      : "") +
```

- [ ] **Step 2: Add the two detail branches**

In `web/static/js/app.js`, `openDetail(kind, name)`, die Branch-Verzweigung erweitern. Füge VOR dem finalen `} else {` (View-Zweig) zwei Zweige ein:

```javascript
  } else if (kind === "sequence") {
    const s = (SCHEMA.sequences || []).find((x) => x.name === name);
    defHtml = `<h2>Sequenz: ${esc(s.name)}</h2>` +
      `<p class="hint">nur Name reflektiert</p>`;
    sqlText = "";
  } else if (kind === "matview") {
    const mv = (SCHEMA.materialized_views || []).find((x) => x.name === name);
    defHtml = `<h2>Materialized View: ${esc(mv.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(mv.columns, false)}</tbody></table>`;
    sqlText = mv.definition;
```

(Das `hasData`-Flag bleibt `kind === "table" || kind === "view"` → `sequence`/`matview` bekommen keinen Daten-Subtab. Keine weitere Änderung am Subtab-/Daten-Wiring nötig.)

- [ ] **Step 3: App neu starten**

```bash
pkill -f "run.sh|app.py|waitress" 2>/dev/null; sleep 1
bash run.sh --skip-setup &
sleep 3
```
Demo-DB sicherstellen (für die Connect-Schritte): `./venv/bin/python -c "from sample_data.build_demo_db import build; build('sample_data/demo_cmdb.db')"`

- [ ] **Step 4: Browser-Smoke via `page.route` (ohne PG)**

Da keine CI-DB Sequenzen/Matviews hat, injiziert der Smoke sie in die `/api/schema`-Antwort. Nach `scratchpad/smoke_seq_matview.py` (Connect-Selektoren aus `scratchpad/smoke_subset_dump.py` übernehmen). Muster:

```python
from playwright.sync_api import sync_playwright
import json, pathlib
DB = pathlib.Path("sample_data/demo_cmdb.db").resolve()

def handle(route):
    resp = route.fetch()
    data = resp.json()
    data["sequences"] = [{"name": "seq_demo"}]
    data["materialized_views"] = [
        {"name": "mv_demo", "columns": [{"name": "x", "type": "INTEGER"}],
         "definition": "SELECT 1 AS x"}]
    route.fulfill(response=resp, body=json.dumps(data))

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.route("**/api/schema", handle)
    pg.goto("http://127.0.0.1:5057")
    # ... echte Connect-Schritte wie in smoke_subset_dump.py (Demo verbinden) ...
    pg.wait_for_selector("h3:has-text('Sequences')")
    pg.wait_for_selector("h3:has-text('Materialized Views')")
    pg.click('li[data-kind="matview"][data-name="mv_demo"]')
    assert "x" in pg.inner_text(".panel.active")
    pg.click('li[data-kind="sequence"][data-name="seq_demo"]')
    assert "seq_demo" in pg.inner_text(".panel.active")
    print("PASS"); b.close()
```

Run: `python3 scratchpad/smoke_seq_matview.py`
Expected: Ausgabe enthält `PASS`. (Connect-Selektoren an die laufende UI anpassen — der Beweis sind die zwei Kategorien + die beiden Detail-Zweige.)

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(subset): Sequences- + Materialized-Views-Sidebar-Kategorien + Detail (AP-63·S2b)"
```

---

### Task 4: Release & Doku

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`, `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/docs/projekt/kennzahlen.md`, `docs/projekt-kennzahlen.html`, `CLAUDE.md`; dann Site-Build.

**Interfaces:** keine Code-Interfaces — Release-/Doku-Schritt.

- [ ] **Step 1: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (395 + 3 neue CI-Tests = 398 passed, 3 skipped). Falls abweichend, gilt die reale Zahl — diese als TEST_COUNT verwenden.

- [ ] **Step 2: Version bump (Feature → minor)**

```bash
./venv/bin/python sync_version.py --minor   # v0.53.0 → v0.54.0
```

- [ ] **Step 3: icon-rail + zensical + Kennzahlen nachziehen**

- `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` `0.53.0`→`0.54.0`, `TEST_COUNT` `395`→`398` (bzw. reale Zahl), `TEST_DATE` `2026-06-29`.
- `luDBxP-docs/zensical.toml`: `v0.53.0`→`v0.54.0`.
- `luDBxP-docs/docs/projekt/kennzahlen.md` **und** `docs/projekt-kennzahlen.html`: Version `v0.53.0`→`v0.54.0`, Tests `395`→`398` (je 2 Stellen).

- [ ] **Step 4: Changelog EN + DE-Mirror**

Eintrag `## [0.54.0] — 2026-06-29` ganz oben in beiden Changelogs: „Sequences and materialized views as two new read-only sidebar categories (AP-63·S2b): reflected via SQLAlchemy (`get_sequence_names`/`get_materialized_view_names`); sequences show their name, materialized views show columns + definition (display-only, no data tab). Real reflection only on PostgreSQL/Oracle (skip-guarded live test `tests/test_pg_integration.py`); other engines return none." / DE-Mirror analog.

- [ ] **Step 5: Roadmap — AP-63·S2b nach Erledigt**

In `luDBxP-docs/docs/projekt/roadmap.md`: den `AP-63 · Stufe 2b`-Eintrag aus dem Offen-Abschnitt entfernen (PG/Oracle-Trigger-Reflektion als verbleibenden Fast-Follow notieren, falls noch offen); im Erledigt-Abschnitt eine `**v0.54.0** (2026-06-29):`-Gruppe mit AP-63·S2b **vor** der `v0.53.0`-Gruppe einfügen. AP-63·S3 (Procedures/Functions) bleibt offen + namentlich. Gerenderte Übersicht nach Build gegenprüfen.

- [ ] **Step 6: CLAUDE.md „Bekannte Einschränkungen" + „How to Test"**

- „Bekannte Einschränkungen": Tier-Hinweis: „Sequences + Materialized-View-Kategorien (AP-63·S2b, v0.54.0): read-only via SQLAlchemy-Reflektion, echte Werte nur PG/Oracle (SQLite/MSSQL → leer); Sequenzen nur Name, Matviews Spalten+Definition, display-only (kein Daten-Tab)."
- „How to Test": eine Zeile zum optionalen `LUCENT_PG_TEST_URL`-Live-Test ergänzen (analog MSSQL/Oracle).

- [ ] **Step 7: Site-Build**

```bash
cd luDBxP-docs && ./run_luDBxP_docs.sh --build
```
Danach prüfen: keine alte `0.53.0` außerhalb von Changelog/Roadmap/Handoffs; Site zeigt `0.54.0` + neue Testzahl.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.54.0 — AP-63·S2b (Sequences + Materialized Views)"
```

(Merge nach master, Push, gh-pages-Deploy erfolgen nach dem finalen Whole-Branch-Review durch den Controller.)

---

## Self-Review (vom Plan-Autor durchgeführt)

- **Spec-Abdeckung:** §1 Reflection → Task 1; §2 Model → Task 1; §3 Endpoint → Task 2; §4 Sidebar → Task 3; §5 Detail (sequence/matview, kein Daten-Tab) → Task 3; §6 Tests → Task 1 (Leer-Pfad + PG-Live) + Task 2 (Endpoint-Monkeypatch + Leer) + Task 3 (page.route-Smoke); §7 Scope-Cuts → respektiert; §8 Release → Task 4. Keine Lücke.
- **Platzhalter:** keine TBD — alle Edits mit konkretem Code (inkl. Import-Ergänzung `Sequence`).
- **Typkonsistenz:** `Sequence(name)`, `Schema.sequences`/`Schema.materialized_views` (Matviews = `View`) identisch in Task 1→2→3; `/api/schema`-Felder `sequences:[{name}]` / `materialized_views:[{name,columns,definition}]` durchgängig; UI liest `SCHEMA.sequences`/`SCHEMA.materialized_views`/`mv.columns`/`mv.definition` exakt so; `hasData` unverändert → kein Daten-Tab für die neuen Kinds.
- **Testzahlen:** Erwartung 396 (nach Task 1, +1 CI) / 398 (final, +3 CI; PG-Live skippt → skipped 2→3). Bei Abweichung gilt die reale Suite-Ausgabe (Release-Task nennt das).
