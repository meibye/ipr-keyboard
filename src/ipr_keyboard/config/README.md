# src/ipr_keyboard/config/

Configuration management for the application.

## Files

- `manager.py`: `AppConfig` + thread-safe singleton `ConfigManager`
- `web.py`: Flask blueprint (`/config/`)

## Current AppConfig Schema

```python
AppConfig(
    IrisPenFolder: str = "/mnt/irispen",
    DeleteFiles: bool = True,
    Logging: bool = True,
    MaxFileSize: int = 1024 * 1024,
    LogPort: int = 8080,
)
```

## API Endpoints

- `GET /config/`: returns current config
- `POST /config/`: partial updates for known config keys

## Threading Model

- class-level lock protects singleton initialization
- instance-level `RLock` protects reads/writes/reload

## Important Clarification

Current `ConfigManager` does **not** implement backend selection sync fields like `KeyboardBackend`. Any docs/scripts expecting that should be treated as legacy behavior references.
