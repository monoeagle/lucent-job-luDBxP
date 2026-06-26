"""Heuristic detection of implied (undeclared) foreign keys.

A column ``c`` in table A implies a relationship to table B when B has a
single-column primary key named ``c`` of a compatible base type, A != B, and
no declared FK ``A.c -> B`` already exists. This is a conservative variant of
SchemaSpy's name-based implied-relationship heuristic.
"""
from dataclasses import dataclass

from core.model import Schema


@dataclass(frozen=True)
class ImpliedFK:
    table: str        # owning table (where the column lives)
    column: str
    ref_table: str
    ref_column: str   # == column (the shared PK name)


def _base_type(type_str: str) -> str:
    """Return the comparable base of a column type ('VARCHAR(50)' -> 'VARCHAR')."""
    return type_str.split("(")[0].strip().upper()


def find_implied_fks(schema: Schema) -> tuple[ImpliedFK, ...]:
    """Detect implied foreign keys via the name-on-primary-key heuristic.

    Args:
        schema: The reflected schema.

    Returns:
        One ImpliedFK per detected relationship.
    """
    # Single-column PK name -> tables owning that PK.
    pk_targets: dict[str, list[str]] = {}
    col_type: dict[tuple[str, str], str] = {}
    for t in schema.tables:
        for c in t.columns:
            col_type[(t.name, c.name)] = _base_type(c.type)
        if len(t.primary_key) == 1:
            pk_targets.setdefault(t.primary_key[0], []).append(t.name)

    implied: list[ImpliedFK] = []
    for t in schema.tables:
        declared = {(local, fk.ref_table)
                    for fk in t.foreign_keys for local in fk.columns}
        for c in t.columns:
            for target in pk_targets.get(c.name, []):
                if target == t.name:
                    continue  # no self-implied relationship
                if (c.name, target) in declared:
                    continue  # already a declared FK on this column -> table
                if col_type.get((t.name, c.name)) != col_type.get((target, c.name)):
                    continue  # incompatible base types
                implied.append(ImpliedFK(t.name, c.name, target, c.name))
    return tuple(implied)
