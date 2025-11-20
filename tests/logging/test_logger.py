from ipr_keyboard.logging.logger import get_logger, log_path


def test_logger_writes(tmp_path, monkeypatch):
    monkeypatch.setattr("ipr_keyboard.logging.logger._LOG_FILE", tmp_path / "test.log")
    logger = get_logger()
    logger.info("Hello log")
    path = log_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Hello log" in text
