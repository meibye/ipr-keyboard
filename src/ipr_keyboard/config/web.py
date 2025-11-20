from flask import Blueprint, jsonify, request
from .manager import ConfigManager

bp_config = Blueprint("config", __name__, url_prefix="/config")


@bp_config.get("/")
def get_config():
    cfg = ConfigManager.instance().get()
    return jsonify(cfg.to_dict())


@bp_config.post("/")
def update_config():
    payload = request.get_json(force=True, silent=True) or {}
    cfg = ConfigManager.instance().update(**payload)
    return jsonify(cfg.to_dict())
