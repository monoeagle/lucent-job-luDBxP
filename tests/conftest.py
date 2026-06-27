"""Shared pytest fixtures: a temp SQLite DB loaded from the inventory schema."""
import os
import pytest
from sqlalchemy import create_engine, text


def _schema_sql(filename: str = "inventory_schema.sql") -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "fixtures", filename), encoding="utf-8") as fh:
        return fh.read()


def _build_sqlite(tmp_path, name: str, schema_file: str) -> str:
    db_path = tmp_path / name
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    with engine.begin() as conn:
        for statement in _schema_sql(schema_file).split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
    engine.dispose()
    return url


@pytest.fixture
def inventory_url(tmp_path) -> str:
    """File-based SQLite URL so SQLAlchemy reflection sees the schema."""
    return _build_sqlite(tmp_path, "inventory.db", "inventory_schema.sql")


@pytest.fixture
def inventory_nofk_url(tmp_path) -> str:
    """Same inventory shape but without declared FKs (for implied-FK tests)."""
    return _build_sqlite(tmp_path, "inventory_nofk.db", "inventory_nofk_schema.sql")


@pytest.fixture
def onetoone_url(tmp_path) -> str:
    """SQLite URL with a 1-1 (Passport, UNIQUE FK) and a 1-N (Orders) child."""
    return _build_sqlite(tmp_path, "onetoone.db", "onetoone_schema.sql")


@pytest.fixture
def sqlite_engine(inventory_url):
    engine = create_engine(inventory_url)
    yield engine
    engine.dispose()
