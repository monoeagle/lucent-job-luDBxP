# AP-63·S3 — Procedures / Functions / Packages / Synonyms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vier neue read-only Sidebar-Kategorien — Stored Procedures, Functions, Oracle Packages, Oracle Synonyms — analog zu Trigger/Sequences/Matviews (AP-63·S2/S2b).

**Architecture:** Pro-Dialekt-Katalog-SQL im Loader (keine native SQLAlchemy-API), zwei neue Model-Dataclasses (`Routine` mit kind-Diskriminator, `Synonym`), Serialisierung in `/api/schema`, vier JS-Kategorien + Detail-Zweige. Routinen werden nie ausgeführt, nehmen an keinem Join teil. SQLite/sonstige Dialekte liefern `()`.

**Tech Stack:** Python 3.10+ / SQLAlchemy (Reflection + raw `text()`-Katalog-SQL), Flask (Route), vanilla JS (Sidebar/Detail), pytest (Naht-/Unit-Tests + skip-guarded Live-Tests).

## Global Constraints

- **Read-only:** Keine Ausführung von Routinen, kein DDL, keine Join-Teilnahme. Nur Anzeige.
- **Layering:** `core/` importiert **nie** Flask. `web/` ruft `core/`.
- **No CDN:** Keine externen Assets in Templates.
- **Resilient pro Dialekt:** Jede Katalog-Reflektion in `try/except SQLAlchemyError → ()`; SQLite/nicht-passende Dialekte liefern `()`.
- **Model-Erweiterungen = Trailing-Felder mit `()`-Default** → andere positionale Konstruktoren unberührt.
- **Sprache:** Deutsch (UI-Labels, Commit-Messages, Doku).
- **Version-Bump nur via `sync_version.py`** (`config.APP_VERSION` nie von Hand), Ziel **v0.55.0** (`--minor`).
- **Tests laufen mit** `./venv/bin/python -m pytest` (venv = Python 3.14).
- **Sidebar-Kategorie nur bei N>0** (etabliertes Muster).

---

### Task 1: Model — `Routine` + `Synonym` Dataclasses + Schema-Felder

**Files:**
- Modify: `core/model.py` (nach `class Trigger`, vor `class Schema`; zwei neue `Schema`-Felder)
- Test: `tests/test_model.py`

**Interfaces:**
- Produces:
  - `Routine(name: str, kind: str, sql: str = "")` — `kind ∈ {"procedure","function","package"}`
  - `Synonym(name: str, target: str)`
  - `Schema.routines: tuple[Routine, ...] = ()`, `Schema.synonyms: tuple[Synonym, ...] = ()` (Trailing, nach `materialized_views`)

- [ ] **Step 1: Write the failing tests** in `tests/test_model.py` (ans Dateiende anhängen):

```python
def test_routine_carries_kind_and_sql():
    from core.model import Routine
    r = Routine("calc_total", "function", "CREATE FUNCTION calc_total() ...")
    assert r.name == "calc_total"
    assert r.kind == "function"
    assert "CREATE FUNCTION" in r.sql


def test_routine_sql_defaults_empty():
    from core.model import Routine
    assert Routine("p", "procedure").sql == ""


def test_synonym_carries_target():
    from core.model import Synonym
    s = Synonym("emp_syn", "HR.EMPLOYEES")
    assert s.name == "emp_syn"
    assert s.target == "HR.EMPLOYEES"


def test_schema_routines_synonyms_default_empty():
    from core.model import Schema
    sch = Schema(tables=())
    assert sch.routines == ()
    assert sch.synonyms == ()


def test_schema_positional_constructor_still_works_with_routines():
    # Bestehende positionale Aufrufe (bis materialized_views) bleiben gültig.
    from core.model import Schema, View, Sequence
    sch = Schema((), (), (), (Sequence("s"),), (View("mv", ()),))
    assert sch.sequences[0].name == "s"
    assert sch.routines == ()
    assert sch.synonyms == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_model.py -k "routine or synonym or positional_constructor_still_works_with_routines" -v`
Expected: FAIL (`ImportError: cannot import name 'Routine'` bzw. `Synonym`)

- [ ] **Step 3: Add the dataclasses + Schema fields** in `core/model.py`.

Nach `class Trigger` (vor `class Schema`) einfügen:

```python
@dataclass(frozen=True)
class Routine:
    name: str
    kind: str        # "procedure" | "function" | "package"
    sql: str = ""    # Quelltext (CREATE …/Package-Source); "" falls nicht lesbar


@dataclass(frozen=True)
class Synonym:
    name: str
    target: str      # (owner.)object — Zielobjekt; kein Quelltext
```

In `class Schema` nach `materialized_views`:

```python
    routines: tuple[Routine, ...] = ()
    synonyms: tuple[Synonym, ...] = ()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_model.py -v`
Expected: PASS (alle, inkl. der neuen)

- [ ] **Step 5: Commit**

```bash
git add core/model.py tests/test_model.py
git commit -m "feat(model): Routine + Synonym Dataclasses + Schema-Felder (AP-63·S3)"
```

---

### Task 2: Loader — `_reflect_routines` + `_reflect_synonyms` + Verdrahtung

**Files:**
- Modify: `core/loaders/sqlalchemy_loader.py` (Import erweitern; zwei Helfer nach `_reflect_triggers`; `load()`-Return erweitern; `schema` an die Helfer durchreichen)
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: `Routine`, `Synonym` aus `core.model` (Task 1)
- Produces:
  - `_reflect_routines(engine, schema) -> tuple[Routine, ...]`
  - `_reflect_synonyms(engine, schema) -> tuple[Synonym, ...]`
  - `Schema(...)` trägt jetzt `routines` + `synonyms` als Trailing-Args nach `materialized_views`.

- [ ] **Step 1: Write the failing tests** in `tests/test_sqlalchemy_loader.py` (ans Dateiende):

```python
def test_loader_routines_synonyms_empty_on_sqlite(inventory_url):
    # SQLite hat keine Prozeduren/Funktionen/Packages/Synonyme → sauber ().
    schema = SqlAlchemyLoader(inventory_url).load()
    assert schema.routines == ()
    assert schema.synonyms == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py::test_loader_routines_synonyms_empty_on_sqlite -v`
Expected: FAIL (`AttributeError: 'Schema' object has no attribute 'routines'` falls Task 1 fehlt — sonst FAIL, weil `load()` die Felder noch nicht befüllt und der Default zwar `()` ist → Test würde grün sein; deshalb zuerst die Verdrahtung gegenprüfen). Erwartet hier konkret: nach Task 1 ist der Default `()`, der Test ist **bereits grün** — er dient als Regressionsschutz für die Verdrahtung in Step 3. Wenn er schon grün ist, weiter zu Step 3 (Helfer + Verdrahtung) und am Ende erneut laufen lassen.

- [ ] **Step 3: Implement the helpers + wire into `load()`** in `core/loaders/sqlalchemy_loader.py`.

Import (Zeile 5) erweitern:

```python
from core.model import Column, ForeignKey, Index, CheckConstraint, Table, View, Schema, Trigger, Sequence, Routine, Synonym
```

Nach `_reflect_triggers` (nach Zeile 40) einfügen:

```python
def _reflect_routines(engine, schema=None) -> tuple:
    """Read-only routine reflection (procedures/functions/packages) via
    per-dialect catalog SQL. PG: pg_proc; Oracle: all_objects+all_source;
    MSSQL: sys.objects+sys.sql_modules. SQLite/other → ()."""
    name = getattr(getattr(engine, "dialect", None), "name", "")
    try:
        with engine.connect() as conn:
            if name == "postgresql":
                rows = conn.execute(text(
                    "SELECT p.proname, p.prokind, pg_get_functiondef(p.oid) "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = :s AND p.prokind IN ('p','f') "
                    "ORDER BY p.proname"
                ), {"s": schema or "public"}).fetchall()
                return tuple(
                    Routine(r[0], "procedure" if str(r[1]) == "p" else "function", r[2] or "")
                    for r in rows
                )
            if name == "oracle":
                owner = (schema or "").upper() or conn.execute(text(
                    "SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual"
                )).scalar()
                objs = conn.execute(text(
                    "SELECT object_name, object_type FROM all_objects "
                    "WHERE owner = :o AND object_type IN ('PROCEDURE','FUNCTION','PACKAGE') "
                    "ORDER BY object_type, object_name"
                ), {"o": owner}).fetchall()
                out = []
                for oname, otype in objs:
                    src_rows = conn.execute(text(
                        "SELECT text FROM all_source WHERE owner = :o AND name = :n "
                        "AND type = :t ORDER BY line"
                    ), {"o": owner, "n": oname, "t": otype}).fetchall()
                    out.append(Routine(oname, otype.lower(), "".join(s[0] or "" for s in src_rows)))
                return tuple(out)
            if name == "mssql":
                rows = conn.execute(text(
                    "SELECT o.name, o.type, m.definition "
                    "FROM sys.objects o LEFT JOIN sys.sql_modules m "
                    "ON m.object_id = o.object_id "
                    "WHERE o.type IN ('P','FN','IF','TF') "
                    "AND SCHEMA_NAME(o.schema_id) = :s ORDER BY o.name"
                ), {"s": schema or "dbo"}).fetchall()
                return tuple(
                    Routine(r[0].strip(), "procedure" if r[1].strip() == "P" else "function", r[2] or "")
                    for r in rows
                )
    except SQLAlchemyError:
        return ()
    return ()


def _reflect_synonyms(engine, schema=None) -> tuple:
    """Read-only synonym reflection — Oracle-only (all_synonyms); other → ()."""
    name = getattr(getattr(engine, "dialect", None), "name", "")
    if name != "oracle":
        return ()
    try:
        with engine.connect() as conn:
            owner = (schema or "").upper() or conn.execute(text(
                "SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual"
            )).scalar()
            rows = conn.execute(text(
                "SELECT synonym_name, table_owner, table_name FROM all_synonyms "
                "WHERE owner = :o ORDER BY synonym_name"
            ), {"o": owner}).fetchall()
        return tuple(
            Synonym(r[0], f"{r[1]}.{r[2]}" if r[1] and r[1] != owner else r[2])
            for r in rows
        )
    except SQLAlchemyError:
        return ()
```

`load()`-Return (aktuell Zeile 167–168) erweitern:

```python
            return Schema(tuple(tables), tuple(views), _reflect_triggers(engine),
                          sequences, tuple(matviews),
                          _reflect_routines(engine, schema),
                          _reflect_synonyms(engine, schema))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -v`
Expected: PASS (inkl. `test_loader_routines_synonyms_empty_on_sqlite`)

- [ ] **Step 5: Commit**

```bash
git add core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat(loader): Routine- + Synonym-Reflektion (PG/Oracle/MSSQL Katalog-SQL) (AP-63·S3)"
```

---

### Task 3: Route — Serialisierung in `/api/schema`

**Files:**
- Modify: `web/routes.py` (`api_schema`, nach dem `materialized_views=[...]`-Block, vor `cross_schema_fks=`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `schema.routines` (kind-Diskriminator) + `schema.synonyms` (Task 1/2)
- Produces: `/api/schema`-JSON-Keys `procedures`, `functions`, `packages` (je `{"name","sql"}`) + `synonyms` (`{"name","target"}`).

- [ ] **Step 1: Write the failing tests** in `tests/test_api.py` (ans Dateiende):

```python
def test_schema_exposes_routines_split_by_kind(client, inventory_url, monkeypatch):
    import web.routes as routes_mod
    from core.model import Schema, Routine, Synonym

    fake = Schema(
        tables=(),
        routines=(
            Routine("do_thing", "procedure", "CREATE PROCEDURE do_thing ..."),
            Routine("calc", "function", "CREATE FUNCTION calc ..."),
            Routine("pkg_util", "package", "PACKAGE pkg_util ..."),
        ),
        synonyms=(Synonym("emp_syn", "HR.EMPLOYEES"),),
    )
    monkeypatch.setattr(routes_mod.SqlAlchemyLoader, "load", lambda self, schema=None: fake)
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    assert data["procedures"] == [{"name": "do_thing", "sql": "CREATE PROCEDURE do_thing ..."}]
    assert data["functions"] == [{"name": "calc", "sql": "CREATE FUNCTION calc ..."}]
    assert data["packages"] == [{"name": "pkg_util", "sql": "PACKAGE pkg_util ..."}]
    assert data["synonyms"] == [{"name": "emp_syn", "target": "HR.EMPLOYEES"}]


def test_schema_routines_synonyms_empty_on_sqlite(client, inventory_url):
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    assert data["procedures"] == []
    assert data["functions"] == []
    assert data["packages"] == []
    assert data["synonyms"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "routines_split_by_kind or routines_synonyms_empty" -v`
Expected: FAIL (`KeyError: 'procedures'`)

- [ ] **Step 3: Add serialization** in `web/routes.py` — im `jsonify(...)` von `api_schema`, direkt nach dem `materialized_views=[...]`-Block (nach Zeile 172):

```python
        procedures=[{"name": r.name, "sql": r.sql}
                    for r in schema.routines if r.kind == "procedure"],
        functions=[{"name": r.name, "sql": r.sql}
                   for r in schema.routines if r.kind == "function"],
        packages=[{"name": r.name, "sql": r.sql}
                  for r in schema.routines if r.kind == "package"],
        synonyms=[{"name": s.name, "target": s.target} for s in schema.synonyms],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api.py -k "routines or synonyms" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(api): procedures/functions/packages/synonyms in /api/schema (AP-63·S3)"
```

---

### Task 4: Frontend — vier Sidebar-Kategorien + Detail-Zweige + Cleanup

**Files:**
- Modify: `web/static/js/app.js` (`objList` ~Z.160; Sidebar-Render ~Z.169–183; `openDetail` ~Z.302–353)
- Test: Manueller Browser-Smoke via Playwright (System-`python3`, `page.route`-Injektion) — kein pytest-JS in diesem Projekt.

**Interfaces:**
- Consumes: `SCHEMA.procedures`, `SCHEMA.functions`, `SCHEMA.packages`, `SCHEMA.synonyms` (Task 3)
- Produces: vier neue `data-kind`-Werte: `procedure`, `function`, `package`, `synonym`.

- [ ] **Step 1: `escAttr` für `data-name` + `findByName`-Helfer** (Cleanup, Backlog).

`objList` (Z.160–161) auf `escAttr` für `data-name` umstellen:

```javascript
  const objList = (items, kind) => items.map((o) =>
    `<li data-kind="${kind}" data-name="${escAttr(o.name)}">${esc(o.name)}</li>`).join("");
```

Direkt nach `objList` einen geteilten Lookup-Helfer einführen:

```javascript
  const findByName = (arr, name) => (arr || []).find((x) => x.name === name);
```

(Falls `findByName` außerhalb des Render-Scopes von `openDetail` gebraucht wird, als
modulweite Funktion neben `tableByName` definieren statt als lokale Closure — am echten
Code prüfen, wo `tableByName` steht, und konsistent platzieren.)

- [ ] **Step 2: Vier Sidebar-Kategorien** nach dem Materialized-Views-Block (nach Z.183) einfügen — exakt das bestehende N>0-Muster:

```javascript
    ((SCHEMA.procedures && SCHEMA.procedures.length)
      ? `<h3>Prozeduren (${SCHEMA.procedures.length})</h3>` +
        `<ul class="objlist">${objList(SCHEMA.procedures, "procedure")}</ul>`
      : "") +
    ((SCHEMA.functions && SCHEMA.functions.length)
      ? `<h3>Funktionen (${SCHEMA.functions.length})</h3>` +
        `<ul class="objlist">${objList(SCHEMA.functions, "function")}</ul>`
      : "") +
    ((SCHEMA.packages && SCHEMA.packages.length)
      ? `<h3>Packages (${SCHEMA.packages.length})</h3>` +
        `<ul class="objlist">${objList(SCHEMA.packages, "package")}</ul>`
      : "") +
    ((SCHEMA.synonyms && SCHEMA.synonyms.length)
      ? `<h3>Synonyme (${SCHEMA.synonyms.length})</h3>` +
        `<ul class="objlist">${objList(SCHEMA.synonyms, "synonym")}</ul>`
      : "") +
```

(Auf korrekte `+`-Verkettung im umgebenden Template-Ausdruck achten — am echten Code prüfen.)

- [ ] **Step 3: Vier `openDetail`-Zweige** vor dem finalen `else` (View-Zweig, Z.347) einfügen. Proc/Func/Package teilen sich Logik:

```javascript
  } else if (kind === "procedure" || kind === "function" || kind === "package") {
    const label = kind === "procedure" ? "Prozedur"
                : kind === "function" ? "Funktion" : "Package";
    const arr = kind === "procedure" ? SCHEMA.procedures
              : kind === "function" ? SCHEMA.functions : SCHEMA.packages;
    const r = findByName(arr, name);
    defHtml = `<h2>${esc(label)}: ${esc(r.name)}</h2>` +
      `<p class="hint">Quelltext im SQL-Tab</p>`;
    sqlText = r.sql;
  } else if (kind === "synonym") {
    const s = findByName(SCHEMA.synonyms, name);
    defHtml = `<h2>Synonym: ${esc(s.name)}</h2>` +
      `<p class="hint">Ziel: ${esc(s.target || "—")}</p>`;
    sqlText = "";   // konsistent mit Sequenz: SQL-Tab bleibt, zeigt "(keine Definition)"
  } else {
```

`hasData` (Z.355) bleibt unverändert (`kind === "table" || kind === "view"`) → Routinen/Synonyme bekommen keinen Daten-Tab. Bestehende `.find()`-Aufrufe in den Trigger/Sequence/Matview/View-Zweigen optional auf `findByName(...)` umstellen (DRY, gleiches Undefined-Verhalten).

- [ ] **Step 4: App neu starten + Browser-Smoke** (Route/JS-Änderung → App-Neustart nötig).

```bash
bash run.sh --skip-setup   # bzw. laufende App neu starten
```

Manueller Playwright-Smoke (System-`python3`) mit `page.route`-Injektion einer `/api/schema`-
Antwort, die alle vier Kategorien (je ≥1 Item) enthält:
- Sidebar zeigt **Prozeduren / Funktionen / Packages / Synonyme** (nur die mit N>0).
- Klick auf je ein Item öffnet Detail: Proc/Func/Package → Quelltext im SQL-Tab, **kein** Daten-Tab; Synonym → „Ziel: …", SQL-Tab zeigt „(keine Definition)".
- Leere Kategorien (N=0) erscheinen **nicht**.

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(ui): Prozeduren/Funktionen/Packages/Synonyme-Kategorien + Detail; objList escAttr + findByName (AP-63·S3)"
```

---

### Task 5: Live-Integrationstests (skip-guarded)

**Files:**
- Modify: `tests/test_pg_integration.py` (Function-Reflektion ergänzen)
- Modify: `tests/test_oracle_integration.py` (Routine + Package + Synonym, wenn `LUCENT_ORACLE_TEST_URL` gesetzt)
- Modify: `tests/test_mssql_integration.py` (Procedure/Function, wenn `LUCENT_MSSQL_TEST_URL` gesetzt)

**Interfaces:**
- Consumes: `SqlAlchemyLoader(...).load()` → `schema.routines`/`schema.synonyms` (Task 2).

- [ ] **Step 1: PG — Function-Reflektion** in `tests/test_pg_integration.py` ergänzen. Im `pg_objects`-Fixture-DDL eine Funktion anlegen + im Teardown droppen, dann eine Assertion:

```python
# in der ddl-Liste (vor yield), z. B. nach der MV:
f"CREATE OR REPLACE FUNCTION {_FN}() RETURNS int LANGUAGE sql AS 'SELECT 1'",
# im Teardown:
f"DROP FUNCTION IF EXISTS {_FN}()",
```

Konstante oben: `_FN = "_lucent_it_fn"`. Neuer Test:

```python
def test_pg_reflects_function(pg_objects):
    schema = SqlAlchemyLoader(_PG_URL).load()
    by = {r.name: r for r in schema.routines}
    assert _FN in by
    assert by[_FN].kind == "function"
    assert "SELECT 1" in by[_FN].sql
```

- [ ] **Step 2: Run PG test** (skippt ohne URL):

Run: `./venv/bin/python -m pytest tests/test_pg_integration.py -v`
Expected: 1 skipped (ohne `LUCENT_PG_TEST_URL`) bzw. PASS mit erreichbarer PG.

- [ ] **Step 3: Oracle + MSSQL — Routinen-Assertions** analog in den bestehenden skip-guarded Tests ergänzen. Mustertreu zu den dort vorhandenen Fixtures (DDL anlegen → reflect → assert → teardown). Oracle zusätzlich:
  - Function → `kind == "function"`, Quelltext nicht leer
  - Package → erscheint in `routines` mit `kind == "package"`
  - Synonym → erscheint in `schema.synonyms` mit korrektem `target`

  MSSQL: Procedure (`kind=="procedure"`) + Function (`kind=="function"`) in `routines`.
  (Exakte DDL/Assertion-Form an die bereits in den Dateien etablierte Struktur anlehnen — am echten Code prüfen, nicht raten.)

- [ ] **Step 4: Run full suite**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün, Live-Tests skipped (3+ skipped ohne URLs).

- [ ] **Step 5: Commit**

```bash
git add tests/test_pg_integration.py tests/test_oracle_integration.py tests/test_mssql_integration.py
git commit -m "test: skip-guarded Routine/Synonym-Live-Tests (PG/Oracle/MSSQL) (AP-63·S3)"
```

---

### Task 6: Release v0.55.0 + Doku (voller Zyklus, am Code geprüft)

**Files:**
- Modify: via `sync_version.py`; Changelog (EN + DE-Mirror), Roadmap-Prosa + `.mmd`-Diagramme (Gantt/Board/Architektur), Referenz-Prosa (Architektur/Datenmodell/Projektstruktur/Oberfläche), Kennzahlen-Dashboard, icon-rail/zensical, CLAUDE.md „Bekannte Einschränkungen", AP-63-Konzept-Status, Site-Build.

**Interfaces:** keine (Release/Doku).

- [ ] **Step 1: Version-Bump**

```bash
./venv/bin/python sync_version.py --minor   # → v0.55.0
```

- [ ] **Step 2: Doku am echten Code geprüft nachziehen** (nicht raten — `grep`-belegt):
  - **Changelog EN + DE-Mirror:** neuer v0.55.0-Eintrag (Procedures/Functions/Packages/Synonyms).
  - **Roadmap-Prosa + Diagramme:** AP-63·S3 auf „done"; Gantt/Board-`.mmd` (done-Klasse + Label), Architektur-`.mmd` (neue Loader-Helfer/Endpoint-Felder/Model-Klassen).
  - **Referenz-Prosa:** `datenmodell.md` (Routine/Synonym + Schema-Felder), `architektur.md` (`_reflect_routines`/`_reflect_synonyms`, `/api/schema`-Keys), `projektstruktur.md`, `oberflaeche.md` (vier neue Kategorien).
  - **Kennzahlen-Dashboard inkl. Nicht-Versionsfelder:** Commits/Sessions/Kalendertage/Coverage **frisch erheben** (`git rev-list --count HEAD`, `pytest --cov`), Tests-Zahl aktualisieren.
  - **CLAUDE.md:** „Bekannte Einschränkungen"-Block um S3 (Procedures/Functions/Packages/Synonyms read-only, Dialekt-Matrix) ergänzen.
  - **icon-rail/zensical** Version, **Site-Build**.
  - Je neuem Objekt mit `grep` gegenprüfen, dass Referenz-Prosa/Diagramme es nennen.

- [ ] **Step 3: Voll-Suite + Verifikation**

Run: `./venv/bin/python -m pytest -q`
Expected: grün; Browser-Smoke vier Kategorien grün.

- [ ] **Step 4: Commit + Deploy**

```bash
git add -A
git commit -m "release: v0.55.0 — AP-63·S3 (Procedures/Functions/Packages/Synonyms)"
# master push + gh-pages-Worktree-Deploy nach etabliertem Muster
```

---

## Self-Review

**1. Spec coverage:**
- Model (Routine/Synonym + Schema-Felder) → Task 1 ✓
- Loader Pro-Dialekt-Katalog-SQL (PG/Oracle/MSSQL) + SQLite→() → Task 2 ✓
- Route-Serialisierung (4 Arrays nach kind) → Task 3 ✓
- Frontend (4 Kategorien + Detail, Synonym-SQL-Tab bleibt) + Cleanup (escAttr/findByName) → Task 4 ✓
- Naht-Tests (Loader-Unit + Serialisierung) → Task 2/3; Live-Tests skip-guarded → Task 5 ✓
- Release/Doku-Zyklus → Task 6 ✓
- Constraint „read-only, keine Join-Teilnahme" → `hasData` unverändert (Task 4), keine SQL-Generierung berührt ✓

**2. Placeholder scan:** Katalog-SQL, Test-Code, JS — alle konkret ausgeschrieben. Die „am echten Code prüfen"-Hinweise (Oracle/MSSQL-Fixture-Form, JS-Template-Verkettung, findByName-Platzierung) betreffen bewusst die bestehende Struktur, nicht zu erfindende Logik.

**3. Type consistency:** `Routine(name, kind, sql="")` + `Synonym(name, target)` durchgängig identisch in Task 1→2→3→5; kind-Werte `"procedure"/"function"/"package"` konsistent in Loader, Route-Filter, JS-Zweig; `data-kind` Werte (`procedure/function/package/synonym`) matchen `openDetail`-Zweige.
