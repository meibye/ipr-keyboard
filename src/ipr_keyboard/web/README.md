# Web Module

This module provides a Flask-based web server for configuration management, log viewing, and health monitoring.

## Overview

The web module implements a REST API using Flask that allows:
- Configuration viewing and updating via HTTP
- Log file viewing and tailing
- Health check endpoint
- Integration with other modules via blueprints

The web server runs in a background thread and listens on a configurable port (default: 8080).

## Files

- **`server.py`** - Main Flask application factory
- **`__init__.py`** - Module initialization

## server.py

Contains the Flask application factory and main endpoints.

### `create_app() -> Flask`
Create and configure the Flask application.

- **Returns**: Configured Flask application instance
- **Behavior**:
  - Creates Flask app
  - Registers blueprints (config, logs)
  - Registers root-level endpoints
  - Initializes logger
- **Pattern**: Factory pattern for testability

### Root Endpoints

#### `GET /health`
Health check endpoint for monitoring.

- **Response**: JSON with status
- **Status Code**: 200
- **Example**:
  ```bash
  curl http://localhost:8080/health
  ```
  ```json
  {
    "status": "ok"
  }
  ```
- **Use case**: 
  - Service monitoring
  - Load balancer health checks
  - Smoke tests

## Registered Blueprints

The application registers blueprints from other modules:

### Configuration Blueprint (`/config/`)
From `config.web` module - see [config/README.md](../config/README.md#web-api)

Endpoints:
- `GET /config/` - Get current configuration
- `POST /config/` - Update configuration

### Logs Blueprint (`/logs/`)
From `logging.web` module - see [logging/README.md](../logging/README.md#web-api)

Endpoints:
- `GET /logs/` - Get full log file
- `GET /logs/tail?lines=N` - Get last N lines

## Application Startup

The web server is started by `main.py` in a daemon thread:

```python
def run_web_server():
    cfg = ConfigManager.instance().get()
    app = create_app()
    app.run(host="0.0.0.0", port=cfg.LogPort, debug=False, use_reloader=False)

t_web = threading.Thread(target=run_web_server, daemon=True)
t_web.start()
```

### Server Configuration

- **Host**: `0.0.0.0` (accessible from network)
- **Port**: Configurable via `LogPort` (default: 8080)
- **Debug**: Disabled (for production use)
- **Reloader**: Disabled (incompatible with threading)
- **Thread**: Daemon (exits with main application)

## API Usage Examples

### Check Service Health

```bash
curl http://raspberry-pi:8080/health
```

### View Configuration

```bash
curl http://raspberry-pi:8080/config/
```

Response:
```json
{
  "DeleteFiles": true,
  "IrisPenFolder": "/mnt/irispen",
  "LogPort": 8080,
  "Logging": true,
  "MaxFileSize": 1048576
}
```

### Update Configuration

```bash
curl -X POST http://raspberry-pi:8080/config/ \
  -H "Content-Type: application/json" \
  -d '{"DeleteFiles": false, "MaxFileSize": 2097152}'
```

### View Recent Logs

```bash
curl http://raspberry-pi:8080/logs/tail?lines=50
```

### View Full Log

```bash
curl http://raspberry-pi:8080/logs/
```

## Web Browser Access

The API can also be accessed via web browser:

1. **Health Check**: `http://<pi-ip>:8080/health`
2. **Configuration**: `http://<pi-ip>:8080/config/`
3. **Logs**: `http://<pi-ip>:8080/logs/tail?lines=100`

JSON responses are displayed in the browser (or use a JSON formatter extension).

## Security Considerations

⚠️ **Important**: This web server is designed for local network use.

### Current Security Posture

- **No authentication**: Anyone with network access can view/modify configuration
- **No HTTPS**: Traffic is unencrypted
- **No rate limiting**: Vulnerable to abuse
- **No input validation**: Basic validation only

### Recommended Deployment

- Use on trusted local network only
- Consider firewall rules to restrict access
- Don't expose directly to internet
- Use SSH tunnel for remote access:
  ```bash
  ssh -L 8080:localhost:8080 pi@raspberry-pi
  # Note: Replace 8080 with your configured LogPort value
  ```

## Error Handling

### Flask Error Responses

- **404 Not Found**: Unknown endpoints
- **405 Method Not Allowed**: Wrong HTTP method
- **400 Bad Request**: Invalid JSON in POST requests
- **500 Internal Server Error**: Unexpected errors (logged)

### Graceful Degradation

- Missing log file: Returns empty log
- Configuration errors: Logged and returned in response
- JSON parsing errors: Returns 400 with error message

## Testing

Tests are located in `tests/web/test_config_api.py`:
- Health endpoint
- Configuration GET/POST
- Invalid requests
- Blueprint registration

## Thread Safety

- **Flask**: Generally thread-safe for read operations
- **ConfigManager**: Uses locks internally
- **Logger**: Thread-safe by design
- **Concurrent requests**: Handled by Flask's threading

## Performance

- **Lightweight**: Flask development server suitable for low traffic
- **Blocking I/O**: File operations are synchronous
- **Scalability**: Designed for single-user/admin access
- **Not recommended for**: High-traffic or public-facing use

## Development Mode

For development with auto-reload (not used in production):

```python
app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=True)
```

Note: Reloader is incompatible with the threaded startup in `main.py`.

## Integration

The web module integrates with:
- **Config module**: Configuration API via blueprint
- **Logging module**: Log viewing API via blueprint
- **Main module**: Startup and threading

## Future Enhancements

Potential improvements:
- Authentication/authorization
- HTTPS support
- WebSocket for live log streaming
- Rich web UI (HTML/JavaScript)
- API documentation (Swagger/OpenAPI)
- Request logging
- Rate limiting
- CORS support

## Logging

Web server operations are logged:
- Startup: `"Starting web server on port {port}"`
- App creation: `"Web server created"`
- Requests: Flask default logging
- Errors: Logged with stack traces

## Port Configuration

The web server port is configurable via the `LogPort` setting:

1. **Via config.json**:
   ```json
   {
     "LogPort": 8080
   }
   ```

2. **Via API**:
   ```bash
   curl -X POST http://localhost:8080/config/ \
     -H "Content-Type: application/json" \
     -d '{"LogPort": 9000}'
   ```

**Important**: Changing the port requires restarting the application for the change to take effect.

## Troubleshooting

### Web server not starting
- Check port not already in use: `sudo lsof -i :8080`
- Verify LogPort in configuration
- Check logs for error messages
- Ensure Flask is installed

### Cannot access from network
- Verify firewall allows port 8080
- Check server is bound to `0.0.0.0` (not `127.0.0.1`)
- Test with `curl http://<pi-ip>:8080/health`
- Ensure Raspberry Pi network is accessible

### Configuration changes not persisting
- Check file permissions on `config.json`
- Verify POST request format (Content-Type: application/json)
- Check application logs for errors
- Ensure disk is not full/read-only
