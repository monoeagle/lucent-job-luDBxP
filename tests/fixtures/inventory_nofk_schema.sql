-- Same shape as inventory_schema.sql but WITHOUT declared foreign keys.
-- Column names still follow the convention (NetworkID, OSID, ClusterID match
-- the referenced tables' primary keys), so implied-FK detection can recover
-- the relationships.
CREATE TABLE OperatingSystems (
    OSID INTEGER PRIMARY KEY,
    OS_Family TEXT NOT NULL
);
CREATE TABLE VMwareCluster (
    ClusterID INTEGER PRIMARY KEY,
    ClusterName TEXT NOT NULL
);
CREATE TABLE Networks (
    NetworkID INTEGER PRIMARY KEY,
    VLAN INTEGER NOT NULL
);
CREATE TABLE VirtualMachines (
    VMID INTEGER PRIMARY KEY,
    NetworkID INTEGER NOT NULL,
    OSID INTEGER NOT NULL,
    ClusterID INTEGER NOT NULL
);
