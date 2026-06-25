import pytest
from web import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_renders_form_and_local_assets(client):
    html = client.get("/").get_data(as_text=True)
    assert "Lucent DB Explorer" in html
    assert 'id="connection_url"' in html
    # assets must be local, never a CDN
    assert "/static/js/app.js" in html
    assert "/static/lib/cytoscape.min.js" in html  # graph lib bundled locally
    assert "http://" not in html and "https://" not in html


def test_index_prefills_default_connection(client):
    # The connection input is prefilled from config.json's default_connection
    # (the bundled demo DB), so the first "Schema laden" click works.
    html = client.get("/").get_data(as_text=True)
    assert 'value="sqlite:///sample_data/demo_cmdb.db"' in html


def test_index_has_three_panel_shell(client):
    # Sidebar (object browser), tab bar, and the fixed graph panel.
    html = client.get("/").get_data(as_text=True)
    assert 'id="objects"' in html
    assert 'id="tabbar"' in html
    assert 'id="graph"' in html
