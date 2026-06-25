from sqlalchemy import inspect


def test_fixture_has_foreign_keys(sqlite_engine):
    insp = inspect(sqlite_engine)
    assert set(insp.get_table_names()) == {
        "OperatingSystems", "VMwareCluster", "Networks", "VirtualMachines",
    }
    fks = insp.get_foreign_keys("VirtualMachines")
    assert len(fks) == 3
