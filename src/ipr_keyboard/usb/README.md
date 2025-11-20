# USB Module

This module handles USB file detection, reading, and optional cleanup for IrisPen scanner output files.

## Overview

The USB module provides utilities for:
- Monitoring a folder for new files
- Reading file contents with size limits
- Deleting processed files
- Sorting files by modification time

This module is designed to work with IrisPen scanner output but can be used with any USB-mounted device that creates text files.

## Files

- **`detector.py`** - File detection and monitoring
- **`reader.py`** - File reading with size limits
- **`deleter.py`** - File deletion utilities
- **`__init__.py`** - Module initialization

## detector.py

Functions for detecting and monitoring files in a folder.

### `list_files(folder: Path) -> List[Path]`
List all files in a folder, sorted by modification time.

- **Parameters**: `folder` - Directory to scan
- **Returns**: List of `Path` objects, oldest to newest
- **Sorting**: By `st_mtime` (modification time)
- **Filters**: Only regular files (no directories)

### `newest_file(folder: Path) -> Optional[Path]`
Get the most recently modified file in a folder.

- **Parameters**: `folder` - Directory to scan
- **Returns**: `Path` of newest file, or `None` if folder empty
- **Use case**: Quick check for latest file

### `wait_for_new_file(folder: Path, last_seen_mtime: float, interval: float = 1.0) -> Optional[Path]`
Poll folder until a file newer than `last_seen_mtime` appears.

- **Parameters**:
  - `folder` - Directory to monitor
  - `last_seen_mtime` - Timestamp of last processed file
  - `interval` - Polling interval in seconds (default: 1.0)
- **Returns**: `Path` of new file when detected
- **Behavior**: 
  - Loops indefinitely until new file found
  - Sleeps between checks
  - Handles folder not existing (waits for mount)
- **Use case**: Main monitoring loop

## reader.py

Functions for reading file contents with safety limits.

### `read_file(path: Path, max_size: int) -> Optional[str]`
Read a file's contents if it exists and is within size limit.

- **Parameters**:
  - `path` - File to read
  - `max_size` - Maximum allowed file size in bytes
- **Returns**: 
  - File contents as string
  - `None` if file doesn't exist, isn't a file, or exceeds size limit
- **Encoding**: UTF-8 with error handling (ignores invalid characters)
- **Safety**: Prevents reading excessively large files

### `read_newest(folder: Path, max_size: int) -> Optional[str]`
Read the newest file in a folder.

- **Parameters**:
  - `folder` - Directory to check
  - `max_size` - Maximum allowed file size
- **Returns**: Contents of newest file, or `None`
- **Convenience**: Combines `newest_file()` and `read_file()`

## deleter.py

Functions for deleting files after processing.

### `delete_file(path: Path) -> bool`
Delete a single file.

- **Parameters**: `path` - File to delete
- **Returns**: `True` if no error occurred (file deleted or didn't exist), `False` on error
- **Safety**: 
  - Checks file exists and is a regular file
  - Catches `OSError` exceptions
  - Returns `True` if file doesn't exist (idempotent operation)

### `delete_all(folder: Path) -> List[Path]`
Delete all files in a folder.

- **Parameters**: `folder` - Directory to clean
- **Returns**: List of successfully deleted files
- **Behavior**:
  - Skips directories
  - Continues on errors
  - Returns partial results if some deletions fail

### `delete_newest(folder: Path) -> Optional[Path]`
Delete the newest file in a folder.

- **Parameters**: `folder` - Directory containing file
- **Returns**: Path of deleted file, or `None` on failure
- **Convenience**: Combines `newest_file()` and `delete_file()`

## Usage Example

### Main Application Loop

```python
from pathlib import Path
from ipr_keyboard.usb import detector, reader, deleter
from ipr_keyboard.config.manager import ConfigManager

cfg = ConfigManager.instance().get()
folder = Path(cfg.IrisPenFolder)
last_mtime = 0.0

while True:
    # Wait for new file
    new_file = detector.wait_for_new_file(folder, last_mtime, interval=1.0)
    if new_file is None:
        continue
    
    # Update timestamp
    last_mtime = new_file.stat().st_mtime
    
    # Read file
    text = reader.read_file(new_file, cfg.MaxFileSize)
    if text is None:
        print(f"File too large or unreadable: {new_file}")
        continue
    
    # Process text
    print(f"Read {len(text)} bytes from {new_file}")
    
    # Optionally delete
    if cfg.DeleteFiles:
        if deleter.delete_file(new_file):
            print(f"Deleted: {new_file}")
        else:
            print(f"Failed to delete: {new_file}")
```

### Manual File Operations

```python
from pathlib import Path
from ipr_keyboard.usb import detector, reader, deleter

folder = Path("/mnt/irispen")

# List all files
files = detector.list_files(folder)
print(f"Found {len(files)} files")

# Get newest file
newest = detector.newest_file(folder)
if newest:
    print(f"Newest file: {newest}")
    
    # Read it
    content = reader.read_file(newest, max_size=1024*1024)
    if content:
        print(f"Content: {content[:100]}...")
    
    # Delete it
    if deleter.delete_file(newest):
        print("Deleted successfully")
```

## File Detection Strategy

The module uses modification time (`st_mtime`) to track files:

1. Store last processed file's `mtime`
2. Poll folder for files
3. Check if newest file's `mtime` is greater than stored value
4. Process file and update stored `mtime`

This approach:
- ✓ Handles files created while monitoring
- ✓ Works with mount/unmount cycles
- ✓ Simple and reliable
- ✗ Assumes IrisPen creates files with increasing timestamps
- ✗ Clock changes could cause issues

## Safety Features

### Size Limits
- Prevents reading extremely large files
- Configurable via `MaxFileSize` setting
- Default: 1 MB

### Encoding Handling
- UTF-8 with error handling
- Invalid characters ignored (`errors="ignore"`)
- Works with various text encodings

### Error Handling
- File operations wrapped in try/except
- Graceful handling of missing folders
- Returns `None`/`False` on errors rather than raising exceptions

## Thread Safety

- **Read-only operations**: Safe from multiple threads
- **File operations**: Not internally synchronized
  - Caller responsible for coordinating deletes
  - Main application uses single monitor thread

## Integration

Used by `main.py` in the main monitoring loop:

1. **Wait** for new file with `wait_for_new_file()`
2. **Read** file content with `read_file()`
3. **Send** text via Bluetooth
4. **Delete** file with `delete_file()` (if configured)

## Testing

Tests are located in `tests/usb/test_usb_reader.py`:
- File detection
- Reading with size limits
- Deletion operations
- Edge cases (missing files, permissions)

## Performance

- **Polling**: 1-second intervals (configurable)
- **File I/O**: Synchronous, blocking operations
- **Scalability**: Designed for low-frequency file creation (typical IrisPen usage)

## Troubleshooting

### Files not detected
- Check folder exists and is mounted
- Verify folder path in configuration
- Check file permissions
- Ensure files have proper modification times

### Files not deleted
- Check write permissions on folder
- Verify `DeleteFiles` configuration
- Check logs for error messages

### Large files skipped
- Check `MaxFileSize` configuration
- Increase limit if needed (default 1 MB)
- Files over limit are logged as warnings
