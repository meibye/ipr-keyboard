On the Pi:

### save the scripts below into scripts/
chmod +x scripts/*.sh


You’d typically run them in this order:

cd /home/meibye/dev/ipr-keyboard

### 1) OS packages & Bluetooth base
sudo ./scripts/01_system_setup.sh

### 2) Bluetooth config
sudo ./scripts/02_configure_bluetooth.sh

### 3) Placeholder BT helper
sudo ./scripts/03_install_bt_helper.sh

### 4) Python env + deps via uv
./scripts/04_setup_venv.sh   # as user meibye

### 5) Systemd service
sudo ./scripts/05_install_service.sh

# How to run the full flow

System + Bluetooth base (root):

cd /home/meibye/dev/ipr-keyboard
sudo ./scripts/01_system_setup.sh
sudo ./scripts/02_configure_bluetooth.sh
sudo ./scripts/03_install_bt_helper.sh


Mount IrisPen USB (root, once you know the device node – check lsblk -fp):
sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1   # adjust device as needed

venv + deps with uv (user):
./scripts/04_setup_venv.sh

Smoke test (user):
./scripts/07_smoke_test.sh


If all green, install + start systemd service (root):
    sudo ./scripts/05_install_service.sh


# How to test features individually

- Config management
    - pytest tests/config
    - Hit GET/POST /config/ with curl or browser.
- USB file handling
    - Plug in USB stick, mount it (e.g. /mnt/irispen), set IrisPenFolder to that path.
    - Run a small script calling wait_for_new_file and create files by copying or using IrisPen.
- Bluetooth keyboard
    - Once your HID helper is real, pair the PC with the Pi (from PC side, see the Pi as “Keyboard”).
    - Test BluetoothKeyboard().send_text("Hello world") from a Python REPL and watch text appear on PC.
- Logging
    - Start ipr_keyboard.main, then check logs/ipr_keyboard.log.
    - Call /logs/tail?lines=50 to see recent entries.
- End-to-end
    - Configure config.json with correct IrisPenFolder.
    - Make sure the systemd service is running.
    - Scan something → IrisPen writes file → Pi reads file → forwards over BT → optionally deletes file → logs visible in web UI.