"""AP-34 — tray launcher core."""
import http.server
import socket
import subprocess
import sys
import threading

import config
from launcher.core import LauncherCore


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_start_picks_port_and_sets_lucent_port_env(monkeypatch):
    captured = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, env=None, **kw):
        captured["cmd"] = cmd
        captured["env"] = env
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    c = LauncherCore()
    url = c.start()
    assert c.port and c.port > 0
    assert captured["env"]["LUCENT_PORT"] == str(c.port)
    assert captured["cmd"][0] == sys.executable
    assert captured["cmd"][1].endswith("app.py")
    assert url == f"http://127.0.0.1:{c.port}"


def test_info_reports_version_url_port(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: type("P", (), {"poll": lambda self: None})())
    c = LauncherCore()
    c.start()
    info = c.info()
    assert info["version"] == config.APP_VERSION
    assert info["name"] == config.APP_NAME
    assert info["url"] == c.url and info["port"] == c.port


def test_open_browser_uses_injected_opener():
    calls = []
    c = LauncherCore(opener=lambda u: calls.append(u))
    c.url = "http://127.0.0.1:1234"
    c.open_browser()
    assert calls == ["http://127.0.0.1:1234"]


def test_wait_until_ready_true_against_stub_server():
    port = _free_port()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = LauncherCore()
        c.url = f"http://127.0.0.1:{port}"
        assert c.wait_until_ready(timeout=3) is True
    finally:
        srv.shutdown()


def test_wait_until_ready_false_on_closed_port():
    c = LauncherCore()
    c.url = f"http://127.0.0.1:{_free_port()}"   # nichts lauscht dort
    assert c.wait_until_ready(timeout=0.6, interval=0.1) is False


def test_stop_terminates_child():
    c = LauncherCore()
    c._proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    assert c.is_running() is True
    c.stop(timeout=5)
    assert c.is_running() is False
    assert c._proc.poll() is not None
