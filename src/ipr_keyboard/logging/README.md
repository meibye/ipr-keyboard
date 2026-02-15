# src/ipr_keyboard/logging/

Centralized logger and log-view API blueprints.

## Files

- `logger.py`: singleton logger + rotating file handler
- `web.py`: Flask blueprint for log retrieval

## Log Location

- `<repo>/logs/ipr_keyboard.log`

## Rotation Settings

- max bytes per file: `256 * 1024`
- backups: `5`

## API Endpoints

- `GET /logs/`: full log text
- `GET /logs/tail?lines=<n>`: tail lines (default 200)
