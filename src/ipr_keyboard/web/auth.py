"""User authentication and credential management.

Stores credentials in users.json at the project root, alongside config.json.
Passwords are hashed with werkzeug's pbkdf2:sha256.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from werkzeug.security import check_password_hash, generate_password_hash

from ..utils.helpers import load_json, project_root, save_json

_USERNAME_RE = re.compile(r"[a-z0-9_]{3,32}")
_MIN_PASSWORD_LEN = 8


def users_path() -> Path:
    return project_root() / "users.json"


def _load_raw() -> dict:
    data = load_json(users_path())
    if not data or "users" not in data:
        return {"users": {}, "version": 1}
    return data


def _save_raw(data: dict) -> None:
    save_json(users_path(), data)


class UserStore:
    """Thread-safe singleton for credential storage and verification."""

    _instance: Optional["UserStore"] = None
    _cls_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ensure_default()

    @classmethod
    def instance(cls) -> "UserStore":
        if cls._instance is None:
            with cls._cls_lock:
                if cls._instance is None:
                    cls._instance = UserStore()
        return cls._instance

    def _ensure_default(self) -> None:
        with self._lock:
            data = _load_raw()
            dirty = False

            if not data["users"]:
                data["users"]["admin"] = {
                    "password_hash": generate_password_hash("password"),
                    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "is_admin": True,
                }
                dirty = True
            else:
                # Backfill is_admin on records created before the field existed.
                for uname, udata in data["users"].items():
                    if "is_admin" not in udata:
                        udata["is_admin"] = (uname == "admin")
                        dirty = True

                # Guarantee at least one admin account exists.
                has_admin = any(u.get("is_admin") for u in data["users"].values())
                if not has_admin:
                    first = next(iter(data["users"]))
                    data["users"][first]["is_admin"] = True
                    dirty = True

            if dirty:
                _save_raw(data)

    def verify(self, username: str, password: str) -> bool:
        with self._lock:
            user = _load_raw()["users"].get(username)
            if user is None:
                return False
            return check_password_hash(user["password_hash"], password)

    def user_info(self, username: str) -> dict:
        with self._lock:
            user = _load_raw()["users"].get(username)
            if user is None:
                raise KeyError(f"User not found: {username}")
            return {
                "username": username,
                "is_admin": user.get("is_admin", False),
                "created_at": user.get("created_at", ""),
            }

    def list_users(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "username": uname,
                    "is_admin": uinfo.get("is_admin", False),
                    "created_at": uinfo.get("created_at", ""),
                }
                for uname, uinfo in _load_raw()["users"].items()
            ]

    def user_exists(self, username: str) -> bool:
        with self._lock:
            return username in _load_raw()["users"]

    def add_user(self, username: str, password: str, is_admin: bool = False) -> None:
        if not _USERNAME_RE.fullmatch(username):
            raise ValueError(
                "Username must be 3–32 characters: lowercase letters, digits, or underscores."
            )
        if len(password) < _MIN_PASSWORD_LEN:
            raise ValueError(f"Password must be at least {_MIN_PASSWORD_LEN} characters.")
        with self._lock:
            data = _load_raw()
            if username in data["users"]:
                raise ValueError(f"User '{username}' already exists.")
            data["users"][username] = {
                "password_hash": generate_password_hash(password),
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "is_admin": is_admin,
            }
            _save_raw(data)

    def change_password(self, username: str, new_password: str) -> None:
        if len(new_password) < _MIN_PASSWORD_LEN:
            raise ValueError(f"Password must be at least {_MIN_PASSWORD_LEN} characters.")
        with self._lock:
            data = _load_raw()
            if username not in data["users"]:
                raise KeyError(f"User not found: {username}")
            data["users"][username]["password_hash"] = generate_password_hash(new_password)
            _save_raw(data)

    def delete_user(self, username: str) -> None:
        with self._lock:
            data = _load_raw()
            if username not in data["users"]:
                raise KeyError(f"User not found: {username}")
            if data["users"][username].get("is_admin", False):
                admin_count = sum(
                    1 for u in data["users"].values() if u.get("is_admin", False)
                )
                if admin_count <= 1:
                    raise ValueError("Cannot delete the last admin account.")
            del data["users"][username]
            _save_raw(data)
