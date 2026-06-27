import pytest

from core.pathfinder import JoinPath, JoinStep
from core.sqlgen import generate_sql, Selection, Filter


def _path():
    return JoinPath(
        tables=("Networks", "VirtualMachines", "VMwareCluster"),
        steps=(
            JoinStep("Networks", "VirtualMachines", (("NetworkID", "NetworkID"),)),
            JoinStep("VirtualMachines", "VMwareCluster", (("ClusterID", "ClusterID"),)),
        ),
    )


def test_basic_select_join():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID")))
    assert "SELECT" in g.sql
    assert 'FROM "Networks"' in g.sql
    # Multi-line layout: JOIN on its own line, ON on the next (AP-43).
    assert 'JOIN "VirtualMachines"' in g.sql
    assert '    ON "Networks"."NetworkID" = "VirtualMachines"."NetworkID"' in g.sql
    assert 'JOIN "VMwareCluster"' in g.sql
    assert '    ON "VirtualMachines"."ClusterID" = "VMwareCluster"."ClusterID"' in g.sql
    assert g.params == {}


def test_composite_join_renders_all_pairs_with_and():
    # A composite FK (multiple column pairs in one JoinStep) must join on every
    # pair, combined with AND, in path order.
    path = JoinPath(
        tables=("VMPlacement", "ResourcePool"),
        steps=(JoinStep("VMPlacement", "ResourcePool",
                        (("ClusterID", "ClusterID"), ("PoolKey", "PoolKey"))),),
    )
    g = generate_sql(path, selects=(Selection("ResourcePool", "Name"),))
    # Each pair on its own line: ON … then AND … ("=" aligned via padding).
    assert 'ON "VMPlacement"."ClusterID" = "ResourcePool"."ClusterID"' in g.sql
    assert 'AND "VMPlacement"."PoolKey"' in g.sql
    assert '= "ResourcePool"."PoolKey"' in g.sql


def test_filter_uses_named_placeholder():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "=", 7),))
    assert 'WHERE "VirtualMachines"."OSID" = :p0' in g.sql
    assert g.params == {"p0": 7}
    # value must never be inlined
    assert "= 7" not in g.sql


def test_sql_inline_substitutes_numeric_literal():
    # Parameterised form keeps :p0; the inline form (for copy/display) renders the
    # literal so it is directly runnable in an external SQL client.
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "=", 7),))
    assert 'WHERE "VirtualMachines"."OSID" = :p0' in g.sql
    assert 'WHERE "VirtualMachines"."OSID" = 7' in g.sql_inline
    assert ":p0" not in g.sql_inline


def test_sql_inline_numeric_string_is_bare():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "=", "7"),))
    assert '= 7' in g.sql_inline
    assert "'7'" not in g.sql_inline


def test_sql_inline_quotes_strings_and_escapes_single_quote():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("Networks", "Name", "LIKE", "O'Brien%"),))
    assert "LIKE 'O''Brien%'" in g.sql_inline


def test_sql_inline_like_numeric_value_stays_quoted():
    # LIKE operands are always strings — even a numeric-looking one must be quoted.
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("Networks", "Name", "LIKE", "123"),))
    assert "LIKE '123'" in g.sql_inline


def test_sql_inline_in_and_between():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "IN", [1, 2]),
                              Filter("VirtualMachines", "VMID", "BETWEEN", [10, 20])))
    assert "IN (1, 2)" in g.sql_inline
    assert "BETWEEN 10 AND 20" in g.sql_inline


def test_sql_inline_is_null_identical():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("Networks", "VLAN", "IS NULL", None),))
    assert 'WHERE "Networks"."VLAN" IS NULL' in g.sql_inline


def test_sql_inline_leading_zero_preserved_as_string():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("Networks", "Code", "=", "01234"),))
    assert "= '01234'" in g.sql_inline


def test_join_types_left_then_default_inner():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     join_types=("LEFT",))
    assert 'LEFT JOIN "VirtualMachines"' in g.sql
    # second step, no type supplied → defaults to plain INNER JOIN
    assert '\nJOIN "VMwareCluster"' in g.sql


def test_join_types_right_and_full():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     join_types=("RIGHT", "FULL"))
    assert 'RIGHT JOIN "VirtualMachines"' in g.sql
    assert 'FULL JOIN "VMwareCluster"' in g.sql


def test_join_types_invalid_raises():
    with pytest.raises(ValueError):
        generate_sql(_path(), selects=(Selection("Networks", "VLAN"),),
                     join_types=("OUTER",))


def test_inline_ends_with_semicolon_executed_sql_does_not():
    # AP-43: the copy/display variant is terminated with ';' (paste-and-run);
    # the executed parameterised `sql` is not.
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),))
    assert g.sql_inline.endswith(";")
    assert not g.sql.rstrip().endswith(";")


def test_determinism():
    a = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),))
    b = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),))
    assert a.sql == b.sql


def test_empty_selects_raises():
    with pytest.raises(ValueError):
        generate_sql(_path(), selects=())


def test_bad_operator_raises():
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "DROP", 1),))


def test_three_selections():
    """generate_sql renders all three columns in the SELECT clause."""
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID"),
                              Selection("VirtualMachines", "VMID")))
    # AP-43: one column per indented line under a bare SELECT.
    assert g.sql.splitlines()[0] == "SELECT"
    assert '    "Networks"."VLAN",' in g.sql
    assert '    "VMwareCluster"."ClusterID",' in g.sql
    assert '    "VirtualMachines"."VMID"' in g.sql      # last column, no trailing comma


# ===== AP-3: DISTINCT =====

def test_distinct_renders_select_distinct():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     distinct=True)
    assert "SELECT DISTINCT" in g.sql
    assert g.sql.startswith("SELECT DISTINCT")


def test_no_distinct_by_default():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),))
    assert "DISTINCT" not in g.sql


# ===== AP-3: ORDER BY =====

def test_order_by_desc():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("VirtualMachines", "VMID", "DESC"),))
    assert 'ORDER BY "VirtualMachines"."VMID" DESC' in g.sql


def test_order_by_asc():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("Networks", "VLAN", "ASC"),))
    assert 'ORDER BY "Networks"."VLAN" ASC' in g.sql


def test_order_by_multiple_cols():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("Networks", "VLAN", "ASC"),
                               ("VirtualMachines", "VMID", "DESC")))
    assert 'ORDER BY "Networks"."VLAN" ASC, "VirtualMachines"."VMID" DESC' in g.sql


def test_order_by_invalid_direction_raises():
    with pytest.raises(ValueError, match="direction"):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("VirtualMachines", "VMID", "SIDEWAYS"),))


# ===== AP-3: LIMIT =====

def test_limit_renders_clause():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     limit=50)
    assert "LIMIT 50" in g.sql


def test_limit_zero_omitted():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     limit=0)
    assert "LIMIT" not in g.sql


def test_limit_none_omitted():
    g = generate_sql(_path(), selects=(Selection("Networks", "VLAN"),))
    assert "LIMIT" not in g.sql


# ===== AP-3: Extended filter operators =====

def test_is_null_no_placeholder():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "IS NULL", None),))
    assert '"VirtualMachines"."OSID" IS NULL' in g.sql
    assert not g.params  # no placeholder generated


def test_is_not_null_no_placeholder():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "IS NOT NULL", None),))
    assert '"VirtualMachines"."OSID" IS NOT NULL' in g.sql
    assert not g.params


def test_in_multiple_placeholders():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "VMID", "IN", [1, 2, 3]),))
    assert '"VirtualMachines"."VMID" IN (:p0_0, :p0_1, :p0_2)' in g.sql
    assert g.params == {"p0_0": 1, "p0_1": 2, "p0_2": 3}


def test_in_values_never_inlined():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "VMID", "IN", ["xyzval1", "xyzval2"]),))
    assert "IN (" in g.sql
    # values must never appear literally in the SQL string — only in params
    assert "xyzval1" not in g.sql
    assert "xyzval2" not in g.sql
    assert g.params.get("p0_0") == "xyzval1"
    assert g.params.get("p0_1") == "xyzval2"


def test_between_two_placeholders():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "VMID", "BETWEEN", (1, 10)),))
    assert '"VirtualMachines"."VMID" BETWEEN :p0_lo AND :p0_hi' in g.sql
    assert g.params == {"p0_lo": 1, "p0_hi": 10}


def test_bad_operator_still_raises():
    """Unsupported operators (not in _ALLOWED_OPS) still raise ValueError."""
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "DROP", 1),))


def test_combined_distinct_orderby_limit():
    """All three AP-3 options compose correctly."""
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     distinct=True,
                     order_by=(("VirtualMachines", "VMID", "DESC"),),
                     limit=100)
    assert "SELECT DISTINCT" in g.sql
    assert 'ORDER BY "VirtualMachines"."VMID" DESC' in g.sql
    assert "LIMIT 100" in g.sql
    # ORDER BY must come before LIMIT
    assert g.sql.index("ORDER BY") < g.sql.index("LIMIT")
