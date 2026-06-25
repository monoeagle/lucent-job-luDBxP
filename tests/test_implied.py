from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.implied import find_implied_fks
from core.graph import build_graph
from core.pathfinder import find_paths


def test_loader_reflects_primary_keys(inventory_nofk_url):
    schema = SqlAlchemyLoader(inventory_nofk_url).load()
    assert schema.table("OperatingSystems").primary_key == ("OSID",)
    assert schema.table("VirtualMachines").primary_key == ("VMID",)


def test_implied_fks_detected_without_declared(inventory_nofk_url):
    schema = SqlAlchemyLoader(inventory_nofk_url).load()
    triples = {(i.table, i.column, i.ref_table) for i in find_implied_fks(schema)}
    assert ("VirtualMachines", "OSID", "OperatingSystems") in triples
    assert ("VirtualMachines", "NetworkID", "Networks") in triples
    assert ("VirtualMachines", "ClusterID", "VMwareCluster") in triples


def test_no_implied_when_relationships_are_declared(inventory_url):
    # inventory_url declares all FKs -> nothing left to imply.
    schema = SqlAlchemyLoader(inventory_url).load()
    assert find_implied_fks(schema) == ()


def test_graph_without_implied_has_no_edges_in_nofk(inventory_nofk_url):
    schema = SqlAlchemyLoader(inventory_nofk_url).load()
    assert build_graph(schema).number_of_edges() == 0


def test_graph_with_implied_connects_and_marks_edges(inventory_nofk_url):
    schema = SqlAlchemyLoader(inventory_nofk_url).load()
    g = build_graph(schema, include_implied=True)
    assert g.has_edge("VirtualMachines", "OperatingSystems")
    assert g["VirtualMachines"]["OperatingSystems"]["implied"] is True


def test_join_path_found_over_implied_edges(inventory_nofk_url):
    schema = SqlAlchemyLoader(inventory_nofk_url).load()
    g = build_graph(schema, include_implied=True)
    paths = find_paths(g, "Networks", "VMwareCluster")
    assert paths
    assert "VirtualMachines" in paths[0].tables
