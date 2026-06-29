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


def _patch_loader(monkeypatch, fake_inspector):
    """Lässt SqlAlchemyLoader.load() gegen einen Fake-Inspector laufen."""
    import core.loaders.sqlalchemy_loader as mod

    class _DummyEngine:
        def dispose(self):
            pass

    monkeypatch.setattr(mod, "create_engine", lambda url: _DummyEngine())
    monkeypatch.setattr(mod, "inspect", lambda engine: fake_inspector)


class _FakeInspector:
    """Minimaler Inspector: eine Tabelle 't' mit kommentierter Spalte 'a'."""
    def __init__(self, table_comment):
        self._table_comment = table_comment  # dict, Exception-Klasse, oder None

    def get_table_names(self, schema=None):
        return ["t"]

    def get_columns(self, tname, schema=None):
        return [{"name": "a", "type": "INT", "comment": "Spalten-Notiz"},
                {"name": "b", "type": "TEXT", "comment": None}]

    def get_foreign_keys(self, tname, schema=None):
        return []

    def get_pk_constraint(self, tname, schema=None):
        return {"constrained_columns": []}

    def get_unique_constraints(self, tname, schema=None):
        return []

    def get_indexes(self, tname, schema=None):
        return []

    def get_check_constraints(self, tname, schema=None):
        return []

    def get_table_comment(self, tname, schema=None):
        if isinstance(self._table_comment, type) and issubclass(self._table_comment, Exception):
            raise self._table_comment()
        return self._table_comment

    def get_view_names(self, schema=None):
        return []


def test_load_reflects_column_and_table_comments(monkeypatch):
    _patch_loader(monkeypatch, _FakeInspector({"text": "Tabellen-Notiz"}))
    schema = SqlAlchemyLoader("fake://").load()
    t = schema.table("t")
    assert t.comment == "Tabellen-Notiz"
    assert next(c for c in t.columns if c.name == "a").comment == "Spalten-Notiz"
    # comment None → leerer String, nie None
    assert next(c for c in t.columns if c.name == "b").comment == ""


def test_load_table_comment_not_implemented_falls_back_empty(monkeypatch):
    _patch_loader(monkeypatch, _FakeInspector(NotImplementedError))
    schema = SqlAlchemyLoader("fake://").load()
    assert schema.table("t").comment == ""


def test_load_table_comment_sqlalchemy_error_falls_back_empty(monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    _patch_loader(monkeypatch, _FakeInspector(SQLAlchemyError))
    schema = SqlAlchemyLoader("fake://").load()
    assert schema.table("t").comment == ""


def test_load_table_comment_text_none_falls_back_empty(monkeypatch):
    _patch_loader(monkeypatch, _FakeInspector({"text": None}))
    schema = SqlAlchemyLoader("fake://").load()
    assert schema.table("t").comment == ""


def test_load_sqlite_has_empty_comments(inventory_url):
    # SQLite kennt keine Kommentare: kein comment-Key, get_table_comment wirft
    # NotImplementedError → alles fällt sauber auf "" zurück, kein Crash.
    schema = SqlAlchemyLoader(inventory_url).load()
    for t in schema.tables:
        assert t.comment == ""
        assert all(c.comment == "" for c in t.columns)


def test_loader_reflects_all_indexes(indexes_checks_url):
    schema = SqlAlchemyLoader(indexes_checks_url).load()
    person = schema.table("Person")
    by_name = {ix.name: ix for ix in person.indexes}
    assert "ix_person_region" in by_name
    assert by_name["ix_person_region"].columns == ("region",)
    assert by_name["ix_person_region"].unique is False
    assert "ux_person_email" in by_name
    assert by_name["ux_person_email"].unique is True


def test_loader_reflects_check_constraints(indexes_checks_url):
    schema = SqlAlchemyLoader(indexes_checks_url).load()
    person = schema.table("Person")
    texts = [cc.sqltext for cc in person.check_constraints]
    names = [cc.name for cc in person.check_constraints]
    assert any("email" in t for t in texts)      # named ck_email
    assert any("age" in t for t in texts)        # unnamed inline check
    assert "ck_email" in names
    assert "" in names                           # the unnamed check → name ""
