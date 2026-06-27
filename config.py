"""App constants, paths, and version."""
import os

APP_NAME = "LucentTools DB Explorer"
APP_SLUG = "luDBxP"
APP_VERSION = "0.24.2"  # change only via sync_version.py
APP_AUTHOR = "Tobias Philipp / LucentTools"
CYTOSCAPE_VERSION = "3.30.2"  # bundled in web/static/lib/cytoscape.min.js

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "Logs")
CONFIG_JSON = os.path.join(BASE_DIR, "config.json")

# Logging defaults (overridable per environment — see core/log.py):
#   LUCENT_LOG_DIR    → log directory (e.g. a per-user path on a terminal server)
#   LUCENT_LOG_LEVEL  → DEBUG/INFO/WARNING/…
#   LUCENT_DEBUG      → truthy implies DEBUG level
LOG_LEVEL = "INFO"
LOG_MAX_BYTES = 1_000_000   # rotate app.log at ~1 MB
LOG_BACKUP_COUNT = 5        # keep app.log.1 … app.log.5

WEB_HOST = "127.0.0.1"
WEB_PORT = 5057  # verify against port registry before hub start

# max number of k-shortest join paths returned
MAX_JOIN_PATHS = 5
MAX_PATH_ENUMERATION = 200  # cap on simple paths enumerated before k-selection (prevents hang on large schemas)

# Join-Builder result output (AP-6): selectable row counts + hard ceiling.
DEFAULT_RESULT_ROWS = 200
MAX_RESULT_ROWS = 5000  # "Alle" is capped here to protect the browser UI
