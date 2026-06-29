from core.model import Schema, Table, Column, ForeignKey
from core.subset import compute_subset, generate_subset_sql, count_sql


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
