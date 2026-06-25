import re

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
    assert "http://" not in html and "https://" not in html


def test_index_prefills_default_connection(client):
    # The connection input is prefilled from config.json's default_connection
    # (the bundled demo DB), so the first "Schema laden" click works.
    html = client.get("/").get_data(as_text=True)
    assert 'value="sqlite:///sample_data/demo_cmdb.db"' in html


def test_filter_add_button_is_enabled(client):
    # The "Filter +" button is wired up now and must not be disabled.
    html = client.get("/").get_data(as_text=True)
    m = re.search(r'<button[^>]*id="btn_add_filter"[^>]*>', html)
    assert m is not None
    assert "disabled" not in m.group(0)
