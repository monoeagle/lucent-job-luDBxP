"""Heuristic detection of implied (undeclared) foreign keys.

A column ``c`` in table A implies a relationship to table B when either
  * **exact:** ``c`` equals B's single-column primary-key name, or
  * **suffix:** ``c`` ends in an id-suffix and its stem names table B, whose
    single-column primary key is a conventional id form (``id``/``uuid``/``guid``
    or ``<stem>id``).
In all cases A != B, base types are compatible, and no declared FK ``A.c -> B``
already exists. Each hit carries a discrete confidence ("hoch"/"mittel"/"niedrig")
and a short German reason. Conservative variant of SchemaSpy's name heuristic.
"""
import re
from dataclasses import dataclass

from core.model import Schema

_ID_SUFFIXES = ("id", "uuid", "guid")       # recognised id endings (normalised)
_GENERIC_PK = {"id", "uuid", "guid"}        # conventional generic primary keys
_RANK = {"hoch": 3, "mittel": 2, "niedrig": 1}


@dataclass(frozen=True)
class ImpliedFK:
    table: str        # owning table (where the column lives)
    column: str
    ref_table: str
    ref_column: str   # the referenced (PK) column name in ref_table
    confidence: str = "hoch"          # "hoch" | "mittel" | "niedrig"
    reason: str = "exakter PK-Name"   # short German match reason


def _base_type(type_str: str) -> str:
    """Return the comparable base of a column type ('VARCHAR(50)' -> 'VARCHAR')."""
    return type_str.split("(")[0].strip().upper()


def _normalize(name: str) -> str:
    """Lowercase, strip non-alphanumerics ('Customer_ID' -> 'customerid')."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _strip_id_suffix(norm_col: str) -> str | None:
    """Entity stem of a normalised column ending in an id-suffix, else None.

    'customerid' -> 'customer', 'orderuuid' -> 'order'. Returns None when no
    known suffix is present or the remaining stem is shorter than 2 chars.
    """
    for suf in _ID_SUFFIXES:
        if norm_col.endswith(suf) and len(norm_col) - len(suf) >= 2:
            return norm_col[: -len(suf)]
    return None


def _singularize(norm_name: str) -> str:
    """Drop a trailing plural 'es'/'s' ('customers' -> 'customer')."""
    if norm_name.endswith("es") and len(norm_name) > 3:
        return norm_name[:-2]
    if norm_name.endswith("s") and len(norm_name) > 2:
        return norm_name[:-1]
    return norm_name


def find_implied_fks(schema: Schema) -> tuple[ImpliedFK, ...]:
    """Detect implied foreign keys via name heuristics with a confidence score.

    Args:
        schema: The reflected schema.

    Returns:
        One ImpliedFK per detected relationship, sorted by
        (table, column, ref_table). Each carries a confidence and reason.
    """
    col_type: dict[tuple[str, str], str] = {}
    pk_targets: dict[str, list[str]] = {}                 # exact pk-name -> tables
    # normalized / singularized table name -> [(table, pk_name, normalized_pk)]
    by_norm: dict[str, list[tuple[str, str, str]]] = {}
    by_singular: dict[str, list[tuple[str, str, str]]] = {}

    for t in schema.tables:
        for c in t.columns:
            col_type[(t.name, c.name)] = _base_type(c.type)
        if len(t.primary_key) == 1:
            pk = t.primary_key[0]
            pk_targets.setdefault(pk, []).append(t.name)
            norm = _normalize(t.name)
            entry = (t.name, pk, _normalize(pk))
            by_norm.setdefault(norm, []).append(entry)
            by_singular.setdefault(_singularize(norm), []).append(entry)

    # (table, column, ref_table) -> (rank, ImpliedFK); keep the highest rank.
    best: dict[tuple[str, str, str], tuple[int, ImpliedFK]] = {}

    def consider(a, col, b_name, ref_col, confidence, reason, declared):
        if b_name == a:
            return  # no self-implied relationship
        if (col, b_name) in declared:
            return  # already a declared FK on this column -> table
        if col_type.get((a, col)) != col_type.get((b_name, ref_col)):
            return  # incompatible base types
        key = (a, col, b_name)
        rank = _RANK[confidence]
        if key not in best or rank > best[key][0]:
            best[key] = (rank, ImpliedFK(a, col, b_name, ref_col, confidence, reason))

    for t in schema.tables:
        declared = {(local, fk.ref_table)
                    for fk in t.foreign_keys for local in fk.columns}
        for c in t.columns:
            # Strategy 1: exact column-name == single-column PK name -> hoch
            for b_name in pk_targets.get(c.name, []):
                consider(t.name, c.name, b_name, c.name,
                         "hoch", "exakter PK-Name", declared)
            # Strategy 2/3: suffix -> table name with a conventional generic PK
            stem = _strip_id_suffix(_normalize(c.name))
            if stem:
                allowed = _GENERIC_PK | {stem + "id"}
                for b_name, pk, norm_pk in by_norm.get(stem, []):
                    if norm_pk in allowed:
                        consider(t.name, c.name, b_name, pk, "mittel",
                                 f"Suffix→Tabelle ({c.name}→{b_name})", declared)
                for b_name, pk, norm_pk in by_singular.get(stem, []):
                    if norm_pk in allowed:
                        consider(t.name, c.name, b_name, pk, "niedrig",
                                 "Suffix→Tabelle (Plural)", declared)

    out = [v[1] for v in best.values()]
    out.sort(key=lambda i: (i.table, i.column, i.ref_table))
    return tuple(out)
