"""Live-DB schema loader via SQLAlchemy reflection (SQLite + Postgres for v1)."""
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from core.model import Column, ForeignKey, Table, View, Schema
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
                    fks.append(ForeignKey(fk["referred_table"], pairs))
                pk = tuple(insp.get_pk_constraint(tname, schema=schema).get("constrained_columns", []))
                try:
                    uniques = tuple(
                        tuple(uc.get("column_names") or ())
                        for uc in insp.get_unique_constraints(tname, schema=schema)
                        if uc.get("column_names")
                    )
                except SQLAlchemyError:
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
                except SQLAlchemyError:
                    uidx = ()
                try:
                    tcomment = ((insp.get_table_comment(tname, schema=schema) or {})
                                .get("text") or "")
                except (NotImplementedError, SQLAlchemyError):
                    tcomment = ""
                tables.append(Table(tname, columns, tuple(fks), pk, uniques, uidx, tcomment))
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
            return Schema(tuple(tables), tuple(views))
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
