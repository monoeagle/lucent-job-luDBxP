"""Live-DB schema loader via SQLAlchemy reflection (SQLite + Postgres for v1)."""
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from core.model import Column, ForeignKey, Table, Schema
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
                    # SQLAlchemy returns parallel lists for composite keys;
                    # v1 models each column pair as its own ForeignKey edge.
                    for local, remote in zip(
                        fk["constrained_columns"], fk["referred_columns"]
                    ):
                        fks.append(ForeignKey(local, fk["referred_table"], remote))
                tables.append(Table(tname, columns, tuple(fks)))
            return Schema(tuple(tables))
        except SQLAlchemyError as exc:
            raise ConnectionError(f"Could not reflect schema: {exc}") from exc
        finally:
            engine.dispose()
