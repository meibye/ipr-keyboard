# Development Workflow

Current developer workflow for this repository.

## Local Loop

```bash
./scripts/sys_setup_venv.sh
./scripts/dev_run_app.sh
pytest
```

## Common Commands

- Run app in foreground: `./scripts/dev_run_app.sh`
- Run web module directly: `./scripts/dev_run_webserver.sh`
- Smoke tests: `./scripts/test_smoke.sh`
- E2E foreground flow: `./scripts/test_e2e_demo.sh`
- E2E systemd flow: `sudo ./scripts/test_e2e_systemd.sh`

## Bluetooth Diagnostics Loop

1. `./scripts/diag_status.sh`
2. `./scripts/diag_troubleshoot.sh`
3. `sudo ./scripts/ble/diag_pairing.sh`
4. `sudo ./scripts/ble/diag_bt_visibility.sh` (or `--fix`)

## Remote Diagnostics Loop (MCP)

Use scripts installed by `scripts/rpi-debug/install_dbg_tools.sh`:
- `dbg_stack_status.sh`
- `dbg_diag_bundle.sh`
- `dbg_pairing_capture.sh <seconds>`
- `dbg_bt_restart.sh`
- `dbg_bt_soft_reset.sh`
- `dbg_bt_bond_wipe.sh <MAC>` (destructive)

## Change Management Guidance

- Treat `ARCHITECTURE.md` as canonical.
- If a module follows a `Legacy` or `Deprecated` pattern there, classify it as architectural dead code candidate before extending it.
