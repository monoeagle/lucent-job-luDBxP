"""Schema domain model: plain immutable dataclasses, no Flask/SQLAlchemy deps."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    comment: str = ""


@dataclass(frozen=True)
class ForeignKey:
    """A foreign key from the owning table to ``ref_table``.

    ``column_pairs`` holds one ``(local_column, ref_column)`` tuple per key
    column, so single-column and composite (multi-column) FKs share one shape.
    A composite FK joins on *all* pairs combined with AND; two *separate*
    single-column FKs between the same tables are two distinct ForeignKey
    objects (alternative join routes), never merged.
    """
    ref_table: str
    column_pairs: tuple[tuple[str, str], ...]  # ((local, ref), ...)

    @classmethod
    def single(cls, column: str, ref_table: str, ref_column: str) -> "ForeignKey":
        """Convenience constructor for a single-column FK."""
        return cls(ref_table, ((column, ref_column),))

    @property
    def columns(self) -> tuple[str, ...]:
        """Local column names, in key order."""
        return tuple(local for local, _ in self.column_pairs)

    @property
    def ref_columns(self) -> tuple[str, ...]:
        """Referenced column names, in key order."""
        return tuple(ref for _, ref in self.column_pairs)

    @property
    def is_composite(self) -> bool:
        """True if the FK spans more than one column pair."""
        return len(self.column_pairs) > 1


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    foreign_keys: tuple[ForeignKey, ...]
    primary_key: tuple[str, ...] = ()  # primary-key column names
    # Each inner tuple is the column names of one UNIQUE constraint (table-level
    # or inline). The primary key is held separately in `primary_key`.
    unique_constraints: tuple[tuple[str, ...], ...] = ()
    # Column names of UNIQUE indexes (full-column, non-partial). Kept separate
    # from `unique_constraints`: a unique index is not a declared constraint.
    unique_indexes: tuple[tuple[str, ...], ...] = ()
    # Tabellenkommentar (COMMENT ON TABLE). Leerer String = kein Kommentar.
    comment: str = ""


@dataclass(frozen=True)
class View:
    name: str
    columns: tuple[Column, ...]
    definition: str = ""


@dataclass(frozen=True)
class Schema:
    tables: tuple[Table, ...]
    views: tuple[View, ...] = ()

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
