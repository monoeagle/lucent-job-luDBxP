"""AP-34 — Info-/About-Dialog.

Läuft als **eigener Prozess** (vom Tray via subprocess gestartet), damit das
Tkinter-Fenster nicht mit der Tray-Mainloop (pystray/GTK bzw. win32) kollidiert.
Reine Anzeige — keine Aktion auf der Datenbank.
"""
import os
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version

import config

_REPO = "github.com/monoeagle/lucent-job-luDBxP"
_GEO_RE = re.compile(r"\b(\d+)x(\d+)\+(\d+)\+(\d+)\b")


def _ver(pkg):
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "?"


def info_text(url=None, port=None):
    """Mehrzeiliger Info-Text (auch ohne GUI testbar)."""
    url = url or os.environ.get("LUCENT_INFO_URL") or "—"
    port = port or os.environ.get("LUCENT_INFO_PORT") or "—"
    py = sys.version.split()[0]
    lines = [
        config.APP_NAME,
        f"Version {config.APP_VERSION}",
        "",
        f"Ersteller:   {config.APP_AUTHOR}",
        "Art:         internes Werkzeug · read-only (keine DB-Mutation)",
        f"Repo:        {_REPO}",
        "",
        f"URL:         {url}",
        f"Port:        {port}",
        "",
        "Stack:",
        f"  Python {py} · Flask {_ver('flask')} · SQLAlchemy {_ver('sqlalchemy')}",
        f"  NetworkX {_ver('networkx')} · sqlglot {_ver('sqlglot')}",
        f"  Frontend: vanilla JS + Cytoscape.js {config.CYTOSCAPE_VERSION} (lokal, NO-CDN)",
        f"  Tray: pystray {_ver('pystray')} · Pillow {_ver('pillow')}",
        "",
        f"Daten pro Nutzer:  ~/.config/{config.APP_SLUG}  (Linux)",
        f"                   %LOCALAPPDATA%\\{config.APP_SLUG}  (Windows)",
    ]
    return "\n".join(lines)


def _parse_primary_geometry(xrandr_output):
    """Aus 'xrandr --query' die (x, y, w, h) des **primären** Monitors lesen;
    sonst der erste verbundene Monitor; sonst None."""
    first = None
    for line in xrandr_output.splitlines():
        m = _GEO_RE.search(line)
        if not m:
            continue
        w, h, x, y = (int(v) for v in m.groups())
        geo = (x, y, w, h)
        if " connected primary " in line:
            return geo
        if first is None and " connected " in line:
            first = geo
    return first


def _primary_geometry(root):
    """(x, y, w, h) des primären Monitors. Linux: via xrandr (Multi-Monitor-fest);
    Windows/Fallback: Tk-Screen (dort = primärer Monitor)."""
    if sys.platform.startswith("linux"):
        try:
            out = subprocess.check_output(["xrandr", "--query"], text=True,
                                          stderr=subprocess.DEVNULL)
            geo = _parse_primary_geometry(out)
            if geo:
                return geo
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def show(url=None, port=None):  # pragma: no cover - GUI, braucht Display
    import tkinter as tk

    text = info_text(url, port)
    lines = text.splitlines()
    cols = max(len(line) for line in lines) + 2   # exakt breit genug → keine Umbrüche
    rows = len(lines) + 1

    root = tk.Tk()
    root.title(f"Info — {config.APP_NAME}")
    root.resizable(False, False)
    body = tk.Text(root, width=cols, height=rows, wrap="none",
                   font=("monospace", 11), borderwidth=0, padx=20, pady=16,
                   background="#f7f7fa")
    body.insert("1.0", text)
    body.configure(state="disabled")
    body.pack()
    tk.Button(root, text="Schließen", command=root.destroy).pack(pady=(0, 16))

    # Auf dem primären Monitor zentrieren (Multi-Monitor-fest).
    root.update_idletasks()
    win_w, win_h = root.winfo_width(), root.winfo_height()
    mx, my, mw, mh = _primary_geometry(root)
    root.geometry(f"+{mx + (mw - win_w) // 2}+{my + (mh - win_h) // 2}")

    root.mainloop()


def main():  # pragma: no cover - GUI entry
    show()


if __name__ == "__main__":
    main()
