"""Build a portable demo CMDB SQLite database for Lucent DB Explorer.

The schema is a small VMware-style datacenter inventory crafted to exercise
every join-path scenario the tool must handle:

* Ambiguous join paths (a "diamond"): a VirtualMachine reaches a Datacenter
  both via its Host and via its Network -- two equally short paths, so the
  deterministic tie-break is observable.
* Composite (multi-column) foreign key: VMPlacement references ResourcePool on
  (ClusterID, PoolKey). v1 joins on only the first column pair -- a documented
  limitation made reproducible here.
* Graph edge cases: a self-referencing FK (Folder.ParentFolderID -> Folder),
  multiple FKs between the same two tables (Replication -> Datastore twice),
  and an isolated table with no FK at all (LicenseKey) that triggers No-Path.
* Realistic data: enough rows that manual click-through yields meaningful
  result rows instead of empty tables.

Uses only the Python standard library (sqlite3), so it runs without the
project venv. Import build() from tests, or run as a script to (re)generate
sample_data/demo_cmdb.db.
"""
import os
import sqlite3

# Table creation order respects foreign-key dependencies (parents first).
_SCHEMA = """
CREATE TABLE Datacenter (
    DatacenterID INTEGER PRIMARY KEY,
    Name         TEXT NOT NULL
);

CREATE TABLE Folder (
    FolderID       INTEGER PRIMARY KEY,
    Name           TEXT NOT NULL,
    ParentFolderID INTEGER REFERENCES Folder(FolderID)   -- self-referencing FK
);

CREATE TABLE OperatingSystem (
    OSID    INTEGER PRIMARY KEY,
    Family  TEXT NOT NULL,
    Version TEXT NOT NULL
);

CREATE TABLE Cluster (
    ClusterID    INTEGER PRIMARY KEY,
    Name         TEXT NOT NULL,
    DatacenterID INTEGER NOT NULL REFERENCES Datacenter(DatacenterID)
);

CREATE TABLE Network (
    NetworkID    INTEGER PRIMARY KEY,
    VLAN         INTEGER NOT NULL,
    DatacenterID INTEGER NOT NULL REFERENCES Datacenter(DatacenterID)
);

CREATE TABLE Host (
    HostID       INTEGER PRIMARY KEY,
    Hostname     TEXT NOT NULL,
    ClusterID    INTEGER NOT NULL REFERENCES Cluster(ClusterID),
    DatacenterID INTEGER NOT NULL REFERENCES Datacenter(DatacenterID)  -- diamond: also reachable via Cluster
);

CREATE TABLE Datastore (
    DatastoreID INTEGER PRIMARY KEY,
    Name        TEXT NOT NULL,
    ClusterID   INTEGER NOT NULL REFERENCES Cluster(ClusterID)
);

CREATE TABLE VirtualMachine (
    VMID      INTEGER PRIMARY KEY,
    Name      TEXT NOT NULL,
    HostID    INTEGER NOT NULL REFERENCES Host(HostID),
    OSID      INTEGER NOT NULL REFERENCES OperatingSystem(OSID),
    NetworkID INTEGER NOT NULL REFERENCES Network(NetworkID),
    FolderID  INTEGER NOT NULL REFERENCES Folder(FolderID)
);

CREATE TABLE VMDisk (
    DiskID      INTEGER PRIMARY KEY,
    VMID        INTEGER NOT NULL REFERENCES VirtualMachine(VMID),
    DatastoreID INTEGER NOT NULL REFERENCES Datastore(DatastoreID),
    SizeGB      INTEGER NOT NULL
);

CREATE TABLE ResourcePool (
    ClusterID INTEGER NOT NULL REFERENCES Cluster(ClusterID),
    PoolKey   TEXT NOT NULL,
    Name      TEXT NOT NULL,
    PRIMARY KEY (ClusterID, PoolKey)
);

CREATE TABLE VMPlacement (
    PlacementID INTEGER PRIMARY KEY,
    VMID        INTEGER NOT NULL REFERENCES VirtualMachine(VMID),
    ClusterID   INTEGER NOT NULL,
    PoolKey     TEXT NOT NULL,
    FOREIGN KEY (ClusterID, PoolKey) REFERENCES ResourcePool(ClusterID, PoolKey)  -- composite FK
);

CREATE TABLE Replication (
    ReplicationID       INTEGER PRIMARY KEY,
    PrimaryDatastoreID  INTEGER NOT NULL REFERENCES Datastore(DatastoreID),
    SecondaryDatastoreID INTEGER NOT NULL REFERENCES Datastore(DatastoreID)  -- two FKs to the same table
);

CREATE TABLE LicenseKey (
    LicenseID INTEGER PRIMARY KEY,
    Product   TEXT NOT NULL,
    KeyValue  TEXT NOT NULL
);
"""

# (table, rows) in insertion order. Each row is a full column tuple.
_DATA = [
    ("Datacenter", [
        (1, "DC-Frankfurt"),
        (2, "DC-Berlin"),
    ]),
    ("Folder", [
        (1, "Datacenters", None),       # root
        (2, "Production", 1),
        (3, "Test", 1),
        (4, "Web-Tier", 2),
    ]),
    ("OperatingSystem", [
        (1, "Windows", "Server 2022"),
        (2, "Windows", "Server 2019"),
        (3, "Ubuntu", "22.04 LTS"),
        (4, "RHEL", "9"),
    ]),
    ("Cluster", [
        (1, "PROD-CL01", 1),
        (2, "PROD-CL02", 1),
        (3, "TEST-CL01", 2),
    ]),
    ("Network", [
        (1, 100, 1),
        (2, 200, 1),
        (3, 300, 2),
        (4, 110, 1),
    ]),
    ("Host", [
        (1, "esxi-01", 1, 1),
        (2, "esxi-02", 1, 1),
        (3, "esxi-03", 2, 1),
        (4, "esxi-04", 2, 1),
        (5, "esxi-05", 3, 2),
        (6, "esxi-06", 3, 2),
    ]),
    ("Datastore", [
        (1, "DS-SSD-01", 1),
        (2, "DS-SSD-02", 2),
        (3, "DS-NL-01", 1),
        (4, "DS-TEST", 3),
    ]),
    ("VirtualMachine", [
        (1, "DC01", 1, 1, 1, 2),
        (2, "WEB01", 1, 3, 1, 4),
        (3, "WEB02", 2, 3, 2, 4),
        (4, "SQL01", 3, 1, 2, 2),
        (5, "APP01", 3, 4, 1, 2),
        (6, "APP02", 4, 4, 4, 2),
        (7, "FILE01", 2, 2, 1, 2),
        (8, "TEST-VM1", 5, 3, 3, 3),
        (9, "TEST-VM2", 6, 1, 3, 3),
        (10, "BACKUP01", 4, 2, 2, 2),
    ]),
    ("VMDisk", [
        (1, 1, 1, 80),
        (2, 1, 3, 500),
        (3, 2, 1, 40),
        (4, 3, 2, 40),
        (5, 4, 2, 200),
        (6, 5, 1, 60),
        (7, 6, 2, 60),
        (8, 7, 3, 1000),
        (9, 8, 4, 40),
        (10, 9, 4, 40),
        (11, 10, 3, 2000),
        (12, 4, 1, 100),
    ]),
    ("ResourcePool", [
        (1, "prod", "Production Pool"),
        (1, "infra", "Infrastructure Pool"),
        (2, "prod", "Production Pool"),
        (3, "test", "Test Pool"),
    ]),
    ("VMPlacement", [
        (1, 1, 1, "infra"),
        (2, 2, 1, "prod"),
        (3, 3, 1, "prod"),
        (4, 4, 2, "prod"),
        (5, 5, 2, "prod"),
        (6, 6, 2, "prod"),
        (7, 7, 1, "infra"),
        (8, 8, 3, "test"),
        (9, 9, 3, "test"),
        (10, 10, 2, "prod"),
    ]),
    ("Replication", [
        (1, 1, 2),
        (2, 3, 4),
    ]),
    ("LicenseKey", [
        (1, "vSphere", "AAAA-BBBB-CCCC-DDDD"),
        (2, "vCenter", "EEEE-FFFF-GGGG-HHHH"),
        (3, "NSX", "IIII-JJJJ-KKKK-LLLL"),
    ]),
]


def build(db_path: str) -> None:
    """Create (or overwrite) a demo CMDB database at db_path.

    Args:
        db_path: Filesystem path for the SQLite file. An existing file at this
            path is removed first so the build is reproducible.
    """
    if os.path.exists(db_path):
        os.remove(db_path)
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        for table, rows in _DATA:
            placeholders = ", ".join(["?"] * len(rows[0]))
            conn.executemany(
                f"INSERT INTO {table} VALUES ({placeholders})", rows
            )
        conn.commit()
    finally:
        conn.close()


def _default_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_cmdb.db")


if __name__ == "__main__":
    target = _default_path()
    build(target)
    print(f"Demo-DB erzeugt: {target}")
