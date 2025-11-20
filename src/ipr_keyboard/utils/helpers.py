import json
from pathlib import Path
from typing import Any, Dict


def project_root() -> Path:
    """Return the project root (two levels up from this file)."""
    return Path(__file__).resolve().parents[2]


def config_path() -> Path:
    """Return the path to the main config.json."""
    root = project_root()
    return root / "config.json"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
