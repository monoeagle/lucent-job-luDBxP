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
