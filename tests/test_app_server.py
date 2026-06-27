"""AP-31: die Server-Weiche in app.run_server wählt waitress vs. Dev-Server."""
import waitress

import app as app_module


class FakeApp:
    """Minimaler App-Stub: zeichnet auf, ob/wie .run() gerufen wurde."""

    def __init__(self):
        self.run_called = False
        self.run_kwargs = None

    def run(self, **kwargs):
        self.run_called = True
        self.run_kwargs = kwargs


def test_run_server_production_uses_waitress(monkeypatch):
    captured = {}
    monkeypatch.setattr(waitress, "serve",
                        lambda app, **kw: captured.update(app=app, kw=kw))
    fake = FakeApp()

    app_module.run_server(fake, "127.0.0.1", 5057, debug=False)

    assert captured["app"] is fake
    assert captured["kw"] == {"host": "127.0.0.1", "port": 5057}
    assert fake.run_called is False


def test_run_server_debug_uses_dev_server(monkeypatch):
    serve_calls = {"n": 0}
    monkeypatch.setattr(waitress, "serve",
                        lambda *a, **k: serve_calls.__setitem__("n", serve_calls["n"] + 1))
    fake = FakeApp()

    app_module.run_server(fake, "127.0.0.1", 5057, debug=True)

    assert fake.run_called is True
    assert fake.run_kwargs.get("use_reloader") is True
    assert serve_calls["n"] == 0
