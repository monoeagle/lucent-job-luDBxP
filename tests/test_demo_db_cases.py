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


def test_composite_fk_joins_only_first_column_pair(demo_graph):
    # Documented v1 limitation: VMPlacement -> ResourcePool is a composite FK
    # (ClusterID, PoolKey) but only one column pair is emitted in the JOIN.
    path = find_paths(demo_graph, "VirtualMachine", "ResourcePool")[0]
    sql = generate_sql(
        path, (Selection("VirtualMachine", "Name"), Selection("ResourcePool", "Name"))
    ).sql
    join_line = next(ln for ln in sql.splitlines() if ln.startswith("JOIN ResourcePool"))
    assert join_line.count("=") == 1
    assert " AND " not in join_line  # would mean PoolKey was also joined


def test_multiple_fks_between_two_tables_accumulate(demo_graph):
    # Replication has two FKs to Datastore (Primary + Secondary).
    joins = demo_graph["Replication"]["Datastore"]["joins"]
    assert len(joins) == 2
    cols = {edge[1] for edge in joins}
    assert cols == {"PrimaryDatastoreID", "SecondaryDatastoreID"}


def test_self_referencing_fk_is_a_self_loop(demo_graph):
    # Folder.ParentFolderID -> Folder produces a self-loop edge in the graph.
    assert demo_graph.has_edge("Folder", "Folder")


def test_isolated_table_raises_no_path(demo_graph):
    # LicenseKey has no foreign key to anything.
    with pytest.raises(NoPathError):
        find_paths(demo_graph, "LicenseKey", "Datacenter")


def test_filter_weave_on_real_schema_has_no_duplicate_tables(demo_graph):
    path = find_paths(
        demo_graph, "Network", "Cluster", filter_tables=("OperatingSystem",)
    )[0]
    assert "OperatingSystem" in path.tables
    assert len(path.tables) == len(set(path.tables))  # each table joined once
