"""Tests for USB file operations.

Tests file detection, reading, and deletion functionality.
"""
from pathlib import Path
from ipr_keyboard.usb import reader, detector, deleter


def test_newest_and_read(tmp_path):
    """Test detecting, reading, and deleting the newest file.
    
    Verifies that the newest file is correctly identified, its content
    is read properly, and it can be deleted.
    """
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("first", encoding="utf-8")
    f2.write_text("second", encoding="utf-8")

    newest = detector.newest_file(tmp_path)
    assert newest == f2

    content = reader.read_file(newest, max_size=1024)
    assert content == "second"

    deleted = deleter.delete_newest(tmp_path)
    assert deleted == f2
    assert not f2.exists()
