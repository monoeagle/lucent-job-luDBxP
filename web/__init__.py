"""Flask application factory."""
import time

from flask import Flask, g, request

from core.log import init_logging


def create_app() -> Flask:
    logger = init_logging()
    app = Flask(__name__)
    from web.routes import bp
    app.register_blueprint(bp)

    @app.before_request
    def _start_timer() -> None:
        g._req_start = time.perf_counter()

    @app.after_request
    def _log_request(response):
        start = getattr(g, "_req_start", None)
        dur = "" if start is None else f" ({(time.perf_counter() - start) * 1000:.1f} ms)"
        logger.info("%s %s -> %s%s", request.method, request.path, response.status_code, dur)
        return response

    return app
