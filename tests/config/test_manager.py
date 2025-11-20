from pathlib import Path
from ipr_keyboard.config.manager import AppConfig, ConfigManager
from ipr_keyboard.utils.helpers import save_json


def test_config_load_and_update(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {"IrisPenFolder": "/tmp/iris", "DeleteFiles": False})

    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )

    mgr = ConfigManager()
    cfg = mgr.get()
    assert cfg.IrisPenFolder == "/tmp/iris"
    assert cfg.DeleteFiles is False

    mgr.update(DeleteFiles=True, MaxFileSize=1234)
    cfg2 = mgr.get()
    assert cfg2.DeleteFiles is True
    assert cfg2.MaxFileSize == 1234
