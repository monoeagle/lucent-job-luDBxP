"""Live-DB schema loader via SQLAlchemy reflection (SQLite + Postgres for v1)."""
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from core.model import Column, ForeignKey, Table, View, Schema
from core.schema_loader import SchemaLoader


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
                tables.append(Table(tname, columns, tuple(fks), pk))
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
            raise ConnectionError(f"Could not reflect schema: {exc}") from exc
        finally:
            engine.dispose()
