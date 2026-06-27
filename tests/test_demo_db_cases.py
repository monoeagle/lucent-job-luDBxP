"""Integration tests over the portable demo CMDB, one per scenario it covers.

Each test builds a fresh demo DB in a tmp dir (via build()) and drives the
real loader -> graph -> pathfinder -> sqlgen stack, so the demo data and the
tool are verified together.
"""
import pytest

from sample_data.build_demo_db import build
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.graph import build_graph
from core.pathfinder import find_paths, NoPathError
from core.sqlgen import generate_sql, Selection, Filter


@pytest.fixture
def demo_graph(tmp_path):
    db = tmp_path / "demo_cmdb.db"
    build(str(db))
    schema = SqlAlchemyLoader(f"sqlite:///{db}").load()
    return build_graph(schema)


def test_diamond_yields_two_equally_short_paths(demo_graph):
    # VirtualMachine reaches Datacenter via Host AND via Network -- both 2 hops.
    paths = find_paths(demo_graph, "VirtualMachine", "Datacenter")
    assert len(paths) >= 2
    assert len(paths[0].steps) == 2 and len(paths[1].steps) == 2
    second_hops = {p.tables[1] for p in paths[:2]}
    assert second_hops == {"Host", "Network"}


def test_diamond_path_order_is_deterministic(demo_graph):
    a = [p.tables for p in find_paths(demo_graph, "VirtualMachine", "Datacenter")]
    b = [p.tables for p in find_paths(demo_graph, "VirtualMachine", "Datacenter")]
    assert a == b


def test_composite_fk_joins_all_column_pairs(demo_graph):
    # VMPlacement -> ResourcePool is a composite FK (ClusterID, PoolKey): it is
    # ONE join option spanning BOTH column pairs, emitted as ON ... AND ...
    options = demo_graph["VMPlacement"]["ResourcePool"]["joins"]
    assert len(options) == 1                 # one composite FK, not two alternatives
    assert len(options[0].pairs) == 2        # both column pairs in a single edge

    path = find_paths(demo_graph, "VirtualMachine", "ResourcePool")[0]
    sql = generate_sql(
        path, (Selection("VirtualMachine", "Name"), Selection("ResourcePool", "Name"))
    ).sql
    # AP-43: composite FK → each pair on its own ON/AND line.
    assert 'JOIN "ResourcePool"' in sql
    assert 'ON "VMPlacement"."ClusterID" = "ResourcePool"."ClusterID"' in sql
    assert 'AND "VMPlacement"."PoolKey"' in sql and '= "ResourcePool"."PoolKey"' in sql


def test_multiple_fks_between_two_tables_stay_alternative(demo_graph):
    # Replication has two SEPARATE FKs to Datastore (Primary + Secondary).
    # These are alternative single-column join routes, never merged into AND.
    options = demo_graph["Replication"]["Datastore"]["joins"]
    assert len(options) == 2                  # two distinct join options
    assert all(len(o.pairs) == 1 for o in options)  # each single-column
    local_cols = {o.pairs[0][0] for o in options}
    assert local_cols == {"PrimaryDatastoreID", "SecondaryDatastoreID"}


def test_self_referencing_fk_is_a_self_loop(demo_graph):
    # Folder.ParentFolderID -> Folder produces a self-loop edge in the graph.
    assert demo_graph.has_edge("Folder", "Folder")


def test_isolated_table_raises_no_path(demo_graph):
    # LicenseKey has no foreign key to anything.
    with pytest.raises(NoPathError):
        find_paths(demo_graph, "LicenseKey", "Datacenter")


def test_filter_weave_on_real_schema_has_no_duplicate_tables(demo_graph):
    path = find_paths(
        demo_graph, "Network", "Cluster", required_tables=("OperatingSystem",)
    )[0]
    assert "OperatingSystem" in path.tables
    assert len(path.tables) == len(set(path.tables))  # each table joined once
