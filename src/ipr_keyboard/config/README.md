# Configuration Module

This module provides thread-safe configuration management with JSON persistence and web API access.

## Overview

The configuration module manages application settings through a singleton `ConfigManager` that provides:
- Thread-safe read/write operations
- JSON file persistence
- Runtime configuration updates
- Web API for remote configuration
- Default configuration values

## Files

- **`manager.py`** - Core ConfigManager class and AppConfig dataclass
- **`web.py`** - Flask blueprint for configuration REST API
- **`__init__.py`** - Module initialization

## AppConfig Dataclass

The `AppConfig` dataclass defines all application configuration fields:

```python
@dataclass
class AppConfig:
    IrisPenFolder: str = "/mnt/irispen"    # USB mount point
    DeleteFiles: bool = True                # Delete after processing
    Logging: bool = True                    # Enable logging
    MaxFileSize: int = 1024 * 1024         # Max file size (1MB)
    LogPort: int = 8080                     # Web server port
```

### Methods

- **`from_dict(data: Dict[str, Any]) -> AppConfig`** - Create config from dictionary
- **`to_dict() -> Dict[str, Any]`** - Convert config to dictionary

## ConfigManager Class

The `ConfigManager` is a thread-safe singleton that manages the application configuration.

### Key Methods

#### `instance() -> ConfigManager`
Get or create the singleton ConfigManager instance.
- **Returns**: The global ConfigManager instance
- **Thread-safe**: Uses class-level lock

#### `get() -> AppConfig`
Get a copy of the current configuration.
- **Returns**: AppConfig instance (shallow copy)
- **Thread-safe**: Uses instance lock
- **Note**: Returns a copy to prevent accidental mutation

#### `update(**kwargs) -> AppConfig`
Update configuration fields and persist to JSON.
- **Parameters**: Keyword arguments matching AppConfig fields
- **Returns**: Updated AppConfig instance
- **Thread-safe**: Uses instance lock
- **Side effects**: Writes to JSON file

#### `reload() -> AppConfig`
Reload configuration from JSON file.
- **Returns**: Updated AppConfig instance
- **Thread-safe**: Uses instance lock
- **Use case**: Manual config.json edits

### Constructor

```python
ConfigManager(path: Optional[Path] = None)
```
- **Parameters**: 
  - `path` - Path to config.json (defaults to project_root/config.json)
- **Note**: Typically not called directly; use `instance()` instead

## Thread Safety

The module uses multiple levels of thread safety:

1. **Class-level lock** (`_lock`): Protects singleton creation
2. **Instance-level lock** (`_cfg_lock`): Protects configuration access
3. **RLock**: Allows recursive locking for nested operations

All public methods are thread-safe and can be called from multiple threads concurrently.

## Configuration Persistence

Configuration is stored in `config.json` in the project root:

```json
{
  "DeleteFiles": true,
  "IrisPenFolder": "/mnt/irispen",
  "LogPort": 8080,
  "Logging": true,
  "MaxFileSize": 1048576
}
```

- **Auto-save**: Updates are immediately persisted
- **Pretty-printed**: JSON is indented and sorted for readability
- **Atomic writes**: File operations use standard Python file I/O

## Web API

The `web.py` module provides a Flask blueprint for HTTP configuration access:

### Endpoints

#### `GET /config/`
Get current configuration.
- **Response**: JSON object with all configuration fields
- **Example**:
  ```json
  {
    "IrisPenFolder": "/mnt/irispen",
    "DeleteFiles": true,
    "Logging": true,
    "MaxFileSize": 1048576,
    "LogPort": 8080
  }
  ```

#### `POST /config/`
Update configuration fields.
- **Request Body**: JSON object with fields to update
- **Response**: Updated configuration
- **Example**:
  ```bash
  curl -X POST http://localhost:8080/config/ \
    -H "Content-Type: application/json" \
    -d '{"DeleteFiles": false, "MaxFileSize": 2097152}'
  ```

The blueprint is registered in the main Flask app as `/config/`.

## Usage Example

```python
from ipr_keyboard.config.manager import ConfigManager

# Get singleton instance
cfg_mgr = ConfigManager.instance()

# Read configuration
config = cfg_mgr.get()
print(f"IrisPen folder: {config.IrisPenFolder}")

# Update configuration
new_config = cfg_mgr.update(
    DeleteFiles=False,
    MaxFileSize=2 * 1024 * 1024
)

# Reload from file (after manual edit)
reloaded = cfg_mgr.reload()
```

## Default Values

If `config.json` doesn't exist or is empty, the default values from `AppConfig` are used:
- IrisPenFolder: `/mnt/irispen`
- DeleteFiles: `true`
- Logging: `true`
- MaxFileSize: `1048576` (1 MB)
- LogPort: `8080`

## Testing

Tests are located in `tests/config/test_manager.py`:
- Singleton pattern
- Thread-safe operations
- JSON persistence
- Field updates
- Default values

Web API tests are in `tests/web/test_config_api.py`:
- GET endpoint
- POST endpoint
- Invalid requests
