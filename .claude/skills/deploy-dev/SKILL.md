---
name: deploy-dev
description: Sync local changes to the dev RPi (ipr-dev-pi4) via MCP SSH and restart services.
---

# When to use
- After local changes pass unit tests and you want to validate on hardware
- To pick up a new dependency or config change on the dev board
- Before running `test-on-rpi`

# Inputs
- None required; reads workspace state via git

# Procedure

1. Verify tests pass locally before deploying:
   Run `pytest tests/ -q` and abort if any fail.

2. Determine changed files since last commit:
   Use `git status` and `git diff --name-only HEAD` to find changed files.

3. Upload changed source files to the dev RPi via `ipr-rpi-dev-ssh`:
   - Target path: `/home/meibye/dev/ipr-keyboard/`
   - Upload each changed file preserving relative path under `src/`, `tests/`, `scripts/`

4. Fix executable permissions on all scripts (Windows upload strips Unix execute bits):
   ```bash
   find /home/meibye/dev/ipr-keyboard/scripts \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} +
   ```
   This must run after every upload — see the `fix-script-permissions` skill for details.

5. Reinstall the package in development mode on the RPi:
   ```bash
   cd /home/meibye/dev/ipr-keyboard && pip install -e . --quiet
   ```

6. Restart the main service:
   ```bash
   sudo systemctl restart ipr_keyboard.service
   sleep 3
   sudo systemctl status ipr_keyboard.service --no-pager -l
   ```

7. Check the health endpoint:
   ```bash
   curl -sk https://localhost/health || curl -s http://localhost:8080/health
   ```

8. Report deployment result: service status, health response, any errors.

# Quality bar
- Service must reach `active (running)` state after restart
- Health endpoint must return `{ "status": "ok" }`
- Any startup errors from journalctl must be surfaced

# Output format
- Files uploaded (count + list)
- Service status after restart
- Health endpoint response
- Any errors or warnings

# Related skills
- run-tests
- test-on-rpi
- root-cause-analysis
