"""Read-only data preview: fetch the first rows of a table or view.

This is the one place the tool executes a query against the database. It is
strictly read-only (SELECT only, fixed LIMIT) and the object name is validated
against the reflected schema before being quoted into the statement, so it is
not an injection vector.
"""
from sqlalchemy import create_engine, text, select, table, literal_column
from sqlalchemy.exc import SQLAlchemyError
from core.subset import count_sql


def execute_select(connection_url: str, sql: str, params: dict,
                   max_rows: int = 200) -> dict:
    """Execute a server-generated parameterized SELECT and return rows.

    The SQL must have been produced by ``generate_sql`` (server-side); the
    caller must never pass client-supplied SQL strings here.

    Args:
        connection_url: SQLAlchemy connection URL.
        sql: A read-only SELECT statement with named :placeholders.
        params: Dict mapping placeholder names to their values.
        max_rows: Maximum number of rows to return (hard cap).

    Returns:
        A dict ``{"columns": [...], "rows": [[...], ...]}``.

    Raises:
        ConnectionError: If the database is unreachable or the query fails.
    """
    try:
        engine = create_engine(connection_url)
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not create engine: {exc}") from exc
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchmany(max_rows)]
        return {"columns": columns, "rows": rows}
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not execute query: {exc}") from exc
    finally:
        engine.dispose()


def count_subset_rows(connection_url: str, scripts) -> list:
    """Execute each subset SELECT as a read-only COUNT, resilient per table.

    For each ``SubsetScript`` the COUNT query (``count_sql``) is run via
    ``execute_select``. A per-table ``ConnectionError`` (permission, broken
    type, missing object) is caught and recorded as ``error`` with
    ``count=None`` so the remaining tables are still counted.

    Returns a list of ``{"table", "count": int|None, "error": str|None}`` in
    the same order as ``scripts``.
    """
    out = []
    for s in scripts:
        try:
            res = execute_select(connection_url, count_sql(s.sql), s.params, max_rows=1)
            count = res["rows"][0][0] if res["rows"] else 0
            out.append({"table": s.table, "count": count, "error": None})
        except ConnectionError as exc:
            out.append({"table": s.table, "count": None, "error": str(exc)})
    return out


def dump_subset_rows(connection_url: str, scripts, *, max_rows_per_table: int) -> list:
    """Execute each subset SELECT read-only and capture its rows. Resilient per table.

    Fetches up to ``max_rows_per_table + 1`` rows to detect truncation: if more
    than the cap come back, the table is flagged ``truncated`` and the rows are
    cut to the cap. A per-table ``ConnectionError`` is caught and recorded as
    ``error`` (empty rows) so the remaining tables still dump.

    Returns a list of ``{"table","columns","rows","row_count","truncated","error"}``
    in the same order as ``scripts``.
    """
    out = []
    for s in scripts:
        try:
            res = execute_select(connection_url, s.sql, s.params,
                                 max_rows=max_rows_per_table + 1)
            rows = res["rows"]
            truncated = len(rows) > max_rows_per_table
            if truncated:
                rows = rows[:max_rows_per_table]
            out.append({"table": s.table, "columns": res["columns"], "rows": rows,
                        "row_count": len(rows), "truncated": truncated, "error": None})
        except ConnectionError as exc:
            out.append({"table": s.table, "columns": [], "rows": [], "row_count": 0,
                        "truncated": False, "error": str(exc)})
    return out


def fetch_rows(connection_url: str, object_name: str,
               valid_names: set, limit: int = 100, schema: str = "") -> dict:
    """Fetch up to `limit` rows from a table or view.

    Args:
        connection_url: SQLAlchemy connection URL.
        object_name: Table or view name; must be in valid_names.
        valid_names: The set of reflected table/view names (allow-list).
        limit: Maximum number of rows to return.
        schema: Optional schema qualifier; if non-empty, the object is qualified.

    Returns:
        A dict ``{"columns": [...], "rows": [[...], ...]}``.

    Raises:
        ValueError: If object_name is not a known table/view.
        ConnectionError: If the database is unreachable or the query fails.
    """
    if object_name not in valid_names:
        raise ValueError(f"Unbekanntes Objekt: {object_name}")
    try:
        engine = create_engine(connection_url)
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not create engine: {exc}") from exc
    try:
        with engine.connect() as conn:
            # object_name is allow-list validated. Build the SELECT via SQLAlchemy
            # Core so the row cap and identifier casing/quoting render per dialect:
            # LIMIT (SQLite/PostgreSQL/MySQL), FETCH FIRST … ROWS ONLY (Oracle),
            # SELECT TOP … (MSSQL). A raw "… LIMIT n" broke on Oracle (ORA-00933),
            # and force-quoting a reflected (lower-cased) Oracle name broke on it too
            # (ORA-00942). Core round-trips the reflected name correctly.
            tbl = table(object_name, schema=schema or None)
            stmt = select(literal_column("*")).select_from(tbl).limit(int(limit))
            result = conn.execute(stmt)
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
        return {"columns": columns, "rows": rows}
    except SQLAlchemyError as exc:
        raise ConnectionError(f"Could not read data: {exc}") from exc
    finally:
        engine.dispose()
