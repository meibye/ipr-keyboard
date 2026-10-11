# src/ipr_keyboard/utils/

Common helper functions.

## Functions in `helpers.py`

- `project_root()` — the repository root; the application keeps its state
  files there (`config.json`, `pen_state.json`, `incidents_handled.json`,
  `users.json`, `logs/`)
- `config_path()` — `<root>/config.json`
- `config_default_path()` — `<root>/config.default.json`
- `seed_from_default(live, default)` — copy the defaults on first start
- `load_json(path)`, `save_json(path, data)`
