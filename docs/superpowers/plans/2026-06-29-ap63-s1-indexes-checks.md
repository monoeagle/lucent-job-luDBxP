# AP-63·Stufe 1 — Indizes + Check-Constraints im Tabellen-Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Im Tabellen-Detail („Definition"-Subtab) alle Indizes (Name/Spalten/unique) und Check-Constraints (Name/Ausdruck) read-only anzeigen.

**Architecture:** Das `Table`-Model bekommt zwei neue frozen Felder (`indexes`, `check_constraints`) plus zwei neue Dataclasses; der SQLAlchemy-Loader füllt sie via `get_indexes()` + `get_check_constraints()` (alle Engines inkl. SQLite); `/api/schema` serialisiert sie; die UI rendert zwei genestete Abschnitte im bestehenden Detail. Demo-CMDB wird minimal um einen Index + Check erweitert.

**Tech Stack:** Python 3.10+ (venv = 3.14), Flask, SQLAlchemy (Reflection), vanilla JS; pytest; Playwright (System-python3) für Browser-Smoke.

## Global Constraints

- **Layering:** `core/` importiert **nie** Flask. Das Model ist reine frozen Dataclasses (kein SQLAlchemy/Flask). Web ruft Core.
- **Read-only:** nur Reflection + Anzeige; nichts wird ausgeführt, kein DDL erzeugt.
- **Model-Erweiterung am Ende:** neue `Table`-Felder mit Default `()` **nach** `comment` — andere Loader (`manual_loader`/`ddl_loader`/`schemaspy_loader`) bleiben unberührt.
- **`unique_indexes` bleibt unverändert** (gefilterte 1-1-Sicht); `indexes` ist die vollständige Anzeige-Liste daneben.
- **Expression-/Funktions-Indizes** (`None` in `column_names`) werden übersprungen (gleicher Guard wie `uidx`).
- **NO CDN:** keine externen Assets. **Sprache:** UI/Doku Deutsch.
- **Version:** nie `config.APP_VERSION` von Hand — nur via `sync_version.py`.
- **Neustart-Reibung:** Route/Python-Änderungen wirken erst nach App-Neustart; JS/CSS live. Tests nutzen den Flask-Testclient.
- **Scope-Cut:** `table_ddl` (SQL-Subtab) bleibt unverändert.

---

### Task 1: Model + Loader — Indizes + Check-Constraints reflektieren

**Files:**
- Modify: `core/model.py` (zwei neue Dataclasses + zwei `Table`-Felder)
- Modify: `core/loaders/sqlalchemy_loader.py` (Reflection + Import)
- Create: `tests/fixtures/indexes_checks_schema.sql`
- Modify: `tests/conftest.py` (neue Fixture `indexes_checks_url`)
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Produces:
  - `core.model.Index(name: str, columns: tuple[str,...], unique: bool = False)`
  - `core.model.CheckConstraint(name: str, sqltext: str)`
  - `Table.indexes: tuple[Index,...] = ()`, `Table.check_constraints: tuple[CheckConstraint,...] = ()`
  - Fixture `indexes_checks_url` (file-SQLite mit Index + Checks).

- [ ] **Step 1: Add the test fixture schema**

Create `tests/fixtures/indexes_checks_schema.sql`:

```sql
CREATE TABLE Person (
    id     INTEGER PRIMARY KEY,
    email  TEXT NOT NULL,
    age    INTEGER CHECK (age >= 0),
    region TEXT,
    CONSTRAINT ck_email CHECK (email LIKE '%@%')
);
CREATE INDEX ix_person_region ON Person(region);
CREATE UNIQUE INDEX ux_person_email ON Person(email);
```

- [ ] **Step 2: Add the conftest fixture**

In `tests/conftest.py`, after the existing `uniqueindex_url` fixture, add:

```python
@pytest.fixture
def indexes_checks_url(tmp_path) -> str:
    """SQLite URL with a named non-unique index, a unique index, a named CHECK
    and an unnamed inline CHECK (for AP-63·S1 reflection tests)."""
    return _build_sqlite(tmp_path, "indexes_checks.db", "indexes_checks_schema.sql")
```

- [ ] **Step 3: Write the failing loader tests**

In `tests/test_sqlalchemy_loader.py`, append (adjust the import at the top to include the loader if not already imported — the file already imports `SqlAlchemyLoader`):

```python
def test_loader_reflects_all_indexes(indexes_checks_url):
    schema = SqlAlchemyLoader(indexes_checks_url).load()
    person = schema.table("Person")
    by_name = {ix.name: ix for ix in person.indexes}
    assert "ix_person_region" in by_name
    assert by_name["ix_person_region"].columns == ("region",)
    assert by_name["ix_person_region"].unique is False
    assert "ux_person_email" in by_name
    assert by_name["ux_person_email"].unique is True


def test_loader_reflects_check_constraints(indexes_checks_url):
    schema = SqlAlchemyLoader(indexes_checks_url).load()
    person = schema.table("Person")
    texts = [cc.sqltext for cc in person.check_constraints]
    names = [cc.name for cc in person.check_constraints]
    assert any("email" in t for t in texts)      # named ck_email
    assert any("age" in t for t in texts)        # unnamed inline check
    assert "ck_email" in names
    assert "" in names                           # the unnamed check → name ""
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -k "indexes or check_constraints" -v`
Expected: FAIL — `AttributeError: 'Table' object has no attribute 'indexes'` (after the model import error is resolved) or `ImportError` for `Index`/`CheckConstraint`.

- [ ] **Step 5: Add the model dataclasses + Table fields**

In `core/model.py`, add after the `ForeignKey` class (before `Table`):

```python
@dataclass(frozen=True)
class Index:
    name: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True)
class CheckConstraint:
    name: str        # "" = unbenannt
    sqltext: str
```

In the `Table` dataclass, append two fields **after** `comment`:

```python
    # Alle Indizes (Anzeige, AP-63·S1); unabhängig von unique_indexes (1-1-Sicht).
    indexes: tuple[Index, ...] = ()
    # Check-Constraints (Anzeige, AP-63·S1).
    check_constraints: tuple[CheckConstraint, ...] = ()
```

- [ ] **Step 6: Fill them in the loader**

In `core/loaders/sqlalchemy_loader.py`, extend the model import (the file imports from `core.model`) to include `Index, CheckConstraint`. Then, right after the `uidx` try/except block (before the `tcomment` block), add:

```python
                try:
                    indexes = tuple(
                        Index(idx.get("name") or "", tuple(idx["column_names"]),
                              bool(idx.get("unique")))
                        for idx in insp.get_indexes(tname, schema=schema)
                        if idx.get("column_names") and None not in idx["column_names"]
                    )
                except SQLAlchemyError:
                    indexes = ()
                try:
                    checks = tuple(
                        CheckConstraint(cc.get("name") or "", cc.get("sqltext") or "")
                        for cc in insp.get_check_constraints(tname, schema=schema)
                    )
                except (SQLAlchemyError, NotImplementedError):
                    checks = ()
```

Then change the `Table(...)` append to pass the two new args at the end:

```python
                tables.append(Table(tname, columns, tuple(fks), pk, uniques, uidx,
                                    tcomment, indexes, checks))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -k "indexes or check_constraints" -v`
Expected: PASS (2 Tests)

- [ ] **Step 8: Run the full suite (model change touches many constructors)**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (386 + 2 neue = 388 passed, 2 skipped) — bestätigt, dass die Model-Erweiterung keine anderen Loader/Tests bricht.

- [ ] **Step 9: Commit**

```bash
git add core/model.py core/loaders/sqlalchemy_loader.py tests/fixtures/indexes_checks_schema.sql tests/conftest.py tests/test_sqlalchemy_loader.py
git commit -m "feat(model): Index + CheckConstraint reflektieren + im Table tragen (AP-63·S1)"
```

---

### Task 2: Endpoint — `/api/schema` serialisiert Indizes + Checks

**Files:**
- Modify: `web/routes.py` (`api_schema` Table-Dict, ~Z. 134–149)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Table.indexes`, `Table.check_constraints` (Task 1); Fixture `indexes_checks_url` (Task 1, in conftest → auch in test_api verfügbar).
- Produces: je Table-Dict zusätzlich `"indexes": [{name,columns,unique}]`, `"check_constraints": [{name,sqltext}]`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_api.py`, append:

```python
def test_schema_exposes_indexes_and_checks(client, indexes_checks_url):
    data = client.post("/api/schema", json={"connection_url": indexes_checks_url}).get_json()
    person = {t["name"]: t for t in data["tables"]}["Person"]
    ix = {i["name"]: i for i in person["indexes"]}
    assert ix["ix_person_region"]["columns"] == ["region"]
    assert ix["ix_person_region"]["unique"] is False
    assert ix["ux_person_email"]["unique"] is True
    assert any("email" in c["sqltext"] for c in person["check_constraints"])
    assert any(c["name"] == "ck_email" for c in person["check_constraints"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_api.py -k schema_exposes_indexes -v`
Expected: FAIL with `KeyError: 'indexes'`

- [ ] **Step 3: Add the serialization**

In `web/routes.py`, in `api_schema`'s table dict (after the `"foreign_keys": [...]` block, before `"ddl"`), add:

```python
            "indexes": [
                {"name": ix.name, "columns": list(ix.columns), "unique": ix.unique}
                for ix in t.indexes
            ],
            "check_constraints": [
                {"name": cc.name, "sqltext": cc.sqltext} for cc in t.check_constraints
            ],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_api.py -k schema_exposes_indexes -v`
Expected: PASS

- [ ] **Step 5: Run the full api module**

Run: `./venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(subset): /api/schema liefert Indizes + Check-Constraints je Tabelle (AP-63·S1)"
```

---

### Task 3: Demo-DB-Erweiterung + UI-Render + Smoke

**Files:**
- Modify: `sample_data/build_demo_db.py` (`_SCHEMA`: ein CHECK + ein Index)
- Modify: `web/static/js/app.js` (`openDetail` Table-Zweig, ~Z. 297–307)
- Test: `tests/test_demo_db_cases.py` (Demo-Loader-Assertion); Browser-Smoke (Playwright)

**Interfaces:**
- Consumes: `/api/schema` `indexes`/`check_constraints` (Task 2); `SCHEMA.tables[].indexes`/`check_constraints` im Client.
- Produces: gerenderte „Indizes"- + „Check-Constraints"-Abschnitte im Detail; Demo-CMDB mit `ix_host_cluster` + `VMDisk.SizeGB`-Check.

- [ ] **Step 1: Extend the demo schema**

In `sample_data/build_demo_db.py`, im `_SCHEMA`-String:

(a) Den VMDisk-`SizeGB` um einen Inline-Check ergänzen — ersetze
```
    SizeGB      INTEGER NOT NULL
```
durch
```
    SizeGB      INTEGER NOT NULL CHECK (SizeGB > 0)
```

(b) Direkt vor `CREATE VIEW WindowsVMs AS` einen benannten Index einfügen:
```sql
CREATE INDEX ix_host_cluster ON Host(ClusterID);
```

- [ ] **Step 2: Write the failing demo-loader test**

In `tests/test_demo_db_cases.py`, append (die Datei baut die Demo schon via `build` + lädt ein Schema; nutze denselben `demo_url`/Loader-Pfad wie die vorhandenen Tests — falls die Datei `SqlAlchemyLoader` noch nicht importiert, oben `from core.loaders.sqlalchemy_loader import SqlAlchemyLoader` ergänzen, und falls keine `demo_url`-Fixture existiert, die lokale Build-Hilfe der Datei verwenden):

```python
def test_demo_has_index_and_check(demo_url):
    schema = SqlAlchemyLoader(demo_url).load()
    host_ix = {ix.name for ix in schema.table("Host").indexes}
    assert "ix_host_cluster" in host_ix
    vmdisk_checks = schema.table("VMDisk").check_constraints
    assert any("SizeGB" in cc.sqltext for cc in vmdisk_checks)
```

(Falls `tests/test_demo_db_cases.py` keine `demo_url`-Fixture hat: oben
```python
@pytest.fixture
def demo_url(tmp_path):
    from sample_data.build_demo_db import build
    db = tmp_path / "demo.db"; build(str(db)); return f"sqlite:///{db}"
```
ergänzen — `import pytest` ist in der Datei vorhanden.)

- [ ] **Step 3: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_demo_db_cases.py -k demo_has_index_and_check -v`
Expected: FAIL (`ix_host_cluster` fehlt) — falls Step 1 noch nicht griff. (Nach Step 1 sollte es bereits passen; dann den Test trotzdem ausführen, um GRÜN zu bestätigen, und mit Step 1 zusammen committen.)

- [ ] **Step 4: Verify the demo test passes + full demo module**

Run: `./venv/bin/python -m pytest tests/test_demo_db_cases.py -q`
Expected: PASS (bestehende Join-/FK-Tests unberührt + neuer Test grün).

- [ ] **Step 5: Render the two sections in the detail**

In `web/static/js/app.js`, im `openDetail`-Table-Zweig den `defHtml`-Aufbau erweitern. Ersetze
```javascript
    defHtml = `<h2${t.comment ? ` title="${escAttr(t.comment)}"` : ""}>Tabelle: ${esc(t.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(t.columns, true)}</tbody></table>` +
      `<h3>Foreign Keys</h3>${fks}`;
```
durch
```javascript
    const idxHtml = (t.indexes && t.indexes.length)
      ? "<ul>" + t.indexes.map((ix) =>
          `<li>${esc(ix.name || "(unbenannt)")} · ${esc(ix.columns.join(", "))}` +
          (ix.unique ? ` <span class="badge">unique</span>` : "") + `</li>`).join("") + "</ul>"
      : "<p class='hint'>keine Indizes</p>";
    const ckHtml = (t.check_constraints && t.check_constraints.length)
      ? "<ul>" + t.check_constraints.map((cc) =>
          `<li>${esc(cc.name || "(unbenannt)")}: ${esc(cc.sqltext)}</li>`).join("") + "</ul>"
      : "<p class='hint'>keine Check-Constraints</p>";
    defHtml = `<h2${t.comment ? ` title="${escAttr(t.comment)}"` : ""}>Tabelle: ${esc(t.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(t.columns, true)}</tbody></table>` +
      `<h3>Foreign Keys</h3>${fks}` +
      `<h3>Indizes</h3>${idxHtml}` +
      `<h3>Check-Constraints</h3>${ckHtml}`;
```

- [ ] **Step 6: App neu starten + Browser-Smoke**

App neu starten (Route/Python-Änderung aus Tasks 1–2 braucht Neustart):
```bash
pkill -f "run.sh|app.py|waitress" 2>/dev/null; sleep 1
bash run.sh --skip-setup &
sleep 3
```
Demo-DB neu bauen (mit Index+Check):
`./venv/bin/python -c "from sample_data.build_demo_db import build; build('sample_data/demo_cmdb.db')"`

Playwright-Smoke nach `scratchpad/smoke_indexes_checks.py` (Connect-/Sidebar-Selektoren aus einem bestehenden Smoke wie `scratchpad/smoke_subset_dump.py` übernehmen): Demo verbinden → Tabelle `Host` im Sidebar öffnen → „Definition" enthält „Indizes" + `ix_host_cluster`; Tabelle `VMDisk` öffnen → „Check-Constraints"-Abschnitt enthält `SizeGB`.

```python
from playwright.sync_api import sync_playwright
import pathlib
DB = pathlib.Path("sample_data/demo_cmdb.db").resolve()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto("http://127.0.0.1:5057")
    # ... echte Connect-/Sidebar-Schritte wie in smoke_subset_dump.py ...
    # Sidebar: Tabelle "Host" öffnen (data-name="Host"), Definition-Subtab aktiv
    pg.wait_for_selector("h3:has-text('Indizes')")
    body = pg.inner_text(".detail")
    assert "ix_host_cluster" in body
    print("PASS"); b.close()
```
Run: `python3 scratchpad/smoke_indexes_checks.py`
Expected: Ausgabe enthält `PASS`; das Detail rendert „Indizes" mit `ix_host_cluster`. (Selektoren an die laufende UI anpassen.)

- [ ] **Step 7: Commit**

```bash
git add sample_data/build_demo_db.py web/static/js/app.js tests/test_demo_db_cases.py
git commit -m "feat(subset): Tabellen-Detail zeigt Indizes + Check-Constraints; Demo-CMDB erweitert (AP-63·S1)"
```

---

### Task 4: Release & Doku

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), `luDBxP-docs/docs/javascripts/icon-rail.js`, `luDBxP-docs/zensical.toml`, `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/projekt/roadmap.md`, `luDBxP-docs/docs/projekt/kennzahlen.md`, `docs/projekt-kennzahlen.html`, `CLAUDE.md`; dann Site-Build.

**Interfaces:** keine Code-Interfaces — Release-/Doku-Schritt.

- [ ] **Step 1: Volle Suite grün**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün (386 + 4 neue = 390 passed, 2 skipped).

- [ ] **Step 2: Version bump (Feature → minor)**

```bash
./venv/bin/python sync_version.py --minor   # v0.51.0 → v0.52.0
```

- [ ] **Step 3: icon-rail + zensical + Kennzahlen nachziehen**

- `luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` `0.51.0`→`0.52.0`, `TEST_COUNT` `386`→`390`, `TEST_DATE` `2026-06-29`.
  (TEST_COUNT = volle Suite-Zahl aus Step 1 — bei Abweichung den realen Wert verwenden.)
- `luDBxP-docs/zensical.toml`: `v0.51.0`→`v0.52.0`.
- `luDBxP-docs/docs/projekt/kennzahlen.md` **und** `docs/projekt-kennzahlen.html`: Version `v0.51.0`→`v0.52.0`, Tests `386`→`390` (je 2 Stellen).

- [ ] **Step 4: Changelog EN + DE-Mirror**

Eintrag `## [0.52.0] — 2026-06-29` ganz oben in beiden Changelogs: „Table detail now lists all indexes (name/columns/unique) and check constraints (name/expression), read-only via reflection (`/api/schema`); demo CMDB gained an index + a check. (AP-63·S1)" / DE-Mirror analog.

- [ ] **Step 5: Roadmap — AP-63·S1 nach Erledigt**

In `luDBxP-docs/docs/projekt/roadmap.md`: den `AP-63 · Stufe 1`-Eintrag aus dem Offen-Abschnitt entfernen; im Erledigt-Abschnitt eine `**v0.52.0** (2026-06-29):`-Gruppe mit AP-63·S1 **vor** der `v0.51.0`-Gruppe einfügen. AP-63·S2/S3 bleiben offen + namentlich. Gerenderte Übersicht nach Build gegenprüfen.

- [ ] **Step 6: CLAUDE.md „Bekannte Einschränkungen"**

Einen kurzen Tier-Hinweis ergänzen: „Indizes + Check-Constraints (AP-63·S1, v0.52.0): im Tabellen-Detail read-only via SQLAlchemy-Reflection (`get_indexes`/`get_check_constraints`, alle Engines inkl. SQLite); Expression-Indizes übersprungen; nur Anzeige, kein DDL/Join-Pfad."

- [ ] **Step 7: Site-Build**

```bash
cd luDBxP-docs && ./run_luDBxP_docs.sh --build
```
Danach prüfen: keine alte `0.51.0` außerhalb von Changelog/Roadmap/Handoffs; Site zeigt `0.52.0` + neue Testzahl.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: Release v0.52.0 — AP-63·S1 (Indizes + Check-Constraints im Tabellen-Detail)"
```

(Merge nach master, Push, gh-pages-Deploy erfolgen nach dem finalen Whole-Branch-Review durch den Controller.)

---

## Self-Review (vom Plan-Autor durchgeführt)

- **Spec-Abdeckung:** §1 Model → Task 1; §2 Loader → Task 1; §3 Endpoint → Task 2; §4 UI → Task 3; §5 Demo+Tests → Task 1 (Fixture-Loader-Tests) + Task 2 (Endpoint) + Task 3 (Demo-Erweiterung + Demo-Loader-Test + Smoke); §6 Scope-Cuts → respektiert (kein DDL, keine Sidebar, Expression-Indizes übersprungen); §7 Release → Task 4. Keine Lücke.
- **Platzhalter:** keine TBD — alle Edits mit konkretem Code/Befehl.
- **Typkonsistenz:** `Index(name, columns, unique)`, `CheckConstraint(name, sqltext)`, `Table.indexes`/`check_constraints` identisch in Task 1→2→3; `/api/schema`-Felder `indexes:[{name,columns,unique}]` / `check_constraints:[{name,sqltext}]` durchgängig; UI liest `t.indexes`/`t.check_constraints`/`ix.unique`/`cc.sqltext` exakt so.
- **Testzahl-Hinweis:** Die exakten TEST_COUNT-Werte (388 nach Task 1, 390 final) sind als Erwartungswerte angegeben (Baseline v0.51.0 = 386); bei Abweichung gilt die reale Suite-Ausgabe — der Release-Task nennt das ausdrücklich.
