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


def test_load_reflects_unique_constraints(onetoone_url):
    schema = SqlAlchemyLoader(onetoone_url).load()
    passport = schema.table("Passport")
    # inline UNIQUE on the FK column is reflected as a one-column unique set
    assert ("PersonID",) in passport.unique_constraints
    orders = schema.table("Orders")
    # the 1-N child has no unique set covering its FK column
    assert all("PersonID" not in u for u in orders.unique_constraints)


def test_load_reflects_unique_indexes(uniqueindex_url):
    schema = SqlAlchemyLoader(uniqueindex_url).load()
    profile = schema.table("Profile")
    # full, non-partial unique index on the FK column is reflected
    assert ("ParentID",) in profile.unique_indexes
    note = schema.table("Note")
    # the only unique index on Note is partial → must be excluded
    assert all("ParentID" not in idx for idx in note.unique_indexes)


def test_load_with_explicit_default_schema_matches(inventory_url):
    # SQLite's real default schema is "main"; reflecting it explicitly must
    # yield the same tables as the no-arg default.
    default = {t.name for t in SqlAlchemyLoader(inventory_url).load().tables}
    explicit = {t.name for t in SqlAlchemyLoader(inventory_url).load(schema="main").tables}
    assert explicit == default and "VirtualMachines" in explicit


def test_list_schemas_includes_main_and_filters_system(inventory_url):
    from core.loaders.sqlalchemy_loader import list_schemas
    schemas = list_schemas(inventory_url)
    assert "main" in schemas
    assert not ({"information_schema", "pg_catalog", "sys"} & set(schemas))


def test_user_schemas_filters_oracle_system_schemas():
    from core.loaders.sqlalchemy_loader import _user_schemas
    names = ["SYS", "SYSTEM", "XDB", "CTXSYS", "HR", "APP_DATA"]
    assert _user_schemas(names) == ("HR", "APP_DATA")
