# Utils Module

This module provides utility functions and helpers used throughout the application.

## Overview

The utils module contains common functionality that doesn't belong to a specific domain module, primarily focusing on file system operations and path resolution.

## Files

- **`helpers.py`** - Project root/config path resolution, JSON helpers
- **`backend_sync.py`** - Backend synchronization utilities for `/etc/ipr-keyboard/backend`
- **`__init__.py`** - Module initialization

## Related Scripts & Utilities

While this module is primarily used internally by other modules, you may see its helpers referenced in scripts throughout the `scripts/` folder for path resolution and JSON file operations. No direct utility scripts are provided in this folder, but see the main and scripts `README.md` for workflow and troubleshooting scripts that rely on these utilities.

## Usage Patterns

### Configuration File Management

```python
from ipr_keyboard.utils.helpers import config_path, load_json, save_json

# Load configuration
cfg_file = config_path()
config = load_json(cfg_file)

# Modify configuration
config["DeleteFiles"] = False

# Save configuration
save_json(cfg_file, config)
```

### Creating Project-Relative Paths

```python
from ipr_keyboard.utils.helpers import project_root

root = project_root()

# Build paths relative to project
logs_dir = root / "logs"
data_dir = root / "data"
scripts_dir = root / "scripts"

# Ensure directories exist
logs_dir.mkdir(exist_ok=True)
```

### JSON Data Handling

```python
from pathlib import Path
from ipr_keyboard.utils.helpers import load_json, save_json

# Load with defaults
data = load_json(Path("settings.json"))
setting = data.get("some_key", "default_value")

# Save with automatic formatting
save_json(Path("settings.json"), {"key": "value"})
```

## helpers.py

Core utility functions for the application.

## backend_sync.py

Backend synchronization utilities for managing `/etc/ipr-keyboard/backend`.

### Purpose

This module ensures that the `KeyboardBackend` setting in `config.json` stays synchronized with the system-level backend selection file `/etc/ipr-keyboard/backend`. This prevents conflicts between the application config and the backend manager service.

### Functions

#### `read_backend_file() -> Optional[str]`
Read the current backend selection from `/etc/ipr-keyboard/backend`.

- **Returns**: Backend type ("uinput" or "ble"), or `None` if file doesn't exist or is unreadable
- **Validation**: Only returns valid backend values
- **Error handling**: Returns `None` on permission errors or I/O errors

**Example:**
```python
from ipr_keyboard.utils.backend_sync import read_backend_file

backend = read_backend_file()
if backend:
    print(f"Current backend: {backend}")
else:
    print("Backend file not found or invalid")
```

#### `write_backend_file(backend: str) -> bool`
Write the backend selection to `/etc/ipr-keyboard/backend`.

- **Parameters**: `backend` - Backend type ("uinput" or "ble")
- **Returns**: `True` if successful, `False` if write failed
- **Side effects**: Creates `/etc/ipr-keyboard/` directory if it doesn't exist
- **Validation**: Only accepts "uinput" or "ble" values
- **Permissions**: Requires write access to `/etc/ipr-keyboard/`

**Example:**
```python
from ipr_keyboard.utils.backend_sync import write_backend_file

success = write_backend_file("ble")
if success:
    print("Backend file updated successfully")
else:
    print("Failed to write backend file (check permissions)")
```

#### `sync_backend_to_file(backend: str) -> bool`
Convenience wrapper for `write_backend_file()`.

- **Parameters**: `backend` - Backend type to sync
- **Returns**: `True` if successful, `False` otherwise

### Integration

This module is used by:
- **ConfigManager**: Synchronizes backend on startup and updates
- **Tests**: Validates backend synchronization behavior

### File Format

The `/etc/ipr-keyboard/backend` file is a simple text file containing a single line:
```
ble
```
or
```
uinput
```

Whitespace is automatically stripped when reading.

### Permissions

Writing to `/etc/ipr-keyboard/backend` typically requires root privileges. If the application runs as a non-root user:
- Reading the file works if readable by all users
- Writing the file may fail silently (returns `False`)
- ConfigManager logs warnings on write failures

### Thread Safety

- All functions are thread-safe (no shared state)
- File operations are not synchronized
- ConfigManager provides higher-level synchronization when needed

## helpers.py

Core utility functions for the application.

### Path Utilities

#### `project_root() -> Path`
Get the absolute path to the project root directory.

- **Returns**: `Path` object pointing to project root
- **Resolution**: Two levels up from this file's location
  - File location: `src/ipr_keyboard/utils/helpers.py`
  - Project root: `../../` from file
- **Use case**: Building paths relative to project root

**Example:**
```python
from ipr_keyboard.utils.helpers import project_root

root = project_root()
logs_dir = root / "logs"
config_file = root / "config.json"
```

#### `config_path() -> Path`
Get the path to the main configuration file.

- **Returns**: `Path` object pointing to `config.json` in project root
- **File location**: `<project_root>/config.json`
- **Use case**: Loading/saving configuration

**Example:**
```python
from ipr_keyboard.utils.helpers import config_path

cfg_path = config_path()
if cfg_path.exists():
    print(f"Config found at: {cfg_path}")
```

### JSON Utilities

#### `load_json(path: Path) -> Dict[str, Any]`
Load JSON data from a file.

- **Parameters**: `path` - Path to JSON file
- **Returns**: Dictionary with parsed JSON data
- **Behavior**:
  - Returns `{}` (empty dict) if file doesn't exist
  - No error raised for missing files
- **Encoding**: UTF-8

**Example:**
```python
from pathlib import Path
from ipr_keyboard.utils.helpers import load_json

data = load_json(Path("config.json"))
print(f"IrisPenFolder: {data.get('IrisPenFolder', 'not set')}")
```

#### `save_json(path: Path, data: Dict[str, Any]) -> None`
Save data to a JSON file.

- **Parameters**:
  - `path` - Destination file path
  - `data` - Dictionary to serialize
- **Behavior**:
  - Creates parent directories if they don't exist
  - Pretty-prints JSON (indented)
  - Sorts keys alphabetically
- **Encoding**: UTF-8

**Example:**
```python
from pathlib import Path
from ipr_keyboard.utils.helpers import save_json

config = {
    "IrisPenFolder": "/mnt/irispen",
    "DeleteFiles": True,
    "LogPort": 8080
}
save_json(Path("config.json"), config)
```

## Usage Patterns

### Configuration File Management

```python
from ipr_keyboard.utils.helpers import config_path, load_json, save_json

# Load configuration
cfg_file = config_path()
config = load_json(cfg_file)

# Modify configuration
config["DeleteFiles"] = False

# Save configuration
save_json(cfg_file, config)
```

### Creating Project-Relative Paths

```python
from ipr_keyboard.utils.helpers import project_root

root = project_root()

# Build paths relative to project
logs_dir = root / "logs"
data_dir = root / "data"
scripts_dir = root / "scripts"

# Ensure directories exist
logs_dir.mkdir(exist_ok=True)
```

### JSON Data Handling

```python
from pathlib import Path
from ipr_keyboard.utils.helpers import load_json, save_json

# Load with defaults
data = load_json(Path("settings.json"))
setting = data.get("some_key", "default_value")

# Save with automatic formatting
save_json(Path("settings.json"), {"key": "value"})
```

## Design Decisions

### Why Empty Dict for Missing Files?

The `load_json()` function returns `{}` instead of raising an exception when a file doesn't exist. This design:
- Simplifies first-run scenarios (no config file yet)
- Allows default values to be applied
- Reduces error handling code
- Follows "be liberal in what you accept" principle

### Why Auto-Create Parent Directories?

The `save_json()` function creates parent directories automatically because:
- Simplifies calling code (no need to check/create dirs first)
- Safe operation (idempotent with `parents=True, exist_ok=True`)
- Common use case (logs/, data/ directories may not exist initially)

### Why Sorted Keys in JSON?

JSON output is sorted for:
- Consistent formatting (easier to compare files)
- Better version control (reduces diff noise)
- Human readability (alphabetical order)

## Integration

This module is used by:
- **Config module**: Path resolution and JSON persistence
- **Logging module**: Project root for logs directory
- **Main module**: Indirectly via other modules

## Testing

While this module doesn't have dedicated tests, its functions are tested indirectly through:
- `tests/config/test_manager.py` - Tests JSON operations via ConfigManager
- Integration tests throughout the test suite

## Thread Safety

- **Path functions**: Thread-safe (no state)
- **JSON functions**: Thread-safe (no shared state)
- **File operations**: Not synchronized
  - Caller responsible for coordinating concurrent writes
  - ConfigManager provides higher-level synchronization

## Performance

- **Path resolution**: Fast (simple parent navigation)
- **JSON parsing**: Standard library performance
- **JSON formatting**: Slightly slower due to sorting/indenting
  - Acceptable for configuration files (infrequent writes)

## Error Handling

### `load_json()`
- Missing file: Returns `{}`
- Invalid JSON: Raises `json.JSONDecodeError`
- Permission denied: Raises `PermissionError`

### `save_json()`
- Permission denied: Raises `PermissionError`
- Invalid path: Raises `OSError`
- Non-serializable data: Raises `TypeError`

Callers should handle exceptions as appropriate for their use case.

## Future Extensions

Possible additions to this module:
- YAML configuration support
- Environment variable expansion
- Configuration validation
- Backup/restore utilities
- Temporary file management

## Best Practices

When using these utilities:
1. **Always use `config_path()`** for config file access
2. **Always use `project_root()`** for project-relative paths
3. **Let `save_json()` create directories** (don't pre-create)
4. **Handle `load_json()` empty dict** with `.get()` or defaults
5. **Don't catch exceptions** unless you have specific recovery logic


## See Also

- [Config Module](../config/README.md) — Uses these utilities for config file management
- [Main Module](../README.md) — Application entry point and structure
- [Main README](../../../README.md) — Project overview
