# Provisioning

Provisioning scripts for Raspberry Pi setup and verification.

## Files in This Directory

| File | Purpose |
|---|---|
| `00_bootstrap.sh` | Validates `/opt/ipr_common.env`, installs base tools, clones/checks out repo |
| `01_os_base.sh` | Installs OS/system dependencies and Bluetooth baseline |
| `02_device_identity.sh` | Applies hostname and Bluetooth name identity |
| `03_app_install.sh` | Creates/validates Python app environment |
| `04_enable_services.sh` | Installs/enables app, BLE, and headless provisioning services |
| `05_copilot_debug_tools.sh` | Optional MCP/Copilot diagnostics tooling setup |
| `06_verify.sh` | Produces verification report and service checks |
| `provision_wizard.sh` | Orchestration for steps `00`..`07`, interactive or fully unattended, with reboot resume and a final audit |
| `common.env.example` | Template for `/opt/ipr_common.env` |

## Typical Sequence

```bash
sudo ./provision/00_bootstrap.sh
sudo ./provision/01_os_base.sh
sudo reboot
sudo ./provision/02_device_identity.sh
sudo reboot
sudo ./provision/03_app_install.sh
sudo ./provision/04_enable_services.sh
sudo ./provision/05_copilot_debug_tools.sh   # optional
sudo ./provision/06_verify.sh
```

## Unattended provisioning

```bash
sudo ./provision/provision_wizard.sh --unattended
```

Nothing is read from the keyboard: every question is answered from
`/opt/ipr_common.env` (the same file the steps already read) or its documented
default, and the reboots after steps 7 and 8 are chained automatically — the
wizard arms a one-shot `ipr-provision-resume.service`, reboots, and the unit
re-runs the wizard with `--unattended --resume` once the system is back, then
disarms itself.  A run that fails does not re-arm, so it cannot loop.

Follow it with `journalctl -u ipr-provision-resume.service -f`, or read
`/opt/ipr_state/provision_wizard.log` afterwards — every run appends to it.

### Choosing the answers in advance

| Key in `/opt/ipr_common.env` | Effect | Default |
|---|---|---|
| `INSTALL_COPILOT_TOOLS` | `no` skips step 05 (the `copilotdiag` account and the `dbg_*` helpers) | `yes` |
| `RECLONE_REPO` | `yes` deletes an existing checkout and clones again | `no` |
| `SKIP_GITHUB_SSH` | `yes` skips the GitHub SSH key setup and test | `no`, forced `yes` when unattended or on a payload device |
| `AUTO_REBOOT` | `no` stops at each reboot point and prints the resume command instead | `yes` when unattended |
| `EDIT_COMMON_ENV` | `yes` opens `$EDITOR` on an existing `provision/common.env` | `yes` interactively, never unattended |
| `FINAL_VERIFY` | `no` skips the closing audit | `yes` |
| `INSTALL_TMUX` | `yes` installs tmux and its plugin manager for the app user | `no` |

Other options:

| Flag | Effect |
|---|---|
| `--resume` | continue from the recorded step without the start-over menu |
| `--from-step N` | start at step N (`--list-steps` prints them) |
| `--no-reboot` | never reboot; stop and say what to run afterwards |
| `--list-steps`, `--help` | print and exit (no root needed) |

The per-device `common.env.*` files are not tracked (see `.gitignore`); only
`common.env.example` is.  The production devices are provisioned with
`INSTALL_COPILOT_TOOLS="no"` — a second SSH account is unwanted on a hardened
device.  Note that the `ipr-rpi-prod-*` entries in `.vscode/mcp.json` connect
as `copilotdiag` and stop working with that setting; reach those devices over
the application account instead.

An unattended run refuses to start unless a device configuration exists and
has been edited — `/opt/ipr_common.env` or `provision/common.env`, not the
untouched `common.env.example`.  Otherwise every device would come up with the
same hostname and Bluetooth name.  The editor is never opened unattended.

## Final verification

The last two steps are deliberately different things:

| Step | Script | Answers |
|---|---|---|
| 12 | `06_verify.sh` | *what does this device look like* — OS, services, Bluetooth, for comparing two devices |
| 13 | `scripts/headless/test_provision.sh --auto` | *did provisioning actually work* — every artefact each step was supposed to create |
| 14 | `07_show_info.sh` | credentials, URLs and SSH details to hand over |

Step 13 is the gate.  It exits with the number of failed checks, the wizard
repeats that in its closing banner, and the whole wizard exits non-zero when
anything failed — so an unattended run can be judged by its exit status alone.
The audit writes that output itself, colour stripped, to
`/opt/ipr_state/provision_verify.log` — so a run started by hand leaves the
same record as one started by the wizard, and the last result a device
reported can always be read back.  `--report FILE` writes elsewhere and
`--no-report` writes nothing; an unwritable path costs the report, not the
run.  Re-run just the audit with:

```bash
sudo ./provision/provision_wizard.sh --from-step 13
```

Checks that need a person (hotspot visible on a phone, BT pairing, the magnet
gestures, the panel) are reported as *skipped*, not failed, under `--auto`.
Run `sudo bash scripts/headless/test_provision.sh` without `--auto` to be
walked through those.

## Generated Artifacts

- `/opt/ipr_common.env` (input config)
- `/opt/ipr_state/*` (state and verification outputs)
- Installed services and binaries under `/etc/systemd/system` and `/usr/local/bin`
- `/opt/ipr_state/provision_wizard.log` (every run, appended)
- `/opt/ipr_state/provision_verify.log` (output of the closing audit)
- `/etc/systemd/system/ipr-provision-resume.service` while a reboot is pending;
  removed when provisioning completes

See `ARCHITECTURE.md` for canonical current/legacy classification.
