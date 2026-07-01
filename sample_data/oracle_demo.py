"""Rich Oracle server-demo CMDB (AP-67 Slice 2a).

A large VMware-style datacenter CMDB (~37 tables across 5 subdomains, 10 views,
~15 routines incl. packages, plus sequences / synonyms / materialized views) so
complex join paths, subsetting and the analyzer have realistic material — and so
the offline-fixture preview (Slice 2b) can snapshot a rich schema.

Externally seeded via ``seed_server_demo.py``; the read-only tool never runs it.
Live-verified against Oracle 21c XE. Oracle specifics: NUMBER/VARCHAR2, per-object
DROP … CASCADE CONSTRAINTS with error swallowed, tables created without inline FKs
then wired via ALTER (avoids create-order coupling), single-row INSERTs, PL/SQL
objects via CREATE OR REPLACE with no trailing '/', reserved words avoided
(CLUSTER → VMCluster). Idempotent.
"""

# ── Drops — every table with CASCADE CONSTRAINTS (order-independent), then the
#    non-table objects. Errors (object absent) are swallowed. ─────────────────
_TABLE_NAMES = [
    "OperatingSystem", "VMTemplate", "Vendor", "Product", "Environment",
    "Datacenter", "Folder", "VMCluster", "Host", "ResourcePool",
    "VirtualMachine", "VMDisk", "VMSnapshot", "VMPlacement", "VMNetworkInterface",
    "StorageArray", "StoragePool", "Datastore", "LUN", "Volume", "DiskBackingFile",
    "Network", "VLAN", "VirtualSwitch", "PortGroup", "IPPool", "IPAddress",
    "BackupPolicy", "BackupJob", "RestorePoint", "Replication",
    "LicenseKey", "LicenseAssignment", "AuditLog", "Tag", "TagAssignment",
    "Server",
]
_OTHER_DROPS = [
    ("MATERIALIZED VIEW", "mv_cluster_capacity"),
    ("MATERIALIZED VIEW", "mv_vm_per_datastore"),
    ("VIEW", "vw_vm_labeled"), ("VIEW", "vw_host_capacity"),
    ("VIEW", "vw_datastore_usage"), ("VIEW", "vw_license_utilization"),
    ("VIEW", "vw_orphaned_vms"), ("VIEW", "vw_vm_full_path"),
    ("VIEW", "vw_windows_vms"), ("VIEW", "vw_cluster_hostcount"),
    ("VIEW", "vw_backup_status"), ("VIEW", "vw_network_topology"),
    ("SYNONYM", "syn_vm"), ("SYNONYM", "syn_host"), ("SYNONYM", "syn_ds"),
    ("PACKAGE", "pkg_capacity"), ("PACKAGE", "pkg_inventory"),
    ("PACKAGE", "pkg_licensing"), ("PACKAGE", "pkg_backup"),
    ("FUNCTION", "fn_vm_label"), ("FUNCTION", "fn_host_capacity"),
    ("FUNCTION", "fn_folder_path"), ("FUNCTION", "fn_datastore_free"),
    ("FUNCTION", "fn_license_seats_used"), ("FUNCTION", "fn_vm_power_state"),
    ("PROCEDURE", "usp_vm_count"), ("PROCEDURE", "usp_rebalance_report"),
    ("PROCEDURE", "usp_cleanup_snapshots"),
    ("TRIGGER", "trg_vm_audit"),
    ("SEQUENCE", "seq_vm_id"), ("SEQUENCE", "seq_ticket"), ("SEQUENCE", "seq_audit"),
    # Slice-1 (compact demo) leftovers — dropped so the rich demo is clean.
    ("SEQUENCE", "demo_vm_seq"), ("MATERIALIZED VIEW", "mv_vm_per_host"),
    ("PACKAGE", "pkg_vm"), ("PROCEDURE", "usp_vm_count"),
    ("FUNCTION", "fn_cluster_vm_count"), ("FUNCTION", "fn_datastore_capacity"),
    ("PROCEDURE", "usp_tag_count"),
]


def _drop(kind, name):
    stmt = f"DROP {kind} {name}"
    if kind == "TABLE":
        stmt += " CASCADE CONSTRAINTS"
    return (f"BEGIN EXECUTE IMMEDIATE '{stmt}'; "
            f"EXCEPTION WHEN OTHERS THEN NULL; END;")


DROPS = (
    [_drop(k, n) for (k, n) in _OTHER_DROPS]
    + [_drop("TABLE", t) for t in _TABLE_NAMES]
)

# ── Tables: CREATE (columns + PK, no inline FK) first, then ALTER … ADD FK. ──
_CREATE = [
    # Reference
    "CREATE TABLE OperatingSystem (OSID NUMBER PRIMARY KEY, OSName VARCHAR2(80), Family VARCHAR2(40))",
    "CREATE TABLE VMTemplate (TemplateID NUMBER PRIMARY KEY, TemplateName VARCHAR2(80), OSID NUMBER)",
    "CREATE TABLE Vendor (VendorID NUMBER PRIMARY KEY, VendorName VARCHAR2(80))",
    "CREATE TABLE Product (ProductID NUMBER PRIMARY KEY, ProductName VARCHAR2(80), VendorID NUMBER)",
    "CREATE TABLE Environment (EnvID NUMBER PRIMARY KEY, EnvName VARCHAR2(40))",
    # Compute
    "CREATE TABLE Datacenter (DatacenterID NUMBER PRIMARY KEY, DCName VARCHAR2(80), Region VARCHAR2(40))",
    "CREATE TABLE Folder (FolderID NUMBER PRIMARY KEY, FolderName VARCHAR2(80), ParentFolderID NUMBER)",
    "CREATE TABLE VMCluster (ClusterID NUMBER PRIMARY KEY, ClusterName VARCHAR2(80), DatacenterID NUMBER)",
    "CREATE TABLE Host (HostID NUMBER PRIMARY KEY, Hostname VARCHAR2(80), ClusterID NUMBER, "
    "CpuCores NUMBER, MemGB NUMBER)",
    "CREATE TABLE ResourcePool (ClusterID NUMBER, PoolKey VARCHAR2(40), PoolName VARCHAR2(80), "
    "CpuShares NUMBER, CONSTRAINT pk_respool PRIMARY KEY (ClusterID, PoolKey))",
    "CREATE TABLE VirtualMachine (VMID NUMBER PRIMARY KEY, VMName VARCHAR2(80), HostID NUMBER, "
    "OSID NUMBER, TemplateID NUMBER, FolderID NUMBER, EnvID NUMBER, PowerState VARCHAR2(20), VCpu NUMBER)",
    "CREATE TABLE VMDisk (DiskID NUMBER PRIMARY KEY, VMID NUMBER, DatastoreID NUMBER, SizeGB NUMBER)",
    "CREATE TABLE VMSnapshot (SnapshotID NUMBER PRIMARY KEY, VMID NUMBER, ParentSnapshotID NUMBER, "
    "SnapName VARCHAR2(80))",
    "CREATE TABLE VMPlacement (PlacementID NUMBER PRIMARY KEY, VMID NUMBER, ClusterID NUMBER, PoolKey VARCHAR2(40))",
    "CREATE TABLE VMNetworkInterface (NicID NUMBER PRIMARY KEY, VMID NUMBER, PortGroupID NUMBER, MacAddr VARCHAR2(40))",
    # Storage
    "CREATE TABLE StorageArray (ArrayID NUMBER PRIMARY KEY, ArrayName VARCHAR2(80), VendorID NUMBER)",
    "CREATE TABLE StoragePool (PoolID NUMBER PRIMARY KEY, PoolName VARCHAR2(80), ArrayID NUMBER)",
    "CREATE TABLE Datastore (DatastoreID NUMBER PRIMARY KEY, DSName VARCHAR2(80), PoolID NUMBER, CapacityGB NUMBER)",
    "CREATE TABLE LUN (LunID NUMBER PRIMARY KEY, LunNumber NUMBER, ArrayID NUMBER, SizeGB NUMBER)",
    "CREATE TABLE Volume (VolumeID NUMBER PRIMARY KEY, VolName VARCHAR2(80), PoolID NUMBER, SizeGB NUMBER)",
    "CREATE TABLE DiskBackingFile (BackingID NUMBER PRIMARY KEY, DatastoreID NUMBER, DiskID NUMBER, FilePath VARCHAR2(200))",
    # Network
    "CREATE TABLE Network (NetworkID NUMBER PRIMARY KEY, NetName VARCHAR2(80), DatacenterID NUMBER)",
    "CREATE TABLE VLAN (VlanID NUMBER PRIMARY KEY, VlanTag NUMBER, NetworkID NUMBER)",
    "CREATE TABLE VirtualSwitch (SwitchID NUMBER PRIMARY KEY, SwitchName VARCHAR2(80), HostID NUMBER)",
    "CREATE TABLE PortGroup (PortGroupID NUMBER PRIMARY KEY, PGName VARCHAR2(80), SwitchID NUMBER, VlanID NUMBER)",
    "CREATE TABLE IPPool (PoolID NUMBER PRIMARY KEY, PoolCidr VARCHAR2(40), NetworkID NUMBER)",
    "CREATE TABLE IPAddress (IPID NUMBER PRIMARY KEY, Addr VARCHAR2(40), PoolID NUMBER, NicID NUMBER)",
    # Backup / DR
    "CREATE TABLE BackupPolicy (PolicyID NUMBER PRIMARY KEY, PolicyName VARCHAR2(80), RetentionDays NUMBER)",
    "CREATE TABLE BackupJob (JobID NUMBER PRIMARY KEY, PolicyID NUMBER, VMID NUMBER, JobStatus VARCHAR2(20))",
    "CREATE TABLE RestorePoint (RestoreID NUMBER PRIMARY KEY, JobID NUMBER, PointLabel VARCHAR2(80))",
    "CREATE TABLE Replication (ReplID NUMBER PRIMARY KEY, SourceVMID NUMBER, TargetDatacenterID NUMBER, ReplState VARCHAR2(20))",
    # License / Audit
    "CREATE TABLE LicenseKey (LicenseID NUMBER PRIMARY KEY, LicKey VARCHAR2(80), ProductID NUMBER, Seats NUMBER)",
    "CREATE TABLE LicenseAssignment (AssignID NUMBER PRIMARY KEY, LicenseID NUMBER, HostID NUMBER)",
    "CREATE TABLE AuditLog (AuditID NUMBER PRIMARY KEY, Actor VARCHAR2(80), Action VARCHAR2(80), LoggedAt VARCHAR2(40))",
    "CREATE TABLE Tag (TagID NUMBER PRIMARY KEY, TagName VARCHAR2(80))",
    "CREATE TABLE TagAssignment (TagAssignID NUMBER PRIMARY KEY, TagID NUMBER, VMID NUMBER)",
    "CREATE TABLE Server (ServerID NUMBER PRIMARY KEY, ServerName VARCHAR2(80), HostID NUMBER)",
]
_FKS = [
    ("VMTemplate", "fk_tmpl_os", "OSID", "OperatingSystem", "OSID"),
    ("Product", "fk_prod_vendor", "VendorID", "Vendor", "VendorID"),
    ("Folder", "fk_folder_parent", "ParentFolderID", "Folder", "FolderID"),
    ("VMCluster", "fk_cluster_dc", "DatacenterID", "Datacenter", "DatacenterID"),
    ("Host", "fk_host_cluster", "ClusterID", "VMCluster", "ClusterID"),
    ("ResourcePool", "fk_pool_cluster", "ClusterID", "VMCluster", "ClusterID"),
    ("VirtualMachine", "fk_vm_host", "HostID", "Host", "HostID"),
    ("VirtualMachine", "fk_vm_os", "OSID", "OperatingSystem", "OSID"),
    ("VirtualMachine", "fk_vm_tmpl", "TemplateID", "VMTemplate", "TemplateID"),
    ("VirtualMachine", "fk_vm_folder", "FolderID", "Folder", "FolderID"),
    ("VirtualMachine", "fk_vm_env", "EnvID", "Environment", "EnvID"),
    ("VMDisk", "fk_disk_vm", "VMID", "VirtualMachine", "VMID"),
    ("VMDisk", "fk_disk_ds", "DatastoreID", "Datastore", "DatastoreID"),
    ("VMSnapshot", "fk_snap_vm", "VMID", "VirtualMachine", "VMID"),
    ("VMSnapshot", "fk_snap_parent", "ParentSnapshotID", "VMSnapshot", "SnapshotID"),
    ("VMPlacement", "fk_place_vm", "VMID", "VirtualMachine", "VMID"),
    ("VMNetworkInterface", "fk_nic_vm", "VMID", "VirtualMachine", "VMID"),
    ("VMNetworkInterface", "fk_nic_pg", "PortGroupID", "PortGroup", "PortGroupID"),
    ("StorageArray", "fk_array_vendor", "VendorID", "Vendor", "VendorID"),
    ("StoragePool", "fk_spool_array", "ArrayID", "StorageArray", "ArrayID"),
    ("Datastore", "fk_ds_pool", "PoolID", "StoragePool", "PoolID"),
    ("LUN", "fk_lun_array", "ArrayID", "StorageArray", "ArrayID"),
    ("Volume", "fk_vol_pool", "PoolID", "StoragePool", "PoolID"),
    ("DiskBackingFile", "fk_bf_ds", "DatastoreID", "Datastore", "DatastoreID"),
    ("DiskBackingFile", "fk_bf_disk", "DiskID", "VMDisk", "DiskID"),
    ("Network", "fk_net_dc", "DatacenterID", "Datacenter", "DatacenterID"),
    ("VLAN", "fk_vlan_net", "NetworkID", "Network", "NetworkID"),
    ("VirtualSwitch", "fk_vsw_host", "HostID", "Host", "HostID"),
    ("PortGroup", "fk_pg_switch", "SwitchID", "VirtualSwitch", "SwitchID"),
    ("PortGroup", "fk_pg_vlan", "VlanID", "VLAN", "VlanID"),
    ("IPPool", "fk_ippool_net", "NetworkID", "Network", "NetworkID"),
    ("IPAddress", "fk_ip_pool", "PoolID", "IPPool", "PoolID"),
    ("IPAddress", "fk_ip_nic", "NicID", "VMNetworkInterface", "NicID"),
    ("BackupJob", "fk_job_policy", "PolicyID", "BackupPolicy", "PolicyID"),
    ("BackupJob", "fk_job_vm", "VMID", "VirtualMachine", "VMID"),
    ("RestorePoint", "fk_rp_job", "JobID", "BackupJob", "JobID"),
    ("Replication", "fk_repl_vm", "SourceVMID", "VirtualMachine", "VMID"),
    ("Replication", "fk_repl_dc", "TargetDatacenterID", "Datacenter", "DatacenterID"),
    ("LicenseKey", "fk_lic_prod", "ProductID", "Product", "ProductID"),
    ("LicenseAssignment", "fk_la_lic", "LicenseID", "LicenseKey", "LicenseID"),
    ("LicenseAssignment", "fk_la_host", "HostID", "Host", "HostID"),
    ("TagAssignment", "fk_ta_tag", "TagID", "Tag", "TagID"),
    ("TagAssignment", "fk_ta_vm", "VMID", "VirtualMachine", "VMID"),
    ("Server", "fk_server_host", "HostID", "Host", "HostID"),
]
# Composite FK (VMPlacement → ResourcePool) — added explicitly (two columns).
_COMPOSITE_FK = (
    "ALTER TABLE VMPlacement ADD CONSTRAINT fk_place_pool "
    "FOREIGN KEY (ClusterID, PoolKey) REFERENCES ResourcePool (ClusterID, PoolKey)"
)
TABLES = (
    _CREATE
    + [f"ALTER TABLE {t} ADD CONSTRAINT {c} FOREIGN KEY ({col}) REFERENCES {rt} ({rc})"
       for (t, c, col, rt, rc) in _FKS]
    + [_COMPOSITE_FK]
)

# ── Data — parent-first, single-row INSERTs (Oracle rejects multi-row VALUES). ─
DATA = [
    "INSERT INTO OperatingSystem VALUES (1, 'Windows Server 2022', 'Windows')",
    "INSERT INTO OperatingSystem VALUES (2, 'Ubuntu 24.04', 'Linux')",
    "INSERT INTO OperatingSystem VALUES (3, 'RHEL 9', 'Linux')",
    "INSERT INTO Vendor VALUES (1, 'Acme Storage')",
    "INSERT INTO Vendor VALUES (2, 'Globex Networks')",
    "INSERT INTO Product VALUES (1, 'vSphere', 1)",
    "INSERT INTO Product VALUES (2, 'BackupSuite', 2)",
    "INSERT INTO VMTemplate VALUES (1, 'Win2022-Base', 1)",
    "INSERT INTO VMTemplate VALUES (2, 'Ubuntu-Base', 2)",
    "INSERT INTO Environment VALUES (1, 'Production')",
    "INSERT INTO Environment VALUES (2, 'Test')",
    "INSERT INTO Datacenter VALUES (1, 'DC-North', 'EU')",
    "INSERT INTO Datacenter VALUES (2, 'DC-South', 'EU')",
    "INSERT INTO Folder VALUES (1, 'Root', NULL)",
    "INSERT INTO Folder VALUES (2, 'Prod', 1)",
    "INSERT INTO Folder VALUES (3, 'Web', 2)",
    "INSERT INTO VMCluster VALUES (1, 'Cluster-A', 1)",
    "INSERT INTO VMCluster VALUES (2, 'Cluster-B', 1)",
    "INSERT INTO Host VALUES (1, 'esx-01', 1, 32, 512)",
    "INSERT INTO Host VALUES (2, 'esx-02', 1, 32, 512)",
    "INSERT INTO Host VALUES (3, 'esx-03', 2, 48, 768)",
    "INSERT INTO ResourcePool VALUES (1, 'default', 'Default Pool', 4000)",
    "INSERT INTO ResourcePool VALUES (1, 'high', 'High Priority', 8000)",
    "INSERT INTO ResourcePool VALUES (2, 'default', 'Default Pool', 4000)",
    "INSERT INTO StorageArray VALUES (1, 'Array-1', 1)",
    "INSERT INTO StoragePool VALUES (1, 'Gold', 1)",
    "INSERT INTO StoragePool VALUES (2, 'Silver', 1)",
    "INSERT INTO Datastore VALUES (1, 'ds-gold-01', 1, 10240)",
    "INSERT INTO Datastore VALUES (2, 'ds-silver-01', 2, 20480)",
    "INSERT INTO LUN VALUES (1, 10, 1, 5120)",
    "INSERT INTO Volume VALUES (1, 'vol-01', 1, 2048)",
    "INSERT INTO Network VALUES (1, 'Prod-Net', 1)",
    "INSERT INTO VLAN VALUES (1, 100, 1)",
    "INSERT INTO VLAN VALUES (2, 200, 1)",
    "INSERT INTO VirtualSwitch VALUES (1, 'vSwitch0', 1)",
    "INSERT INTO PortGroup VALUES (1, 'PG-Prod', 1, 1)",
    "INSERT INTO IPPool VALUES (1, '10.0.0.0/24', 1)",
    "INSERT INTO VirtualMachine VALUES (1, 'web-vm', 1, 1, 1, 3, 1, 'poweredOn', 4)",
    "INSERT INTO VirtualMachine VALUES (2, 'db-vm', 2, 2, 2, 2, 1, 'poweredOn', 8)",
    "INSERT INTO VirtualMachine VALUES (3, 'test-vm', 3, 3, 2, 1, 2, 'poweredOff', 2)",
    "INSERT INTO VMDisk VALUES (1, 1, 1, 80)",
    "INSERT INTO VMDisk VALUES (2, 2, 1, 200)",
    "INSERT INTO VMDisk VALUES (3, 3, 2, 40)",
    "INSERT INTO VMSnapshot VALUES (1, 1, NULL, 'base')",
    "INSERT INTO VMSnapshot VALUES (2, 1, 1, 'patched')",
    "INSERT INTO VMPlacement VALUES (1, 1, 1, 'default')",
    "INSERT INTO VMPlacement VALUES (2, 2, 1, 'high')",
    "INSERT INTO VMNetworkInterface VALUES (1, 1, 1, '00:50:56:aa:bb:01')",
    "INSERT INTO VMNetworkInterface VALUES (2, 2, 1, '00:50:56:aa:bb:02')",
    "INSERT INTO IPAddress VALUES (1, '10.0.0.11', 1, 1)",
    "INSERT INTO IPAddress VALUES (2, '10.0.0.12', 1, 2)",
    "INSERT INTO DiskBackingFile VALUES (1, 1, 1, '[ds-gold-01] web-vm/web-vm.vmdk')",
    "INSERT INTO BackupPolicy VALUES (1, 'Daily-30d', 30)",
    "INSERT INTO BackupJob VALUES (1, 1, 1, 'success')",
    "INSERT INTO BackupJob VALUES (2, 1, 2, 'running')",
    "INSERT INTO RestorePoint VALUES (1, 1, 'RP-2026-06-30')",
    "INSERT INTO Replication VALUES (1, 1, 2, 'inSync')",
    "INSERT INTO LicenseKey VALUES (1, 'AAAA-BBBB-CCCC', 1, 10)",
    "INSERT INTO LicenseAssignment VALUES (1, 1, 1)",
    "INSERT INTO LicenseAssignment VALUES (2, 1, 2)",
    "INSERT INTO AuditLog VALUES (1, 'admin', 'login', '2026-06-30T09:00')",
    "INSERT INTO Tag VALUES (1, 'critical')",
    "INSERT INTO TagAssignment VALUES (1, 1, 1)",
    "INSERT INTO Server VALUES (1, 'phys-01', 1)",
]

# ── Objects: sequences, functions, procedures, packages, trigger, views,
#    materialized views, synonyms. PL/SQL via CREATE OR REPLACE, no trailing '/'. ─
OBJECTS = [
    "CREATE SEQUENCE seq_vm_id START WITH 1000 INCREMENT BY 1",
    "CREATE SEQUENCE seq_ticket START WITH 500 INCREMENT BY 1",
    "CREATE SEQUENCE seq_audit START WITH 1 INCREMENT BY 1",
    # Functions
    "CREATE OR REPLACE FUNCTION fn_vm_label(p_id IN NUMBER) RETURN VARCHAR2 IS v VARCHAR2(120); "
    "BEGIN SELECT VMName INTO v FROM VirtualMachine WHERE VMID = p_id; RETURN v; "
    "EXCEPTION WHEN NO_DATA_FOUND THEN RETURN NULL; END;",
    "CREATE OR REPLACE FUNCTION fn_host_capacity(p_host IN NUMBER) RETURN NUMBER IS v NUMBER; "
    "BEGIN SELECT CpuCores * MemGB INTO v FROM Host WHERE HostID = p_host; RETURN v; "
    "EXCEPTION WHEN NO_DATA_FOUND THEN RETURN 0; END;",
    "CREATE OR REPLACE FUNCTION fn_folder_path(p_id IN NUMBER) RETURN VARCHAR2 IS "
    "v VARCHAR2(400); p NUMBER; nm VARCHAR2(80); cur NUMBER := p_id; "
    "BEGIN v := ''; WHILE cur IS NOT NULL LOOP "
    "SELECT FolderName, ParentFolderID INTO nm, p FROM Folder WHERE FolderID = cur; "
    "v := nm || '/' || v; cur := p; END LOOP; RETURN v; "
    "EXCEPTION WHEN NO_DATA_FOUND THEN RETURN v; END;",
    "CREATE OR REPLACE FUNCTION fn_datastore_free(p_ds IN NUMBER) RETURN NUMBER IS cap NUMBER; used NUMBER; "
    "BEGIN SELECT CapacityGB INTO cap FROM Datastore WHERE DatastoreID = p_ds; "
    "SELECT NVL(SUM(SizeGB),0) INTO used FROM VMDisk WHERE DatastoreID = p_ds; "
    "RETURN cap - used; EXCEPTION WHEN NO_DATA_FOUND THEN RETURN 0; END;",
    "CREATE OR REPLACE FUNCTION fn_license_seats_used(p_lic IN NUMBER) RETURN NUMBER IS v NUMBER; "
    "BEGIN SELECT COUNT(*) INTO v FROM LicenseAssignment WHERE LicenseID = p_lic; RETURN v; END;",
    "CREATE OR REPLACE FUNCTION fn_vm_power_state(p_id IN NUMBER) RETURN VARCHAR2 IS v VARCHAR2(20); "
    "BEGIN SELECT PowerState INTO v FROM VirtualMachine WHERE VMID = p_id; RETURN v; "
    "EXCEPTION WHEN NO_DATA_FOUND THEN RETURN 'unknown'; END;",
    "CREATE OR REPLACE FUNCTION fn_cluster_vm_count(p_cluster IN NUMBER) RETURN NUMBER IS v NUMBER; "
    "BEGIN SELECT COUNT(*) INTO v FROM VirtualMachine vm JOIN Host h ON vm.HostID = h.HostID "
    "WHERE h.ClusterID = p_cluster; RETURN v; END;",
    "CREATE OR REPLACE FUNCTION fn_datastore_capacity(p_ds IN NUMBER) RETURN NUMBER IS v NUMBER; "
    "BEGIN SELECT CapacityGB INTO v FROM Datastore WHERE DatastoreID = p_ds; RETURN v; "
    "EXCEPTION WHEN NO_DATA_FOUND THEN RETURN 0; END;",
    # Procedures
    "CREATE OR REPLACE PROCEDURE usp_tag_count(p_n OUT NUMBER) IS "
    "BEGIN SELECT COUNT(*) INTO p_n FROM TagAssignment; END;",
    "CREATE OR REPLACE PROCEDURE usp_vm_count(p_n OUT NUMBER) IS "
    "BEGIN SELECT COUNT(*) INTO p_n FROM VirtualMachine; END;",
    "CREATE OR REPLACE PROCEDURE usp_rebalance_report(p_cluster IN NUMBER, p_hosts OUT NUMBER) IS "
    "BEGIN SELECT COUNT(*) INTO p_hosts FROM Host WHERE ClusterID = p_cluster; END;",
    "CREATE OR REPLACE PROCEDURE usp_cleanup_snapshots(p_vm IN NUMBER, p_removed OUT NUMBER) IS "
    "BEGIN SELECT COUNT(*) INTO p_removed FROM VMSnapshot WHERE VMID = p_vm; END;",
    # Packages (spec + body)
    "CREATE OR REPLACE PACKAGE pkg_capacity AS FUNCTION host_capacity(p_host IN NUMBER) RETURN NUMBER; "
    "PROCEDURE cluster_hosts(p_cluster IN NUMBER, p_n OUT NUMBER); END pkg_capacity;",
    "CREATE OR REPLACE PACKAGE BODY pkg_capacity AS "
    "FUNCTION host_capacity(p_host IN NUMBER) RETURN NUMBER IS BEGIN RETURN fn_host_capacity(p_host); END; "
    "PROCEDURE cluster_hosts(p_cluster IN NUMBER, p_n OUT NUMBER) IS "
    "BEGIN SELECT COUNT(*) INTO p_n FROM Host WHERE ClusterID = p_cluster; END; END pkg_capacity;",
    "CREATE OR REPLACE PACKAGE pkg_inventory AS FUNCTION vm_name(p_id IN NUMBER) RETURN VARCHAR2; "
    "PROCEDURE vm_count(p_n OUT NUMBER); END pkg_inventory;",
    "CREATE OR REPLACE PACKAGE BODY pkg_inventory AS "
    "FUNCTION vm_name(p_id IN NUMBER) RETURN VARCHAR2 IS BEGIN RETURN fn_vm_label(p_id); END; "
    "PROCEDURE vm_count(p_n OUT NUMBER) IS BEGIN SELECT COUNT(*) INTO p_n FROM VirtualMachine; END; "
    "END pkg_inventory;",
    "CREATE OR REPLACE PACKAGE pkg_licensing AS FUNCTION seats_used(p_lic IN NUMBER) RETURN NUMBER; "
    "PROCEDURE total_seats(p_n OUT NUMBER); END pkg_licensing;",
    "CREATE OR REPLACE PACKAGE BODY pkg_licensing AS "
    "FUNCTION seats_used(p_lic IN NUMBER) RETURN NUMBER IS BEGIN RETURN fn_license_seats_used(p_lic); END; "
    "PROCEDURE total_seats(p_n OUT NUMBER) IS BEGIN SELECT NVL(SUM(Seats),0) INTO p_n FROM LicenseKey; END; "
    "END pkg_licensing;",
    "CREATE OR REPLACE PACKAGE pkg_backup AS PROCEDURE job_count(p_n OUT NUMBER); END pkg_backup;",
    "CREATE OR REPLACE PACKAGE BODY pkg_backup AS "
    "PROCEDURE job_count(p_n OUT NUMBER) IS BEGIN SELECT COUNT(*) INTO p_n FROM BackupJob; END; "
    "END pkg_backup;",
    # Trigger
    "CREATE OR REPLACE TRIGGER trg_vm_audit AFTER INSERT ON VirtualMachine BEGIN NULL; END;",
    # Views (several call functions → AP-66·S1)
    "CREATE OR REPLACE VIEW vw_vm_labeled AS SELECT VMID, fn_vm_label(VMID) AS VMLabel FROM VirtualMachine",
    "CREATE OR REPLACE VIEW vw_host_capacity AS "
    "SELECT h.HostID, h.Hostname, fn_host_capacity(h.HostID) AS Capacity FROM Host h",
    "CREATE OR REPLACE VIEW vw_datastore_usage AS "
    "SELECT d.DatastoreID, d.DSName, d.CapacityGB, fn_datastore_free(d.DatastoreID) AS FreeGB FROM Datastore d",
    "CREATE OR REPLACE VIEW vw_license_utilization AS "
    "SELECT lk.LicenseID, lk.LicKey, lk.Seats, fn_license_seats_used(lk.LicenseID) AS Used FROM LicenseKey lk",
    "CREATE OR REPLACE VIEW vw_orphaned_vms AS "
    "SELECT v.VMID, v.VMName FROM VirtualMachine v WHERE NOT EXISTS "
    "(SELECT 1 FROM BackupJob b WHERE b.VMID = v.VMID)",
    "CREATE OR REPLACE VIEW vw_vm_full_path AS "
    "SELECT v.VMID, v.VMName, fn_folder_path(v.FolderID) AS FolderPath FROM VirtualMachine v",
    "CREATE OR REPLACE VIEW vw_windows_vms AS "
    "SELECT v.VMID, v.VMName FROM VirtualMachine v JOIN OperatingSystem o ON v.OSID = o.OSID "
    "WHERE o.Family = 'Windows'",
    "CREATE OR REPLACE VIEW vw_cluster_hostcount AS "
    "SELECT c.ClusterID, c.ClusterName, COUNT(h.HostID) AS HostCount "
    "FROM VMCluster c LEFT JOIN Host h ON h.ClusterID = c.ClusterID GROUP BY c.ClusterID, c.ClusterName",
    "CREATE OR REPLACE VIEW vw_backup_status AS "
    "SELECT j.JobID, fn_vm_label(j.VMID) AS VMLabel, j.JobStatus FROM BackupJob j",
    "CREATE OR REPLACE VIEW vw_network_topology AS "
    "SELECT n.NetName, vl.VlanTag, pg.PGName FROM Network n "
    "JOIN VLAN vl ON vl.NetworkID = n.NetworkID JOIN PortGroup pg ON pg.VlanID = vl.VlanID",
    # Materialized views
    "CREATE MATERIALIZED VIEW mv_cluster_capacity AS "
    "SELECT h.ClusterID, SUM(h.CpuCores) AS Cores, SUM(h.MemGB) AS MemGB FROM Host h GROUP BY h.ClusterID",
    "CREATE MATERIALIZED VIEW mv_vm_per_datastore AS "
    "SELECT d.DatastoreID, COUNT(*) AS DiskCount FROM VMDisk d GROUP BY d.DatastoreID",
    # Synonyms
    "CREATE OR REPLACE SYNONYM syn_vm FOR VirtualMachine",
    "CREATE OR REPLACE SYNONYM syn_host FOR Host",
    "CREATE OR REPLACE SYNONYM syn_ds FOR Datastore",
]
