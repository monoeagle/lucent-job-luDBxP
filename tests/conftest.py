"""Shared pytest fixtures: a temp SQLite DB loaded from the inventory schema."""
import os
import pytest
from sqlalchemy import create_engine, text


def _schema_sql() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "fixtures", "inventory_schema.sql"), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture
def inventory_url(tmp_path) -> str:
    """File-based SQLite URL so SQLAlchemy reflection sees the schema."""
    db_path = tmp_path / "inventory.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    with engine.begin() as conn:
        # PRAGMA so SQLite reports foreign keys during reflection
        for statement in _schema_sql().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
    engine.dispose()
    return url


@pytest.fixture
def sqlite_engine(inventory_url):
    engine = create_engine(inventory_url)
    yield engine
    engine.dispose()
