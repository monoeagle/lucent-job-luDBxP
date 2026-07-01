# AP-67·Oracle-Adaption Slice 1 — Oracle-Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den `oracle`-Zweig von `sample_data/seed_server_demo.py` mit live-verifizierter Oracle-DDL/PL-SQL füllen, sodass die Server-Demo-CMDB alle Oracle-Objektkategorien im Sidebar-Tree zeigt.

**Architecture:** Reine Daten-/Seed-Arbeit — kein Tool-/Reflektions-Code. Vier `_ORACLE_*`-Statement-Listen (analog `_MSSQL_*`) + der `oracle`-Zweig in `seed()`. Ein skip-guardeter Live-Integrationstest + ein Bring-up-README-Abschnitt.

**Tech Stack:** Python, SQLAlchemy + `oracledb` (Thin), Oracle 21c XE (Container), pytest.

## Global Constraints

- Read-only-Invariante: das Seed ist externes Setup, das das Werkzeug NIE ausführt.
- Kein Tool-/Reflektions-Code — alle Reflektionspfade existieren.
- Die gesamte Oracle-DDL unten ist **live gegen den Container verifiziert** (Oracle 21c XE, `demo/demo @ localhost:1521/XEPDB1`); alle Kategorien reflektieren inkl. AP-66·S1 (View→Function). Verbatim übernehmen.
- `CLUSTER` ist in Oracle reserviert → die Tabelle heißt im Oracle-Demo `VMCluster` (Oracle uppercased ohnehin alle unquoted Namen).
- Baseline: `./venv/bin/python -m pytest` → **445 passed, 10 skipped** (v0.63.0); ohne `LUCENT_ORACLE_TEST_URL` bleibt der neue Test `skipped`.

---

### Task 1: Oracle-Seed-Block in `seed_server_demo.py`

**Files:**
- Modify: `sample_data/seed_server_demo.py` — vier `_ORACLE_*`-Listen + `oracle`-Zweig in `seed()`.
- Verifikation: Controller führt das Seed live gegen den Container aus + reflektiert (Seeder ist nur live prüfbar; kein pytest ohne Oracle).

**Interfaces:**
- Produces: `seed(url)` unterstützt jetzt `engine.dialect.name == "oracle"`; führt `_ORACLE_DROPS + _ORACLE_TABLES + _ORACLE_DATA + _ORACLE_OBJECTS` in dieser Reihenfolge aus.

- [ ] **Step 1: Die vier `_ORACLE_*`-Listen einfügen.** In `sample_data/seed_server_demo.py` nach den `_MSSQL_OBJECTS` (vor `def seed`) einfügen:

```python
# --- Oracle (AP-67·Oracle-Adaption) — live gegen Oracle 21c XE verifiziert. ---
# Kein IF EXISTS in Oracle → Drop je Objekt als eigener Block, Fehler geschluckt.
_ORACLE_DROPS = [
    "BEGIN EXECUTE IMMEDIATE 'DROP VIEW vw_vm_labeled'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP MATERIALIZED VIEW mv_vm_per_host'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP SYNONYM syn_vm'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP TRIGGER trg_vm_audit'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP PACKAGE pkg_vm'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP FUNCTION fn_vm_label'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP PROCEDURE usp_vm_count'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP SEQUENCE demo_vm_seq'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP TABLE VirtualMachine'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP TABLE Host'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP TABLE VMCluster'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP TABLE Datacenter'; EXCEPTION WHEN OTHERS THEN NULL; END;",
    "BEGIN EXECUTE IMMEDIATE 'DROP TABLE OperatingSystem'; EXCEPTION WHEN OTHERS THEN NULL; END;",
]

_ORACLE_TABLES = [
    "CREATE TABLE OperatingSystem (OSID NUMBER PRIMARY KEY, Name VARCHAR2(100))",
    "CREATE TABLE Datacenter (DatacenterID NUMBER PRIMARY KEY, Name VARCHAR2(100))",
    "CREATE TABLE VMCluster (ClusterID NUMBER PRIMARY KEY, DatacenterID NUMBER, Name VARCHAR2(100), "
    "CONSTRAINT fk_cluster_dc FOREIGN KEY (DatacenterID) REFERENCES Datacenter(DatacenterID))",
    "CREATE TABLE Host (HostID NUMBER PRIMARY KEY, ClusterID NUMBER, Hostname VARCHAR2(100), "
    "CONSTRAINT fk_host_cluster FOREIGN KEY (ClusterID) REFERENCES VMCluster(ClusterID))",
    "CREATE TABLE VirtualMachine (VMID NUMBER PRIMARY KEY, HostID NUMBER, OSID NUMBER, Name VARCHAR2(100), "
    "CONSTRAINT fk_vm_host FOREIGN KEY (HostID) REFERENCES Host(HostID), "
    "CONSTRAINT fk_vm_os FOREIGN KEY (OSID) REFERENCES OperatingSystem(OSID))",
]

# Oracle kennt kein Multi-Row-VALUES → je Zeile ein INSERT.
_ORACLE_DATA = [
    "INSERT INTO OperatingSystem VALUES (1, 'Windows Server 2022')",
    "INSERT INTO OperatingSystem VALUES (2, 'Ubuntu 24.04')",
    "INSERT INTO Datacenter VALUES (1, 'DC-North')",
    "INSERT INTO VMCluster VALUES (1, 1, 'Cluster-A')",
    "INSERT INTO Host VALUES (1, 1, 'esx-01')",
    "INSERT INTO VirtualMachine VALUES (1, 1, 1, 'web-vm')",
    "INSERT INTO VirtualMachine VALUES (2, 1, 2, 'db-vm')",
]

# Je Statement ein execute(); PL/SQL-Blöcke ohne abschließendes '/'.
_ORACLE_OBJECTS = [
    "CREATE SEQUENCE demo_vm_seq START WITH 1000 INCREMENT BY 1",
    "CREATE OR REPLACE FUNCTION fn_vm_label(p_id IN NUMBER) RETURN VARCHAR2 IS v VARCHAR2(120); "
    "BEGIN SELECT Name INTO v FROM VirtualMachine WHERE VMID = p_id; RETURN v; END;",
    "CREATE OR REPLACE PROCEDURE usp_vm_count(p_n OUT NUMBER) IS "
    "BEGIN SELECT COUNT(*) INTO p_n FROM VirtualMachine; END;",
    "CREATE OR REPLACE PACKAGE pkg_vm AS FUNCTION vm_name(p_id IN NUMBER) RETURN VARCHAR2; "
    "PROCEDURE vm_count(p_n OUT NUMBER); END pkg_vm;",
    "CREATE OR REPLACE PACKAGE BODY pkg_vm AS "
    "FUNCTION vm_name(p_id IN NUMBER) RETURN VARCHAR2 IS v VARCHAR2(120); "
    "BEGIN SELECT Name INTO v FROM VirtualMachine WHERE VMID = p_id; RETURN v; END; "
    "PROCEDURE vm_count(p_n OUT NUMBER) IS "
    "BEGIN SELECT COUNT(*) INTO p_n FROM VirtualMachine; END; END pkg_vm;",
    "CREATE OR REPLACE TRIGGER trg_vm_audit AFTER INSERT ON VirtualMachine BEGIN NULL; END;",
    "CREATE OR REPLACE VIEW vw_vm_labeled AS "
    "SELECT VMID, fn_vm_label(VMID) AS VMLabel FROM VirtualMachine",
    "CREATE MATERIALIZED VIEW mv_vm_per_host AS "
    "SELECT HostID, COUNT(*) AS Cnt FROM VirtualMachine GROUP BY HostID",
    "CREATE OR REPLACE SYNONYM syn_vm FOR VirtualMachine",
]
```

- [ ] **Step 2: `oracle`-Zweig in `seed()`.** Ersetze im `seed()` den Oracle-Stub:

```python
            elif name == "oracle":
                raise NotImplementedError(
                    "Oracle-Seed ist eine Folgescheibe — siehe sample_data/server-demo-README.md")
```

durch:

```python
            elif name == "oracle":
                for stmt in (_ORACLE_DROPS + _ORACLE_TABLES + _ORACLE_DATA + _ORACLE_OBJECTS):
                    conn.execute(text(stmt))
```

- [ ] **Step 3: Live-Verifikation (Controller-Schritt).** Der Container `oracle-luDBxP` läuft (`demo/demo @ localhost:1521/XEPDB1`). Seed ausführen und reflektieren:

```bash
./venv/bin/python sample_data/seed_server_demo.py 'oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1'
```

Dann via `SqlAlchemyLoader` reflektieren und prüfen: 5 Tabellen (inkl. FKs `hostid→host`, `osid→operatingsystem`), View `vw_vm_labeled`, Sequence `demo_vm_seq`, Matview `mv_vm_per_host`, Trigger `trg_vm_audit`, Routinen `fn_vm_label`(function)/`usp_vm_count`(procedure)/`pkg_vm`(package), Synonym `syn_vm`, und `vw_vm_labeled.routines` enthält `fn_vm_label`. Zweiter Seed-Lauf = idempotent (keine Fehler).

- [ ] **Step 4: Commit**

```bash
git add sample_data/seed_server_demo.py
git commit -m "feat(demo): Oracle-Server-Demo-CMDB-Seeder (alle Objektkategorien) [AP-67·Oracle]"
```

---

### Task 2: Skip-guardeter Live-Test + Bring-up-README

**Files:**
- Create: `tests/test_oracle_seed_integration.py`
- Modify: `sample_data/server-demo-README.md` — Oracle-Abschnitt
- Verifikation: pytest (skip ohne URL); Controller läuft ihn mit gesetzter `LUCENT_ORACLE_TEST_URL` live grün.

**Interfaces:**
- Consumes: `seed_server_demo.seed` (Task 1), `SqlAlchemyLoader`.

- [ ] **Step 1: Integrationstest schreiben** (`tests/test_oracle_seed_integration.py`, neu):

```python
"""Skip-guarded Oracle demo-seed integration test (AP-67·Oracle-Adaption).

Runs only when ``LUCENT_ORACLE_TEST_URL`` points at a reachable Oracle instance;
otherwise it skips, so the suite stays green without an Oracle backend. Example::

    LUCENT_ORACLE_TEST_URL='oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1' \\
        ./venv/bin/python -m pytest tests/test_oracle_seed_integration.py

Seeds the server-demo CMDB via the app's seeder and asserts every reflectable
Oracle object category appears (case-insensitive: Oracle reflection returns
table/view/sequence names lower-cased and trigger/routine/synonym names upper-cased).
"""
import os
import pathlib
import sys

import pytest

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader

_ORACLE_URL = os.environ.get("LUCENT_ORACLE_TEST_URL")


@pytest.mark.skipif(
    not _ORACLE_URL,
    reason="set LUCENT_ORACLE_TEST_URL to a reachable Oracle URL to run the live "
           "integration test",
)
def test_oracle_demo_seed_shows_all_categories():
    """Seed the server demo CMDB and assert every reflectable category appears."""
    pytest.importorskip("oracledb")
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "sample_data"))
    try:
        from seed_server_demo import seed
        seed(_ORACLE_URL)
    except Exception as exc:  # instance unreachable / seed failed → skip
        pytest.skip(f"Oracle not reachable or seed failed: {exc}")

    schema = SqlAlchemyLoader(_ORACLE_URL).load()
    up = lambda xs: {x.name.upper() for x in xs}
    assert {"VIRTUALMACHINE", "HOST", "VMCLUSTER", "DATACENTER", "OPERATINGSYSTEM"} <= up(schema.tables)
    assert "VW_VM_LABELED" in up(schema.views)
    assert "TRG_VM_AUDIT" in up(schema.triggers)
    assert "DEMO_VM_SEQ" in up(schema.sequences)
    assert "MV_VM_PER_HOST" in up(schema.materialized_views)
    assert "SYN_VM" in up(schema.synonyms)
    kinds = {r.name.upper(): r.kind for r in schema.routines}
    assert kinds.get("FN_VM_LABEL") == "function"
    assert kinds.get("USP_VM_COUNT") == "procedure"
    assert kinds.get("PKG_VM") == "package"
    # AP-66·S1: the view references the function
    vw = next(v for v in schema.views if v.name.upper() == "VW_VM_LABELED")
    assert "FN_VM_LABEL" in {r.upper() for r in vw.routines}
```

- [ ] **Step 2: Test läuft (skip ohne URL)**

Run: `./venv/bin/python -m pytest tests/test_oracle_seed_integration.py -v`
Expected: `1 skipped` (kein `LUCENT_ORACLE_TEST_URL`).

- [ ] **Step 3: README-Oracle-Abschnitt.** In `sample_data/server-demo-README.md` einen Oracle-Abschnitt ergänzen (Deutsch), analog zum MSSQL-Teil:

```markdown
## Oracle (AP-67·Oracle-Adaption)

Oracle hat kein portables Einzeldatei-Format — die Demo braucht eine laufende Instanz.

1. Container starten (login-freies Image):
   ```bash
   podman run -d --name oracle-luDBxP -p 1521:1521 \
     -e ORACLE_PASSWORD=LucentTest2026 -e APP_USER=demo -e APP_USER_PASSWORD=demo \
     docker.io/gvenzl/oracle-xe:21-slim-faststart
   ```
2. Demo einspielen (idempotent):
   ```bash
   ./venv/bin/python sample_data/seed_server_demo.py \
     'oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1'
   ```
3. In der App verbinden mit
   `oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1` — der Sidebar-Tree
   zeigt dann alle Oracle-Kategorien (Tabellen, View, Sequence, Materialized View,
   Trigger, Function, Procedure, Package, Synonym).
4. Live-Test (optional):
   ```bash
   LUCENT_ORACLE_TEST_URL='oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1' \
     ./venv/bin/python -m pytest tests/test_oracle_seed_integration.py
   ```

Hinweis: `CLUSTER` ist in Oracle reserviert; die Cluster-Tabelle heißt im Oracle-Demo `VMCluster`.
```

- [ ] **Step 4: Volle Suite (Regressions-Guard) + Live-Test (Controller)**

Run: `./venv/bin/python -m pytest -q`
Expected: **445 passed, 11 skipped** (der neue Test skippt ohne URL).
Controller-Live: mit gesetzter `LUCENT_ORACLE_TEST_URL` → `test_oracle_demo_seed_shows_all_categories PASSED`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_oracle_seed_integration.py sample_data/server-demo-README.md
git commit -m "test+docs: Oracle-Demo-Seed-Integrationstest + Bring-up-README [AP-67·Oracle]"
```

---

### Task 3: Release v0.64.0 + Doku

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`); `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`; `roadmap.md` (AP-67·Oracle-Adaption erledigt) + Gantt `projekt-roadmap-1.mmd` (AP-67·Oracle done; `:p43`-Zeile in den done-Block) + Board falls AP-67·Oracle dort geführt; `zensical.toml`; `icon-rail.js`; `kennzahlen.md`; Konzept-Status (`docs/concepts/2026-06-30-oracle-demo-cmdb.md` → Oracle-Adaption erledigt); ggf. `CLAUDE.md` (Oracle-Demo-Hinweis); Site + gh-pages.

**Interfaces:**
- Consumes: fertige, live-verifizierte Änderungen aus Task 1-2.

- [ ] **Step 1: Version bumpen (minor — neues Feature/Demo)**

```bash
./venv/bin/python sync_version.py --minor   # 0.63.0 → 0.64.0
```

- [ ] **Step 2: Doku nachziehen (am echten Code geprüft, nicht geraten).** Changelog EN + DE (neuer `[0.64.0]`: Oracle-Server-Demo-CMDB-Seeder, alle Oracle-Kategorien, live gegen Oracle-XE verifiziert, `VMCluster` wegen reserviertem `CLUSTER`); `roadmap.md` AP-67·Oracle-Adaption-Zeile von „offen/hängt an Oracle-Instanz" → „erledigt v0.64.0" + Detail; Gantt `AP-67·Oracle-Adaption :done, f39, 2026-07-01, 1d` (aus dem `:p43`-Block), Band-Header ggf. v0.64.0; Konzept-Status auf „Oracle-Adaption erledigt (v0.64.0)". Kennzahlen frisch erheben:

```bash
git rev-list --count HEAD
./venv/bin/python -m pytest -q | tail -1
```

`zensical.toml` (v0.63.0 → v0.64.0), `icon-rail.js` (`APP_VERSION`/`TEST_COUNT`=445/`TEST_DATE`), `kennzahlen.md` (Version, Tests 445, Skipped 11, Commits, Stand-Datum; Statements praktisch unverändert — Seeder ist `sample_data/`, nicht im Coverage-Nenner). Danach per `grep` gegenprüfen, dass Changelog/Roadmap/Gantt-SVG/Kennzahlen den Oracle-Seed nennen.

- [ ] **Step 3: Suite + Site**

Run: `./venv/bin/python -m pytest`
Expected: **445 passed, 11 skipped**.
Danach `./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py`; gerendertes Gantt-SVG + `index.html`-Version gegenprüfen.

- [ ] **Step 4: Commit (Merge/Push/gh-pages nur auf Nutzer-Ansage)**

```bash
git add -A
git commit -m "release: v0.64.0 — AP-67·Oracle-Adaption (Oracle-Server-Demo-CMDB-Seeder)"
```
