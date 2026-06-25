# Demo-Datenbank (portable Test-CMDB)

Eine eigenständige SQLite-Datenbank mit einem kleinen VMware-/Rechenzentrum-Inventar.
Sie ist absichtlich so gebaut, dass sie **alle Join-Pfad-Fälle** abdeckt, die das Tool
beherrschen muss — zum manuellen Durchklicken im Browser und für die automatischen
Integrationstests (`tests/test_demo_db_cases.py`).

## Dateien

| Datei | Zweck |
|---|---|
| `build_demo_db.py` | Generator (reine stdlib `sqlite3`, läuft ohne venv). Erzeugt beide DBs reproduzierbar. |
| `demo_cmdb.db` | Die fertige Datenbank (mit deklarierten Foreign Keys) — sofort nutzbar. |
| `demo_cmdb_nofk.db` | Gleiche Tabellen/Daten, aber **ohne** deklarierte FKs — zum Ausprobieren der **impliziten Foreign Keys**. |

## Neu erzeugen

```bash
python sample_data/build_demo_db.py
# -> sample_data/demo_cmdb.db
```

## Im Tool verwenden

Tool starten (`bash run.sh`), im Browser öffnen und als **Connection-URL** eintragen:

```
sqlite:////ABSOLUTER/PFAD/zum/repo/sample_data/demo_cmdb.db
```

(Vier Schrägstriche nach `sqlite:` = absoluter Pfad.)

## Abgedeckte Fälle und Beispiel-Eingaben

### 1. Mehrdeutige Join-Pfade (Diamant)
`VirtualMachine` erreicht `Datacenter` sowohl über `Host` als auch über `Network` —
**zwei gleich kurze Pfade**. Das Tool zeigt beide als Alternativen, der erste ist durch
den deterministischen Tie-Break festgelegt.

- **Start:** `VirtualMachine.Name` · **Ziel:** `Datacenter.Name`
- Erwartung: u. a. `VirtualMachine → Host → Datacenter` und `VirtualMachine → Network → Datacenter`.

### 2. Zusammengesetzter (mehrspaltiger) Foreign Key
`VMPlacement` referenziert `ResourcePool` über **(ClusterID, PoolKey)**. In v1 wird der
JOIN nur über **das erste Spaltenpaar** (`ClusterID`) gebildet — `PoolKey` fehlt. Das ist
die dokumentierte v1-Einschränkung, hier sichtbar gemacht.

- **Start:** `VirtualMachine.Name` · **Ziel:** `ResourcePool.Name`
- Erwartung: `JOIN ResourcePool ON VMPlacement.ClusterID = ResourcePool.ClusterID` (ohne `AND PoolKey`).

### 3. Graph-Sonderfälle
- **Mehrere FKs zwischen zwei Tabellen:** `Replication` zeigt mit zwei FKs auf `Datastore`
  (`PrimaryDatastoreID`, `SecondaryDatastoreID`).
- **Selbstreferenz:** `Folder.ParentFolderID → Folder` (Ordnerhierarchie).
- **Isolierte Tabelle:** `LicenseKey` hat keinen FK. Ein Pfad von/zu ihr löst die
  „Keine Join-Verbindung gefunden"-Meldung (HTTP 400) aus.

- **Beispiel No-Path:** Start `LicenseKey.Product` · Ziel `Datacenter.Name`.

### 3b. Implizite Foreign Keys (`demo_cmdb_nofk.db`)
In `demo_cmdb_nofk.db` sind **keine** FKs deklariert — die Beziehungen stecken
nur in den Spaltennamen (`Host.ClusterID` passt zur PK `Cluster.ClusterID`).

- Connection-URL auf `…/sample_data/demo_cmdb_nofk.db` setzen, **„Implizite
  (geratene) Beziehungen einbeziehen"** ankreuzen, „Schema laden".
- Ohne Häkchen: keine Kanten, keine Pfade. Mit Häkchen: die geratenen
  Beziehungen erscheinen **gestrichelt** im Graph und Join-Pfade werden möglich.
- Beispiel: Start `Network.VLAN` · Ziel `Datacenter.Name`.

### 4. Realistische Daten + Filter
Genug Zeilen (Cluster, Hosts, VMs, Netze, Betriebssysteme, Datastores …), damit Abfragen
echte Ergebnisse hätten. Filter weben Zwischentabellen ein.

- **Start:** `Network.VLAN` · **Ziel:** `Cluster.Name` · **Filter:** `OperatingSystem.Family = 'Windows'`

## Schema-Überblick

```
Datacenter ─< Cluster ─< Host ─< VirtualMachine ─< VMDisk >─ Datastore >─ Replication
     │           │        │            │  │  │                  │
     ├─< Network ┘        │            │  │  └─ Folder (self-ref)│
     │   (diamond) ───────┘            │  └─ OperatingSystem     │
     └─ Cluster ─< ResourcePool (PK ClusterID,PoolKey)           │
                       ^                │                         │
                       └── VMPlacement (composite FK) ──< VirtualMachine
LicenseKey   (isoliert, keine Beziehung)
```
