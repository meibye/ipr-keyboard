---
name: test-on-rpi
description: Run automated and hardware tests on the dev RPi (ipr-dev-pi4) via MCP SSH.
---

# When to use
- After `deploy-dev` to validate code on actual hardware
- To run GPIO/LED/reed-switch hardware tests
- To run the integration and headless test suite in the RPi environment

# Inputs
- Optional: test tier to run — `unit`, `integration`, `gpio`, `all` (default: `all`)
- Optional: `--auto` flag for unattended gpio tests (skips visual/manual steps)

# Procedure

## Tier 1 — Unit + integration (no hardware needed)

```bash
cd /home/meibye/dev/ipr-keyboard
python -m pytest tests/ -v --tb=short -q
```

Report pass/fail/skip counts. Flag any failures immediately.

## Tier 2 — Headless smoke test

```bash
cd /home/meibye/dev/ipr-keyboard
bash scripts/test_smoke.sh
```

## Tier 3 — GPIO hardware test (LED + reed switch)

```bash
cd /home/meibye/dev/ipr-keyboard
sudo bash scripts/headless/test_gpio_led_reed.sh --auto
```

Interpret results:
- `Passed: N | Failed: 0 | Skipped: M` where M are visual/manual steps → OK
- Any `FAIL` → report pin, symptom, and likely cause
- Known skips at `--auto`: visual LED confirmations (B.2, B.3) and manual magnet steps

## Tier 4 — Service health check

```bash
sudo systemctl status ipr_keyboard.service --no-pager -l
sudo systemctl status bt_hid_ble.service --no-pager -l
sudo systemctl status bt_hid_agent_unified.service --no-pager -l
curl -sk https://localhost/health
```

All three services must be `active (running)` and health must return `ok`.

# Quality bar
- Zero pytest failures
- GPIO test: 6+ PASS, 0 FAIL (skips are acceptable for visual steps)
- All three systemd services healthy
- Health endpoint responds

# Output format
- Per-tier result summary
- Any failures with diagnostic output
- Next recommended actions

# Related skills
- deploy-dev
- run-tests
- root-cause-analysis
