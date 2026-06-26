"""LucentTools DB Explorer - entry point."""
import os

import config
from web import create_app

app = create_app()

if __name__ == "__main__":
    # Debug optional via Umgebungsvariable (run.ps1 -DebugMode setzt sie).
    # Achtung: Debug aktiviert den interaktiven Debugger + Reloader -> nur lokal/Diagnose.
    debug = os.environ.get("LUCENT_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT,
            debug=debug, use_reloader=debug, threaded=True)
