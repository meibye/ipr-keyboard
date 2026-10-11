# src/ipr_keyboard/logging/

The application's logger and a small blueprint that serves its file.

## Files

- `logger.py`: `get_logger()` (singleton), `set_log_level()`, `log_path()`
- `web.py`: Flask blueprint `bp_logs` at `/logs/`

## Log Location

- `<repo>/logs/ipr_keyboard.log`, rotated at 256 KB with 5 backups (6
  files at most).  Everything also goes to the journal
  (`journalctl -u ipr_keyboard.service`), which is what the dashboard reads.

## Endpoints

- `GET /logs/`: the whole log file as text
- `GET /logs/tail?lines=<n>`: the last lines (default 200)

The journal viewer is the dashboard's Debug ▸ Logs (`/api/logs/raw`).
