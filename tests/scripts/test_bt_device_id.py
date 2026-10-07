"""The keyboard's identity is set once, as bluetoothd's DeviceID.

bluetoothd publishes a Device Information service of its own, and a host reads
that one.  With DeviceID unset it carries the BlueZ default, whose revision is
the BlueZ version -- so a paired Windows laptop identified the keyboard as
VID 1d6b / PID 0246 / REV 0552, and that identity changed with the bluez
package.  svc_install_bt_gatt_hid.sh now writes DeviceID from BT_USB_*.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "service" / "svc_install_bt_gatt_hid.sh"
LF = "\n"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

# The relevant part of a stock BlueZ main.conf: the example is commented out.
STOCK_MAIN_CONF = LF.join(
    [
        "[General]",
        "",
        "# Use vendor id source (assigner), vendor, product and version information for",
        '# DID profile support. The values are separated by ":" and assigner, VID, PID',
        "# and version.",
        "# Possible vendor id source values: bluetooth, usb (defaults to usb)",
        "#DeviceID = bluetooth:1234:5678:abcd",
        "",
        "Experimental=true",
        "",
        "[BR]",
        "#PageScanType = ",
        "",
        "[LE]",
        "#MinAdvertisementInterval = ",
        "",
    ]
)


def _identity_block() -> str:
    """The DeviceID part of the installer, from hex4() to its closing fi."""
    text = INSTALLER.read_text(encoding="utf-8").replace("\r\n", LF)
    start = text.index("hex4() {")
    tail = 'if [[ -f "$BT_MAIN_CONF" ]]; then'
    end = text.index(LF + "fi" + LF, text.index(tail, start)) + 4
    return text[start:end]


@pytest.fixture
def install(tmp_path):
    (tmp_path / "block.sh").write_text(_identity_block(), encoding="utf-8", newline=LF)
    # A file, not `bash -c`: through the Windows command line MSYS bash
    # re-parses quoting and loses arguments.
    (tmp_path / "driver.sh").write_text(
        LF.join(
            [
                "set -euo pipefail",
                'ENV_FILE="./env"',
                'BT_MAIN_CONF="./main.conf"',
                "source ./block.sh",
                "",
            ]
        ),
        encoding="utf-8",
        newline=LF,
    )

    def run(env: str, main_conf: str = STOCK_MAIN_CONF) -> str:
        (tmp_path / "env").write_text(env, encoding="utf-8", newline=LF)
        (tmp_path / "main.conf").write_text(main_conf, encoding="utf-8", newline=LF)
        out = subprocess.run(
            ["bash", "driver.sh"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=tmp_path,
        )
        assert out.returncode == 0, out.stderr
        return (tmp_path / "main.conf").read_text(encoding="utf-8")

    return run


def _device_ids(conf: str) -> list[str]:
    return re.findall(r"(?m)^DeviceID = (\S+)$", conf)


def test_the_identity_comes_from_the_configured_values(install):
    conf = install('BT_USB_VID="0x1209"\nBT_USB_PID="0x0001"\nBT_USB_VER="0x0100"\n')
    assert _device_ids(conf) == ["usb:1209:0001:0100"]


def test_it_replaces_the_commented_example_in_place(install):
    conf = install('BT_USB_VID="0x1209"\nBT_USB_PID="0x0001"\nBT_USB_VER="0x0100"\n')
    assert "#DeviceID" not in conf
    # Still in [General], where bluetoothd reads it.
    section = None
    for line in conf.splitlines():
        if line.startswith("["):
            section = line
        if line.startswith("DeviceID"):
            assert section == "[General]", section


def test_only_that_line_changes(install):
    conf = install('BT_USB_VID="0x1209"\nBT_USB_PID="0x0001"\nBT_USB_VER="0x0100"\n')
    before = STOCK_MAIN_CONF.splitlines()
    after = conf.splitlines()
    assert len(before) == len(after)
    changed = [(b, a) for b, a in zip(before, after) if b != a]
    assert changed == [
        ("#DeviceID = bluetooth:1234:5678:abcd", "DeviceID = usb:1209:0001:0100")
    ]


def test_running_it_twice_changes_nothing(install):
    env = 'BT_USB_VID="0x1209"\nBT_USB_PID="0x0001"\nBT_USB_VER="0x0100"\n'
    once = install(env)
    assert install(env, main_conf=once) == once


def test_a_changed_identity_replaces_the_old_one(install):
    first = install('BT_USB_VID="0x1234"\nBT_USB_PID="0x5678"\nBT_USB_VER="0x0100"\n')
    second = install(
        'BT_USB_VID="0x1209"\nBT_USB_PID="0x0001"\nBT_USB_VER="0x0100"\n',
        main_conf=first,
    )
    assert _device_ids(second) == ["usb:1209:0001:0100"], "one DeviceID, the new one"


def test_hex_is_normalised_whatever_form_it_is_written_in(install):
    conf = install("BT_USB_VID=0X1209\nBT_USB_PID='1'\nBT_USB_VER=\"0x100\"\n")
    assert _device_ids(conf) == ["usb:1209:0001:0100"]


def test_missing_values_leave_main_conf_alone(install):
    """An empty identity would be usb:0000:0000:0000 -- worse than the default."""
    conf = install("BT_DEVICE_NAME=x\n")
    assert _device_ids(conf) == []
    assert conf == STOCK_MAIN_CONF
