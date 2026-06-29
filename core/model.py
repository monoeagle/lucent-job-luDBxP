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
    ref_schema: str = ""   # Schema, auf das der FK zeigt, falls abweichend; "" = gleiches/unbekanntes Schema

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
class Index:
    name: str
    columns: tuple[str, ...]
    unique: bool = False


@dataclass(frozen=True)
class CheckConstraint:
    name: str        # "" = unbenannt
    sqltext: str


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
    # Alle Indizes (Anzeige, AP-63·S1); unabhängig von unique_indexes (1-1-Sicht).
    indexes: tuple[Index, ...] = ()
    # Check-Constraints (Anzeige, AP-63·S1).
    check_constraints: tuple[CheckConstraint, ...] = ()


@dataclass(frozen=True)
class View:
    name: str
    columns: tuple[Column, ...]
    definition: str = ""


@dataclass(frozen=True)
class Sequence:
    name: str


@dataclass(frozen=True)
class Trigger:
    name: str
    table: str       # besitzende Tabelle (tbl_name); "" falls unbekannt
    sql: str         # CREATE TRIGGER …-Quelltext


@dataclass(frozen=True)
class Routine:
    name: str
    kind: str        # "procedure" | "function" | "package"
    sql: str = ""    # Quelltext (CREATE …/Package-Source); "" falls nicht lesbar


@dataclass(frozen=True)
class Synonym:
    name: str
    target: str      # (owner.)object — Zielobjekt; kein Quelltext


@dataclass(frozen=True)
class Schema:
    tables: tuple[Table, ...]
    views: tuple[View, ...] = ()
    triggers: tuple[Trigger, ...] = ()
    sequences: tuple[Sequence, ...] = ()
    materialized_views: tuple[View, ...] = ()   # Matviews reusen das View-Shape
    routines: tuple[Routine, ...] = ()
    synonyms: tuple[Synonym, ...] = ()

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

    def cross_schema_fks(self, current_schema: str) -> tuple[dict, ...]:
        """FK-Kanten, deren ref_schema gesetzt und != dem reflektierten Schema ist."""
        out = []
        for t in self.tables:
            for fk in t.foreign_keys:
                if fk.ref_schema and fk.ref_schema != current_schema:
                    out.append({
                        "from_table": t.name,
                        "columns": list(fk.columns),
                        "to_schema": fk.ref_schema,
                        "to_table": fk.ref_table,
                        "to_columns": list(fk.ref_columns),
                    })
        return tuple(out)
