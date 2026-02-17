# src/ipr_keyboard/web/

Flask web layer for status/config/log/pairing operations.

## Files

- `server.py`: app factory and root endpoints
- `pairing_routes.py`: pairing wizard routes
- `templates/pairing_wizard.html`: pairing UI

## Endpoints Registered by `create_app()`

- `GET /health`
- `GET /status`
- `GET /config/`
- `POST /config/`
- `GET /logs/`
- `GET /logs/tail`
- `GET /pairing`
- `GET /pairing/start`

## Implementation Notes

- `/status` reads environment (`IPR_USER`, `IPR_PROJECT_ROOT`) and reports service/adaptor data.
- Pairing routes execute shell/systemctl calls and are operationally privileged.
