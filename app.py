"""LucentTools DB Explorer - entry point."""
import logging
import os

import config
from core import userpaths
from core.settings import Settings
from web import create_app

app = create_app()  # initialisiert auch das Logging (core.log.init_logging)


def run_server(app, host, port, debug):
    """AP-31: Server-Weiche. Normalbetrieb → waitress (Prod-WSGI-Server);
    Debug → Werkzeug-Dev-Server mit Auto-Reload (waitress kann kein Reload)."""
    if debug:
        app.run(host=host, port=port, debug=True, use_reloader=True, threaded=True)
    else:
        from waitress import serve
        serve(app, host=host, port=port)


if __name__ == "__main__":
    logger = logging.getLogger("luDBxP")

    # AP-31: vorhandene App-Verzeichnis-config.json einmalig pro Nutzer übernehmen.
    user_cfg = userpaths.user_config_file(config.APP_SLUG)
    if userpaths.migrate_legacy_config(user_cfg, config.LEGACY_CONFIG_JSON):
        logger.info("config.json aus App-Verzeichnis übernommen → %s", user_cfg)

    # Seed the bundled "Demo" connection (SQLite demo CMDB) so the connection
    # picker works out of the box. Added once if absent; never overwrites.
    demo_db = os.path.join(config.BASE_DIR, "sample_data", "demo_cmdb.db")
    if os.path.exists(demo_db):
        settings = Settings.load()
        conns = list(settings.get("connections") or [])
        if not any(c.get("name") == "Demo" for c in conns):
            conns.append({"name": "Demo", "db_type": "sqlite", "filepath": demo_db})
            settings.set("connections", conns)
            settings.save()
            logger.info("Demo-Verbindung angelegt → %s", demo_db)

    # Debug optional via Umgebungsvariable (run.ps1 -DebugMode setzt sie).
    debug = os.environ.get("LUCENT_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

    # AP-31: Port pro Session. Ohne LUCENT_PORT erst 5057 versuchen, sonst freien
    # Port; LUCENT_PORT=<n> erzwingt einen festen Port, =0 immer dynamisch.
    port = userpaths.resolve_port(os.environ.get("LUCENT_PORT"),
                                  config.WEB_PORT, config.WEB_HOST)
    url = f"http://{config.WEB_HOST}:{port}"
    logger.info("%s läuft auf %s", config.APP_NAME, url)
    print(f"\n  ▸ {config.APP_NAME} — {url}\n", flush=True)

    run_server(app, config.WEB_HOST, port, debug)
