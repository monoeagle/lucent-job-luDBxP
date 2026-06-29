import pytest
from core.model import Column, ForeignKey, Table, Schema


def _sample() -> Schema:
    return Schema(tables=(
        Table("Networks", (Column("NetworkID", "INTEGER"), Column("VLAN", "INTEGER")), ()),
        Table("VirtualMachines",
              (Column("VMID", "INTEGER"), Column("NetworkID", "INTEGER")),
              (ForeignKey.single("NetworkID", "Networks", "NetworkID"),)),
    ))


def test_table_lookup_returns_table():
    assert _sample().table("Networks").name == "Networks"


def test_table_lookup_unknown_raises():
    with pytest.raises(KeyError):
        _sample().table("Nope")


def test_has_column():
    s = _sample()
    assert s.has_column("Networks", "VLAN") is True
    assert s.has_column("Networks", "Ghost") is False
    assert s.has_column("Ghost", "VLAN") is False


def test_column_carries_comment_default_empty():
    assert Column("a", "INT").comment == ""
    assert Column("a", "INT", comment="fachliche Beschreibung").comment == "fachliche Beschreibung"


def test_table_carries_comment_default_empty():
    cols = (Column("a", "INT"),)
    assert Table("t", cols, ()).comment == ""
    assert Table("t", cols, (), comment="Auftragskopf").comment == "Auftragskopf"


def test_table_positional_constructor_still_works():
    # comment ist letztes Feld mit Default → bestehende positionsbasierte
    # Konstruktoren (name, cols, fks, pk, uniques, uidx) brechen nicht.
    cols = (Column("a", "INT"),)
    t = Table("t", cols, (), ("a",), (("a",),), (("a",),))
    assert t.primary_key == ("a",) and t.comment == ""


# ===== AP-54: Cross-Schema-FK-Diagnose =====

def _tbl(name, fks):
    return Table(name, (), tuple(fks))


def test_foreign_key_ref_schema_defaults_empty():
    fk = ForeignKey("Product", (("ProductID", "ProductID"),))
    assert fk.ref_schema == ""


def test_cross_schema_fks_lists_foreign_schema_edge():
    fk = ForeignKey("Product", (("ProductID", "ProductID"),), "Production")
    sch = Schema((_tbl("SalesOrderDetail", [fk]),))
    edges = sch.cross_schema_fks("Sales")
    assert edges == ({
        "from_table": "SalesOrderDetail",
        "columns": ["ProductID"],
        "to_schema": "Production",
        "to_table": "Product",
        "to_columns": ["ProductID"],
    },)


def test_cross_schema_fks_excludes_same_schema():
    same = ForeignKey("Customer", (("CustomerID", "CustomerID"),), "Sales")
    none = ForeignKey("Customer", (("CustomerID", "CustomerID"),))  # ref_schema=""
    sch = Schema((_tbl("SalesOrderHeader", [same, none]),))
    assert sch.cross_schema_fks("Sales") == ()


def test_cross_schema_fks_empty_current_treats_any_ref_schema_as_cross():
    fk = ForeignKey("Product", (("ProductID", "ProductID"),), "Production")
    sch = Schema((_tbl("SalesOrderDetail", [fk]),))
    assert len(sch.cross_schema_fks("")) == 1


# ===== AP-63·S3: Routine + Synonym Dataclasses =====

def test_routine_carries_kind_and_sql():
    from core.model import Routine
    r = Routine("calc_total", "function", "CREATE FUNCTION calc_total() ...")
    assert r.name == "calc_total"
    assert r.kind == "function"
    assert "CREATE FUNCTION" in r.sql


def test_routine_sql_defaults_empty():
    from core.model import Routine
    assert Routine("p", "procedure").sql == ""


def test_synonym_carries_target():
    from core.model import Synonym
    s = Synonym("emp_syn", "HR.EMPLOYEES")
    assert s.name == "emp_syn"
    assert s.target == "HR.EMPLOYEES"


def test_schema_routines_synonyms_default_empty():
    from core.model import Schema
    sch = Schema(tables=())
    assert sch.routines == ()
    assert sch.synonyms == ()


def test_schema_positional_constructor_still_works_with_routines():
    # Bestehende positionale Aufrufe (bis materialized_views) bleiben gültig.
    from core.model import Schema, View, Sequence
    sch = Schema((), (), (), (Sequence("s"),), (View("mv", ()),))
    assert sch.sequences[0].name == "s"
    assert sch.routines == ()
    assert sch.synonyms == ()
