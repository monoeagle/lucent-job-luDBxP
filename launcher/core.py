"""Tray launcher core (AP-34): own the app.py child process, pick the port,
poll for readiness, open the browser. Pure stdlib — no pystray/Pillow import,
so it stays headless-testable. The GUI shell (launcher/tray.py) drives this."""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

import config
from core import userpaths

_APP_PY = os.path.join(config.BASE_DIR, "app.py")
_CREATE_NO_WINDOW = 0x08000000  # Windows: no console for the child


class LauncherCore:
    """Owns the app.py child process; start/stop/info for the tray shell."""

    def __init__(self, host=config.WEB_HOST, opener=webbrowser.open):
        self.host = host
        self._opener = opener
        self.port = None
        self.url = None
        self._proc = None

    def start(self):
        """Pick a free port, spawn app.py with LUCENT_PORT set; return the URL."""
        self.port = userpaths.pick_port(config.WEB_PORT, self.host)
        self.url = f"http://{self.host}:{self.port}"
        env = dict(os.environ, LUCENT_PORT=str(self.port))
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        self._proc = subprocess.Popen([sys.executable, _APP_PY], env=env, **kwargs)
        return self.url

    def wait_until_ready(self, timeout=20.0, interval=0.3):
        """Poll self.url until the server answers (any HTTP status) or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(self.url, timeout=1):
                    return True
            except urllib.error.HTTPError:
                return True   # answered (e.g. 4xx) → it is up
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(interval)
        return False

    def open_browser(self):
        if self.url:
            self._opener(self.url)

    def is_running(self):
        return self._proc is not None and self._proc.poll() is None

    def stop(self, timeout=5.0):
        """Terminate the app process (frees the port). SIGTERM then kill."""
        if self._proc is None or self._proc.poll() is not None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()

    def info(self):
        return {"name": config.APP_NAME, "version": config.APP_VERSION,
                "url": self.url, "port": self.port, "running": self.is_running()}
