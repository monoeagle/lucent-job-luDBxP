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


from core.model import Schema, Table, Column, ForeignKey


def _c(name, type_="INTEGER"):
    return Column(name, type_)


def test_exact_pk_name_is_high_confidence():
    schema = Schema((
        Table("Kunde", (_c("KundeID"), _c("Name", "TEXT")), (), primary_key=("KundeID",)),
        Table("Bestellung", (_c("BestellungID"), _c("KundeID")), (), primary_key=("BestellungID",)),
    ))
    hit = {(i.table, i.column, i.ref_table): i for i in find_implied_fks(schema)}[
        ("Bestellung", "KundeID", "Kunde")]
    assert hit.confidence == "hoch"
    assert hit.ref_column == "KundeID"
    assert hit.reason == "exakter PK-Name"


def test_suffix_to_table_generic_pk_is_medium():
    schema = Schema((
        Table("Kunde", (_c("id"), _c("name", "TEXT")), (), primary_key=("id",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id")), (), primary_key=("nr",)),
    ))
    hit = {(i.column, i.ref_table): i for i in find_implied_fks(schema)}[("kunde_id", "Kunde")]
    assert hit.confidence == "mittel"
    assert hit.ref_column == "id"
    assert "Suffix" in hit.reason


def test_plural_table_is_low_confidence():
    schema = Schema((
        Table("Customers", (_c("id"), _c("name", "TEXT")), (), primary_key=("id",)),
        Table("Order", (_c("nr"), _c("customer_id")), (), primary_key=("nr",)),
    ))
    hit = {(i.column, i.ref_table): i for i in find_implied_fks(schema)}[("customer_id", "Customers")]
    assert hit.confidence == "niedrig"
    assert hit.ref_column == "id"


def test_no_hit_when_target_pk_is_not_a_generic_id():
    # Stem 'kunde' names table Kunde, but Kunde's PK is 'name' -> not a generic id form.
    schema = Schema((
        Table("Kunde", (_c("name", "TEXT"), _c("ort", "TEXT")), (), primary_key=("name",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id")), (), primary_key=("nr",)),
    ))
    assert all(i.ref_table != "Kunde" for i in find_implied_fks(schema))


def test_no_hit_when_base_type_incompatible():
    schema = Schema((
        Table("Kunde", (_c("id"), _c("x", "TEXT")), (), primary_key=("id",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id", "TEXT")), (), primary_key=("nr",)),
    ))
    assert find_implied_fks(schema) == ()


def test_short_stem_yields_no_suffix_match():
    # column 'id' -> stem '' (< 2 chars) -> no suffix match; the exact-name path
    # (Other.id == It.id) still fires as 'hoch'.
    schema = Schema((
        Table("It", (_c("id"),), (), primary_key=("id",)),
        Table("Other", (_c("nr"), _c("id")), (), primary_key=("nr",)),
    ))
    assert all(i.confidence == "hoch" for i in find_implied_fks(schema))


def test_declared_fk_is_excluded():
    schema = Schema((
        Table("Kunde", (_c("id"),), (), primary_key=("id",)),
        Table("Bestellung", (_c("nr"), _c("kunde_id")),
              (ForeignKey.single("kunde_id", "Kunde", "id"),), primary_key=("nr",)),
    ))
    assert all(i.ref_table != "Kunde" for i in find_implied_fks(schema))


def test_results_are_sorted_deterministically():
    schema = Schema((
        Table("A", (_c("id"),), (), primary_key=("id",)),
        Table("B", (_c("id"),), (), primary_key=("id",)),
        Table("C", (_c("nr"), _c("a_id"), _c("b_id")), (), primary_key=("nr",)),
    ))
    keys = [(i.table, i.column, i.ref_table) for i in find_implied_fks(schema)]
    assert keys == sorted(keys)
