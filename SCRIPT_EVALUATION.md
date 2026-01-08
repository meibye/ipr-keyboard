# Script Evaluation Report

**Date:** 2025-11-24  
**Purpose:** Evaluate all scripts in the `scripts/` folder to determine if they should be deleted based on whether the implementation still needs them.

**Evaluation Criteria:** A script should be marked for deletion if the current implementation in `src/ipr_keyboard/` no longer requires it for setup, testing, deployment, or maintenance.

---

## Summary of Findings

| Script | Status | Recommendation |
|--------|--------|----------------|
| env_set_variables.sh | ✅ KEEP | Required by all other scripts |
| sys_install_packages.sh | ✅ KEEP | Essential for system installation |
| bt_configure_system.sh | ✅ KEEP | Required for Bluetooth HID setup |
| ble_install_helper.sh | ✅ KEEP | Installs critical Bluetooth helper |
| sys_setup_venv.sh | ✅ KEEP | Required for Python environment |
| svc_install_systemd.sh | ✅ KEEP | Required for systemd service |
| usb_setup_mount.sh | ✅ KEEP | Optional but useful for USB mount |
| test_smoke.sh | ✅ KEEP | Useful for testing installation |
| test_e2e_demo.sh | ✅ KEEP | Useful for testing workflow |
| test_e2e_systemd.sh | ⚠️ REVIEW | Has incomplete code, missing definitions |
| diag_troubleshoot.sh | ✅ KEEP | Essential troubleshooting tool |
| usb_mount_mtp.sh | ✅ KEEP | Required for MTP device mounting |
| usb_sync_cache.sh | ✅ KEEP | Uses mtp_sync.py module |
| ble_install_daemon.sh | ⚠️ REVIEW | Contains malformed code, duplicates 03 |
| test_bluetooth.sh | ✅ KEEP | Manual testing tool |
| ble_switch_backend.sh | ⚠️ LEGACY | Uses hardcoded path, marked as legacy |
| dev_run_app.sh | ✅ KEEP | Essential development tool |

**TOTAL:** 17 scripts evaluated  
**KEEP:** 14 scripts  
**REVIEW/ISSUES:** 3 scripts (09, 13, 15)

---

## Detailed Evaluation

### env_set_variables.sh
**Status:** ✅ **KEEP**

**Purpose:** Environment configuration for all other scripts

**Analysis:**
- Sourced by all other scripts (except itself)
- Sets `IPR_USER` and `IPR_PROJECT_ROOT` environment variables
- Critical dependency for dynamic project directory resolution
- No code replacement exists for this functionality

**Dependencies in Implementation:**
- Required by: All numbered scripts + dev_run_app.sh
- Referenced in: scripts/README.md

**Recommendation:** **KEEP** - Foundational script required by entire setup system

---

### sys_install_packages.sh
**Status:** ✅ **KEEP**

**Purpose:** System package installation and base setup

**Analysis:**
- Installs apt packages (git, bluez, mtp-tools, etc.)
- Installs uv package manager
- Creates project directories
- Sets up Python venv
- No equivalent implementation exists in src/

**Dependencies in Implementation:**
- None - this is a setup prerequisite

**Recommendation:** **KEEP** - Essential for first-time system setup

---

### bt_configure_system.sh
**Status:** ✅ **KEEP**

**Purpose:** Configures /etc/bluetooth/main.conf for HID keyboard profile

**Analysis:**
- Modifies system Bluetooth configuration
- Sets Class=0x002540 for keyboard profile
- Must be run as root
- No equivalent implementation in src/ (system-level config)

**Dependencies in Implementation:**
- Required for BluetoothKeyboard class to function
- Referenced in: src/ipr_keyboard/bluetooth/keyboard.py

**Recommendation:** **KEEP** - Required for Bluetooth keyboard functionality

---

### ble_install_helper.sh
**Status:** ✅ **KEEP**

**Purpose:** Installs Bluetooth HID helper script and backend daemons

**Analysis:**
- Creates `/usr/local/bin/bt_kb_send` (directly called by BluetoothKeyboard)
- Creates backend daemons: bt_hid_uinput_daemon.py and bt_hid_ble_daemon.py
- Creates systemd services for both backends
- This is the ONLY script that creates/updates bt_kb_send

**Dependencies in Implementation:**
- **CRITICAL:** BluetoothKeyboard class at src/ipr_keyboard/bluetooth/keyboard.py directly calls `/usr/local/bin/bt_kb_send`
- Line 29: `self.helper_path = helper_path` (default: "/usr/local/bin/bt_kb_send")
- Line 53-56: subprocess.run([self.helper_path, text])

**Recommendation:** **KEEP** - Absolutely essential, creates helper used by core implementation

---

### sys_setup_venv.sh
**Status:** ✅ **KEEP**

**Purpose:** Creates Python virtual environment using uv

**Analysis:**
- Creates .venv directory
- Installs project dependencies
- Sets up bash aliases
- No equivalent implementation in src/

**Dependencies in Implementation:**
- Required by: All testing and running scripts
- venv path used by: svc_install_systemd.sh, dev_run_app.sh, and all test scripts

**Recommendation:** **KEEP** - Required for Python development environment

---

### svc_install_systemd.sh
**Status:** ✅ **KEEP**

**Purpose:** Installs systemd service for ipr_keyboard

**Analysis:**
- Creates /etc/systemd/system/ipr_keyboard.service
- Service runs: `$VENV_DIR/bin/python -m ipr_keyboard.main`
- Enables auto-start on boot
- No equivalent in src/ (system-level service)

**Dependencies in Implementation:**
- Service runs: src/ipr_keyboard/main.py
- Referenced by: test_e2e_systemd.sh, diag_troubleshoot.sh

**Recommendation:** **KEEP** - Required for production deployment

---

### usb_setup_mount.sh
**Status:** ✅ **KEEP**

**Purpose:** Sets up persistent USB mount for IrisPen

**Analysis:**
- Creates mount point
- Adds entry to /etc/fstab using UUID
- Optional (config can point to any folder)
- No equivalent in src/

**Dependencies in Implementation:**
- Implementation reads from cfg.IrisPenFolder (can be any path)
- Optional but useful for USB mode

**Recommendation:** **KEEP** - Optional but useful utility for USB mounting

---

### test_smoke.sh
**Status:** ✅ **KEEP**

**Purpose:** Runs basic functionality tests

**Analysis:**
- Tests imports from src/ipr_keyboard modules
- Tests ConfigManager, logger, web server, USB operations, Bluetooth
- Validates installation without full integration
- Not replaced by pytest (different purpose - installation validation)

**Dependencies in Implementation:**
- Imports and tests all major modules from src/ipr_keyboard/

**Recommendation:** **KEEP** - Useful quick validation tool for post-installation testing

---

### test_e2e_demo.sh
**Status:** ✅ **KEEP**

**Purpose:** End-to-end workflow demo (foreground mode)

**Analysis:**
- Starts app in background
- Creates test file
- Verifies processing
- Shows logs
- Manual testing utility
- Not replaced by automated tests

**Dependencies in Implementation:**
- Runs: python -m ipr_keyboard.main
- Tests the complete workflow

**Recommendation:** **KEEP** - Useful for manual workflow testing

---

### test_e2e_systemd.sh
**Status:** ⚠️ **REVIEW** (Has Issues)

**Purpose:** End-to-end test with systemd service

**Analysis:**
- **ISSUE:** Script has incomplete/broken code
- Line 9-31: Missing service name definition before use
- Line 34: `$SERVICE_NAME` used but not defined until later
- Line 66: Uses `$VENV_DIR` but not defined
- Script would fail if executed
- Similar functionality to test_e2e_demo.sh but for systemd

**Dependencies in Implementation:**
- Intends to test systemd service
- Uses: src/ipr_keyboard modules via systemd

**Recommendation:** ⚠️ **REVIEW** - Script needs fixes before it can be used. Could be deleted or fixed depending on needs.

---

### diag_troubleshoot.sh
**Status:** ✅ **KEEP**

**Purpose:** Comprehensive diagnostic tool for troubleshooting

**Analysis:**
- Checks project directory, venv, Python imports
- Validates configuration
- Checks mount points
- Checks systemd service status
- Views logs and journal
- Tests Bluetooth helper availability
- Optional test file mode
- Essential troubleshooting tool

**Dependencies in Implementation:**
- Tests all components in src/ipr_keyboard/
- No replacement exists

**Recommendation:** **KEEP** - Essential for debugging and support

---

### usb_mount_mtp.sh
**Status:** ✅ **KEEP**

**Purpose:** Mounts/unmounts IrisPen as MTP device

**Analysis:**
- Uses jmtpfs to mount MTP devices
- Alternative to USB mass storage mode
- Required for devices that don't present as USB mass storage
- No equivalent in src/ (system-level operation)

**Dependencies in Implementation:**
- Used by: usb_sync_cache.sh
- IrisPenFolder can point to /mnt/irispen

**Recommendation:** **KEEP** - Required for MTP mode operation

---

### usb_sync_cache.sh
**Status:** ✅ **KEEP**

**Purpose:** Syncs files from MTP mount to local cache

**Analysis:**
- Wrapper around `python -m ipr_keyboard.usb.mtp_sync`
- Uses implementation module: src/ipr_keyboard/usb/mtp_sync.py
- Validates MTP mount exists
- Passes arguments to mtp_sync module

**Dependencies in Implementation:**
- **DIRECTLY USES:** src/ipr_keyboard/usb/mtp_sync.py module
- Line 35-38: Runs the mtp_sync module
- Required by: MTP workflow

**Recommendation:** **KEEP** - Actively uses implementation module, part of MTP workflow

---

### ble_install_daemon.sh
**Status:** ⚠️ **REVIEW** (Has Issues)

**Purpose:** Installs optional Bluetooth HID daemon

**Analysis:**
- **MAJOR ISSUES:**
  - Lines 47-202: Contains malformed code - bash script embeds Python code without proper syntax
  - Line 47: `sudo tee /usr/local/bin/bt_hid_daemon.py > /dev/null << 'EOF'` but next line 49 starts bash shebang
  - Lines 49-72: Bash script code inside what should be Python file
  - Line 74: Python imports start without closing bash context
  - Script would fail if executed
- README.md line 63 says: "References `/usr/local/bin/bt_kb_send` but does NOT overwrite it"
- README.md line 66: Says script 15 is legacy, prefer 16, but 16 doesn't exist
- **FUNCTIONAL OVERLAP:** ble_install_helper.sh already creates bt_hid daemon functionality
- Marked as "optional/advanced" in README

**Dependencies in Implementation:**
- None - implementation uses bt_kb_send from script 03
- This is meant as alternative/addon

**Recommendation:** ⚠️ **REVIEW** - Script is broken and functionality overlaps with 03. Should be either fixed or deleted.

---

### test_bluetooth.sh
**Status:** ✅ **KEEP**

**Purpose:** Manual Bluetooth keyboard testing tool

**Analysis:**
- Sends test string via bt_kb_send
- Tests Danish characters (æøå ÆØÅ)
- Validates Bluetooth pipeline is working
- README.md states: "For manual, interactive testing only. Not used in automated workflows or CI."
- Simple utility for manual verification

**Dependencies in Implementation:**
- Tests: /usr/local/bin/bt_kb_send (created by 03)
- Validates BluetoothKeyboard functionality

**Recommendation:** **KEEP** - Useful manual testing utility, minimal maintenance burden

---

### ble_switch_backend.sh
**Status:** ⚠️ **LEGACY**

**Purpose:** Switch between uinput and BLE keyboard backends

**Analysis:**
- **ISSUE:** Line 14: Uses hardcoded path `/home/meibye/dev/ipr-keyboard`
- **LEGACY STATUS:** README.md line 65-66 explicitly states:
  - "Legacy script to switch the active keyboard backend"
  - "Uses a hardcoded project directory path"
  - "Prefer 16_switch_keyboard_backend.sh for environment-variable-based resolution"
- **PROBLEM:** Script 16 doesn't exist!
- Manages systemd services: bt_hid_uinput.service and bt_hid_ble.service
- Reads KeyboardBackend from config.json
- Functional but uses hardcoded path instead of env vars

**Dependencies in Implementation:**
- Manages backends used by BluetoothKeyboard
- Config field: AppConfig.KeyboardBackend (src/ipr_keyboard/config/manager.py line 36)

**Recommendation:** ⚠️ **REVIEW** - Marked as legacy, but replacement (script 16) doesn't exist. Options:
1. Delete and document manual backend switching
2. Create script 16 with proper env var usage
3. Fix to use environment variables from env_set_variables.sh

---

### dev_run_app.sh
**Status:** ✅ **KEEP**

**Purpose:** Run application in foreground for development

**Analysis:**
- Activates venv
- Runs: `python -m ipr_keyboard.main`
- Essential development tool
- Alternative to systemd service for debugging
- Sources env_set_variables.sh
- Uses environment variables properly

**Dependencies in Implementation:**
- Runs: src/ipr_keyboard/main.py
- Development workflow essential

**Recommendation:** **KEEP** - Essential for development workflow

---

## Scripts Referenced in README but Missing

### 16_switch_keyboard_backend.sh
**Status:** ❌ **MISSING**

**Analysis:**
- Referenced in scripts/README.md lines 66-67
- Described as recommended replacement for script 15
- Should use environment variables instead of hardcoded paths
- **Does not exist in repository**

**Recommendation:** Script should either be created or references removed from README

---

## Conclusion

### Scripts to KEEP (14 scripts)
All of these are actively used by the implementation or are essential utilities:
1. ✅ env_set_variables.sh - Required by all
2. ✅ sys_install_packages.sh - System installation
3. ✅ bt_configure_system.sh - BT configuration
4. ✅ ble_install_helper.sh - **CRITICAL** - Creates bt_kb_send used by code
5. ✅ sys_setup_venv.sh - Python environment
6. ✅ svc_install_systemd.sh - Systemd service
7. ✅ usb_setup_mount.sh - USB mounting utility
8. ✅ test_smoke.sh - Installation validation
9. ✅ test_e2e_demo.sh - Testing utility
10. ✅ diag_troubleshoot.sh - Troubleshooting tool
11. ✅ usb_mount_mtp.sh - MTP mounting
12. ✅ usb_sync_cache.sh - Uses mtp_sync.py module
13. ✅ test_bluetooth.sh - Manual testing
14. ✅ dev_run_app.sh - Development tool

### Scripts with ISSUES (3 scripts)
These need review/fixes:
1. ⚠️ test_e2e_systemd.sh - Incomplete/broken code, missing variable definitions
2. ⚠️ ble_install_daemon.sh - Malformed code (bash+python mixed), overlaps with 03
3. ⚠️ ble_switch_backend.sh - Marked as legacy, uses hardcoded path, but replacement doesn't exist

### Scripts to DELETE
**NONE** - However, scripts 09, 13, and 15 should be reviewed:
- **09**: Either fix or delete (appears to be a broken version of 08 for systemd)
- **13**: Either fix or delete (broken code, overlaps with 03)
- **15**: Either delete (if backend switching not needed), fix (use env vars), or create script 16 as documented

---

## Final Recommendation

**DO NOT DELETE any scripts at this time.**

However, the following actions are recommended:

### High Priority Issues
1. **Fix test_e2e_systemd.sh** - Add missing variable definitions or delete if not needed
2. **Fix ble_install_daemon.sh** - Correct bash/Python syntax or delete if redundant
3. **Resolve 15/16 confusion** - Either:
   - Fix script 15 to use env vars from env_set_variables.sh
   - Create script 16 as documented in README
   - Remove references to script 16 from README if not needed

### Scripts Currently Required by Implementation
- **ble_install_helper.sh** is **CRITICAL** - BluetoothKeyboard directly calls bt_kb_send
- **usb_sync_cache.sh** actively uses mtp_sync.py module
- All other scripts provide essential setup, deployment, or troubleshooting functionality

### No Candidates for Deletion
Based on the analysis, no scripts have been made obsolete by the implementation. All functional scripts serve distinct purposes that are not replaced by code in src/ipr_keyboard/.
