"""Tray GUI shell (AP-34): pystray icon + menu wired to LauncherCore.
Thin by design — all logic lives in launcher.core (headless-testable)."""
import os
import subprocess
import sys

import pystray
from PIL import Image, ImageDraw

import config


def make_icon_image(size=64):
    """A simple branded tray icon (no bundled asset): brand square + 'DB'."""
    img = Image.new("RGBA", (size, size), (46, 111, 174, 255))  # #2E6FAE
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, size - 5, size - 5], outline=(255, 255, 255, 255), width=2)
    draw.text((14, 22), "DB", fill=(255, 255, 255, 255))
    return img


def build_tray(core):
    """Build the pystray.Icon with the Open/Info/Quit menu wired to `core`."""
    def on_open(icon, item):
        core.open_browser()

    def on_info(icon, item):
        # Eigener Prozess: das Tkinter-Fenster kollidiert nicht mit der Tray-Mainloop.
        env = dict(os.environ,
                   LUCENT_INFO_URL=core.url or "",
                   LUCENT_INFO_PORT=str(core.port or ""))
        subprocess.Popen([sys.executable, "-m", "launcher.about"], env=env)

    def on_quit(icon, item):
        core.stop()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Im Browser öffnen", on_open, default=True),
        pystray.MenuItem("Info", on_info),
        pystray.MenuItem("Beenden", on_quit),
    )
    return pystray.Icon("luDBxP", make_icon_image(), config.APP_NAME, menu)
