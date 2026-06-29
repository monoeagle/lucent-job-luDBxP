import pytest
from sample_data.build_demo_db import build
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.datapreview import count_subset_rows, execute_select, dump_subset_rows
from core.subset import SubsetScript
from core.model import Schema, Table, Column, ForeignKey
from core.subset import compute_subset, generate_subset_sql, count_sql, subset_keys, subset_in_list_sql


def _t(name, cols, fks=(), pk=()):
    return Table(name, tuple(Column(c, "INTEGER") for c in cols), tuple(fks), primary_key=tuple(pk))


# Schema: Country<-Customer<-Order<-LineItem->Product ; plus lookups' other children
# that must NOT be pulled (no re-descent): Region (child of Country), Inventory (child of Product).
def _shop_schema(extra=()):
    tables = [
        _t("Country", ["code", "name"], pk=["code"]),
        _t("Customer", ["id", "country_code"],
           [ForeignKey.single("country_code", "Country", "code")], pk=["id"]),
        _t("Order", ["id", "customer_id"],
           [ForeignKey.single("customer_id", "Customer", "id")], pk=["id"]),
        _t("Product", ["id"], pk=["id"]),
        _t("LineItem", ["id", "order_id", "product_id"],
           [ForeignKey.single("order_id", "Order", "id"),
            ForeignKey.single("product_id", "Product", "id")], pk=["id"]),
        _t("Region", ["id", "country_code"],
           [ForeignKey.single("country_code", "Country", "code")], pk=["id"]),
        _t("Inventory", ["id", "product_id"],
           [ForeignKey.single("product_id", "Product", "id")], pk=["id"]),
    ]
    return Schema(tuple(tables) + tuple(extra))


def test_downward_collects_children_recursively():
    r = compute_subset(_shop_schema(), "Customer")
    names = {t.name for t in r.tables}
    assert {"Order", "LineItem"} <= names


def test_upward_collects_lookups_of_start_and_children():
    r = compute_subset(_shop_schema(), "Customer")
    by = {t.name: t for t in r.tables}
    assert by["Country"].edge.kind == "parent"   # lookup of Customer
    assert by["Product"].edge.kind == "parent"   # lookup of LineItem


def test_down_then_up_no_redescent():
    # Country and Product are lookups (upward); their OTHER children must NOT be pulled.
    r = compute_subset(_shop_schema(), "Customer")
    names = {t.name for t in r.tables}
    assert "Region" not in names
    assert "Inventory" not in names


def test_root_has_no_edge_and_child_kinds_recorded():
    r = compute_subset(_shop_schema(), "Customer")
    by = {t.name: t for t in r.tables}
    assert by["Customer"].edge is None
    assert by["Order"].edge.kind == "child" and by["Order"].edge.via_table == "Customer"
    assert by["LineItem"].edge.kind == "child" and by["LineItem"].edge.via_table == "Order"


def test_topological_order_parents_before_children():
    order = [t.name for t in compute_subset(_shop_schema(), "Customer").tables]
    assert order.index("Country") < order.index("Customer")
    assert order.index("Customer") < order.index("Order")
    assert order.index("Order") < order.index("LineItem")
    assert order.index("Product") < order.index("LineItem")


def test_cycle_terminates():
    schema = Schema((
        _t("A", ["id", "b_id"], [ForeignKey.single("b_id", "B", "id")], pk=["id"]),
        _t("B", ["id", "a_id"], [ForeignKey.single("a_id", "A", "id")], pk=["id"]),
    ))
    names = {t.name for t in compute_subset(schema, "A").tables}
    assert names == {"A", "B"}


def test_self_fk_terminates():
    schema = Schema((
        _t("Employee", ["id", "manager_id"],
           [ForeignKey.single("manager_id", "Employee", "id")], pk=["id"]),
    ))
    names = {t.name for t in compute_subset(schema, "Employee").tables}
    assert names == {"Employee"}


def test_depth_limit_truncates_downward():
    schema = Schema((
        _t("R", ["id"], pk=["id"]),
        _t("C1", ["id", "r_id"], [ForeignKey.single("r_id", "R", "id")], pk=["id"]),
        _t("C2", ["id", "c1_id"], [ForeignKey.single("c1_id", "C1", "id")], pk=["id"]),
        _t("C3", ["id", "c2_id"], [ForeignKey.single("c2_id", "C2", "id")], pk=["id"]),
    ))
    r = compute_subset(schema, "R", max_depth=2)
    names = {t.name for t in r.tables}
    assert "C3" not in names and "C2" in names
    assert r.truncated is True


def test_implied_only_with_toggle():
    # Order.kunde references Kunde by name (no declared FK).
    schema = Schema((
        _t("Kunde", ["id"], pk=["id"]),
        Table("Bestellung",
              (Column("id", "INTEGER"), Column("kunde_id", "INTEGER")),
              (), primary_key=("id",)),
    ))
    assert "Bestellung" not in {t.name for t in compute_subset(schema, "Kunde").tables}
    assert "Bestellung" in {t.name for t in compute_subset(schema, "Kunde", include_implied=True).tables}


def test_unknown_start_table_raises():
    import pytest
    with pytest.raises(ValueError):
        compute_subset(_shop_schema(), "Nope")


from core.subset import generate_subset_sql
from core.sqlgen import SQLITE


def _scripts(start="Customer", **kw):
    r = compute_subset(_shop_schema(), start)
    flt = kw.pop("flt", {"column": "id", "op": "=", "value": 5})
    return {s.table: s for s in generate_subset_sql(_shop_schema(), r, flt, **kw)}


def test_root_select_filters_on_root():
    s = _scripts()["Customer"]
    assert "FROM" in s.sql and "Customer" in s.sql
    assert ":root" in s.sql and s.params == {"root": 5}
    assert "DISTINCT" not in s.sql            # root has no parent edge


def test_child_select_joins_back_to_root_no_distinct():
    s = _scripts()["Order"]
    assert "JOIN" in s.sql and "Customer" in s.sql
    assert "DISTINCT" not in s.sql            # pure downward path
    lines = [ln for ln in s.sql.rstrip().rstrip(";").splitlines() if ln.strip()]
    assert lines[-1].startswith("WHERE")
    assert ":root" in lines[-1]


def test_parent_lookup_select_is_distinct():
    s = _scripts()["Country"]                 # upward lookup of Customer
    assert s.sql.lstrip().startswith("SELECT DISTINCT")
    assert "Customer" in s.sql                # joins through Customer back to root


def test_schema_qualification_when_given():
    r = compute_subset(_shop_schema(), "Customer")
    s = {x.table: x for x in generate_subset_sql(
        _shop_schema(), r, {"column": "id", "op": "=", "value": 1},
        dialect=SQLITE, schema_name="dbo")}["Order"]
    assert '"dbo"."Order"' in s.sql


def test_in_operator_expands_params():
    r = compute_subset(_shop_schema(), "Customer")
    s = {x.table: x for x in generate_subset_sql(
        _shop_schema(), r, {"column": "id", "op": "IN", "value": [1, 2, 3]})}["Customer"]
    assert "IN (" in s.sql
    assert s.params == {"root0": 1, "root1": 2, "root2": 3}


def test_bad_operator_raises():
    import pytest
    r = compute_subset(_shop_schema(), "Customer")
    with pytest.raises(ValueError):
        generate_subset_sql(_shop_schema(), r, {"column": "id", "op": "DROP", "value": 1})


def test_count_sql_wraps_and_strips_semicolon():
    inner = "SELECT DISTINCT t0.*\nFROM Country t0\nWHERE t0.code = :root;"
    out = count_sql(inner)
    assert out.startswith("SELECT COUNT(*) FROM (")
    assert out.rstrip().endswith(") subset_cnt")
    assert ";" not in out                      # trailing ';' stripped before embedding
    assert "DISTINCT t0.*" in out              # inner SELECT (incl. DISTINCT) preserved
    assert " AS " not in out                   # alias without AS → Oracle-portable


@pytest.fixture
def demo_url(tmp_path):
    db = tmp_path / "demo.db"
    build(str(db))
    return f"sqlite:///{db}"


def _demo_scripts(url, start, column, value):
    schema = SqlAlchemyLoader(url).load()
    result = compute_subset(schema, start)
    return schema, generate_subset_sql(
        schema, result, {"column": column, "op": "=", "value": value})


def test_count_subset_rows_matches_actual_rows(demo_url):
    # Cross-check: each table's COUNT must equal the real number of rows the
    # original (non-count) subset SELECT returns. Data-independent correctness.
    _, scripts = _demo_scripts(demo_url, "VirtualMachine", "VMID", 1)
    counts = count_subset_rows(demo_url, scripts)
    assert [c["table"] for c in counts] == [s.table for s in scripts]  # order preserved
    by_table = {c["table"]: c for c in counts}
    for s in scripts:
        actual = len(execute_select(demo_url, s.sql, s.params, max_rows=100000)["rows"])
        assert by_table[s.table]["count"] == actual
        assert by_table[s.table]["error"] is None


def test_count_subset_rows_empty_datacenter_is_one_total(demo_url):
    # DatacenterID=3 is "DC-Empty": no Cluster/Network/Host hang off it, so every
    # child count is 0 and only the root row itself counts.
    _, scripts = _demo_scripts(demo_url, "Datacenter", "DatacenterID", 3)
    counts = count_subset_rows(demo_url, scripts)
    by = {c["table"]: c for c in counts}
    assert by["Datacenter"]["count"] == 1
    assert sum(c["count"] for c in counts) == 1


def test_count_subset_rows_resilient_per_table(demo_url):
    # A script referencing a non-existent column fails only that table.
    good = SubsetScript("Datacenter",
                        "SELECT * FROM Datacenter WHERE DatacenterID = :root;",
                        {"root": 1})
    bad = SubsetScript("Bogus", "SELECT * FROM NoSuchTable;", {})
    counts = count_subset_rows(demo_url, [good, bad])
    by = {c["table"]: c for c in counts}
    assert by["Datacenter"]["count"] == 1
    assert by["Bogus"]["count"] is None
    assert by["Bogus"]["error"] is not None


def test_dump_subset_rows_matches_actual_rows(demo_url):
    # Cross-check: each table's dumped rows equal the rows the original subset
    # SELECT returns directly. Data-independent.
    _, scripts = _demo_scripts(demo_url, "VirtualMachine", "VMID", 1)
    dump = dump_subset_rows(demo_url, scripts, max_rows_per_table=5000)
    assert [d["table"] for d in dump] == [s.table for s in scripts]  # order preserved
    by = {d["table"]: d for d in dump}
    for s in scripts:
        direct = execute_select(demo_url, s.sql, s.params, max_rows=100000)
        assert by[s.table]["rows"] == direct["rows"]
        assert by[s.table]["columns"] == direct["columns"]
        assert by[s.table]["row_count"] == len(direct["rows"])
        assert by[s.table]["truncated"] is False
        assert by[s.table]["error"] is None


def test_dump_subset_rows_empty_datacenter(demo_url):
    # DatacenterID=3 = "DC-Empty": root has 1 row, every child has 0.
    _, scripts = _demo_scripts(demo_url, "Datacenter", "DatacenterID", 3)
    dump = dump_subset_rows(demo_url, scripts, max_rows_per_table=5000)
    by = {d["table"]: d for d in dump}
    assert by["Datacenter"]["row_count"] == 1
    assert sum(d["row_count"] for d in dump) == 1
    assert all(d["error"] is None and d["truncated"] is False for d in dump)


def test_dump_subset_rows_truncates_per_table(demo_url):
    # A tiny cap forces truncation on any table whose subset has >2 rows.
    _, scripts = _demo_scripts(demo_url, "Datacenter", "DatacenterID", 1)
    dump = dump_subset_rows(demo_url, scripts, max_rows_per_table=2)
    # At least one closure table of DC-Frankfurt has >2 rows (e.g. Host/VirtualMachine).
    truncated = [d for d in dump if d["truncated"]]
    assert truncated, "expected at least one truncated table with cap=2"
    for d in truncated:
        assert d["row_count"] == 2 and len(d["rows"]) == 2


def test_dump_subset_rows_resilient_per_table(demo_url):
    good = SubsetScript("Datacenter",
                        "SELECT * FROM Datacenter WHERE DatacenterID = :root;",
                        {"root": 1})
    bad = SubsetScript("Bogus", "SELECT * FROM NoSuchTable;", {})
    dump = dump_subset_rows(demo_url, [good, bad], max_rows_per_table=5000)
    by = {d["table"]: d for d in dump}
    assert by["Datacenter"]["row_count"] == 1
    assert by["Bogus"]["rows"] == [] and by["Bogus"]["error"] is not None


def test_subset_keys_dedup_order_preserving():
    keys = subset_keys(("id",), ["id", "x"], [[1, "a"], [1, "b"], [2, "c"], [1, "d"]])
    assert keys == [(1,), (2,)]


def test_subset_keys_empty_cases():
    assert subset_keys((), ["id"], [[1]]) == []          # no PK
    assert subset_keys(("id",), ["id"], []) == []        # no rows
    assert subset_keys(("missing",), ["id"], [[1]]) == []  # PK col absent


def test_in_list_sql_single_pk():
    sql = subset_in_list_sql("T", ("id",), ["id", "x"], [[1, "a"], [2, "b"]])
    assert sql == 'SELECT * FROM "T" WHERE "id" IN (1, 2);'


def test_in_list_sql_composite_pk_or_form():
    sql = subset_in_list_sql("RP", ("ClusterID", "PoolKey"),
                             ["ClusterID", "PoolKey", "Name"],
                             [[1, "P1", "a"], [2, "P2", "b"]])
    assert sql == ('SELECT * FROM "RP" WHERE '
                   '("ClusterID" = 1 AND "PoolKey" = \'P1\') OR '
                   '("ClusterID" = 2 AND "PoolKey" = \'P2\');')


def test_in_list_sql_escapes_string_literals():
    sql = subset_in_list_sql("T", ("name",), ["name"], [["O'Brien"]])
    assert "'O''Brien'" in sql


def test_in_list_sql_composite_none_uses_is_null():
    sql = subset_in_list_sql("T", ("a", "b"), ["a", "b"], [[1, None]])
    assert sql == 'SELECT * FROM "T" WHERE ("a" = 1 AND "b" IS NULL);'


def test_in_list_sql_none_when_no_pk_or_no_rows():
    assert subset_in_list_sql("T", (), ["id"], [[1]]) is None
    assert subset_in_list_sql("T", ("id",), ["id"], []) is None


def test_in_list_sql_schema_qualified():
    sql = subset_in_list_sql("T", ("id",), ["id"], [[1]], schema_name="dbo")
    assert sql.startswith('SELECT * FROM "dbo"."T" WHERE')
