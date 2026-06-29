# AP-67·MSSQL-Grundlage — Server-Demo-CMDB + MSSQL-Synonym-Reflektion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine MSSQL-Server-Demo-CMDB, die alle reflektierbaren Objektkategorien (Tabellen/Views/Trigger/Procedures/Functions/Sequences/Synonyms) im Tree zeigt — als Grundlage, später auf Oracle adaptierbar; inkl. der dafür nötigen MSSQL-Synonym-Reflektion.

**Architecture:** Kleine Reflektions-Erweiterung (`_reflect_synonyms` bekommt einen MSSQL-`sys.synonyms`-Zweig) + ein neuer SQLAlchemy-basierter Seeder (`sample_data/seed_server_demo.py`, idempotent, dialekt-dispatch) + ein skip-guarded Integrationstest, der gegen den laufenden MSSQL-Container seedet, reflektiert und alle 7 Kategorien prüft. Read-only-Invariante des Tools unberührt (der Seeder ist externes Setup).

**Tech Stack:** Python/SQLAlchemy (Reflektion + Seed), pyodbc/ODBC Driver 18 (MSSQL, vorhanden), pytest (skip-guarded Live-Test + SQLite-Unit).

## Global Constraints

- **Read-only (Tool):** der Loader liest nur; der Seeder ist ein **externes** Setup-Skript, nicht vom Tool ausgeführt.
- **Layering:** `core/` importiert nie Flask; der Loader bleibt resilient (`except SQLAlchemyError → ()`).
- **Reflektion dialekt-gegated:** `_reflect_synonyms` → MSSQL + Oracle behandelt, sonst `()`; SQLite-Test bleibt grün.
- **Idempotenter Seeder:** erst drop-if-exists, dann create; mehrfach ausführbar.
- **MSSQL-DDL-Batches:** `CREATE FUNCTION/PROCEDURE/TRIGGER/VIEW` müssen je eigene Anweisung sein → ein `conn.execute(text(...))` pro Statement; Engine mit `isolation_level="AUTOCOMMIT"`.
- **Sprache:** Deutsch (Commits/Doku). **No CDN.** **Version-Bump nur via `sync_version.py`**, Ziel **v0.60.0** (`--minor`).
- **Live-Container:** `LUCENT_MSSQL_TEST_URL='mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'` (läuft).
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14).

---

### Task 1: Reflektion — `_reflect_synonyms` MSSQL-Zweig

**Files:**
- Modify: `core/loaders/sqlalchemy_loader.py` (`_reflect_synonyms`)
- Test: `tests/test_sqlalchemy_loader.py`

**Interfaces:**
- Produces: `_reflect_synonyms(engine, schema)` reflektiert jetzt auch MSSQL (`sys.synonyms`) → `Synonym(name, target)`; Oracle unverändert; SQLite/PG/sonst → `()`.

- [ ] **Step 1: Write the failing test** in `tests/test_sqlalchemy_loader.py` (ans Dateiende). SQLite bleibt leer (Regressionsschutz; der MSSQL-Pfad wird in Task 3 live geprüft):

```python
def test_loader_synonyms_empty_on_sqlite_after_mssql_branch(inventory_url):
    # Der neue MSSQL-Zweig darf SQLite nicht berühren — Synonyms bleiben ().
    schema = SqlAlchemyLoader(inventory_url).load()
    assert schema.synonyms == ()
```

- [ ] **Step 2: Run it** — Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py::test_loader_synonyms_empty_on_sqlite_after_mssql_branch -v` — Expected: PASS schon jetzt (Default-Verhalten); dient als Regressionswächter für Step 3.

- [ ] **Step 3: Add the MSSQL branch** in `core/loaders/sqlalchemy_loader.py::_reflect_synonyms`. Aktuell beginnt die Funktion mit `if name != "oracle": return ()`. Ersetzen durch eine Dialekt-Verzweigung:

```python
def _reflect_synonyms(engine, schema=None) -> tuple:
    """Read-only synonym reflection — Oracle (all_synonyms) + MSSQL
    (sys.synonyms); other dialects → ()."""
    name = getattr(getattr(engine, "dialect", None), "name", "")
    if name not in ("oracle", "mssql"):
        return ()
    try:
        if name == "mssql":
            with engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT name, base_object_name FROM sys.synonyms "
                    "WHERE SCHEMA_NAME(schema_id) = :s ORDER BY name"
                ), {"s": schema or "dbo"}).fetchall()
            return tuple(
                Synonym(r[0], (r[1] or "").replace("[", "").replace("]", ""))
                for r in rows
            )
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

- [ ] **Step 4: Run the loader test file** — Run: `./venv/bin/python -m pytest tests/test_sqlalchemy_loader.py -q` — Expected: PASS, pristine.

- [ ] **Step 5: Live-verify against the container** (the MSSQL synonym path):

```bash
export LUCENT_MSSQL_TEST_URL='mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
./venv/bin/python - <<'PY'
import os
from sqlalchemy import create_engine, text
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
u=os.environ["LUCENT_MSSQL_TEST_URL"]
e=create_engine(u, isolation_level="AUTOCOMMIT"); c=e.connect()
c.execute(text("IF OBJECT_ID('_t_x') IS NULL CREATE TABLE _t_x(id int)"))
c.execute(text("IF OBJECT_ID('_syn_x') IS NULL CREATE SYNONYM _syn_x FOR dbo._t_x"))
syn={s.name:s.target for s in SqlAlchemyLoader(u).load().synonyms}
print("synonyms:", syn)
assert "_syn_x" in syn and "_t_x" in syn["_syn_x"], syn
for s in ["DROP SYNONYM IF EXISTS _syn_x","DROP TABLE IF EXISTS _t_x"]: c.execute(text(s))
c.close(); e.dispose(); print("OK")
PY
```
Expected: `synonyms: {'_syn_x': 'dbo._t_x'}` + `OK`. Paste into the report.

- [ ] **Step 6: Commit**

```bash
git add core/loaders/sqlalchemy_loader.py tests/test_sqlalchemy_loader.py
git commit -m "feat(loader): MSSQL-Synonym-Reflektion (sys.synonyms) (AP-67·MSSQL)"
```

---

### Task 2: Seeder — `sample_data/seed_server_demo.py`

**Files:**
- Create: `sample_data/seed_server_demo.py`

**Interfaces:**
- Produces: `seed(url: str) -> None` — legt die kompakte CMDB + MSSQL-Objekte idempotent an. CLI: `python sample_data/seed_server_demo.py <url>` (oder `LUCENT_DEMO_SEED_URL`).

- [ ] **Step 1: Create `sample_data/seed_server_demo.py`**

```python
"""Seed a server-side demo CMDB so the LucentTools tree shows all reflectable
object categories (tables, views, triggers, procedures, functions, sequences,
synonyms). MSSQL is implemented; Oracle is a documented follow-up (see
sample_data/server-demo-README.md). Idempotent: drops then recreates.

This is an external SETUP script — it is NOT run by the read-only tool itself.

    python sample_data/seed_server_demo.py 'mssql+pyodbc://sa:...@host:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
"""
import os
import sys

from sqlalchemy import create_engine, text

# Compact CMDB: Datacenter <- Cluster <- Host <- VirtualMachine -> OperatingSystem
_MSSQL_DROPS = [
    "IF OBJECT_ID('dbo.vw_vm_labeled','V') IS NOT NULL DROP VIEW dbo.vw_vm_labeled",
    "IF OBJECT_ID('dbo.syn_vm','SN') IS NOT NULL DROP SYNONYM dbo.syn_vm",
    "IF OBJECT_ID('dbo.trg_vm_audit','TR') IS NOT NULL DROP TRIGGER dbo.trg_vm_audit",
    "IF OBJECT_ID('dbo.usp_vm_count','P') IS NOT NULL DROP PROCEDURE dbo.usp_vm_count",
    "IF OBJECT_ID('dbo.fn_vm_label','FN') IS NOT NULL DROP FUNCTION dbo.fn_vm_label",
    "IF EXISTS (SELECT 1 FROM sys.sequences WHERE name='demo_vm_seq') DROP SEQUENCE dbo.demo_vm_seq",
    "IF OBJECT_ID('dbo.VirtualMachine','U') IS NOT NULL DROP TABLE dbo.VirtualMachine",
    "IF OBJECT_ID('dbo.Host','U') IS NOT NULL DROP TABLE dbo.Host",
    "IF OBJECT_ID('dbo.Cluster','U') IS NOT NULL DROP TABLE dbo.Cluster",
    "IF OBJECT_ID('dbo.Datacenter','U') IS NOT NULL DROP TABLE dbo.Datacenter",
    "IF OBJECT_ID('dbo.OperatingSystem','U') IS NOT NULL DROP TABLE dbo.OperatingSystem",
]

_MSSQL_TABLES = [
    "CREATE TABLE dbo.OperatingSystem (OSID INT PRIMARY KEY, Name NVARCHAR(100))",
    "CREATE TABLE dbo.Datacenter (DatacenterID INT PRIMARY KEY, Name NVARCHAR(100))",
    "CREATE TABLE dbo.Cluster (ClusterID INT PRIMARY KEY, DatacenterID INT, Name NVARCHAR(100), "
    "CONSTRAINT fk_cluster_dc FOREIGN KEY (DatacenterID) REFERENCES dbo.Datacenter(DatacenterID))",
    "CREATE TABLE dbo.Host (HostID INT PRIMARY KEY, ClusterID INT, Hostname NVARCHAR(100), "
    "CONSTRAINT fk_host_cluster FOREIGN KEY (ClusterID) REFERENCES dbo.Cluster(ClusterID))",
    "CREATE TABLE dbo.VirtualMachine (VMID INT PRIMARY KEY, HostID INT, OSID INT, Name NVARCHAR(100), "
    "CONSTRAINT fk_vm_host FOREIGN KEY (HostID) REFERENCES dbo.Host(HostID), "
    "CONSTRAINT fk_vm_os FOREIGN KEY (OSID) REFERENCES dbo.OperatingSystem(OSID))",
]

_MSSQL_DATA = [
    "INSERT INTO dbo.OperatingSystem VALUES (1,'Windows Server 2022'),(2,'Ubuntu 24.04')",
    "INSERT INTO dbo.Datacenter VALUES (1,'DC-North')",
    "INSERT INTO dbo.Cluster VALUES (1,1,'Cluster-A')",
    "INSERT INTO dbo.Host VALUES (1,1,'esx-01')",
    "INSERT INTO dbo.VirtualMachine VALUES (1,1,1,'web-vm'),(2,1,2,'db-vm')",
]

# Each object DDL is its own batch (MSSQL requires CREATE FUNCTION/PROC/TRIGGER/VIEW alone).
_MSSQL_OBJECTS = [
    "CREATE SEQUENCE dbo.demo_vm_seq AS INT START WITH 1000 INCREMENT BY 1",
    "CREATE FUNCTION dbo.fn_vm_label(@id INT) RETURNS NVARCHAR(120) AS "
    "BEGIN RETURN (SELECT Name FROM dbo.VirtualMachine WHERE VMID = @id) END",
    "CREATE PROCEDURE dbo.usp_vm_count AS BEGIN SET NOCOUNT ON; "
    "SELECT COUNT(*) AS n FROM dbo.VirtualMachine END",
    "CREATE TRIGGER dbo.trg_vm_audit ON dbo.VirtualMachine AFTER INSERT AS BEGIN SET NOCOUNT ON END",
    "CREATE VIEW dbo.vw_vm_labeled AS SELECT VMID, dbo.fn_vm_label(VMID) AS Label FROM dbo.VirtualMachine",
    "CREATE SYNONYM dbo.syn_vm FOR dbo.VirtualMachine",
]


def seed(url):
    """Seed the demo CMDB at `url`. Idempotent. Raises on unsupported dialect."""
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        name = engine.dialect.name
        with engine.connect() as conn:
            if name == "mssql":
                for stmt in (_MSSQL_DROPS + _MSSQL_TABLES + _MSSQL_DATA + _MSSQL_OBJECTS):
                    conn.execute(text(stmt))
            elif name == "oracle":
                raise NotImplementedError(
                    "Oracle-Seed ist eine Folgescheibe — siehe sample_data/server-demo-README.md")
            else:
                raise SystemExit(f"Demo-Seed unterstuetzt nur mssql/oracle, nicht: {name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LUCENT_DEMO_SEED_URL")
    if not target:
        sys.exit("Usage: python seed_server_demo.py <SQLAlchemy-URL>  (or set LUCENT_DEMO_SEED_URL)")
    seed(target)
    print("Demo-CMDB geseedet:", target.split("@")[-1])
```

- [ ] **Step 2: Run the seeder against the live container (idempotent — run TWICE)**

```bash
./venv/bin/python sample_data/seed_server_demo.py 'mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
./venv/bin/python sample_data/seed_server_demo.py 'mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
```
Expected: beide Läufe ohne Fehler (idempotent). Wenn ein DDL-Batch scheitert (z. B. Syntax), hier fixen — am echten Container verifiziert. Paste both runs into the report.

- [ ] **Step 3: Commit**

```bash
git add sample_data/seed_server_demo.py
git commit -m "feat(demo): Server-Demo-CMDB-Seeder (MSSQL) für alle Objektkategorien (AP-67·MSSQL)"
```

---

### Task 3: Integrationstest (Seed + Reflect + 7 Kategorien) + Bring-up-README

**Files:**
- Modify: `tests/test_mssql_integration.py`
- Create: `sample_data/server-demo-README.md`

**Interfaces:**
- Consumes: `seed(url)` (Task 2), `SqlAlchemyLoader(url).load()` (Task 1 für Synonyms).

- [ ] **Step 1: Add the integration test** in `tests/test_mssql_integration.py` (ans Dateiende, skip-guarded wie die anderen). Verifiziert, dass nach dem Seed alle 7 Kategorien reflektieren:

```python
@pytest.mark.skipif(
    not _MSSQL_URL,
    reason="set LUCENT_MSSQL_TEST_URL to a reachable MSSQL URL to run the live "
           "integration test",
)
def test_mssql_demo_seed_shows_all_categories():
    """Seed the server demo CMDB and assert every reflectable category appears."""
    pytest.importorskip("pyodbc")
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "sample_data"))
    try:
        from seed_server_demo import seed
        seed(_MSSQL_URL)
    except Exception as exc:
        pytest.skip(f"MSSQL not reachable or seed failed: {exc}")

    schema = SqlAlchemyLoader(_MSSQL_URL).load()
    names = lambda xs: {x.name for x in xs}
    assert {"VirtualMachine", "Host", "Cluster", "Datacenter", "OperatingSystem"} <= names(schema.tables)
    assert "vw_vm_labeled" in names(schema.views)
    assert "trg_vm_audit" in names(schema.triggers)
    assert "demo_vm_seq" in names(schema.sequences)
    assert "syn_vm" in names(schema.synonyms)
    kinds = {r.name: r.kind for r in schema.routines}
    assert kinds.get("fn_vm_label") == "function"
    assert kinds.get("usp_vm_count") == "procedure"
    # AP-66·S1: the view references the function
    vw = next(v for v in schema.views if v.name == "vw_vm_labeled")
    assert "fn_vm_label" in vw.routines
```

- [ ] **Step 2: Run it live + the full suite**

```bash
LUCENT_MSSQL_TEST_URL='mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes' \
  ./venv/bin/python -m pytest tests/test_mssql_integration.py::test_mssql_demo_seed_shows_all_categories -v
./venv/bin/python -m pytest -q   # ohne URL: skippt; alles grün
```
Expected: live PASS; full suite green (the new test skips without the URL). If the view-routine assertion fails, check whether viewdeps matched `fn_vm_label` (the reflected routine name) — report as a concern, do not weaken the assertion without checking.

- [ ] **Step 3: Write `sample_data/server-demo-README.md`** — podman-MSSQL-Bring-up + seed + connect:

```markdown
# Server-Demo-CMDB (MSSQL; Oracle-Adaption als Folge)

Zeigt im LucentTools-Tree alle reflektierbaren Objektkategorien (Tabellen, Views,
Trigger, Procedures, Functions, Sequences, Synonyms) — anders als die SQLite-Demo.

## MSSQL-Container (podman)
```bash
podman run -d --name mssql-luDBxP -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='LucentTest2026' \
  -p 1433:1433 mcr.microsoft.com/mssql/server:2022-latest
```

## Seed einspielen
```bash
./venv/bin/python sample_data/seed_server_demo.py \
  'mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
```
Idempotent — mehrfach ausführbar.

## Aufgeräumter Tree: eigene Demo-DB (empfohlen)
Die `master`-DB enthält MSSQL-System-Prozeduren (`sp_MSrepl_startup` …), die sonst im
Routinen-Tree mit auftauchen. Für einen sauberen Demo-Tree eine eigene DB anlegen und
die URL darauf zeigen lassen (eine frische User-DB hat keine System-Procs):
```bash
# DB einmalig anlegen (z. B. via sqlcmd im Container):
podman exec -i mssql-luDBxP /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'LucentTest2026' -C \
  -Q "IF DB_ID('luDBxP_demo') IS NULL CREATE DATABASE luDBxP_demo"
# dann gegen die Demo-DB seeden + verbinden (…/luDBxP_demo statt …/master):
./venv/bin/python sample_data/seed_server_demo.py \
  'mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/luDBxP_demo?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
```

## In der App verbinden
Verbindung mit der Seed-URL anlegen → der Tree zeigt alle 7 Kategorien; `vw_vm_labeled`
zeigt im Detail „Verwendet Routinen: fn_vm_label" (AP-66·S1).

## Oracle-Adaption (Folge)
Gleiche Tabellen, Oracle-Objekt-DDL (PL/SQL-Trigger/Function/Procedure, PACKAGE, SEQUENCE,
SYNONYM, MATERIALIZED VIEW). `seed()` dispatcht bereits auf den Dialekt; der Oracle-Block ist
zu ergänzen, sobald eine Oracle-Instanz verfügbar ist.
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_mssql_integration.py sample_data/server-demo-README.md
git commit -m "test+docs: MSSQL-Demo-Seed-Integrationstest (7 Kategorien) + Bring-up-README (AP-67·MSSQL)"
```

---

### Task 4: Release v0.60.0 + Doku (am Code geprüft)

**Files:**
- Modify: via `sync_version.py`; Changelog (EN + DE-Mirror), Roadmap-Prosa + `.mmd`, CLAUDE.md, Kennzahlen, `zensical.toml`, AP-67-Konzept-Doc, Site, gh-pages.

**Interfaces:** keine (Release/Doku).

- [ ] **Step 1: Version-Bump** — `./venv/bin/python sync_version.py --minor`  (→ v0.60.0)

- [ ] **Step 2: Doku am echten Code geprüft nachziehen** (grep-belegt):
  - **Changelog EN + DE-Mirror:** v0.60.0 — MSSQL-Synonym-Reflektion + Server-Demo-CMDB-Seeder (alle Objektkategorien im Tree).
  - **CLAUDE.md** „Bekannte Einschränkungen": Synonyms jetzt **Oracle + MSSQL** (`sys.synonyms`); die Sequences-Notiz korrigieren (MSSQL-Sequences reflektieren via `get_sequence_names`, **nicht** leer).
  - **Roadmap-Prosa + Diagramme** (`roadmap.md`, `projekt-roadmap-1.mmd`, `entwicklung-arbeitspakete-1.mmd`): AP-67·MSSQL-Grundlage als erledigt (eigener Eintrag); AP-67·Oracle-Adaption offen.
  - **`docs/concepts/2026-06-30-oracle-demo-cmdb.md`:** Status um „MSSQL-first-Grundlage erledigt (v0.60.0)" ergänzen.
  - **`architektur.md`/`datenmodell.md`:** falls die Synonym-Reflektion/Dialekt-Matrix dort steht, MSSQL ergänzen.
  - **Kennzahlen** (`kennzahlen.md`): Version v0.60.0, Commits/Tests/Coverage **frisch erheben**
    (`git rev-list --count HEAD`, `pytest`, `pytest --cov=core --cov=web --cov=launcher --cov=config --cov=app`),
    Karten + Tabelle + **Per-Modul-Balken**.
  - **`zensical.toml`** Versionsstring.
  - Mit `grep` gegenprüfen, dass CLAUDE.md die MSSQL-Synonyms nennt + die Sequence-Korrektur drin ist.

- [ ] **Step 3: Site bauen + verifizieren** — `bash luDBxP-docs/run_luDBxP_docs.sh --build`; grep `v0.60.0` in der Site + AP-67 im Gantt-SVG.

- [ ] **Step 4: Voll-Suite + Commit + Deploy**

```bash
./venv/bin/python -m pytest -q   # grün
git add -A
git commit -m "release: v0.60.0 — AP-67·MSSQL-Grundlage (Server-Demo-CMDB + MSSQL-Synonyme)"
# FF-Merge nach master + Push + gh-pages-Worktree-Deploy (etabliertes Muster)
```

---

## Self-Review

**1. Spec coverage:**
- A. MSSQL-Synonym-Reflektion (`sys.synonyms`-Zweig, `[]`-Strip) + SQLite-Regression → Task 1 ✓
- B. Seeder `seed_server_demo.py` (5-Tabellen-CMDB + MSSQL-Objekte, idempotent, Oracle-Stub, CLI) → Task 2 ✓
- C. Integrationstest (7 Kategorien + AP-66·S1-View-Routine) + Bring-up-README → Task 3 ✓
- Release/Doku inkl. Sequence-Doku-Korrektur + AP-67-Konzept-Update → Task 4 ✓
- Read-only (Tool): Seeder ist externes Setup, kein Tool-Pfad ändert sich ✓

**2. Placeholder scan:** Reflektions-Code, Seeder-DDL, Test, README konkret. „Am echten Code/Container prüfen" betrifft die Live-Verifikation (Container läuft), nicht zu erfindende Logik.

**3. Type consistency:** `_reflect_synonyms(engine, schema)` Signatur unverändert, liefert weiter `tuple[Synonym]`; `seed(url) -> None` identisch in Task 2 (def) + Task 3 (Import/Aufruf); Objektnamen (`vw_vm_labeled`/`trg_vm_audit`/`demo_vm_seq`/`syn_vm`/`fn_vm_label`/`usp_vm_count`) durchgängig zwischen Seeder (Task 2) und Test (Task 3).

## Verifikations-Hinweis (Controller-vorab gegen den Container geprüft)
Das gesamte Seeder-DDL + die Reflektion sind **vorab live gegen den laufenden Container** verifiziert: alle 5 Tabellen, View, Trigger, Sequence, Function (`fn_vm_label`) + Procedure (`usp_vm_count`) reflektieren, und `vw_vm_labeled.routines == ('fn_vm_label',)` (AP-66·S1). **Synonyms** waren dabei erwartungsgemäß leer (Task 1 = der MSSQL-Zweig fehlte noch). In `master` erscheinen zusätzlich MSSQL-System-Procs (`sp_MSrepl_*`) — daher nutzt der Integrationstest (Task 3) **Subset-/Namens-genaue** Assertions (`<=`, `kinds.get(...)`), nie exakte Mengengleichheit.
