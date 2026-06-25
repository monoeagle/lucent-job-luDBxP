"""Reconstruct a readable CREATE TABLE statement from a Table model.

This is a portable, dialect-neutral rendering for display (the "SQL" tab),
not a byte-exact copy of the original DDL.
"""
from core.model import Table


def table_ddl(table: Table) -> str:
    """Render a CREATE TABLE statement for the given table.

    Args:
        table: The reflected table.

    Returns:
        A formatted CREATE TABLE string with columns, primary key, and FKs.
    """
    single_pk = table.primary_key[0] if len(table.primary_key) == 1 else None
    lines = []
    for c in table.columns:
        suffix = " PRIMARY KEY" if c.name == single_pk else ""
        lines.append(f"    {c.name} {c.type}{suffix}")
    if len(table.primary_key) > 1:
        lines.append(f"    PRIMARY KEY ({', '.join(table.primary_key)})")
    for fk in table.foreign_keys:
        lines.append(
            f"    FOREIGN KEY ({fk.column}) "
            f"REFERENCES {fk.ref_table}({fk.ref_column})"
        )
    return f"CREATE TABLE {table.name} (\n" + ",\n".join(lines) + "\n);"
