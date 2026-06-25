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
