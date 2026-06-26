import pytest
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader


def test_load_reflects_tables_and_columns(inventory_url):
    schema = SqlAlchemyLoader(inventory_url).load()
    names = {t.name for t in schema.tables}
    assert names == {"OperatingSystems", "VMwareCluster", "Networks", "VirtualMachines"}
    assert schema.has_column("Networks", "VLAN")


def test_load_reflects_foreign_keys(inventory_url):
    schema = SqlAlchemyLoader(inventory_url).load()
    vm = schema.table("VirtualMachines")
    fk_targets = {(fk.columns, fk.ref_table, fk.ref_columns) for fk in vm.foreign_keys}
    assert (("NetworkID",), "Networks", ("NetworkID",)) in fk_targets
    assert (("OSID",), "OperatingSystems", ("OSID",)) in fk_targets
    assert (("ClusterID",), "VMwareCluster", ("ClusterID",)) in fk_targets


def test_load_reflects_views(inventory_url):
    schema = SqlAlchemyLoader(inventory_url).load()
    names = {v.name for v in schema.views}
    assert "VMNetworks" in names
    vmn = next(v for v in schema.views if v.name == "VMNetworks")
    assert any(c.name == "VLAN" for c in vmn.columns)
    assert "SELECT" in vmn.definition.upper()


def test_bad_url_raises_connection_error():
    with pytest.raises(ConnectionError):
        SqlAlchemyLoader("sqlite:////nonexistent/path/that/cannot/exist.db").load()
