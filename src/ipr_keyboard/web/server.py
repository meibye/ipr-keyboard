"""Flask web server application factory.

Creates and configures the Flask application with all blueprints.
"""
from __future__ import annotations

from flask import Flask, jsonify

from ..logging.logger import get_logger
from ..config.web import bp_config
from ..logging.web import bp_logs

logger = get_logger()


def create_app() -> Flask:
    """Create and configure the Flask application.
    
    Registers all blueprints (config and logs) and sets up health check endpoint.
    
    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    app.register_blueprint(bp_config)
    app.register_blueprint(bp_logs)

    @app.get("/health")
    def health():
        """Health check endpoint.
        
        Returns:
            JSON response with status "ok".
        """
        return jsonify({"status": "ok"})

    logger.info("Web server created")
    return app
