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
