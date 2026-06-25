"""Build a SQLAlchemy connection URL from structured connection parameters.

Keeping URL assembly here (rather than in the browser) centralizes driver
selection and credential encoding. Passwords are URL-encoded so special
characters do not break the URL.
"""
from urllib.parse import quote_plus

# db_type -> SQLAlchemy dialect+driver prefix for server databases.
_DRIVERS = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
}

_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306, "mssql": 1433}


def build_url(params: dict) -> str:
    """Build a SQLAlchemy URL from a connection-parameter dict.

    Args:
        params: Keys ``db_type`` plus, for SQLite, ``filepath``; for server
            databases ``host``, ``port`` (optional), ``database``, ``user``,
            ``password``.

    Returns:
        A SQLAlchemy connection URL string.

    Raises:
        ValueError: On unknown db_type or missing required fields.
    """
    db_type = (params.get("db_type") or "").strip()
    if db_type == "sqlite":
        path = (params.get("filepath") or "").strip()
        if not path:
            raise ValueError("Dateipfad fehlt.")
        return f"sqlite:///{path}"

    if db_type not in _DRIVERS:
        raise ValueError(f"Unbekannter Datenbank-Typ: {db_type or '(leer)'}")

    host = (params.get("host") or "").strip()
    database = (params.get("database") or "").strip()
    if not host:
        raise ValueError("Host fehlt.")
    if not database:
        raise ValueError("Datenbankname fehlt.")
    port = params.get("port") or _DEFAULT_PORTS[db_type]

    user = quote_plus(params.get("user") or "")
    password = quote_plus(params.get("password") or "")
    auth = f"{user}:{password}@" if user else ""
    url = f"{_DRIVERS[db_type]}://{auth}{host}:{port}/{database}"
    if db_type == "mssql":
        url += "?driver=ODBC+Driver+17+for+SQL+Server"
    return url
