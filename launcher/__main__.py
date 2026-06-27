"""Entry point: `python -m launcher` (Windows fensterlos via pythonw)."""
import threading

from launcher.core import LauncherCore
from launcher.tray import build_tray


def main():
    core = LauncherCore()
    core.start()

    def _open_when_ready():
        if core.wait_until_ready():
            core.open_browser()

    threading.Thread(target=_open_when_ready, daemon=True).start()
    build_tray(core).run()   # blockiert bis „Beenden"


if __name__ == "__main__":
    main()
