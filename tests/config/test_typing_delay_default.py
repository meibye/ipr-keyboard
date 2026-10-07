"""The app's typing-speed default is the provisioned one.

The BLE daemon starts at BT_KEY_DELAY_MS from /opt/ipr_common.env -- 12 ms in
the shipped example -- but the app re-applies TypingDelayMs about once a
second, and its default was a hard-coded 20.  Every fresh install therefore
typed at ~25 characters a second instead of the ~40 provisioning asked for,
and the audit's O.14 skipped right past it.
"""

from __future__ import annotations

import pytest

from ipr_keyboard.config import manager


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.delenv("BT_KEY_DELAY_MS", raising=False)
    monkeypatch.setenv("IPR_COMMON_ENV", str(tmp_path / "absent.env"))
    return tmp_path


def _env_file(tmp_path, monkeypatch, text):
    f = tmp_path / "ipr_common.env"
    f.write_text(text, encoding="utf-8")
    monkeypatch.setenv("IPR_COMMON_ENV", str(f))


def test_the_provisioned_value_is_read_from_the_env_file(tmp_path, monkeypatch):
    """ipr_keyboard.service does not load the env file, so it reads it."""
    _env_file(tmp_path, monkeypatch, 'APP_USER="meibye"\nBT_KEY_DELAY_MS="12"\n')
    assert manager._provisioned_typing_delay() == 12


@pytest.mark.parametrize(
    "line", ["BT_KEY_DELAY_MS=12", "BT_KEY_DELAY_MS='12'", 'BT_KEY_DELAY_MS="12"']
)
def test_any_quoting_style_is_read(tmp_path, monkeypatch, line):
    _env_file(tmp_path, monkeypatch, line + "\n")
    assert manager._provisioned_typing_delay() == 12


def test_the_process_environment_wins_over_the_file(tmp_path, monkeypatch):
    _env_file(tmp_path, monkeypatch, 'BT_KEY_DELAY_MS="12"\n')
    monkeypatch.setenv("BT_KEY_DELAY_MS", "8")
    assert manager._provisioned_typing_delay() == 8


def test_no_env_file_falls_back_to_twenty():
    """A development machine has no /opt/ipr_common.env."""
    assert manager._provisioned_typing_delay() == 20


@pytest.mark.parametrize("bad", ["fast", "", "0", "-5", "5000", "12ms"])
def test_unusable_values_fall_back_rather_than_stop_typing(tmp_path, monkeypatch, bad):
    _env_file(tmp_path, monkeypatch, f'BT_KEY_DELAY_MS="{bad}"\n')
    assert manager._provisioned_typing_delay() == 20


def test_a_commented_line_is_not_a_setting(tmp_path, monkeypatch):
    _env_file(tmp_path, monkeypatch, '# BT_KEY_DELAY_MS="4"\n')
    assert manager._provisioned_typing_delay() == 20


def test_a_saved_choice_still_beats_the_provisioned_default():
    """Settings writes TypingDelayMs to config.json; that must win."""
    cfg = manager.AppConfig.from_dict({"TypingDelayMs": 8})
    assert cfg.TypingDelayMs == 8


def test_the_field_default_is_the_provisioned_value():
    assert manager.AppConfig().TypingDelayMs == manager._PROVISIONED_TYPING_DELAY_MS
