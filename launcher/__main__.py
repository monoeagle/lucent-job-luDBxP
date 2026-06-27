"""Entry point: `python -m launcher` (Windows fensterlos via pythonw)."""
import atexit
import signal
import threading

from launcher.core import LauncherCore
from launcher.tray import build_tray


def _install_cleanup(core):
    """Garantiert sauberes Abräumen des app.py-Kindprozesses (Port frei) bei
    JEDEM Ende des Launchers — Menü „Beenden", Fenster schließen, SIGTERM/SIGINT
    oder normales Programmende. `core.stop()` ist idempotent. Gibt den
    Signal-Handler zurück (für Tests)."""
    atexit.register(core.stop)

    def _terminate(_signum, _frame):
        core.stop()
        raise SystemExit(0)

    for _sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(_sig, _terminate)
        except (ValueError, OSError):
            pass  # z. B. nicht im Haupt-Thread / Signal nicht verfügbar
    return _terminate


def main():
    core = LauncherCore()
    core.start()
    _install_cleanup(core)

    def _open_when_ready():
        if core.wait_until_ready():
            core.open_browser()

    threading.Thread(target=_open_when_ready, daemon=True).start()
    build_tray(core).run()   # blockiert bis „Beenden"


if __name__ == "__main__":
    main()
