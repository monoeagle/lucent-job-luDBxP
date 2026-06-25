"""Lucent DB Explorer — entry point."""
import config
from web import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=config.WEB_HOST, port=config.WEB_PORT)
