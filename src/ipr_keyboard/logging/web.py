from __future__ import annotations

from flask import Blueprint, jsonify, request, Response

from .logger import log_path

bp_logs = Blueprint("logs", __name__, url_prefix="/logs")


@bp_logs.get("/")
def get_log_whole() -> Response:
    path = log_path()
    if not path.exists():
        return jsonify({"log": ""})
    text = path.read_text(encoding="utf-8", errors="ignore")
    return jsonify({"log": text})


@bp_logs.get("/tail")
def get_log_tail() -> Response:
    lines_param = request.args.get("lines", "200")
    try:
        n_lines = int(lines_param)
    except ValueError:
        n_lines = 200

    path = log_path()
    if not path.exists():
        return jsonify({"log": ""})

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        all_lines = f.readlines()

    tail = "".join(all_lines[-n_lines:])
    return jsonify({"log": tail})
