"""Flask blueprint for configuration API endpoints.

Provides REST API endpoints for viewing and updating application configuration.
"""
from flask import Blueprint, jsonify, request
from .manager import ConfigManager

bp_config = Blueprint("config", __name__, url_prefix="/config")


@bp_config.get("/")
def get_config():
    """Get the current application configuration.
    
    Returns:
        JSON response containing the current configuration as a dictionary.
    """
    cfg = ConfigManager.instance().get()
    return jsonify(cfg.to_dict())


@bp_config.post("/")
def update_config():
    """Update application configuration.
    
    Accepts a JSON payload with configuration key-value pairs to update.
    Only existing configuration fields will be updated.
    
    Returns:
        JSON response containing the updated configuration.
    """
    payload = request.get_json(force=True, silent=True) or {}
    cfg = ConfigManager.instance().update(**payload)
    return jsonify(cfg.to_dict())
