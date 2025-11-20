import subprocess
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard


def test_send_text(monkeypatch):
    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr("ipr_keyboard.bluetooth.keyboard.subprocess.run", fake_run)

    kb = BluetoothKeyboard(helper_path="/fake/path")
    assert kb.send_text("abc") is True
    assert "abc" in calls["args"]
