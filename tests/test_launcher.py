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


def test_wait_until_ready_false_when_child_dies():
    import time
    c = LauncherCore()
    c._proc = subprocess.Popen([sys.executable, "-c", "pass"])  # exits immediately
    c._proc.wait()                                              # now dead
    c.url = f"http://127.0.0.1:{_free_port()}"                  # nothing listening
    t0 = time.monotonic()
    assert c.wait_until_ready(timeout=10, interval=0.2) is False
    assert time.monotonic() - t0 < 3                            # returned fast, not full 10s


def test_install_cleanup_reaps_child_on_exit_and_signal(monkeypatch):
    """Der Launcher räumt den Kindprozess bei Exit (atexit) UND bei SIGTERM/SIGINT
    sauber ab → keine Waisen, Port frei."""
    import atexit as _atexit
    import signal as _signal
    import pytest
    from launcher import __main__ as m

    stopped = []

    class FakeCore:
        def stop(self):
            stopped.append("stop")

    reg = {}
    monkeypatch.setattr(_atexit, "register", lambda fn: reg.setdefault("atexit", fn))
    handlers = {}
    monkeypatch.setattr(_signal, "signal", lambda s, h: handlers.setdefault(s, h))

    core = FakeCore()
    m._install_cleanup(core)

    assert reg["atexit"] == core.stop                 # atexit reapt den Kindprozess
    assert _signal.SIGTERM in handlers and _signal.SIGINT in handlers
    with pytest.raises(SystemExit):                   # Signal-Handler stoppt + beendet
        handlers[_signal.SIGTERM](_signal.SIGTERM, None)
    assert stopped == ["stop"]


def test_about_info_text_contains_key_fields():
    import config
    from launcher.about import info_text
    txt = info_text(url="http://127.0.0.1:5057", port=5057)
    assert config.APP_NAME in txt
    assert config.APP_VERSION in txt
    assert config.APP_AUTHOR in txt                   # Ersteller
    assert "http://127.0.0.1:5057" in txt and "5057" in txt
    assert "Python" in txt and "Flask" in txt and "SQLAlchemy" in txt  # Stack
    assert "read-only" in txt


def test_tray_info_launches_about_subprocess(monkeypatch):
    import subprocess as _sp
    from launcher import tray as traymod

    class FakeCore:
        url = "http://127.0.0.1:5057"
        port = 5057

        def open_browser(self):
            pass

        def stop(self):
            pass

    captured = {}
    monkeypatch.setattr(_sp, "Popen",
                        lambda cmd, env=None, **k: captured.update(cmd=cmd, env=env))
    icon = traymod.build_tray(FakeCore())
    info_item = [it for it in icon.menu if str(it.text) == "Info"][0]
    info_item(icon)                                   # MenuItem aufrufbar → Action
    assert captured["cmd"][0] == sys.executable
    assert captured["cmd"][1:] == ["-m", "launcher.about"]
    assert captured["env"]["LUCENT_INFO_URL"] == "http://127.0.0.1:5057"
    assert captured["env"]["LUCENT_INFO_PORT"] == "5057"


def test_parse_primary_geometry_picks_primary_monitor():
    from launcher.about import _parse_primary_geometry
    sample = (
        "Screen 0: minimum 320 x 200, current 5120 x 1440, maximum 16384 x 16384\n"
        "DP-1 connected 2560x1440+2560+0 (normal left inverted right) 600mm x 340mm\n"
        "DP-2 connected primary 2560x1440+0+0 (normal) 600mm x 340mm\n"
    )
    # die primäre Auflösung+Offset, NICHT der virtuelle Gesamt-Screen (5120x1440)
    assert _parse_primary_geometry(sample) == (0, 0, 2560, 1440)


def test_parse_primary_geometry_falls_back_to_first_connected():
    from launcher.about import _parse_primary_geometry
    sample = "HDMI-1 connected 1920x1080+0+0 (normal) 510mm x 290mm\n"
    assert _parse_primary_geometry(sample) == (0, 0, 1920, 1080)
