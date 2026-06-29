"""Extract user-routine references from a view definition (read-only, sqlglot).

A view that calls a stored procedure/function — or an Oracle package routine —
holds part of its data logic outside plain join/FK lineage. This module finds
which *reflected* routines a view definition references: it parses the SQL and
matches function-call names (and package qualifiers) against the known routine
names. No DB access, no execution.
"""
from sqlglot import exp, parse_one
from sqlglot.errors import SqlglotError

# This project's dialect names → sqlglot's (mirrors core.sqlanalyze).
_SQLGLOT_DIALECT = {
    "sqlite": "sqlite",
    "postgresql": "postgres",
    "mysql": "mysql",
    "mssql": "tsql",
    "oracle": "oracle",
}


def referenced_routines(definition, known_routine_names, dialect=None):
    """Return the reflected routine names referenced by a view definition.

    Args:
        definition: raw view definition SQL (may be empty).
        known_routine_names: iterable of reflected routine names (ground truth).
        dialect: this project's dialect name (e.g. "oracle"); mapped to sqlglot.

    Returns:
        Sorted, de-duplicated tuple of the canonical names (original casing from
        known_routine_names) referenced as function calls in the definition.
        Empty on empty definition, empty known set, parse failure, or no match.
    """
    if not definition or not definition.strip():
        return ()
    canon = {n.upper(): n for n in known_routine_names}
    if not canon:
        return ()
    try:
        tree = parse_one(definition, read=_SQLGLOT_DIALECT.get(dialect or ""))
    except SqlglotError:
        return ()
    if tree is None:
        return ()

    hits = set()
    for call in tree.find_all(exp.Anonymous):
        candidates = {call.name}
        # Package-qualified call (PKG.FN(...) / SCHEMA.PKG.FN(...)): the qualifier
        # lives on the parent Dot's left side. Collect every identifier there so
        # the package name can match a reflected package routine. This also adds
        # the schema part (e.g. SCHEMA) as a candidate; it only ever matches when
        # that name is itself a known routine, so the "confirmed-match" guarantee
        # holds (a stray schema name equal to a routine name would be a rare FP).
        parent = call.parent
        if isinstance(parent, exp.Dot):
            for ident in parent.left.find_all(exp.Identifier):
                candidates.add(ident.name)
        for cand in candidates:
            if cand and cand.upper() in canon:
                hits.add(canon[cand.upper()])
    return tuple(sorted(hits))
