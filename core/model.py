"""Schema domain model: plain immutable dataclasses, no Flask/SQLAlchemy deps."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    type: str


@dataclass(frozen=True)
class ForeignKey:
    column: str       # local column on the owning table
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    foreign_keys: tuple[ForeignKey, ...]


@dataclass(frozen=True)
class Schema:
    tables: tuple[Table, ...]

    def table(self, name: str) -> Table:
        for t in self.tables:
            if t.name == name:
                return t
        raise KeyError(name)

    def has_column(self, table: str, column: str) -> bool:
        try:
            t = self.table(table)
        except KeyError:
            return False
        return any(c.name == column for c in t.columns)
