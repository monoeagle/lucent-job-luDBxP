# AP-67 Slice 2a — Reiches Oracle-Demo-Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Oracle-Server-Demo von 5 Tabellen auf eine große VMware-artige CMDB (~37 Tabellen · 10 Views · ~15 Routinen + Packages/Sequences/Synonyme/Matviews) ausbauen, damit komplexe Join-Pfade/Subsetting/Analyzer erkundbar sind.

**Architecture:** Reine Demo-Daten. Die große Oracle-DDL wandert in ein eigenes Modul `sample_data/oracle_demo.py` (Listen `DROPS/TABLES/DATA/OBJECTS`); `seed_server_demo.py` importiert es. **Die DDL wird iterativ live gegen den laufenden Oracle-21c-XE-Container entwickelt** (`oracle-luDBxP`, `demo/demo @ localhost:1521/XEPDB1`) — jedes Objekt muss reflektieren; Dialekt-Fallen werden sofort gefangen. Kein Tool-/Reflektions-Code.

**Tech Stack:** Python, SQLAlchemy + `oracledb` (Thin), Oracle 21c XE (Container), pytest.

## Global Constraints

- Read-only-Invariante: das Seed ist externes Setup, das das Werkzeug NIE ausführt.
- Kein Tool-/Reflektions-Code — nur Daten.
- Oracle-Besonderheiten: `NUMBER`/`VARCHAR2`; per-Objekt-Drop `BEGIN EXECUTE IMMEDIATE 'DROP …'; EXCEPTION WHEN OTHERS THEN NULL; END;`; `CREATE OR REPLACE` für PL/SQL; **einzeilige INSERTs** (kein Multi-Row-`VALUES`); PL/SQL-Blöcke ohne trailing `/`; reservierte Wörter meiden (`CLUSTER`→`VMCluster`); kein `dbo.`-Präfix; AUTOCOMMIT.
- **Jedes Statement muss live gegen den Container erfolgreich laufen und reflektieren** — die DDL ist erst fertig, wenn der Reflektions-Check alle Kategorien + Merkmale zeigt.
- Baseline: `./venv/bin/python -m pytest` → **445 passed, 11 skipped** (v0.64.2); ohne `LUCENT_ORACLE_TEST_URL` bleibt der Oracle-Test `skipped`.

---

### Task 1: `sample_data/oracle_demo.py` — reiches DDL-Modul (live entwickelt)

**Files:**
- Create: `sample_data/oracle_demo.py` — `DROPS`, `TABLES`, `DATA`, `OBJECTS` (jede ein `list[str]`).
- Verifikation: Controller entwickelt + verifiziert live gegen den Container (kein pytest ohne Oracle).

**Interfaces:**
- Produces: Modul `sample_data/oracle_demo.py` mit vier Listen `DROPS`, `TABLES`, `DATA`, `OBJECTS` (Statement = ein String), ausführbar in dieser Reihenfolge über `conn.execute(text(stmt))` unter AUTOCOMMIT.

**Schema-Ziel (aus der Spec — exakt zu treffen):**
- **~37 Tabellen** in 5 Subdomänen: Referenz (OperatingSystem, VMTemplate, Vendor, Product, Environment); Compute (Datacenter, Folder [Self-Ref ParentFolderID], VMCluster, Host, ResourcePool [Composite-Key ClusterID,PoolKey], VirtualMachine, VMDisk, VMSnapshot [Self-Ref ParentSnapshotID], VMPlacement [Composite-FK→ResourcePool], VMNetworkInterface); Storage (StorageArray, StoragePool, Datastore, LUN, Volume, DiskBackingFile); Network (Network, VLAN, VirtualSwitch, PortGroup, IPPool, IPAddress); Backup/DR (BackupPolicy, BackupJob, RestorePoint, Replication [2 FKs: Quell-VM + Ziel-Datacenter]); Lizenz/Audit (LicenseKey, LicenseAssignment, AuditLog [No-Path], Tag, TagAssignment).
- **FK-Graph-Merkmale (Pflicht):** ≥2 Diamanten, 1 Composite-FK (VMPlacement), 2 Self-Refs (Folder, VMSnapshot), alternative Routen (Replication), 1 No-Path-Tabelle (AuditLog).
- **10 Views**, davon ≥4 funktions-aufrufend (AP-66·S1): vw_vm_labeled, vw_host_capacity, vw_datastore_usage, vw_license_utilization, vw_orphaned_vms, vw_vm_full_path, vw_windows_vms, vw_cluster_hostcount, vw_backup_status, vw_network_topology.
- **~15 Routinen:** ~6 Functions (fn_vm_label, fn_host_capacity, fn_folder_path, fn_datastore_free, fn_license_seats_used, fn_vm_power_state); ~3 Procedures (usp_vm_count, usp_rebalance_report, usp_cleanup_snapshots); 3–4 Packages (pkg_capacity, pkg_inventory, pkg_licensing, pkg_backup — je Spec+Body).
- **3 Sequences** (seq_vm_id, seq_ticket, seq_audit), **3 Synonyme** (syn_vm, syn_host, syn_ds), **2 Materialized Views** (mv_cluster_capacity, mv_vm_per_datastore).
- **Daten:** referentiell konsistente Zeilen (Eltern vor Kindern), mehrere je Tabelle, einzeilige INSERTs.

- [ ] **Step 1: DDL iterativ live entwickeln.** Modul `sample_data/oracle_demo.py` mit den vier Listen anlegen und **Statement für Statement gegen den Container** ausführen (Reihenfolge Drops→Tables→Data→Objects; Tabellen Eltern-zuerst, Drops abhängige-zuerst). Nach jeder Erweiterung ausführen und Fehler sofort beheben (reservierte Wörter, FK-Reihenfolge, PL/SQL-Syntax). Ablauf je Runde:

```bash
./venv/bin/python -c "import sys; sys.path.insert(0,'sample_data'); import oracle_demo as o; \
from sqlalchemy import create_engine, text; \
e=create_engine('oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1', isolation_level='AUTOCOMMIT'); \
c=e.connect(); \
[c.execute(text(s)) for s in (o.DROPS+o.TABLES+o.DATA+o.OBJECTS)]; \
print('seed ok'); e.dispose()"
```

- [ ] **Step 2: Live-Reflektions-Check (Ziel-Erfüllung).** Über den `SqlAlchemyLoader` reflektieren und prüfen: ≥35 Tabellen, ≥10 Views, ≥15 Routinen (mit ≥1 function/procedure/package), ≥2 Sequences, ≥2 Synonyme, ≥2 Materialized Views; mindestens ein Composite-FK (Tabelle mit 2-spaltigem FK), mindestens eine Self-Ref (FK auf dieselbe Tabelle), und der AP-66·S1-Link (eine View mit `routines`).

```bash
./venv/bin/python -c "from core.loaders.sqlalchemy_loader import SqlAlchemyLoader; \
s=SqlAlchemyLoader('oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1').load(); \
print('tables',len(s.tables),'views',len(s.views),'routines',len(s.routines),'seq',len(s.sequences),'mv',len(s.materialized_views),'syn',len(s.synonyms)); \
print('composite-FK', any(len(fk.columns)>1 for t in s.tables for fk in t.foreign_keys)); \
print('self-ref', any(fk.ref_table.upper()==t.name.upper() for t in s.tables for fk in t.foreign_keys)); \
print('view-routines', [v.name for v in s.views if v.routines])"
```

Expected: alle Schwellen erfüllt, `composite-FK True`, `self-ref True`, mindestens eine View mit routines.

- [ ] **Step 3: Idempotenz.** Den Seed-Lauf aus Step 1 ein zweites Mal ausführen — muss fehlerfrei durchlaufen (`seed ok`), Reflektions-Check unverändert.

- [ ] **Step 4: Commit**

```bash
git add sample_data/oracle_demo.py
git commit -m "feat(demo): reiches Oracle-Demo-DDL-Modul (~37 Tab · 10 Views · ~15 Routinen) [AP-67 Slice 2a]"
```

---

### Task 2: Seeder-Verdrahtung + reicher Integrationstest + README

**Files:**
- Modify: `sample_data/seed_server_demo.py` — Oracle-Zweig nutzt das Modul; alte inline-`_ORACLE_*`-Listen entfernen.
- Modify: `tests/test_oracle_seed_integration.py` — Assertions auf die reiche Menge.
- Modify: `sample_data/server-demo-README.md` — Objekt-Übersicht der reichen Oracle-Demo.

**Interfaces:**
- Consumes: `sample_data/oracle_demo.py` (Task 1: `DROPS/TABLES/DATA/OBJECTS`), `seed_server_demo.seed`, `SqlAlchemyLoader`, `fetch_rows`.

- [ ] **Step 1: Seeder auf das Modul umstellen.** In `sample_data/seed_server_demo.py` die vier inline-`_ORACLE_*`-Listen entfernen und den `oracle`-Zweig auf das Modul umstellen:

```python
            elif name == "oracle":
                from oracle_demo import DROPS, TABLES, DATA, OBJECTS
                for stmt in (DROPS + TABLES + DATA + OBJECTS):
                    conn.execute(text(stmt))
```

(Der `import` steht lokal im Zweig, damit `seed_server_demo.py` ohne `sample_data` auf `sys.path` importierbar bleibt; die Integrationstests fügen `sample_data` bereits zum Pfad hinzu.)

- [ ] **Step 2: Integrationstest auf die reiche Menge erweitern.** In `tests/test_oracle_seed_integration.py::test_oracle_demo_seed_shows_all_categories` die Assertions ergänzen/anpassen (nach dem Seed + `load()`):

```python
    assert len(schema.tables) >= 35
    assert len(schema.views) >= 10
    assert len(schema.routines) >= 15
    kinds = {r.kind for r in schema.routines}
    assert {"function", "procedure", "package"} <= kinds
    assert len(schema.sequences) >= 2
    assert len(schema.materialized_views) >= 2
    assert len(schema.synonyms) >= 2
    # strukturelle Merkmale
    assert any(len(fk.columns) > 1 for t in schema.tables for fk in t.foreign_keys)      # Composite-FK
    assert any(fk.ref_table.upper() == t.name.upper()
               for t in schema.tables for fk in t.foreign_keys)                          # Self-Ref
    assert any(v.routines for v in schema.views)                                         # AP-66·S1
```

Die bestehende Daten-Vorschau-Assertion (v0.64.2, `fetch_rows` auf Tabelle + View) bleibt — ggf. den Tabellennamen auf ein existierendes Objekt der reichen Demo anpassen (z. B. `VirtualMachine`).

- [ ] **Step 3: README aktualisieren.** In `sample_data/server-demo-README.md` den Oracle-Abschnitt um eine kurze Objekt-Übersicht der reichen Demo ergänzen (~37 Tabellen in 5 Subdomänen, 10 Views, ~15 Routinen/Packages, Sequences/Synonyme/Matviews; Hinweis auf die scrollbare Sidebar).

- [ ] **Step 4: Volle Suite (Regress) + Live-Test (Controller).**

Run: `./venv/bin/python -m pytest -q`
Expected: **445 passed, 11 skipped** (Oracle-Test skippt ohne URL).
Controller-Live: `LUCENT_ORACLE_TEST_URL=… ./venv/bin/python -m pytest tests/test_oracle_seed_integration.py` → PASSED.

- [ ] **Step 5: Commit**

```bash
git add sample_data/seed_server_demo.py tests/test_oracle_seed_integration.py sample_data/server-demo-README.md
git commit -m "feat(demo): Seeder auf reiches Oracle-Modul + reicher Integrationstest + README [AP-67 Slice 2a]"
```

---

### Task 3: Release v0.65.0 + Doku

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`); `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`; `roadmap.md` (AP-67 Slice 2a) + Gantt `projekt-roadmap-1.mmd`; `zensical.toml`; `icon-rail.js`; `kennzahlen.md`; Konzept-Status; Site + gh-pages.

**Interfaces:**
- Consumes: fertige, live-verifizierte Änderungen aus Task 1-2.

- [ ] **Step 1: Version bumpen (minor — reiches Demo-Feature)**

```bash
./venv/bin/python sync_version.py --minor   # 0.64.2 → 0.65.0
```

- [ ] **Step 2: Doku nachziehen (am echten Code geprüft).** Changelog EN + DE (reiche Oracle-Demo: ~37 Tabellen/10 Views/~15 Routinen, live verifiziert, eigenes `oracle_demo.py`-Modul); `roadmap.md` AP-67-Bereich um Slice 2a (erledigt v0.65.0) + Detail; Gantt `AP-67 Slice 2a — reiches Oracle-Schema :done, …` + Band-Obergrenze v0.65.0; Konzept-Status um Slice 2a. Kennzahlen frisch erheben:

```bash
git rev-list --count HEAD
./venv/bin/python -m pytest -q | tail -1
```

`zensical.toml`/`icon-rail.js` (v0.65.0, TEST_COUNT bleibt 445), `kennzahlen.md` (Version, Commits, Stand; Statements/Tests praktisch unverändert — Demo liegt in `sample_data/`). Danach per `grep` gegenprüfen.

- [ ] **Step 3: Suite + Site**

Run: `./venv/bin/python -m pytest`
Expected: **445 passed, 11 skipped**.
Danach `./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py`; gerendertes Gantt-SVG + `index.html`-Version gegenprüfen.

- [ ] **Step 4: Commit (Merge/Push/gh-pages nur auf Nutzer-Ansage)**

```bash
git add -A
git commit -m "release: v0.65.0 — AP-67 Slice 2a (reiches Oracle-Demo-Schema)"
```
