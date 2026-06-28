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
