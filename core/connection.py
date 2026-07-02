"""Build a SQLAlchemy connection URL from structured connection parameters.

Keeping URL assembly here (rather than in the browser) centralizes driver
selection and credential encoding. Passwords are URL-encoded so special
characters do not break the URL.
"""
from urllib.parse import quote_plus, urlencode

# db_type -> SQLAlchemy dialect+driver prefix for server databases.
_DRIVERS = {
    "postgresql": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
    "oracle": "oracle+oracledb",
}

_DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306, "mssql": 1433, "oracle": 1521}

# Current Microsoft ODBC driver. Driver 18 encrypts by default; with a
# self-signed server certificate the caller must add trust_server_certificate.
_DEFAULT_MSSQL_DRIVER = "ODBC Driver 18 for SQL Server"


def _mssql_query(params: dict) -> str:
    """Build the MSSQL ODBC query string from connection params.

    Always includes the ODBC ``driver`` (overridable via ``driver``); adds
    ``Encrypt`` and/or ``TrustServerCertificate`` only when explicitly given,
    so behaviour stays predictable and nothing insecure is assumed by default.

    Args:
        params: Connection params; recognises ``driver``, ``encrypt``
            ("yes"/"no") and ``trust_server_certificate`` ("yes"/"no").

    Returns:
        A URL-encoded query string (without the leading ``?``).
    """
    query = {"driver": (params.get("driver") or _DEFAULT_MSSQL_DRIVER)}
    encrypt = params.get("encrypt")
    if encrypt:
        query["Encrypt"] = encrypt
    trust = params.get("trust_server_certificate")
    if trust:
        query["TrustServerCertificate"] = trust
    return urlencode(query, quote_via=quote_plus)


def build_url(params: dict) -> str:
    """Build a SQLAlchemy URL from a connection-parameter dict.

    Args:
        params: Keys ``db_type`` plus, for SQLite, ``filepath``; for server
            databases ``host``, ``port`` (optional), ``database``, ``user``,
            ``password``; for Oracle ``service_name`` instead of ``database``,
            additionally ``oracle_connect_type`` (service/sid) and ``sid``.

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
    if not host:
        raise ValueError("Host fehlt.")
    port = params.get("port") or _DEFAULT_PORTS[db_type]

    user = quote_plus(params.get("user") or "")
    password = quote_plus(params.get("password") or "")
    auth = f"{user}:{password}@" if user else ""

    if db_type == "oracle":
        # Oracle: address by service name (query) or SID (URL path). Default to
        # service for backward compatibility with saved connections that predate
        # the SID option and carry only service_name.
        connect_type = (params.get("oracle_connect_type") or "service").strip().lower()
        if connect_type == "sid":
            sid = (params.get("sid") or "").strip()
            if not sid:
                raise ValueError("SID fehlt.")
            # SID belongs in the URL path — the ?sid= query form yields a broken
            # DSN (dsn='host', sid as a stray kwarg); the path form produces a
            # correct (CONNECT_DATA=(SID=...)) descriptor.
            return f"{_DRIVERS['oracle']}://{auth}{host}:{port}/{quote_plus(sid)}"
        if connect_type != "service":
            raise ValueError(f"Unbekannte Oracle-Verbindungsart: {connect_type!r}")
        service = (params.get("service_name") or "").strip()
        if not service:
            raise ValueError("Service-Name fehlt.")
        return (f"{_DRIVERS['oracle']}://{auth}{host}:{port}"
                f"/?service_name={quote_plus(service)}")

    database = (params.get("database") or "").strip()
    if not database:
        raise ValueError("Datenbankname fehlt.")
    url = f"{_DRIVERS[db_type]}://{auth}{host}:{port}/{database}"
    if db_type == "mssql":
        url += "?" + _mssql_query(params)
    return url
