# AP-67·MSSQL-Grundlage — Server-Demo-CMDB + MSSQL-Synonym-Reflektion

**Datum:** 2026-06-30 · **Zielversion:** v0.60.0 (Minor) · **Typ:** Demo-Tooling + kleine Reflektions-Erweiterung

## Zweck

Die mitgelieferte SQLite-Demo kann die DB-Objekt-Kategorien (Procedures/Functions/Trigger/
Sequences/Synonyms/…) nicht zeigen — SQLite hat sie nicht. AP-67 legt eine **Server-Demo-CMDB**
an, die diese Kategorien im Tree sichtbar macht. **MSSQL-first**, weil der Container in dieser
Session bereits läuft (Oracle müsste erst aufgesetzt werden), und so strukturiert, dass das Seed
später auf **Oracle adaptierbar** ist. Nutzerwunsch.

## Code-Befund (verifiziert, gegen den laufenden MSSQL-Container)

- `sample_data/build_demo_db.py` baut die SQLite-Demo (stdlib `sqlite3`, 13 Tabellen). Reflektiert
  0 Sequences/Procedures/Functions/Synonyms (SQLite kann sie nicht).
- MSSQL reflektiert **heute schon**: Tabellen, Views, **Trigger** (Trigger-FF), **Procedures + Functions**
  (S3), und **Sequences** (`insp.get_sequence_names()` liefert sie — **empirisch bestätigt**; die
  Projekt-Doku „MSSQL-Sequences = leer" ist falsch und wird mitkorrigiert).
- **Synonyms reflektieren auf MSSQL noch nicht:** `_reflect_synonyms` ist Oracle-only gegated, obwohl
  MSSQL `sys.synonyms` hat. `SELECT name, base_object_name FROM sys.synonyms` liefert z. B.
  `('_syn_x', '[dbo].[_t_x]')` (empirisch bestätigt).
- Oracle ist verbindbar (AP-53), aber nicht als portable Datei bündelbar.

## A. Reflektions-Erweiterung — `core/loaders/sqlalchemy_loader.py`

`_reflect_synonyms` bekommt einen **MSSQL-Zweig** neben dem bestehenden Oracle-Zweig (dialekt-gegated,
resilient `except SQLAlchemyError → ()`):
```sql
SELECT name, base_object_name FROM sys.synonyms
WHERE SCHEMA_NAME(schema_id) = :s ORDER BY name
```
→ `Synonym(name, target)`, wobei `target` die `[ ]`-Klammern von `base_object_name` entfernt
(`[dbo].[_t_x]` → `dbo._t_x`). Oracle-Zweig unverändert; SQLite/PG/sonst → `()`. `:s` = `schema or "dbo"`.

## B. Server-Demo-Seeder — `sample_data/seed_server_demo.py` (neu)

SQLAlchemy-basiert (kein stdlib-sqlite3 wie `build_demo_db.py`), läuft gegen jede URL. **Idempotent**
(erst drop-if-exists, dann create). Struktur:

1. **Geteilte kompakte CMDB** (5 Tabellen, FK-Kette + Join-Pfad):
   - `OperatingSystem(OSID PK, Name)`
   - `Datacenter(DatacenterID PK, Name)`
   - `Cluster(ClusterID PK, DatacenterID FK→Datacenter, Name)`
   - `Host(HostID PK, ClusterID FK→Cluster, Hostname)`
   - `VirtualMachine(VMID PK, HostID FK→Host, OSID FK→OperatingSystem, Name)`
   - Join-Pfad: VM→Host→Cluster→Datacenter und VM→OperatingSystem. Ein paar Demo-Zeilen.
2. **Dialekt-spezifischer Objekt-DDL-Block.** Dispatch auf `engine.dialect.name`; **MSSQL jetzt
   implementiert**, Oracle als dokumentierter Folge-Block (Stub mit Hinweis):
   - **Sequence** `demo_vm_seq`
   - **Scalar Function** `dbo.fn_vm_label(@id)` (liest `VirtualMachine`)
   - **Procedure** `dbo.usp_vm_count`
   - **Trigger** `trg_vm_audit` (AFTER INSERT ON VirtualMachine)
   - **View** `vw_vm_labeled` die `dbo.fn_vm_label(...)` aufruft → macht **AP-66·S1** sichtbar
     (viewdeps matcht `fn_vm_label` gegen die reflektierte Function)
   - **Synonym** `syn_vm` FOR `dbo.VirtualMachine`
3. Aufruf: `python sample_data/seed_server_demo.py <SQLAlchemy-URL>` (oder `LUCENT_DEMO_SEED_URL`).
   Read-only-Invariante des **Tools** unberührt — der Seeder ist ein einmaliges Setup-Skript
   außerhalb der App.

## C. Verifikation + Bring-up

- **Skip-guarded Integrationstest** (`tests/test_mssql_integration.py` erweitern, `LUCENT_MSSQL_TEST_URL`):
  Seed ausführen → `SqlAlchemyLoader(url).load()` → assert **alle 7 Kategorien** befüllt
  (tables, views, triggers, routines[procedure+function], sequences, synonyms) und dass `vw_vm_labeled.routines`
  die Function enthält (AP-66·S1). Teardown droppt alles. **Gegen den laufenden Container real ausführbar.**
- **README** `sample_data/server-demo-README.md`: podman-MSSQL-Container-Start, Seed-Befehl,
  Connection-String, plus „Oracle-Adaption"-Abschnitt (gleiche Tabellen, Oracle-Objekt-DDL).

## D. App-Verbindung

Connection-String **dokumentiert** (Nutzer verbindet manuell). Gespeicherte „MSSQL-Demo"-Verbindung
bewusst zurückgestellt (YAGNI).

## Release (voller SDD-Zyklus)

`sync_version.py --minor` → **v0.60.0**. Doku am Code geprüft: Changelog EN + DE-Mirror, Roadmap-Prosa
+ Diagramme (AP-67·MSSQL-Grundlage erledigt, enumeriert; AP-67·Oracle-Adaption offen), CLAUDE.md
(Synonyms jetzt Oracle **+ MSSQL**; Sequence-„MSSQL leer"-Aussage korrigieren), `datenmodell.md`/
`architektur.md` falls Synonym-Reflektion dort beschrieben, Kennzahlen frisch (inkl. Per-Modul-Balken),
Site, gh-pages. **AP-67-Konzept-Doc** (`docs/concepts/2026-06-30-oracle-demo-cmdb.md`) um die
MSSQL-first-Grundlage ergänzen.

## Verifikation

- `./venv/bin/python -m pytest` grün (skip-guarded Test skippt ohne URL; mit `LUCENT_MSSQL_TEST_URL`
  gegen den Container grün).
- Browser-Smoke: nach Seed + Verbinden zeigt der Tree alle 7 Kategorien; `vw_vm_labeled` zeigt
  „Verwendet Routinen: fn_vm_label".

## Nicht-Scope

- **Oracle-Seed-Implementierung** — nur Struktur/Stub + Doku; echte Oracle-DDL = Folgescheibe
  (braucht Oracle-Instanz).
- **Materialized Views / Packages** auf MSSQL — gibt es dort nicht (Oracle/PG).
- **Gebündelte gespeicherte Verbindung** — dokumentiert, nicht eingebaut.
- Read-only-Invariante des Tools unberührt (Seeder ist externes Setup).

## Risiken

- **MSSQL-DDL-Syntax** muss gegen den Container verifiziert werden (CREATE FUNCTION/PROCEDURE/TRIGGER
  als eigene Batches; `CREATE VIEW`/`CREATE FUNCTION` müssen erste Anweisung im Batch sein → je
  Statement ein eigener `conn.execute(text(...))`).
- **Synonym-Target-Format** (`[dbo].[VirtualMachine]`) — Klammer-Strippen ist best-effort; reicht für
  die Anzeige.
