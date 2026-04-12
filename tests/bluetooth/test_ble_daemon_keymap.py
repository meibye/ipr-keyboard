"""Keymap tests for the BLE HID daemon."""

import importlib.util
import os
import sys
import types
from pathlib import Path


def load_daemon_module(unicode_mode=None):
    """Import the daemon module with lightweight DBus/GI stubs."""
    if unicode_mode is None:
        os.environ.pop("BT_BLE_UNICODE_MODE", None)
    else:
        os.environ["BT_BLE_UNICODE_MODE"] = unicode_mode

    dbus = types.ModuleType("dbus")
    dbus.Byte = int
    dbus.UInt16 = int
    dbus.String = str
    dbus.Boolean = bool
    dbus.ObjectPath = str
    dbus.Array = list
    dbus.Dictionary = dict
    dbus.ByteArray = bytes

    class DummyDBusException(Exception):
        def get_dbus_name(self):
            return ""

    dbus.DBusException = DummyDBusException
    dbus.Interface = lambda *args, **kwargs: None
    dbus.SystemBus = lambda *args, **kwargs: None

    dbus_service = types.ModuleType("dbus.service")

    class DummyObject:
        def __init__(self, *args, **kwargs):
            pass

    def passthrough_decorator(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    dbus_service.Object = DummyObject
    dbus_service.method = passthrough_decorator
    dbus_service.signal = passthrough_decorator

    dbus_mainloop = types.ModuleType("dbus.mainloop")
    dbus_mainloop_glib = types.ModuleType("dbus.mainloop.glib")
    dbus_mainloop_glib.DBusGMainLoop = lambda *args, **kwargs: None

    dbus.mainloop = dbus_mainloop
    dbus.mainloop.glib = dbus_mainloop_glib
    dbus.service = dbus_service

    sys.modules["dbus"] = dbus
    sys.modules["dbus.service"] = dbus_service
    sys.modules["dbus.mainloop"] = dbus_mainloop
    sys.modules["dbus.mainloop.glib"] = dbus_mainloop_glib

    gi = types.ModuleType("gi")
    repository = types.ModuleType("gi.repository")
    repository.GLib = types.SimpleNamespace(MainLoop=lambda *args, **kwargs: None)
    gi.repository = repository
    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = repository
    sys.modules["gi.repository.GLib"] = repository.GLib

    path = Path("scripts/service/bin/bt_hid_ble_daemon.py")
    spec = importlib.util.spec_from_file_location("bt_hid_ble_daemon", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_windows_hex_unicode_sequence_for_emdash():
    mod = load_daemon_module("windows_hex_alt")

    sequence = mod.map_char("—")

    assert sequence[0] == (mod.MOD_LALT, 0)
    assert sequence[1] == (mod.MOD_LALT, mod.KEYPAD_PLUS_USAGE)
    assert sequence[-1] == mod.REPORT_RELEASE
    assert (mod.MOD_LALT, mod.DIGIT_USAGES["2"]) in sequence
    assert (mod.MOD_LALT, mod.DIGIT_USAGES["0"]) in sequence
    assert (mod.MOD_LALT, mod.DIGIT_USAGES["1"]) in sequence
    assert (mod.MOD_LALT, mod.DIGIT_USAGES["4"]) in sequence


def test_explicit_combining_cluster_preserves_codepoints():
    mod = load_daemon_module("windows_alt_decimal")

    sequence = mod.map_char("a\u0301")

    assert sequence[:2] == [(0, mod.LETTER_USAGES["a"]), mod.REPORT_RELEASE]
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["0"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["7"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["6"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["8"]) in sequence


def test_literal_dead_key_mark_keeps_layout_typing():
    mod = load_daemon_module()

    sequence = mod.map_char("´")

    expected = [
        (0, 0x2E),
        mod.REPORT_RELEASE,
        mod.SPACE_KEYPRESS,
        mod.REPORT_RELEASE,
    ]
    assert sequence == expected


def test_direct_danish_letter_uses_layout_mapping():
    mod = load_daemon_module()

    assert mod.map_char("æ") == [(0, 0x33), mod.REPORT_RELEASE]


def test_default_mode_uses_decimal_unicode_for_emdash():
    mod = load_daemon_module()

    assert mod.UNICODE_MODE == "windows_alt_decimal"
    sequence = mod.map_char("—")
    assert sequence[0] == (mod.MOD_LALT, 0)
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["2"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["0"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["1"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["4"]) in sequence


def test_default_mode_uses_decimal_unicode_for_endash():
    mod = load_daemon_module()

    sequence = mod.map_char("–")
    assert sequence[0] == (mod.MOD_LALT, 0)
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["2"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["0"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["1"]) in sequence
    assert (mod.MOD_LALT, mod.KEYPAD_DIGIT_USAGES["3"]) in sequence


def test_off_mode_keeps_ascii_fallback_for_emdash():
    mod = load_daemon_module("off")

    expected = [
        (0, 0x38),
        mod.REPORT_RELEASE,
        (0, 0x38),
        mod.REPORT_RELEASE,
    ]
    assert mod.map_char("—") == expected
