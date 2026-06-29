"""Live-DB schema loader via SQLAlchemy reflection (SQLite + Postgres for v1)."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from core.model import Column, ForeignKey, Index, CheckConstraint, Table, View, Schema, Trigger, Sequence, Routine, Synonym
from core.schema_loader import SchemaLoader


def _odbc_driver_hint(exc) -> "str | None":
    """Return a clear hint when the error is a missing ODBC driver, else None.

    pyodbc surfaces a missing driver as SQLSTATE IM002 / "Data source name not
    found and no default driver specified" / "Can't open lib …". We translate
    that into an actionable message instead of leaking the raw exception.
    """
    msg = str(exc).lower()
    markers = ("im002", "data source name not found", "can't open lib",
               "no default driver", "libodbc")
    if any(m in msg for m in markers):
        return ("ODBC-Treiber nicht gefunden. Fuer MS SQL Server bitte den "
                "'ODBC Driver 18 for SQL Server' installieren — Windows: "
                "Microsoft-Installer; Linux: unixODBC + msodbcsql18.")
    return None


def _reflect_triggers(engine) -> tuple:
    """Read-only trigger reflection. SQLite via sqlite_master; other dialects
    return () for now (SQLAlchemy has no native trigger API)."""
    dialect_name = getattr(getattr(engine, "dialect", None), "name", "")
    if dialect_name != "sqlite":
        return ()
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT name, tbl_name, sql FROM sqlite_master "
                "WHERE type='trigger' AND sql IS NOT NULL ORDER BY name"
            )).fetchall()
        return tuple(Trigger(r[0], r[1] or "", r[2] or "") for r in rows)
    except SQLAlchemyError:
        return ()


def _reflect_routines(engine, schema=None) -> tuple:
    """Read-only routine reflection (procedures/functions/packages) via
    per-dialect catalog SQL. PG: pg_proc; Oracle: all_objects+all_source;
    MSSQL: sys.objects+sys.sql_modules. SQLite/other → ()."""
    name = getattr(getattr(engine, "dialect", None), "name", "")
    if name not in ("postgresql", "oracle", "mssql"):
        return ()
    try:
        with engine.connect() as conn:
            if name == "postgresql":
                # pg_proc.prokind exists only on PostgreSQL >= 11; on older
                # servers this query raises and routines fall back to () below.
                rows = conn.execute(text(
                    "SELECT p.proname, p.prokind, pg_get_functiondef(p.oid) "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = :s AND p.prokind IN ('p','f') "
                    "ORDER BY p.proname"
                ), {"s": schema or "public"}).fetchall()
                return tuple(
                    Routine(r[0], "procedure" if str(r[1]) == "p" else "function", r[2] or "")
                    for r in rows
                )
            if name == "oracle":
                owner = (schema or "").upper() or conn.execute(text(
                    "SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual"
                )).scalar()
                objs = conn.execute(text(
                    "SELECT object_name, object_type FROM all_objects "
                    "WHERE owner = :o AND object_type IN ('PROCEDURE','FUNCTION','PACKAGE') "
                    "ORDER BY object_type, object_name"
                ), {"o": owner}).fetchall()
                out = []
                for oname, otype in objs:
                    src_rows = conn.execute(text(
                        "SELECT text FROM all_source WHERE owner = :o AND name = :n "
                        "AND type = :t ORDER BY line"
                    ), {"o": owner, "n": oname, "t": otype}).fetchall()
                    out.append(Routine(oname, otype.lower(), "".join(s[0] or "" for s in src_rows)))
                return tuple(out)
            if name == "mssql":
                rows = conn.execute(text(
                    "SELECT o.name, o.type, m.definition "
                    "FROM sys.objects o LEFT JOIN sys.sql_modules m "
                    "ON m.object_id = o.object_id "
                    "WHERE o.type IN ('P','FN','IF','TF') "
                    "AND SCHEMA_NAME(o.schema_id) = :s ORDER BY o.name"
                ), {"s": schema or "dbo"}).fetchall()
                return tuple(
                    Routine(r[0].strip(), "procedure" if r[1].strip() == "P" else "function", r[2] or "")
                    for r in rows
                )
    except SQLAlchemyError:
        return ()
    return ()


def _reflect_synonyms(engine, schema=None) -> tuple:
    """Read-only synonym reflection — Oracle-only (all_synonyms); other → ()."""
    name = getattr(getattr(engine, "dialect", None), "name", "")
    if name != "oracle":
        return ()
    try:
        with engine.connect() as conn:
            owner = (schema or "").upper() or conn.execute(text(
                "SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual"
            )).scalar()
            rows = conn.execute(text(
                "SELECT synonym_name, table_owner, table_name FROM all_synonyms "
                "WHERE owner = :o ORDER BY synonym_name"
            ), {"o": owner}).fetchall()
        return tuple(
            Synonym(r[0], f"{r[1]}.{r[2]}" if r[1] and r[1] != owner else r[2])
            for r in rows
        )
    except SQLAlchemyError:
        return ()


class SqlAlchemyLoader(SchemaLoader):
    """Reflects a live database schema using SQLAlchemy introspection.

    Args:
        connection_url: SQLAlchemy-compatible database URL
            (e.g. ``sqlite:///path/to/db`` or ``postgresql://user:pw@host/db``).
    """

    def __init__(self, connection_url: str) -> None:
        self._url = connection_url

    def load(self, schema=None) -> Schema:
        """Reflect the database schema and return a :class:`~core.model.Schema`.

        Args:
            schema: Optional schema name to reflect. If None (default), reflects
                the database's default schema (e.g. "main" in SQLite).

        Returns:
            A fully-populated ``Schema`` with all tables, columns, and FK edges.

        Raises:
            ConnectionError: If the database is unreachable or the URL is invalid.
        """
        try:
            engine = create_engine(self._url)
        except SQLAlchemyError as exc:
            raise ConnectionError(f"Could not create engine: {exc}") from exc
        try:
            insp = inspect(engine)
            tables = []
            for tname in insp.get_table_names(schema=schema):
                columns = tuple(
                    Column(col["name"], str(col["type"]), col.get("comment") or "")
                    for col in insp.get_columns(tname, schema=schema)
                )
                fks = []
                for fk in insp.get_foreign_keys(tname, schema=schema):
                    # Keep composite keys intact: one ForeignKey per constraint,
                    # carrying all (local, referred) column pairs. Two separate
                    # FKs between the same tables stay separate ForeignKey objects.
                    pairs = tuple(zip(
                        fk["constrained_columns"], fk["referred_columns"]
                    ))
                    fks.append(ForeignKey(fk["referred_table"], pairs, fk.get("referred_schema") or ""))
                pk = tuple(insp.get_pk_constraint(tname, schema=schema).get("constrained_columns", []))
                try:
                    uniques = tuple(
                        tuple(uc.get("column_names") or ())
                        for uc in insp.get_unique_constraints(tname, schema=schema)
                        if uc.get("column_names")
                    )
                except (SQLAlchemyError, NotImplementedError):
                    uniques = ()
                try:
                    uidx = tuple(
                        tuple(idx["column_names"])
                        for idx in insp.get_indexes(tname, schema=schema)
                        if idx.get("unique")
                        and idx.get("column_names")
                        and None not in idx["column_names"]
                        and not any(k.endswith("_where")
                                    for k in (idx.get("dialect_options") or {}))
                    )
                except (SQLAlchemyError, NotImplementedError):
                    uidx = ()
                try:
                    indexes = tuple(
                        Index(idx.get("name") or "", tuple(idx["column_names"]),
                              bool(idx.get("unique")))
                        for idx in insp.get_indexes(tname, schema=schema)
                        if idx.get("column_names") and None not in idx["column_names"]
                    )
                except (SQLAlchemyError, NotImplementedError):
                    indexes = ()
                try:
                    checks = tuple(
                        CheckConstraint(cc.get("name") or "", cc.get("sqltext") or "")
                        for cc in insp.get_check_constraints(tname, schema=schema)
                    )
                except (SQLAlchemyError, NotImplementedError):
                    checks = ()
                try:
                    tcomment = ((insp.get_table_comment(tname, schema=schema) or {})
                                .get("text") or "")
                except (NotImplementedError, SQLAlchemyError):
                    tcomment = ""
                tables.append(Table(tname, columns, tuple(fks), pk, uniques, uidx,
                                    tcomment, indexes, checks))
            views = []
            for vname in insp.get_view_names(schema=schema):
                vcols = tuple(
                    Column(col["name"], str(col["type"]))
                    for col in insp.get_columns(vname, schema=schema)
                )
                try:
                    definition = insp.get_view_definition(vname, schema=schema) or ""
                except SQLAlchemyError:
                    definition = ""
                views.append(View(vname, vcols, definition))
            try:
                sequences = tuple(
                    Sequence(n) for n in insp.get_sequence_names(schema=schema)
                )
            except (SQLAlchemyError, NotImplementedError):
                sequences = ()
            try:
                mv_names = insp.get_materialized_view_names(schema=schema)
            except (SQLAlchemyError, NotImplementedError):
                mv_names = []
            matviews = []
            for mvname in mv_names:
                try:
                    mvcols = tuple(
                        Column(c["name"], str(c["type"]))
                        for c in insp.get_columns(mvname, schema=schema)
                    )
                except SQLAlchemyError:
                    mvcols = ()
                try:
                    mvdef = insp.get_view_definition(mvname, schema=schema) or ""
                except (SQLAlchemyError, NotImplementedError):
                    mvdef = ""
                matviews.append(View(mvname, mvcols, mvdef))
            return Schema(tuple(tables), tuple(views), _reflect_triggers(engine),
                          sequences, tuple(matviews),
                          _reflect_routines(engine, schema),
                          _reflect_synonyms(engine, schema))
        except SQLAlchemyError as exc:
            hint = _odbc_driver_hint(exc)
            raise ConnectionError(hint or f"Could not reflect schema: {exc}") from exc
        finally:
            engine.dispose()


# Schemas that are infrastructure, not user data — hidden from the picker.
_SYSTEM_SCHEMAS = frozenset({
    # Postgres / MySQL / MSSQL
    "information_schema", "pg_catalog", "pg_toast",
    "sys", "INFORMATION_SCHEMA", "performance_schema", "mysql",
    # Oracle (uppercase, as Oracle reports them)
    "SYS", "SYSTEM", "XDB", "OUTLN", "DBSNMP", "APPQOSSYS", "CTXSYS",
    "MDSYS", "ORDSYS", "ORDDATA", "OLAPSYS", "WMSYS", "LBACSYS", "DVSYS",
    "AUDSYS", "GSMADMIN_INTERNAL", "DBSFWUSER", "REMOTE_SCHEDULER_AGENT",
    "SYS$UMF", "GGSYS", "ANONYMOUS", "XS$NULL", "OJVMSYS", "DGPDB_INT",
})


def _user_schemas(names) -> tuple:
    """Drop infrastructure schemas, keeping only user-facing ones."""
    return tuple(n for n in names if n not in _SYSTEM_SCHEMAS)


def list_schemas(connection_url: str) -> tuple:
    """Return the connectable, user-facing schema names (system schemas removed).

    Raises:
        ConnectionError: If the database is unreachable or the URL is invalid.
    """
    try:
        engine = create_engine(connection_url)
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not create engine: {exc}") from exc
    try:
        names = inspect(engine).get_schema_names()
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not list schemas: {exc}") from exc
    finally:
        engine.dispose()
    return _user_schemas(names)
