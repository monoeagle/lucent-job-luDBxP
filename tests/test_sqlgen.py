import pytest

from core.pathfinder import JoinPath, JoinStep
from core.sqlgen import generate_sql, Selection, Filter, Having


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


# ===== Tier-3: Aggregate functions + auto-GROUP-BY =====

def test_aggregate_wraps_column_and_groups_by_rest():
    # COUNT on the target column -> GROUP BY the non-aggregated select column.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert '"Networks"."VLAN"' in g.sql
    assert 'GROUP BY "Networks"."VLAN"' in g.sql
    # GROUP BY is identical in the copy/inline variant (no filter values in it).
    assert 'GROUP BY "Networks"."VLAN"' in g.sql_inline


def test_no_aggregate_emits_no_group_by_unchanged():
    # Backward compatibility: without any aggregate the SQL has no GROUP BY.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID")))
    assert "GROUP BY" not in g.sql


def test_all_columns_aggregated_emits_no_group_by():
    # Every select aggregated -> single-row aggregate, no GROUP BY.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN", agg="MIN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'MIN("Networks"."VLAN")' in g.sql
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert "GROUP BY" not in g.sql


def test_group_by_clause_order_before_order_by_and_limit():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     order_by=(("Networks", "VLAN", "ASC"),),
                     limit=10)
    # WHERE -> GROUP BY -> ORDER BY -> LIMIT
    assert g.sql.index("GROUP BY") < g.sql.index("ORDER BY") < g.sql.index("LIMIT")


def test_same_column_as_key_and_aggregate_coexist():
    # A column may appear once plain (group key) and once aggregated.
    g = generate_sql(_path(),
                     selects=(Selection("VMwareCluster", "ClusterID"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert 'GROUP BY "VMwareCluster"."ClusterID"' in g.sql


def test_unsupported_aggregate_raises_value_error():
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN", agg="MEDIAN"),))


# ===== Aggregat-Ops: ORDER BY aggregate + HAVING =====

def test_order_by_aggregate_renders_func():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     order_by=(("VMwareCluster", "ClusterID", "DESC", "COUNT"),))
    assert 'ORDER BY COUNT("VMwareCluster"."ClusterID") DESC' in g.sql


def test_order_by_three_tuple_still_works():
    # Backward compatibility: a 3-tuple order_by renders a raw column, no aggregate.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("Networks", "VLAN", "ASC"),))
    assert 'ORDER BY "Networks"."VLAN" ASC' in g.sql


def test_having_renders_parametrised():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">", 5),))
    assert 'HAVING COUNT("VMwareCluster"."ClusterID") > :h0' in g.sql
    assert g.params["h0"] == 5
    assert "> 5" not in g.sql            # value never inlined into the executed SQL
    assert "> 5" in g.sql_inline          # but inlined in the copy/display variant


def test_having_numeric_string_value_coerced_to_number():
    # The web layer passes form values as strings. An aggregate has no column
    # affinity, so a TEXT-bound '5' never compares equal to the integer COUNT
    # (SQLite sorts integers before text) → the HAVING would silently drop every
    # row. A numeric-looking string must bind as a real number.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">", "5"),))
    assert g.params["h0"] == 5
    assert isinstance(g.params["h0"], int)


def test_having_non_numeric_string_value_kept():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "Name", agg="MAX")),
                     having=(Having("VMwareCluster", "Name", "MAX", ">", "abc"),))
    assert g.params["h0"] == "abc"


def test_having_clause_order():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     filters=(Filter("VirtualMachines", "OSID", "=", 7),),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">=", 2),),
                     order_by=(("Networks", "VLAN", "ASC"),),
                     limit=10)
    s = g.sql
    assert s.index("WHERE") < s.index("GROUP BY") < s.index("HAVING") < s.index("ORDER BY") < s.index("LIMIT")


def test_multiple_having_anded():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">", 1),
                             Having("VMwareCluster", "ClusterID", "COUNT", "<", 9)))
    assert 'HAVING COUNT("VMwareCluster"."ClusterID") > :h0' in g.sql
    assert '  AND COUNT("VMwareCluster"."ClusterID") < :h1' in g.sql
    assert g.params == {"h0": 1, "h1": 9}


def test_having_unsupported_op_raises():
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     having=(Having("Networks", "VLAN", "COUNT", "LIKE", "x"),))


def test_having_requires_aggregate_raises():
    with pytest.raises(ValueError):
        generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     having=(Having("Networks", "VLAN", "", ">", 1),))


def test_no_having_no_orderby_agg_unchanged():
    # Backward compatibility: omit having and order-by aggregates -> no HAVING clause.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert "HAVING" not in g.sql


# ===== COUNT(*) + COUNT(DISTINCT) =====

def test_count_star_renders_ignoring_column():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT*")))
    assert "COUNT(*)" in g.sql
    # the column attached to the COUNT* selection is ignored in the rendered expr
    assert 'COUNT(*)("' not in g.sql and 'COUNT("VMwareCluster"."ClusterID")' not in g.sql
    # group by the non-aggregated select
    assert 'GROUP BY "Networks"."VLAN"' in g.sql


def test_count_distinct_renders_with_column():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT DISTINCT")))
    assert 'COUNT(DISTINCT "VMwareCluster"."ClusterID")' in g.sql
    assert 'GROUP BY "Networks"."VLAN"' in g.sql


def test_count_star_in_having_and_order_by():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT*")),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT*", ">", 5),),
                     order_by=(("VMwareCluster", "ClusterID", "DESC", "COUNT*"),))
    assert "HAVING COUNT(*) > :h0" in g.sql
    assert "ORDER BY COUNT(*) DESC" in g.sql


def test_count_distinct_in_having_and_order_by():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT DISTINCT", ">", 2),),
                     order_by=(("VMwareCluster", "ClusterID", "ASC", "COUNT DISTINCT"),))
    assert 'HAVING COUNT(DISTINCT "VMwareCluster"."ClusterID") > :h0' in g.sql
    assert 'ORDER BY COUNT(DISTINCT "VMwareCluster"."ClusterID") ASC' in g.sql


def test_existing_aggregates_unchanged():
    # Backward compat: the five original tokens still render func(col).
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID", agg="COUNT")))
    assert 'COUNT("VMwareCluster"."ClusterID")' in g.sql
    assert "COUNT(*)" not in g.sql
    assert "DISTINCT" not in g.sql


def test_aggregate_only_in_having_triggers_group_by():
    # An aggregate that appears ONLY in HAVING (not in the SELECT list) must still
    # force GROUP BY over the non-aggregated select columns — else strict engines
    # reject "Networks.VLAN must appear in GROUP BY".
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     having=(Having("VMwareCluster", "ClusterID", "COUNT", ">", 1),))
    assert 'GROUP BY "Networks"."VLAN"' in g.sql


def test_aggregate_only_in_order_by_triggers_group_by():
    # Same for an aggregate that appears ONLY in ORDER BY.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("VMwareCluster", "ClusterID", "DESC", "COUNT"),))
    assert 'GROUP BY "Networks"."VLAN"' in g.sql


def test_no_aggregate_anywhere_still_no_group_by():
    # Backward compat guard: a plain ORDER BY (no aggregate) and no HAVING must
    # NOT introduce a GROUP BY.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("Networks", "VLAN", "ASC"),))
    assert "GROUP BY" not in g.sql


def test_all_selects_aggregated_with_having_emits_no_group_by():
    # All select columns aggregated -> no group key -> single-row aggregate, no
    # GROUP BY, even though HAVING carries an aggregate.
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN", agg="COUNT"),),
                     having=(Having("Networks", "VLAN", "COUNT", ">", 1),))
    assert "GROUP BY" not in g.sql
