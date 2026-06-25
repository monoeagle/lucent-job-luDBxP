"""HTTP API: reflect a schema and compute join-path SQL. Read-only."""
from flask import Blueprint, jsonify, render_template, request

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.graph import build_graph
from core.pathfinder import find_paths, NoPathError
from core.sqlgen import generate_sql, Selection, Filter

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

    graph = build_graph(schema)
    try:
        start = data["start"]
        target = data["target"]
        filters = tuple(
            Filter(f["table"], f["column"], f["op"], f["value"])
            for f in data.get("filters", [])
        )
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
