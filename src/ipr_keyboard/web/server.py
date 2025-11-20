from __future__ import annotations

from flask import Flask, jsonify

from ..logging.logger import get_logger
from ..config.web import bp_config
from ..logging.web import bp_logs

logger = get_logger()


def create_app() -> Flask:
    app = Flask(__name__)

    app.register_blueprint(bp_config)
    app.register_blueprint(bp_logs)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    logger.info("Web server created")
    return app
