"""App constants, paths, and version."""
import os

APP_NAME = "Lucent DB Explorer"
APP_SLUG = "luDBxP"
APP_VERSION = "0.1.0"  # NUR via sync_version.py ändern!
APP_AUTHOR = "Tobias Philipp / Lucent Trails"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "Logs")
CONFIG_JSON = os.path.join(BASE_DIR, "config.json")

WEB_HOST = "127.0.0.1"
WEB_PORT = 5057  # vor Hub-Start gegen Registry prüfen

# k-kürzeste Join-Pfade, die maximal zurückgegeben werden
MAX_JOIN_PATHS = 5
