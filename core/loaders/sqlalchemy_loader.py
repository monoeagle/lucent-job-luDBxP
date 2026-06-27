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

    def load(self) -> Schema:
        """Reflect the database schema and return a :class:`~core.model.Schema`.

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
            for tname in insp.get_table_names():
                columns = tuple(
                    Column(col["name"], str(col["type"]))
                    for col in insp.get_columns(tname)
                )
                fks = []
                for fk in insp.get_foreign_keys(tname):
                    # Keep composite keys intact: one ForeignKey per constraint,
                    # carrying all (local, referred) column pairs. Two separate
                    # FKs between the same tables stay separate ForeignKey objects.
                    pairs = tuple(zip(
                        fk["constrained_columns"], fk["referred_columns"]
                    ))
                    fks.append(ForeignKey(fk["referred_table"], pairs))
                pk = tuple(insp.get_pk_constraint(tname).get("constrained_columns", []))
                try:
                    uniques = tuple(
                        tuple(uc.get("column_names") or ())
                        for uc in insp.get_unique_constraints(tname)
                        if uc.get("column_names")
                    )
                except SQLAlchemyError:
                    uniques = ()
                try:
                    uidx = tuple(
                        tuple(idx["column_names"])
                        for idx in insp.get_indexes(tname)
                        if idx.get("unique")
                        and idx.get("column_names")
                        and None not in idx["column_names"]
                        and not any(k.endswith("_where")
                                    for k in (idx.get("dialect_options") or {}))
                    )
                except SQLAlchemyError:
                    uidx = ()
                tables.append(Table(tname, columns, tuple(fks), pk, uniques, uidx))
            views = []
            for vname in insp.get_view_names():
                vcols = tuple(
                    Column(col["name"], str(col["type"]))
                    for col in insp.get_columns(vname)
                )
                try:
                    definition = insp.get_view_definition(vname) or ""
                except SQLAlchemyError:
                    definition = ""
                views.append(View(vname, vcols, definition))
            return Schema(tuple(tables), tuple(views))
        except SQLAlchemyError as exc:
            hint = _odbc_driver_hint(exc)
            raise ConnectionError(hint or f"Could not reflect schema: {exc}") from exc
        finally:
            engine.dispose()
