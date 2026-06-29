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
