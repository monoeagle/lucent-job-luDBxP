"""HTTP API: reflect a schema and compute join-path SQL. Read-only."""
import logging

from flask import Blueprint, jsonify, render_template, request

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.graph import build_graph
from core.pathfinder import find_paths, NoPathError
from core.sqlgen import generate_sql, Selection, Filter

_log = logging.getLogger("luDBxP")

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Serve the main single-page application shell."""
    return render_template("index.html")


@bp.post("/api/schema")
def api_schema():
    """Reflect a database schema and return tables with their columns."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    try:
        schema = SqlAlchemyLoader(url).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(tables=[
        {"name": t.name, "columns": [c.name for c in t.columns]}
        for t in schema.tables
    ])


@bp.post("/api/joinpath")
def api_joinpath():
    """Find join paths between two columns and return the generated SQL."""
    data = request.get_json(silent=True) or {}
    try:
        schema = SqlAlchemyLoader(data["connection_url"]).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    except KeyError:
        return jsonify(error="connection_url is required"), 400

    try:
        graph = build_graph(schema)
    except Exception as exc:
        _log.exception("graph build failed")
        return jsonify(error="internal error building schema graph"), 500
    try:
        start = data["start"]
        target = data["target"]
        filters = tuple(
            Filter(f["table"], f["column"], f["op"], f["value"])
            for f in data.get("filters", [])
        )
        # Validate that every referenced column exists in the reflected schema.
        for tbl, col in ([(start["table"], start["column"]),
                          (target["table"], target["column"])] +
                         [(f.table, f.column) for f in filters]):
            if not schema.has_column(tbl, col):
                return jsonify(error=f"unknown column: {tbl}.{col}"), 400
        selects = (Selection(start["table"], start["column"]),
                   Selection(target["table"], target["column"]))
        filter_tables = tuple(f.table for f in filters)
        paths = find_paths(graph, start["table"], target["table"], filter_tables)
    except KeyError as exc:
        return jsonify(error=f"missing field: {exc}"), 400
    except NoPathError as exc:
        return jsonify(error=str(exc)), 400

    out = []
    try:
        for p in paths:
            gen = generate_sql(p, selects, filters)
            out.append({"tables": list(p.tables), "sql": gen.sql, "params": gen.params})
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(paths=out)
