# Design — AP-67 Slice 2a: Reiches Oracle-Demo-Schema

**Datum:** 2026-07-01
**Kontext:** LucentTools DB Explorer. Fortsetzung von AP-67 (Server-Demo-CMDB). Slice 1 (v0.64.0)
lieferte einen **kompakten 5-Tabellen**-Oracle-Seed. Diese Scheibe baut ihn zu einer **großen,
komplexen** CMDB aus, damit komplexe Join-Pfade, Subsetting und der Analyzer an realistischem
Material erkundbar sind — und damit die Folge-Scheibe **2b (Offline-Fixture-Vorschau)** einen
reichen Snapshot generieren kann.

> **Teil der erweiterten AP-67-Initiative:** Slice 2a (hier) = reiches Oracle-Schema. Slice 2b
> (eigene Spec danach) = Offline-Fixture-Vorschau (`Schema.to_dict/from_dict`, Snapshot aus der
> Live-Reflektion, Fixture-Loader + Load-Dispatcher, „Oracle-Vorschau"-Verbindung, No-Exec). 2a
> ist die Datenquelle für 2b.

## Scope

Nur Demo-**Daten**: die Oracle-DDL/PL-SQL massiv ausbauen. **Kein Tool-/Reflektions-Code** — alle
Reflektionspfade existieren. Das Seed bleibt ein **externes Setup-Skript**, das das read-only-Werkzeug
nie ausführt (Read-only-Invariante unberührt). **Live gegen Oracle 21c XE verifiziert.**

Der MSSQL-Zweig bleibt kompakt (unverändert). Die Sidebar-Objektliste ist bereits scrollbar
(`.objects { overflow-y: auto }`, live bestätigt) — kein UI-Change nötig; TOOLS-Anpinnen ist
bewusst **nicht** Teil dieser Scheibe.

## Datei-Struktur (Isolation)

Die große Oracle-DDL wandert aus `seed_server_demo.py` in ein eigenes Modul
**`sample_data/oracle_demo.py`** mit vier Listen: `DROPS`, `TABLES`, `DATA`, `OBJECTS` (Statement =
ein String, wie die `_MSSQL_*`-Listen). `seed_server_demo.py` importiert es; sein `oracle`-Zweig
führt `DROPS + TABLES + DATA + OBJECTS` in Reihenfolge aus. Das hält den Seeder klein und die
umfangreiche DDL fokussiert.

## Schema — ~35 Tabellen in 5 Subdomänen

VMware-artige Datacenter-CMDB, erweitert:

- **Referenz:** `OperatingSystem`, `VMTemplate`, `Vendor`, `Product`, `Environment`
- **Compute:** `Datacenter`, `Folder` *(Self-Ref `ParentFolderID`)*, `VMCluster` *(`CLUSTER` reserviert)*,
  `Host`, `ResourcePool` *(Composite-Key `ClusterID`,`PoolKey`)*, `VirtualMachine`, `VMDisk`,
  `VMSnapshot` *(Self-Ref `ParentSnapshotID`)*, `VMPlacement` *(Composite-FK → `ResourcePool`)*,
  `VMNetworkInterface`
- **Storage:** `StorageArray`, `StoragePool`, `Datastore`, `LUN`, `Volume`, `DiskBackingFile`
- **Network:** `Network`, `VLAN`, `VirtualSwitch`, `PortGroup`, `IPPool`, `IPAddress`
- **Backup/DR:** `BackupPolicy`, `BackupJob`, `RestorePoint`, `Replication` *(zwei FKs: Quell-VM +
  Ziel-Datacenter → alternative Join-Routen)*
- **Lizenz/Audit:** `LicenseKey`, `LicenseAssignment`, `AuditLog` *(No-Path-Standalone)*, `Tag`,
  `TagAssignment`

**Bewusste FK-Graph-Merkmale** (für komplexe Pfade): mehrere Diamanten (z. B. VM→Host→VMCluster→Datacenter
**und** VM→ResourcePool→VMCluster), ein **Composite-FK** (`VMPlacement`), zwei **Self-Refs**
(`Folder`, `VMSnapshot`), **alternative Routen** (`Replication`: zwei FKs), eine **No-Path-Tabelle**
(`AuditLog`), und Zwei-Wege-FKs zwischen denselben Tabellen (getrennte alternative Routen).

## Views (~10)

Filter, Aggregate, Multi-Join — davon **mehrere funktions-aufrufend** (→ AP-66·S1 ƒ-Badge), z. B.:
`vw_vm_labeled` (fn_vm_label), `vw_host_capacity` (fn_host_capacity, Multi-Join), `vw_datastore_usage`
(Aggregat), `vw_license_utilization` (fn + Aggregat), `vw_orphaned_vms` (Anti-Join),
`vw_vm_full_path` (fn_folder_path), `vw_windows_vms` (Filter), `vw_cluster_hostcount` (Aggregat),
`vw_backup_status` (Join + fn), `vw_network_topology` (Multi-Join).

## Routinen (~15) + weitere Objekte

- **~6 Functions:** `fn_vm_label`, `fn_host_capacity`, `fn_folder_path`, `fn_datastore_free`,
  `fn_license_seats_used`, `fn_vm_power_state`.
- **~3 Procedures:** `usp_vm_count`, `usp_rebalance_report`, `usp_cleanup_snapshots`.
- **3–4 Packages** (je Spec+Body mit Functions+Procedures): `pkg_capacity`, `pkg_inventory`,
  `pkg_licensing`, `pkg_backup`.
- **3 Sequences:** `seq_vm_id`, `seq_ticket`, `seq_audit`.
- **3 Synonyme:** `syn_vm`→VirtualMachine, `syn_host`→Host, `syn_ds`→Datastore.
- **2 Materialized Views:** `mv_cluster_capacity`, `mv_vm_per_datastore`.

Damit sind alle Oracle-Sidebar-Kategorien reich belegt (Tabellen, Views, Sequences, Materialized
Views, Trigger, Procedures, Functions, Packages, Synonyme).

## Daten

Referentiell konsistente Beispielzeilen — mehrere je Tabelle (Eltern vor Kindern), sodass
Daten-Vorschau, Subsetting-Hülle und der Analyzer sinnvolle Ergebnisse zeigen. Einzeilige INSERTs
(Oracle kennt kein Multi-Row-`VALUES`).

## Oracle-Besonderheiten (wie Slice 1)

`NUMBER`/`VARCHAR2`; per-Objekt-Drop `BEGIN EXECUTE IMMEDIATE 'DROP …'; EXCEPTION WHEN OTHERS THEN
NULL; END;` (abhängige zuerst); `CREATE OR REPLACE` für PL/SQL-Objekte; PL/SQL-Blöcke als je ein
`execute()` ohne `/`; reservierte Wörter meiden; kein `dbo.`-Präfix (Schema des Connect-Users
`demo`); AUTOCOMMIT.

## Test

Der skip-guardete `tests/test_oracle_seed_integration.py` prüft die **reiche** Menge: Zähler
(≥35 Tabellen, ≥10 Views, ≥15 Routinen inkl. je ≥1 function/procedure/package, ≥2 Sequences/
Synonyme/Matviews), repräsentative Objekte namentlich, mindestens ein **Composite-FK**, mindestens
eine **Self-Ref**, der **AP-66·S1** View→Function-Link, und die Daten-Vorschau (`fetch_rows`) für
eine Tabelle + eine View (Regressions-Guard aus v0.64.2). Ohne `LUCENT_ORACLE_TEST_URL` → skip.

## Verifikation

Live gegen den Container `oracle-luDBxP`: Seed ausführen (idempotent, zweiter Lauf fehlerfrei), in
der App verbinden, im (scrollbaren) Tree alle ~35 Tabellen + 10 Views + Routinen/Kategorien
sichten; der skip-guardete Test läuft mit gesetzter URL grün. Die DDL wird **iterativ live
entwickelt** (Dialekt-Fallen sofort gefangen).

## Randbedingungen

- Read-only-Invariante unberührt; Deutsch für neue Doku.
- Kein Auto-Provisioning ohne Nutzer-Opt-in (Container-Bring-up bleibt dokumentierter Schritt).
- `sample_data/server-demo-README.md` um die reiche Oracle-Demo aktualisieren (Objekt-Übersicht).

## Betroffene Dateien

- `sample_data/oracle_demo.py` **(neu)** — `DROPS`/`TABLES`/`DATA`/`OBJECTS`.
- `sample_data/seed_server_demo.py` — Oracle-Zweig importiert + führt die Modul-Listen aus (die
  bisherigen inline-`_ORACLE_*`-Listen entfallen/ziehen ins Modul um).
- `tests/test_oracle_seed_integration.py` — Assertions auf die reiche Menge.
- `sample_data/server-demo-README.md` — Objekt-Übersicht der reichen Oracle-Demo.
