# Logging Module

This module provides centralized logging functionality with file rotation and web-based log viewing.

## Overview

The logging module sets up a singleton logger with:
- File-based logging with rotation
- Console output for debugging
- Standardized formatting
- Web API for log viewing
- Thread-safe operation

All application logs are written to a single rotating log file in the `logs/` directory.

## Files

- **`logger.py`** - Logger initialization and configuration
- **`web.py`** - Flask blueprint for log viewing API
- **`__init__.py`** - Module initialization

## Related Scripts

- The log viewing web API is started by the main application and is accessible via the endpoints described below. No direct script is needed to start the logging API, but you can use the diagnostic and demo scripts in the `scripts/` folder to test log output and web access.

## Logger Configuration

### Log File Location

Logs are stored at: `<project_root>/logs/ipr_keyboard.log`

### File Rotation

The logger uses `RotatingFileHandler` with:
- **Max size**: 256 KB per file
- **Backup count**: 5 backup files (plus 1 active file = 6 total)
- **Encoding**: UTF-8
- **Rotation**: Automatic when size limit reached

Total log storage: ~1.5 MB (256 KB × 6 files: 1 active + 5 backups)

### Log Format

```
YYYY-MM-DD HH:MM:SS [LEVEL] logger_name - message
```

Example:
```
2025-11-20 22:40:18 [INFO] ipr_keyboard - Starting web server on port 8080
```

### Log Levels

The logger is configured at `INFO` level, capturing:
- INFO: Normal operations (file detected, text sent, etc.)
- WARNING: Non-critical issues (Bluetooth unavailable, missing folder)
- ERROR: Error conditions (failed to delete file, helper execution failed)

DEBUG messages are not logged by default.

## get_logger() Function

```python
def get_logger() -> logging.Logger
```

Returns the singleton logger instance.

- **Name**: `ipr_keyboard`
- **Handlers**: File (rotating) + console (stdout)
- **Thread-safe**: Safe to call from multiple modules/threads
- **Lazy initialization**: Logger created on first call

### Usage

```python
from ipr_keyboard.logging.logger import get_logger

logger = get_logger()
logger.info("Application started")
logger.warning("Configuration issue detected")
logger.error("Failed to process file")
```

## log_path() Function

```python
def log_path() -> Path
```

Returns the path to the log file.

- **Returns**: `Path` object pointing to `logs/ipr_keyboard.log`
- **Use case**: Web endpoints, external log viewers

## Web API

The `web.py` module provides Flask endpoints for viewing logs:

### Endpoints

#### `GET /logs/`
Retrieve the entire log file.

- **Response**: JSON with `log` field containing full log content
- **Example**:
  ```bash
  curl http://localhost:8080/logs/
  ```
  ```json
  {
    "log": "2025-11-20 22:40:18 [INFO] ipr_keyboard - Starting...\n..."
  }
  ```

#### `GET /logs/tail?lines=N`
Retrieve the last N lines of the log.

- **Query Parameter**: 
  - `lines` - Number of lines to return (default: 200)
- **Response**: JSON with `log` field containing tail of log
- **Example**:
  ```bash
  curl http://localhost:8080/logs/tail?lines=50
  ```

### Error Handling

If the log file doesn't exist:
- Returns `{"log": ""}` (empty string)
- No error raised

The blueprint is registered in the main Flask app as `/logs/`.

## Usage Examples

### Basic Logging

```python
from ipr_keyboard.logging.logger import get_logger

logger = get_logger()

# Log operations
logger.info("Detected new file: %s", file_path)
logger.warning("Bluetooth helper not available")
logger.error("Failed to delete file: %s", error)
```

### Accessing Logs Programmatically

```python
from ipr_keyboard.logging.logger import log_path

log_file = log_path()
if log_file.exists():
    content = log_file.read_text()
    print(f"Log size: {len(content)} bytes")
```

### Web-based Log Viewing

```bash
# View recent logs
curl http://localhost:8080/logs/tail?lines=100

# View full log
curl http://localhost:8080/logs/
```

## Log Directory Structure

```
logs/
├── ipr_keyboard.log       # Current log file
├── ipr_keyboard.log.1     # Previous rotation
├── ipr_keyboard.log.2
├── ipr_keyboard.log.3
├── ipr_keyboard.log.4
└── ipr_keyboard.log.5     # Oldest backup
```

## Integration with Application

The logger is used throughout the application:

1. **Main module**: Application lifecycle events
2. **Bluetooth module**: Text sending operations
3. **USB module**: File detection and processing
4. **Config module**: Configuration changes
5. **Web module**: HTTP requests (via Flask)

## Thread Safety

- Logger instance is thread-safe (Python's `logging` module is thread-safe)
- Multiple threads can log concurrently
- File rotation is atomic
- Console output is thread-safe

## Testing

Tests are located in `tests/logging/test_logger.py`:
- Logger initialization
- Log file creation
- Directory creation
- Singleton behavior

## Performance Considerations

- **File I/O**: Logs are written synchronously (blocking)
- **Rotation**: Happens synchronously when size limit reached
- **Console output**: May slow down high-frequency logging
- **Recommendation**: Use INFO level for production, DEBUG for development

## Troubleshooting

### Logs not appearing
- Check `logs/` directory exists and is writable
- Verify logger is initialized (`get_logger()` called)
- Check log level (DEBUG messages not shown by default)

### Log file not rotating
- Check file size (rotation at 256 KB)
- Verify write permissions
- Check backup count (max 5 backups)

### Web endpoint returns empty log
- Verify log file exists at `logs/ipr_keyboard.log`
- Check file permissions
- Ensure logger has been initialized
