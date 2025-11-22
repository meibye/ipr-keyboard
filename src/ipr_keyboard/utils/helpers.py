"""Utility helper functions.

Provides path resolution and JSON file operations.
"""
import json
from pathlib import Path
from typing import Any, Dict


def project_root() -> Path:
    """Get the project root directory.
    
    Returns:
+        Path to the project root (repository root).
+        Layout:
+          <repo>/src/ipr_keyboard/utils/helpers.py
+          -> project root is three levels up.
    """
    return Path(__file__).resolve().parents[3]


def config_path() -> Path:
    """Get the path to the main configuration file.
    
    Returns:
        Path to config.json in the project root.
    """
    root = project_root()
    return root / "config.json"


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON data from a file.
    
    Args:
        path: Path to the JSON file.
        
    Returns:
        Dictionary containing the JSON data, or an empty dictionary
        if the file doesn't exist.
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    """Save data to a JSON file.
    
    Creates parent directories if they don't exist. The JSON is formatted
    with indentation and sorted keys for readability.
    
    Args:
        path: Path to the JSON file to write.
        data: Dictionary to serialize as JSON.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
