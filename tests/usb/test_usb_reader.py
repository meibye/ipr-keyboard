"""Tests for USB file reading functionality.

Tests file reading with size limits, error handling, and integration
with detection and deletion modules.
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


def test_read_file(usb_folder):
    """Test reading a file successfully.
    
    Verifies that file content is read correctly.
    """
    test_file = usb_folder / "test.txt"
    test_file.write_text("Test content", encoding="utf-8")
    
    content = reader.read_file(test_file, max_size=1024)
    
    assert content == "Test content"


def test_read_file_nonexistent(tmp_path):
    """Test reading a non-existent file.
    
    Verifies that None is returned for missing files.
    """
    nonexistent = tmp_path / "missing.txt"
    
    content = reader.read_file(nonexistent, max_size=1024)
    
    assert content is None


def test_read_file_not_file(usb_folder):
    """Test reading a directory path instead of a file.
    
    Verifies that None is returned when path is a directory.
    """
    subdir = usb_folder / "subdir"
    subdir.mkdir()
    
    content = reader.read_file(subdir, max_size=1024)
    
    assert content is None


def test_read_file_too_large(usb_folder):
    """Test reading a file that exceeds the size limit.
    
    Verifies that None is returned for oversized files.
    """
    large_file = usb_folder / "large.txt"
    # Create a file with 100 bytes
    large_file.write_text("x" * 100, encoding="utf-8")
    
    # Try to read with a 50-byte limit
    content = reader.read_file(large_file, max_size=50)
    
    assert content is None


def test_read_file_exactly_at_limit(usb_folder):
    """Test reading a file exactly at the size limit.
    
    Verifies that files at exactly the limit are accepted (uses > not >=).
    """
    file = usb_folder / "exact.txt"
    content_text = "12345"  # 5 bytes
    file.write_text(content_text, encoding="utf-8")
    
    # File size equals limit - should be accepted (uses > for rejection)
    # Based on reader.py: if path.stat().st_size > max_size: return None
    result = reader.read_file(file, max_size=5)
    
    assert result == content_text


def test_read_file_utf8_encoding(usb_folder):
    """Test reading a file with UTF-8 characters.
    
    Verifies that Unicode content is handled correctly.
    """
    utf8_file = usb_folder / "unicode.txt"
    utf8_content = "Hello æøå ÆØÅ 日本語"
    utf8_file.write_text(utf8_content, encoding="utf-8")
    
    content = reader.read_file(utf8_file, max_size=1024)
    
    assert content == utf8_content


def test_read_file_with_errors(usb_folder):
    """Test reading a file with invalid UTF-8 bytes.
    
    Verifies that encoding errors are ignored (errors='ignore').
    """
    bad_file = usb_folder / "bad_encoding.txt"
    # Write raw bytes including invalid UTF-8 sequence
    bad_file.write_bytes(b"Hello \xff\xfe World")
    
    content = reader.read_file(bad_file, max_size=1024)
    
    # Should have content with bad bytes ignored
    assert content is not None
    assert "Hello" in content
    assert "World" in content


def test_read_newest(usb_folder, sample_text_files):
    """Test reading the newest file in a folder.
    
    Verifies that read_newest combines detection and reading.
    """
    content = reader.read_newest(usb_folder, max_size=1024)
    
    # Third file contains "Third file"
    assert content == "Third file"


def test_read_newest_empty_folder(usb_folder):
    """Test reading from an empty folder.
    
    Verifies that None is returned when no files exist.
    """
    content = reader.read_newest(usb_folder, max_size=1024)
    
    assert content is None


def test_read_newest_too_large(usb_folder):
    """Test read_newest when newest file is too large.
    
    Verifies that None is returned if the newest file exceeds the limit.
    """
    # Create a file that's too large
    large_file = usb_folder / "large.txt"
    large_file.write_text("x" * 100, encoding="utf-8")
    
    content = reader.read_newest(usb_folder, max_size=50)
    
    assert content is None
