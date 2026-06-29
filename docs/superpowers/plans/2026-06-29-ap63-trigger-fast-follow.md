# AP-63·Trigger-Fast-Follow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trigger-Reflektion (heute nur SQLite) auf PostgreSQL, Oracle und MS SQL Server ausweiten — die bestehende Trigger-Sidebar-Kategorie (AP-63·S2) füllt sich damit für alle Ziel-Dialekte.

**Architecture:** Eine Funktion erweitern — `_reflect_triggers(engine, schema)` bekommt PG/Oracle/MSSQL-Zweige neben dem SQLite-Zweig, via Pro-Dialekt-Katalog-SQL. Model/Route/Frontend bleiben unverändert (`Trigger(name, table, sql)`, `/api/schema`-Serialisierung und JS-Kategorie existieren schon). Trigger werden nie ausgeführt.

**Tech Stack:** Python/SQLAlchemy (raw `text()`-Katalog-SQL), pytest (SQLite-Unit + skip-guarded Live-Tests gegen laufendes MSSQL + podman-PG).

## Global Constraints

- **Read-only:** Katalog-SQL liest nur Metadaten; keine Ausführung von Triggern, kein DDL, keine Join-Teilnahme.
- **Layering:** `core/` importiert nie Flask.
- **Resilient + dialekt-gegated:** Reflektion in `try/except SQLAlchemyError → ()`; Early-Return-Guard für nicht-passende Dialekte; SQLite/PG/Oracle/MSSQL behandelt, alle anderen → `()`.
- **Model unverändert:** `Trigger(name, table, sql)` — keine neuen Felder.
- **Nur Tabellen-/DML-Trigger:** DB-/Schema-weite DDL-Trigger (MSSQL `parent_id=0`, Oracle non-`TABLE`) bleiben draußen.
- **Sprache:** Deutsch (Commits/Doku).
- **Version-Bump nur via `sync_version.py`**, Ziel **v0.56.0** (`--minor`).
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14).

---

### Task 1: Loader — multi-dialekt `_reflect_triggers(engine, schema)`

**Files:**
- Modify: `core/loaders/sqlalchemy_loader.py` (`_reflect_triggers` ~Z.26–41; Call-Site in `load()`)
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Consumes: `Trigger` aus `core.model` (bestehend), `text`/`SQLAlchemyError` (bestehende Imports).
- Produces: `_reflect_triggers(engine, schema=None) -> tuple[Trigger, ...]` — SQLite/PG/Oracle/MSSQL via Katalog-SQL, sonst `()`. Call-Site in `load()` ruft jetzt `_reflect_triggers(engine, schema)`.

- [ ] **Step 1: Write the failing test** in `tests/test_sqlalchemy_loader.py` (ans Dateiende). Verifiziert die neue Signatur + dass der SQLite-Pfad den `schema`-Param akzeptiert und ignoriert:

```python
def test_reflect_triggers_accepts_schema_param_on_sqlite(triggers_url):
    # Signatur-Erweiterung (engine, schema): SQLite ignoriert schema, liefert
    # weiterhin die Trigger. Regression-Schutz für die Call-Site-Änderung.
    from core.loaders.sqlalchemy_loader import _reflect_triggers
    from sqlalchemy import create_engine
    engine = create_engine(triggers_url)
    try:
        trigs = _reflect_triggers(engine, "ignored_schema")
    finally:
        engine.dispose()
    by_name = {t.name: t for t in trigs}
    assert "trg_account_audit" in by_name
    assert by_name["trg_account_audit"].table == "Account"
    assert "CREATE TRIGGER" in by_name["trg_account_audit"].sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py::test_reflect_triggers_accepts_schema_param_on_sqlite -v`
Expected: FAIL — `TypeError: _reflect_triggers() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Rewrite `_reflect_triggers`** in `core/loaders/sqlalchemy_loader.py` (ersetzt die bestehende SQLite-only-Funktion, Z.26–41):

```python
def _reflect_triggers(engine, schema=None) -> tuple:
    """Read-only trigger reflection via per-dialect catalog SQL.
    SQLite: sqlite_master; PG: pg_trigger; Oracle: all_triggers + dbms_metadata;
    MSSQL: sys.triggers. Other dialects → (). Only table/DML triggers."""
    name = getattr(getattr(engine, "dialect", None), "name", "")
    if name not in ("sqlite", "postgresql", "oracle", "mssql"):
        return ()
    try:
        with engine.connect() as conn:
            if name == "sqlite":
                rows = conn.execute(text(
                    "SELECT name, tbl_name, sql FROM sqlite_master "
                    "WHERE type='trigger' AND sql IS NOT NULL ORDER BY name"
                )).fetchall()
                return tuple(Trigger(r[0], r[1] or "", r[2] or "") for r in rows)
            if name == "postgresql":
                rows = conn.execute(text(
                    "SELECT t.tgname, c.relname, pg_get_triggerdef(t.oid) "
                    "FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid = t.tgrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE NOT t.tgisinternal AND n.nspname = :s "
                    "ORDER BY t.tgname"
                ), {"s": schema or "public"}).fetchall()
                return tuple(Trigger(r[0], r[1] or "", r[2] or "") for r in rows)
            if name == "oracle":
                owner = (schema or "").upper() or conn.execute(text(
                    "SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual"
                )).scalar()
                trigs = conn.execute(text(
                    "SELECT trigger_name, table_name FROM all_triggers "
                    "WHERE owner = :o AND base_object_type = 'TABLE' "
                    "ORDER BY trigger_name"
                ), {"o": owner}).fetchall()
                out = []
                for tname, tbl in trigs:
                    try:
                        ddl = conn.execute(text(
                            "SELECT DBMS_METADATA.GET_DDL('TRIGGER', :n, :o) FROM dual"
                        ), {"n": tname, "o": owner}).scalar()
                    except SQLAlchemyError:
                        ddl = ""
                    out.append(Trigger(tname, tbl or "", str(ddl or "")))
                return tuple(out)
            if name == "mssql":
                rows = conn.execute(text(
                    "SELECT tr.name, OBJECT_NAME(tr.parent_id), m.definition "
                    "FROM sys.triggers tr "
                    "LEFT JOIN sys.sql_modules m ON m.object_id = tr.object_id "
                    "WHERE tr.is_ms_shipped = 0 "
                    "AND OBJECT_SCHEMA_NAME(tr.parent_id) = :s "
                    "ORDER BY tr.name"
                ), {"s": schema or "dbo"}).fetchall()
                return tuple(Trigger(r[0], r[1] or "", r[2] or "") for r in rows)
    except SQLAlchemyError:
        return ()
    return ()
```

- [ ] **Step 4: Update the call-site** in `load()`. Suche die `Schema(...)`-Return-Zeile mit `_reflect_triggers(engine)` und ändere sie zu `_reflect_triggers(engine, schema)`:

```python
            return Schema(tuple(tables), tuple(views), _reflect_triggers(engine, schema),
                          sequences, tuple(matviews),
                          _reflect_routines(engine, schema),
                          _reflect_synonyms(engine, schema))
```

- [ ] **Step 5: Run trigger tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -k trigger -v`
Expected: PASS — `test_loader_reflects_triggers`, `test_loader_no_triggers_is_empty`, `test_reflect_triggers_accepts_schema_param_on_sqlite`.

- [ ] **Step 6: Run full loader suite**

Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -q`
Expected: PASS, pristine.

- [ ] **Step 7: Commit**

```bash
git add core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat(loader): Trigger-Reflektion für PG/Oracle/MSSQL (Katalog-SQL) (AP-63 Trigger-FF)"
```

---

### Task 2: Live-Integrationstests — MSSQL (live) + PG (live) + Oracle (skip-guarded)

**Files:**
- Modify: `tests/test_mssql_integration.py` (Trigger-Test)
- Modify: `tests/test_pg_integration.py` (Trigger-Provision + Test)
- Modify: `tests/test_oracle_integration.py` (Trigger-Assertion, skip-guarded)

**Interfaces:**
- Consumes: `SqlAlchemyLoader(...).load().triggers` (Task 1) → `tuple[Trigger(name, table, sql)]`.

- [ ] **Step 1: MSSQL — Trigger-Test** in `tests/test_mssql_integration.py` (ans Dateiende). Folgt exakt dem Idiom von `test_mssql_reflects_routines` (AUTOCOMMIT, try/except-skip, try/finally-Drop):

```python
_TRG_TAB = "_lucent_it_trg_tab"
_TRG = "_lucent_it_trg"
_DROP_TRG = (
    f"IF OBJECT_ID('{_TRG}', 'TR') IS NOT NULL DROP TRIGGER {_TRG}; "
    f"IF OBJECT_ID('{_TRG_TAB}') IS NOT NULL DROP TABLE {_TRG_TAB};"
)


@pytest.mark.skipif(
    not _MSSQL_URL,
    reason="set LUCENT_MSSQL_TEST_URL to a reachable MSSQL URL to run the live "
           "integration test",
)
def test_mssql_reflects_trigger():
    """Provision a table + AFTER-INSERT trigger on MSSQL and reflect via loader."""
    pytest.importorskip("pyodbc")
    try:
        engine = create_engine(_MSSQL_URL, isolation_level="AUTOCOMMIT")
        conn = engine.connect()
    except Exception as exc:
        pytest.skip(f"MSSQL not reachable or ODBC driver missing: {exc}")
    try:
        conn.execute(text(_DROP_TRG))
        conn.execute(text(f"CREATE TABLE {_TRG_TAB} (id INT PRIMARY KEY)"))
        conn.execute(text(
            f"CREATE TRIGGER {_TRG} ON {_TRG_TAB} AFTER INSERT AS SELECT 1"
        ))
        schema = SqlAlchemyLoader(_MSSQL_URL).load()
        by_trg = {t.name: t for t in schema.triggers}
        assert _TRG in by_trg, f"{_TRG} not in triggers: {list(by_trg)}"
        assert by_trg[_TRG].table == _TRG_TAB
        assert "TRIGGER" in by_trg[_TRG].sql.upper()
    finally:
        conn.execute(text(_DROP_TRG))
        conn.close()
        engine.dispose()
```

- [ ] **Step 2: Run MSSQL trigger test against the live container**

Run: `LUCENT_MSSQL_TEST_URL='mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes' ./venv/bin/python -m pytest tests/test_mssql_integration.py::test_mssql_reflects_trigger -v`
Expected: PASS (the container is running). If it fails, the MSSQL catalog SQL in Task 1 is wrong — fix Task 1 before continuing.

- [ ] **Step 3: PG — Trigger provisioning + test** in `tests/test_pg_integration.py`. Add the trigger objects to the `pg_objects` fixture DDL (a table, a trigger function, a trigger) and a drop in teardown, plus a constant block and a new test:

Constants near the top (next to `_SEQ`/`_MV`/`_FN`):
```python
_TRG_TAB = "_lucent_it_trg_tab"
_TRG = "_lucent_it_trg"
_TRG_FN = "_lucent_it_trg_fn"
```

In the `pg_objects` fixture `ddl` list (before `yield`), append:
```python
    f"CREATE TABLE IF NOT EXISTS {_TRG_TAB} (id int)",
    f"CREATE OR REPLACE FUNCTION {_TRG_FN}() RETURNS trigger LANGUAGE plpgsql "
    f"AS 'BEGIN RETURN NEW; END'",
    f"CREATE TRIGGER {_TRG} AFTER INSERT ON {_TRG_TAB} "
    f"FOR EACH ROW EXECUTE FUNCTION {_TRG_FN}()",
```

In the teardown block, add (drop trigger/table/function before existing drops):
```python
        conn.execute(text(f"DROP TRIGGER IF EXISTS {_TRG} ON {_TRG_TAB}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {_TRG_TAB}"))
        conn.execute(text(f"DROP FUNCTION IF EXISTS {_TRG_FN}()"))
```

New test:
```python
def test_pg_reflects_trigger(pg_objects):
    schema = SqlAlchemyLoader(_PG_URL).load()
    by_trg = {t.name: t for t in schema.triggers}
    assert _TRG in by_trg
    assert by_trg[_TRG].table == _TRG_TAB
    assert "TRIGGER" in by_trg[_TRG].sql.upper()
```

- [ ] **Step 4: Oracle — Trigger-Assertion (skip-guarded)** in `tests/test_oracle_integration.py`. Im bestehenden Routinen/Live-Test-Idiom (DDL anlegen → reflect → assert → teardown) eine Trigger-Provision ergänzen: eine Tabelle + ein `BEFORE INSERT`-Trigger; assert, dass der Trigger in `schema.triggers` mit `table` erscheint und `sql` nicht leer ist. Genaue Fixture-/Drop-Form an die in der Datei etablierte Struktur anlehnen (am echten Code prüfen — Oracle hat kein `IF EXISTS`, also per-Objekt-`try/except`-Drop wie bei den Routinen).

- [ ] **Step 5: Run the full suite (live tests skip without URLs)**

Run: `./venv/bin/python -m pytest -q`
Expected: alle grün; PG/Oracle-Trigger-Tests skipped ohne URL; MSSQL skipped ohne URL.
Dann mit MSSQL-URL gegengeprüft (Step 2 grün).

- [ ] **Step 6: Commit**

```bash
git add tests/test_mssql_integration.py tests/test_pg_integration.py tests/test_oracle_integration.py
git commit -m "test: Live-Trigger-Reflektion MSSQL(live)/PG/Oracle (AP-63 Trigger-FF)"
```

---

### Task 3: Release v0.56.0 + Doku (am Code geprüft)

**Files:**
- Modify: via `sync_version.py`; Changelog (EN + DE-Mirror), Roadmap-Prosa + `.mmd` (Trigger-Status), CLAUDE.md, `architektur.md`, Kennzahlen, Site, gh-pages.

**Interfaces:** keine (Release/Doku).

- [ ] **Step 1: Version-Bump**

```bash
./venv/bin/python sync_version.py --minor   # → v0.56.0
```

- [ ] **Step 2: Doku am echten Code geprüft nachziehen** (grep-belegt):
  - **Changelog EN + DE-Mirror:** v0.56.0-Eintrag — Trigger-Reflektion jetzt PG/Oracle/MSSQL (vorher nur SQLite).
  - **CLAUDE.md** „Bekannte Einschränkungen": die AP-63·S2-Trigger-Notiz aktualisieren — heute steht dort sinngemäß „nur SQLite … PG/Oracle = Fast-Follow"; auf „SQLite + PG + Oracle + MSSQL via Pro-Dialekt-Katalog-SQL" ändern.
  - **Roadmap-Prosa + Diagramme** (`roadmap.md`, `projekt-roadmap-1.mmd`, `entwicklung-arbeitspakete-1.mmd`): den Trigger-Fast-Follow als erledigt markieren (eigener Eintrag, kein Sammeleintrag).
  - **`architektur.md`:** `_reflect_triggers` als multi-dialekt (PG/Oracle/MSSQL) beschreiben statt SQLite-only.
  - **Kennzahlen** (`kennzahlen.md`): Version v0.56.0, Commits/Tests/Coverage **frisch erheben** (`git rev-list --count HEAD`, `pytest`, `pytest --cov=core --cov=web --cov=launcher --cov=config --cov=app`), Karten + Tabelle.
  - **zensical.toml** Versionsstring.
  - Je Dialekt mit `grep` gegenprüfen, dass Changelog/CLAUDE.md/architektur den neuen Trigger-Support nennen.

- [ ] **Step 3: Site bauen + verifizieren**

```bash
bash luDBxP-docs/run_luDBxP_docs.sh --build
```
Danach grep: `v0.56.0` in gebauter Site + Trigger-Notiz aktualisiert.

- [ ] **Step 4: Voll-Suite + Commit + Deploy**

```bash
./venv/bin/python -m pytest -q   # grün
git add -A
git commit -m "release: v0.56.0 — AP-63 Trigger-Fast-Follow (PG/Oracle/MSSQL-Trigger)"
# FF-Merge nach master + Push + gh-pages-Worktree-Deploy (etabliertes Muster)
```

---

## Self-Review

**1. Spec coverage:**
- Signatur `_reflect_triggers(engine, schema)` + Call-Site → Task 1 ✓
- PG/Oracle/MSSQL-Katalog-SQL (+ SQLite unverändert, sonst `()`) → Task 1 ✓
- Nur Tabellen-/DML-Trigger (PG `NOT tgisinternal`, Oracle `base_object_type='TABLE'`, MSSQL `OBJECT_SCHEMA_NAME(parent_id)` filtert `parent_id=0` raus) → Task 1 ✓
- Oracle-Body via `dbms_metadata.get_ddl` → Task 1 ✓
- Route/Frontend unverändert → kein Task (bewusst, Spec §3) ✓
- Live-Tests MSSQL(live)/PG/Oracle + SQLite-Unit → Task 1/2 ✓
- Release/Doku inkl. CLAUDE.md-Trigger-Notiz-Update → Task 3 ✓
- Read-only/keine Join-Teilnahme → Loader liest nur Katalog, `Trigger` nimmt nirgends an Joins teil (unverändert) ✓

**2. Placeholder scan:** Katalog-SQL + Test-Code ausgeschrieben. Der „am echten Code prüfen"-Hinweis bei Oracle (Step 4) betrifft die bestehende Fixture-Form, nicht zu erfindende Logik.

**3. Type consistency:** `Trigger(name, table, sql)` durchgängig (unverändertes Model); `_reflect_triggers(engine, schema=None)` einheitlich in Definition + Call-Site; `.triggers`-Zugriff in allen Live-Tests identisch.
