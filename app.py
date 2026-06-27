"""LucentTools DB Explorer - entry point."""
import logging
import os

import config
from core import userpaths
from web import create_app

app = create_app()  # initialisiert auch das Logging (core.log.init_logging)

if __name__ == "__main__":
    logger = logging.getLogger("luDBxP")

    # AP-31: vorhandene App-Verzeichnis-config.json einmalig pro Nutzer übernehmen.
    user_cfg = userpaths.user_config_file(config.APP_SLUG)
    if userpaths.migrate_legacy_config(user_cfg, config.LEGACY_CONFIG_JSON):
        logger.info("config.json aus App-Verzeichnis übernommen → %s", user_cfg)

    # Debug optional via Umgebungsvariable (run.ps1 -DebugMode setzt sie).
    debug = os.environ.get("LUCENT_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

    # AP-31: Port pro Session. Ohne LUCENT_PORT erst 5057 versuchen, sonst freien
    # Port; LUCENT_PORT=<n> erzwingt einen festen Port, =0 immer dynamisch.
    port = userpaths.resolve_port(os.environ.get("LUCENT_PORT"),
                                  config.WEB_PORT, config.WEB_HOST)
    url = f"http://{config.WEB_HOST}:{port}"
    logger.info("%s läuft auf %s", config.APP_NAME, url)
    print(f"\n  ▸ {config.APP_NAME} — {url}\n", flush=True)

    app.run(host=config.WEB_HOST, port=port,
            debug=debug, use_reloader=debug, threaded=True)
