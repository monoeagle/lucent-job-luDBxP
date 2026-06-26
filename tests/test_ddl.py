from core.model import Column, ForeignKey, Table
from core.ddl import table_ddl


def test_table_ddl_renders_columns_pk_and_fks():
    t = Table(
        "VM",
        (Column("VMID", "INTEGER"), Column("NetworkID", "INTEGER")),
        (ForeignKey.single("NetworkID", "Networks", "NetworkID"),),
        ("VMID",),
    )
    sql = table_ddl(t)
    assert sql.startswith("CREATE TABLE VM (")
    assert "VMID INTEGER PRIMARY KEY" in sql
    assert "FOREIGN KEY (NetworkID) REFERENCES Networks(NetworkID)" in sql


def test_table_ddl_composite_primary_key():
    t = Table(
        "Pool",
        (Column("ClusterID", "INTEGER"), Column("PoolKey", "TEXT")),
        (),
        ("ClusterID", "PoolKey"),
    )
    sql = table_ddl(t)
    assert "PRIMARY KEY (ClusterID, PoolKey)" in sql
