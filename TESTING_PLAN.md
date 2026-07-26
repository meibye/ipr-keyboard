# Testing Plan

Tiered strategy aligned to the project's split runtime: pure-Python logic testable on any host,
hardware-dependent GPIO and Bluetooth testable only on a Raspberry Pi.

---

## Test tiers at a glance

| Tier | Where | Trigger | Tooling |
|------|-------|---------|---------|
| 1 — Unit | Local Win11 / Dev container / CI | Every commit | pytest |
| 2 — Integration | Local Win11 / Dev container / CI | Every commit | pytest |
| 3 — Headless RPi | Dev RPi via MCP SSH | Before merge | bash + pytest |
| 4 — Hardware | Dev RPi (hands-on) | Before release | Manual checklist |
| 5 — Post-provision | New RPi Zero W via MCP SSH | After provisioning a new device | `test_provision.sh` |
| 6 — Acceptance | Prod RPi | Release gate | Manual checklist |

---

## Tier 1 — Unit tests

Run on any Python 3.12 host.  No hardware, no network, no RPi.GPIO.

```bash
pytest tests/ -v --tb=short --cov=src/ipr_keyboard --cov-report=term-missing -rs
```

### Test file inventory

| File | What it tests |
|------|--------------|
| `tests/test_transmission.py` | State machine, history, thread safety |
| `tests/bluetooth/test_keyboard.py` | BluetoothKeyboard, `send_text()`, subprocess mocking |
| `tests/bluetooth/test_ble_daemon_keymap.py` | Unicode, Danish dead-keys, keymap encoding |
| `tests/config/test_manager.py` | ConfigManager singleton, JSON persistence, migration |
| `tests/logging/test_logger.py` | Logger singleton, levels, formatting |
| `tests/usb/test_detector.py` | File detection, mtime ordering, wait logic |
| `tests/usb/test_deleter.py` | Safe deletion, read-only files, error handling |
| `tests/usb/test_mtp_sync.py` | jmtpfs mount/umount, mount-point detection |
| `tests/usb/test_usb_reader.py` | UTF-8 decoding, encoding fallback, I/O errors |
| `tests/utils/test_helpers.py` | JSON load/save, path resolution, seeding |
| `tests/web/test_auth.py` | UserStore CRUD, verify, singleton, default bootstrap |
| `tests/web/test_api.py` | `/api/` endpoints, health, status, transmission |
| `tests/web/test_config_api.py` | `/api/config` GET/PUT, validation |
| `tests/web/test_logs_api.py` | Log file list, content, streaming |
| `tests/web/test_server.py` | Blueprint registration, auth middleware, secret key |
| `tests/web/test_setup.py` | Setup blueprint, login, Wi-Fi config, reboot/shutdown |

### Coverage targets

| Module | Target |
|--------|--------|
| `transmission.py` | 95 % |
| `bluetooth/keyboard.py` | 85 % |
| `config/manager.py` | 90 % |
| `usb/` | 85 % |
| `web/auth.py` | 90 % |
| `web/api.py` | 85 % |
| `web/setup.py` | 80 % |
| `gpio_monitor.py` | n/a — hardware only (see Tier 3) |

---

## Tier 2 — Integration tests

Run together with unit tests in CI.  No hardware; uses in-process Flask test client.

```bash
pytest tests/integration/ tests/e2e/ -v --tb=short
```

| File | What it tests |
|------|--------------|
| `tests/integration/test_main.py` | Thread lifecycle, config init, USB/BT loop |
| `tests/integration/test_usb_flow.py` | USB file read → Bluetooth send |
| `tests/integration/test_web_integration.py` | Dashboard endpoints with real config |
| `tests/e2e/test_web_e2e.py` | Authenticated HTTP session against live server |
| `tests/e2e/test_setup_e2e.py` | Setup portal against live server |

### E2E target selection

`tests/e2e/` talks real HTTP, unlike the rest of the suite, which uses the Flask
test client.  It picks its target automatically:

| Invocation | Target | Missing config |
|------------|--------|----------------|
| `pytest tests/e2e/` | Local server started in-process on `127.0.0.1:<ephemeral>` | n/a — nothing to configure |
| `IPR_BASE_URL=… pytest tests/e2e/` | That device | Skips |
| `IPR_BASE_URL=… pytest tests/e2e/ --e2e` | That device | **Fails** |

Local mode is the default, so these tests no longer skip in an ordinary run.  It
covers what the test client cannot: real socket binding, the WSGI path, redirect
chains, and session-cookie round-trips.  It does **not** cover hardware —
`systemctl`, `nmcli` and `journalctl` fall through to their error paths, so pages
render but report nothing meaningful.  Device behaviour is Tier 3 and up.

Use `--e2e` whenever you intend to test a real device.  Without it, a wrong
`IPR_PASSWORD` / `IPR_SETUP_PASSWORD` turns into a *skip*, which reads as a green
run — you would think the device was verified when it was not.

```bash
# Verify the dev Pi, failing loudly if it is unreachable or credentials are wrong
IPR_BASE_URL=https://ipr-dev-pi4:8443 \
IPR_SETUP_PASSWORD=<hotspot-secret> \
  pytest tests/e2e/ -v --e2e
```

Add `-rs` to any run to print skip reasons; the bare command hides them.

---

## Tier 3 — Headless RPi tests

Run on `ipr-dev-pi4` via MCP SSH (`ipr-rpi-dev-ssh`) after deploying.

### 3a — Python tests on the Pi

```bash
cd /home/meibye/dev/ipr-keyboard
python -m pytest tests/ -v --tb=short -q
```

These run identically to Tier 1/2 but confirm the RPi environment (Python version, installed deps)
is correct.

### 3b — Smoke test

```bash
bash scripts/test_smoke.sh
```

Verifies that the app starts, the web server responds, and `/health` returns `ok`.

### 3c — GPIO hardware test (LED + reed switch)

```bash
sudo bash scripts/headless/test_gpio_led_reed.sh --auto
```

Expected output:

```
Passed: 6  |  Failed: 0  |  Skipped: 12
✓ All automated checks passed.
  (12 step(s) skipped — hardware or visual steps not confirmed)
```

Skips are intentional at `--auto`; they require human presence (see Tier 4).

### 3d — Bluetooth diagnostics

```bash
sudo bash scripts/ble/diag_pairing.sh
sudo bash scripts/ble/diag_bt_visibility.sh
```

### 3e — Service health

```bash
sudo systemctl status ipr_keyboard.service bt_hid_ble.service bt_hid_agent_unified.service --no-pager -l
curl -sk https://localhost/health
```

---

## Tier 4 — Manual hardware tests (dev RPi, hands-on)

Run these interactively on the device before a release.  Check off each row.

### 4a — GPIO / LED visual

Run without `--auto` to get visual confirmation prompts:

```bash
sudo bash scripts/headless/test_gpio_led_reed.sh
```

| Step | Expected | Pass? |
|------|----------|-------|
| B.2 — reed closed (magnet held) | GPIO 27 reads LOW | ☐ |
| B.3 — reed open again (magnet removed) | GPIO 27 reads HIGH | ☐ |
| A.1 — Red anode only | LED glows red | ☐ |
| A.2 — Green anode only | LED glows green | ☐ |
| A.3 — Blue anode only | LED glows blue (may be dim with 330 Ω) | ☐ |
| A.4 — Red + Green | LED glows amber/yellow | ☐ |
| C.1 — GpioMonitor boot blink | White fast blink for 3 s | ☐ |
| C.2 — Tap reed (< 3 s) | LED shows status colour for 30 s then off | ☐ |
| C.3 — Hold reed ≥ 3 s | LED blinks blue fast; hotspot toggles on release | ☐ |

### 4b — Bluetooth pairing

| Step | Expected | Pass? |
|------|----------|-------|
| Start pairing mode from web UI | Pairing LED blinks; BT discoverable | ☐ |
| Pair host device | Host appears in paired devices list | ☐ |
| Send IrisPen text | Keystrokes appear on host | ☐ |
| Disconnect host BT | Device re-advertises within 10 s | ☐ |
| Reconnect host BT | Keystrokes resume without reboot | ☐ |

### 4c — USB / IrisPen flow

| Step | Expected | Pass? |
|------|----------|-------|
| Plug in IrisPen pen | New file detected in configured folder | ☐ |
| Ink text with pen | Text file appears in scan folder | ☐ |
| Automatic processing | Text transmitted to host, file deleted | ☐ |
| Large file (> 500 KB) | Accepted / rejected per MaxFileSize | ☐ |

### 4d — Web UI

| Step | Expected | Pass? |
|------|----------|-------|
| Open `https://<device>/` | Login page renders | ☐ |
| Log in as admin | Dashboard loads | ☐ |
| Status panel | WiFi and BT state shown correctly | ☐ |
| Config save | Change PollIntervalSeconds; verify persisted in config.json | ☐ |
| Log viewer | Recent log lines stream live | ☐ |
| Logout | Session cleared; redirects to login | ☐ |

### 4e — Hotspot / setup portal

| Step | Expected | Pass? |
|------|----------|-------|
| Hold reed ≥ 3 s | Hotspot activates; SSID `ipr-keyboard` visible | ☐ |
| Connect to hotspot | Browser opens `https://192.168.4.1/setup/` | ☐ |
| Login with hotspot password | Setup home page shown | ☐ |
| Select Wi-Fi network | Profile saved; device connects | ☐ |
| Hold reed ≥ 3 s again | Hotspot deactivates | ☐ |

### 4f — Factory reset (destructive — do last)

| Step | Expected | Pass? |
|------|----------|-------|
| Hold reed ≥ 10 s | LED blinks red fast | ☐ |
| Release at ≥ 10 s | Wi-Fi profiles deleted; device reboots | ☐ |
| After reboot | Device in fresh state; hotspot activates | ☐ |

---

## Tier 5 — Post-provision validation (new RPi Zero W)

Run immediately after completing the full provisioning sequence on a new device.
Uses the `/test-new-rpi` skill and `scripts/headless/test_provision.sh` via MCP SSH.

### Provisioning sequence (must complete before testing)

```bash
# 1. System packages (as root)
sudo ./scripts/sys_install_packages.sh

# 2. Python venv (as user)
./scripts/sys_setup_venv.sh

# 3. BLE services (as root)
sudo ./scripts/service/svc_install_bt_gatt_hid.sh

# 4. BT keyboard helper (as root)
sudo ./scripts/ble/ble_install_helper.sh

# 5. Hotspot + TLS certs (as root)
sudo ./scripts/headless/install_provision_service.sh

# 6. Full update — starts all services (as root)
sudo ./scripts/deploy/deploy_full_update.sh --install-python
```

### 5a — Automated validation via MCP SSH

Invoke the `test-new-rpi` skill, or run manually:

```bash
# Via ipr-rpi-dev-ssh MCP execute-command:
sudo bash /home/meibye/dev/ipr-keyboard/scripts/headless/test_provision.sh --auto
```

The script validates all provisioning artifacts in phases:

| Phase | What is checked | Provisioning step |
|-------|----------------|-------------------|
| **A — System packages** | git, python3-venv, bluez, nmcli, jmtpfs, uv, /mnt/irispen, Bluetooth experimental mode | `sys_install_packages.sh` |
| **B — Python venv** | .venv exists, ipr_keyboard importable, pytest passes | `sys_setup_venv.sh` |
| **C — BLE services** | bt_hid_agent_unified.py, bt_hid_ble_daemon.py installed + executable, service units, /opt/ipr_common.env | `svc_install_bt_gatt_hid.sh` |
| **D — BT helper** | bt_kb_send, bt_kb_send_file installed + executable | `ble_install_helper.sh` |
| **E — Provision service** | ipr-provision.sh, ipr-cert-gen.sh, ipr-cert-renew.sh installed, service units registered, renewal timer enabled | `install_provision_service.sh` |
| **F — TLS certificates** | /etc/ipr-ssl/{ca,server}.{crt,key} present, server.key at 0640, server.crt not expired, covers 10.42.0.1 and .local hostname | `gen_ipr_ssl_cert.sh` |
| **G — Service health** | NetworkManager, bluetooth, bt_hid_agent_unified, bt_hid_ble, ipr_keyboard all active | `deploy_full_update.sh` |
| **H — Application health** | /health returns ok, config.json and users.json seeded, admin_initial_password.txt written | First start of ipr_keyboard |
| **I — Script permissions** | All .sh and .py under scripts/ have executable flag | `fix-script-permissions` skill |

**Pass criteria:** 0 failures in phases A–I.

### 5b — Manual validation (J phase)

After the automated run, perform the J-phase checks interactively (run without `--auto`):

| Check | What to verify |
|-------|---------------|
| J.1 | Hotspot SSID `ipr-setup-XXXX` visible in Wi-Fi scan on a phone/laptop |
| J.2 | Browser reaches `https://10.42.0.1/setup/` (may warn about cert) |
| J.3 | Login with hotspot credentials from `/etc/ipr-hotspot.secret` succeeds |
| J.4 | CA cert downloaded from `https://10.42.0.1/setup/ca.crt` and trusted; HTTPS no longer warns |
| J.5 | Main dashboard at `https://<hostname>.local/` accessible and shows correct status |
| J.6 | BT pairing with a host device completes (device appears in host BT list) |

### 5c — GPIO hardware (if reed switch + LED wired)

```bash
sudo bash /home/meibye/dev/ipr-keyboard/scripts/headless/test_gpio_led_reed.sh --auto
```

See Tier 4a for the manual LED visual confirmation steps.

---

## Tier 6 — Production acceptance

After deploying to `ipr-prod-zero2`, run via `ipr-rpi-prod-ssh` (whitelist-only):

```bash
dbg_stack_status.sh
dbg_diag_bundle.sh | head -100
```

Then repeat Tiers 4a (LED visual), 4b (BT pairing), 4c (USB) with the production device.

For a freshly imaged production device, run Tier 5 (post-provision) first.

---

## Running tests on Windows 11 (local, no container)

Requirements: Python 3.12, `pip install -e ".[dev]" ruff`

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src/ipr_keyboard --cov-report=term-missing

# Single file
pytest tests/web/test_auth.py -v

# Lint
ruff check src/ tests/
ruff format src/ tests/ --check
```

VS Code keyboard shortcuts (after tasks.json / launch.json are loaded):

| Action | Method |
|--------|--------|
| Run all tests | `Ctrl+Shift+P` → `Tasks: Run Test Task` → **test: run all** |
| Run current test file | `Ctrl+Shift+P` → **test: current file** |
| Debug tests | `F5` → **pytest: all tests** |
| Lint | `Ctrl+Shift+B` → **lint: ruff check** |

---

## Running tests in the dev container (Windows 11 + Docker Desktop)

Prerequisites:
- Docker Desktop for Windows with WSL2 backend enabled
- VS Code extension: **Dev Containers** (`ms-vscode-remote.remote-containers`)

Steps:
1. Open the repository folder in VS Code
2. `Ctrl+Shift+P` → **Dev Containers: Reopen in Container**
3. First open installs Python 3.12 and all dev dependencies automatically
4. All VS Code tasks and launch configs work identically inside the container
5. GPIO is disabled via `IPR_GPIO_ENABLED=false` env var (set in `devcontainer.json`)

The container runs on Linux (via WSL2), giving a much closer match to the RPi environment
than running pytest natively on Windows.  systemd calls and RPi.GPIO are both mocked in tests,
so all 210+ tests pass in the container without hardware.

---

## CI/CD

`.github/workflows/quality-gates.yml` runs on every PR and push to `main`:

1. `ruff check` — lint (non-blocking; `|| true`)
2. `ruff format --check` — format check (non-blocking)
3. `pytest -q` — all tests (non-blocking)

**Tighten CI gates** when the test suite is stable by removing `|| true` from each step.

---

## Known gaps

| Area | Gap | Recommended action |
|------|-----|-------------------|
| `gpio_monitor.py` | 0 % coverage; no unit tests | Mock RPi.GPIO at module level; test state transitions |
| `main.py` | Partial; signal handling not tested | Add shutdown/restart signal tests |
| `web/pairing_routes.py` | Unknown coverage | Add pairing wizard endpoint tests |
| BT hardware reconnect | Not automated | Tier 4b manual only |
| MTP real device | jmtpfs calls mocked | Test with physical IrisPen pen |
| CI gates | `|| true` means failures pass CI | Remove after suite stabilises |
