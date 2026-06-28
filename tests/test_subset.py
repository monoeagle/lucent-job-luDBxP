from core.model import Schema, Table, Column, ForeignKey
from core.subset import compute_subset


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
