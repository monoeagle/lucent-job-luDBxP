import json
import pytest
from web import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_renders_form_and_local_assets(client):
    html = client.get("/").get_data(as_text=True)
    assert "LucentTools DB Explorer" in html
    assert 'id="connection_url"' in html
    # assets must be local, never a CDN
    assert "/static/js/app.js" in html
    assert "/static/lib/cytoscape.min.js" in html  # graph lib bundled locally
    assert "http://" not in html and "https://" not in html


def test_index_prefills_default_connection(tmp_path, monkeypatch):
    # The connection input is prefilled from the per-user config.json's
    # default_connection (the bundled demo DB), so the first "Schema laden" click works.
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"default_connection": "sqlite:///sample_data/demo_cmdb.db"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    app = create_app()
    app.config.update(TESTING=True)
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'value="sqlite:///sample_data/demo_cmdb.db"' in html


def test_index_has_three_panel_shell(client):
    # Sidebar (object browser), tab bar, and the fixed graph panel.
    html = client.get("/").get_data(as_text=True)
    assert 'id="objects"' in html
    assert 'id="tabbar"' in html
    assert 'id="graph"' in html


def test_index_has_topbar_connection_picker(client):
    # AP-10: a saved-connection dropdown sits in the topbar next to "Verbinden".
    html = client.get("/").get_data(as_text=True)
    assert 'id="topbar_conn"' in html


def test_index_has_ap13_polish_controls(client):
    # AP-13: object-browser search field, left (sidebar) splitter, graph relayout.
    html = client.get("/").get_data(as_text=True)
    assert 'id="obj_search"' in html
    assert 'id="splitter_left"' in html
    assert 'id="graph_relayout"' in html
