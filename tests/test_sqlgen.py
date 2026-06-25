import pytest

from core.pathfinder import JoinPath, JoinStep
from core.sqlgen import generate_sql, Selection, Filter


def _path():
    return JoinPath(
        tables=("Networks", "VirtualMachines", "VMwareCluster"),
        steps=(
            JoinStep("Networks", "NetworkID", "VirtualMachines", "NetworkID"),
            JoinStep("VirtualMachines", "ClusterID", "VMwareCluster", "ClusterID"),
        ),
    )


def test_basic_select_join():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),
                              Selection("VMwareCluster", "ClusterID")))
    assert "SELECT" in g.sql
    assert "FROM Networks" in g.sql
    assert "JOIN VirtualMachines ON Networks.NetworkID = VirtualMachines.NetworkID" in g.sql
    assert "JOIN VMwareCluster ON VirtualMachines.ClusterID = VMwareCluster.ClusterID" in g.sql
    assert g.params == {}


def test_filter_uses_named_placeholder():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "=", 7),))
    assert "WHERE VirtualMachines.OSID = :p0" in g.sql
    assert g.params == {"p0": 7}
    # value must never be inlined
    assert "= 7" not in g.sql


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
    assert "Networks.VLAN" in g.sql
    assert "VMwareCluster.ClusterID" in g.sql
    assert "VirtualMachines.VMID" in g.sql
    # All three must appear on the same SELECT line
    select_line = g.sql.splitlines()[0]
    assert "Networks.VLAN" in select_line
    assert "VMwareCluster.ClusterID" in select_line
    assert "VirtualMachines.VMID" in select_line


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
    assert "ORDER BY VirtualMachines.VMID DESC" in g.sql


def test_order_by_asc():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("Networks", "VLAN", "ASC"),))
    assert "ORDER BY Networks.VLAN ASC" in g.sql


def test_order_by_multiple_cols():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     order_by=(("Networks", "VLAN", "ASC"),
                               ("VirtualMachines", "VMID", "DESC")))
    assert "ORDER BY Networks.VLAN ASC, VirtualMachines.VMID DESC" in g.sql


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
    assert "VirtualMachines.OSID IS NULL" in g.sql
    assert not g.params  # no placeholder generated


def test_is_not_null_no_placeholder():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "OSID", "IS NOT NULL", None),))
    assert "VirtualMachines.OSID IS NOT NULL" in g.sql
    assert not g.params


def test_in_multiple_placeholders():
    g = generate_sql(_path(),
                     selects=(Selection("Networks", "VLAN"),),
                     filters=(Filter("VirtualMachines", "VMID", "IN", [1, 2, 3]),))
    assert "VirtualMachines.VMID IN (:p0_0, :p0_1, :p0_2)" in g.sql
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
    assert "VirtualMachines.VMID BETWEEN :p0_lo AND :p0_hi" in g.sql
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
    assert "ORDER BY VirtualMachines.VMID DESC" in g.sql
    assert "LIMIT 100" in g.sql
    # ORDER BY must come before LIMIT
    assert g.sql.index("ORDER BY") < g.sql.index("LIMIT")
