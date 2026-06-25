import pytest

from core.connection import build_url


def test_sqlite_url():
    assert build_url({"db_type": "sqlite", "filepath": "/tmp/x.db"}) == "sqlite:////tmp/x.db"


def test_postgresql_url_with_credentials():
    url = build_url({
        "db_type": "postgresql", "host": "db.local", "port": 5432,
        "database": "cmdb", "user": "admin", "password": "secret",
    })
    assert url == "postgresql+psycopg2://admin:secret@db.local:5432/cmdb"


def test_mysql_default_port():
    url = build_url({
        "db_type": "mysql", "host": "h", "database": "d", "user": "u", "password": "p"})
    assert url == "mysql+pymysql://u:p@h:3306/d"


def test_mssql_includes_odbc_driver():
    url = build_url({
        "db_type": "mssql", "host": "h", "database": "d", "user": "u", "password": "p"})
    assert url.startswith("mssql+pyodbc://u:p@h:1433/d")
    assert "driver=ODBC+Driver+17+for+SQL+Server" in url


def test_password_is_url_encoded():
    url = build_url({
        "db_type": "postgresql", "host": "h", "database": "d",
        "user": "u", "password": "p@ss:w/rd"})
    assert "p%40ss%3Aw%2Frd" in url  # special chars encoded


def test_unknown_db_type_raises():
    with pytest.raises(ValueError):
        build_url({"db_type": "oracle", "host": "h", "database": "d"})


def test_sqlite_without_path_raises():
    with pytest.raises(ValueError):
        build_url({"db_type": "sqlite"})
