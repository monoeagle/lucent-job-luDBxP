"""Flask application factory."""
from flask import Flask

from core.log import init_logging


def create_app() -> Flask:
    init_logging()
    app = Flask(__name__)
    from web.routes import bp
    app.register_blueprint(bp)
    return app
