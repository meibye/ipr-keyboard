"""Tests for utility helper functions.

Tests path resolution and JSON file operations.
"""
import json
from pathlib import Path

from ipr_keyboard.utils.helpers import (
    project_root,
    config_path,
    load_json,
    save_json,
)


def test_project_root():
    """Test that project_root returns the repository root.
    
    Verifies that the path contains expected project files.
    """
    root = project_root()
    
    assert root.is_dir()
    # Should contain pyproject.toml
    assert (root / "pyproject.toml").exists()
    # Should contain src directory
    assert (root / "src").exists()


def test_config_path():
    """Test that config_path returns path to config.json.
    
    Verifies that the config path is in project root.
    """
    path = config_path()
    
    assert path.name == "config.json"
    assert path.parent == project_root()


def test_load_json(tmp_path):
    """Test loading JSON from a file.
    
    Verifies that JSON content is correctly parsed.
    """
    json_file = tmp_path / "test.json"
    expected = {"key": "value", "number": 42, "nested": {"a": 1}}
    
    with open(json_file, "w") as f:
        json.dump(expected, f)
    
    result = load_json(json_file)
    
    assert result == expected


def test_load_json_missing_file(tmp_path):
    """Test loading JSON from non-existent file.
    
    Verifies that an empty dict is returned.
    """
    missing = tmp_path / "nonexistent.json"
    
    result = load_json(missing)
    
    assert result == {}


def test_save_json(tmp_path):
    """Test saving data to JSON file.
    
    Verifies that data is correctly serialized.
    """
    json_file = tmp_path / "output.json"
    data = {"key": "value", "list": [1, 2, 3]}
    
    save_json(json_file, data)
    
    assert json_file.exists()
    
    with open(json_file, "r") as f:
        loaded = json.load(f)
    
    assert loaded == data


def test_save_json_creates_directories(tmp_path):
    """Test that save_json creates parent directories.
    
    Verifies that missing directories are created automatically.
    """
    nested = tmp_path / "deep" / "nested" / "path" / "file.json"
    data = {"test": True}
    
    save_json(nested, data)
    
    assert nested.exists()
    assert nested.parent.exists()


def test_save_json_formatting(tmp_path):
    """Test that saved JSON is formatted with indentation.
    
    Verifies that the output is human-readable.
    """
    json_file = tmp_path / "formatted.json"
    data = {"b": 2, "a": 1}
    
    save_json(json_file, data)
    
    content = json_file.read_text()
    
    # Should be indented (multi-line)
    assert "\n" in content
    # Should have keys sorted
    assert content.index('"a"') < content.index('"b"')


def test_save_json_overwrites(tmp_path):
    """Test that save_json overwrites existing files.
    
    Verifies that existing content is replaced.
    """
    json_file = tmp_path / "existing.json"
    
    # Write initial content
    save_json(json_file, {"old": True})
    
    # Overwrite
    save_json(json_file, {"new": True})
    
    result = load_json(json_file)
    assert result == {"new": True}
    assert "old" not in result


def test_load_save_roundtrip(tmp_path):
    """Test that data survives a save/load roundtrip.
    
    Verifies that no data is lost in serialization.
    """
    json_file = tmp_path / "roundtrip.json"
    original = {
        "string": "value",
        "number": 42,
        "float": 3.14,
        "boolean": True,
        "null": None,
        "list": [1, 2, 3],
        "nested": {"a": {"b": {"c": 1}}}
    }
    
    save_json(json_file, original)
    loaded = load_json(json_file)
    
    assert loaded == original
