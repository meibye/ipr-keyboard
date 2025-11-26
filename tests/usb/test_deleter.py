"""Tests for USB file deletion functionality.

Tests file and folder deletion operations.
"""
import os
from pathlib import Path
from unittest.mock import patch

from ipr_keyboard.usb import deleter


def test_delete_file(usb_folder):
    """Test deleting a single file.
    
    Verifies that a file is successfully deleted.
    """
    test_file = usb_folder / "to_delete.txt"
    test_file.write_text("content")
    
    assert test_file.exists()
    
    result = deleter.delete_file(test_file)
    
    assert result is True
    assert not test_file.exists()


def test_delete_file_nonexistent(usb_folder):
    """Test deleting a non-existent file.
    
    Verifies that deleting a missing file returns True (no error).
    """
    nonexistent = usb_folder / "missing.txt"
    
    result = deleter.delete_file(nonexistent)
    
    assert result is True


def test_delete_file_directory(usb_folder):
    """Test deleting a directory path (should not delete).
    
    Verifies that directories are not deleted by delete_file.
    """
    subdir = usb_folder / "subdir"
    subdir.mkdir()
    
    result = deleter.delete_file(subdir)
    
    # Should return True since the path is not a file
    assert result is True
    # Directory should still exist
    assert subdir.exists()


def test_delete_file_permission_error(usb_folder, monkeypatch):
    """Test handling permission errors during deletion.
    
    Verifies that OSError is caught and False is returned.
    """
    test_file = usb_folder / "protected.txt"
    test_file.write_text("protected content")
    
    # Mock unlink to raise OSError
    def fake_unlink(self):
        raise OSError("Permission denied")
    
    monkeypatch.setattr(Path, "unlink", fake_unlink)
    
    result = deleter.delete_file(test_file)
    
    assert result is False


def test_delete_all(usb_folder):
    """Test deleting all files in a folder.
    
    Verifies that all files are deleted and returned.
    """
    # Create multiple files
    files = []
    for i in range(3):
        f = usb_folder / f"file{i}.txt"
        f.write_text(f"content {i}")
        files.append(f)
    
    deleted = deleter.delete_all(usb_folder)
    
    assert len(deleted) == 3
    for f in files:
        assert not f.exists()


def test_delete_all_empty_folder(usb_folder):
    """Test deleting from an empty folder.
    
    Verifies that an empty list is returned.
    """
    deleted = deleter.delete_all(usb_folder)
    
    assert deleted == []


def test_delete_all_nonexistent_folder(tmp_path):
    """Test deleting from a non-existent folder.
    
    Verifies that an empty list is returned.
    """
    nonexistent = tmp_path / "missing"
    
    deleted = deleter.delete_all(nonexistent)
    
    assert deleted == []


def test_delete_all_preserves_directories(usb_folder):
    """Test that delete_all only deletes files, not subdirectories.
    
    Verifies that directories are not deleted.
    """
    # Create files and a subdirectory
    (usb_folder / "file1.txt").write_text("content")
    (usb_folder / "file2.txt").write_text("content")
    subdir = usb_folder / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested content")
    
    deleted = deleter.delete_all(usb_folder)
    
    # Only top-level files should be deleted
    assert len(deleted) == 2
    # Subdirectory should still exist
    assert subdir.exists()
    # Nested file should still exist
    assert (subdir / "nested.txt").exists()


def test_delete_all_with_errors(usb_folder, monkeypatch):
    """Test delete_all when some files fail to delete.
    
    Verifies that other files are still deleted even if some fail.
    """
    # Create files
    f1 = usb_folder / "file1.txt"
    f2 = usb_folder / "file2.txt"
    f3 = usb_folder / "file3.txt"
    f1.write_text("content1")
    f2.write_text("content2")
    f3.write_text("content3")
    
    original_unlink = Path.unlink
    
    def selective_unlink(self):
        # Only fail for file2
        if "file2" in str(self):
            raise OSError("Permission denied")
        original_unlink(self)
    
    monkeypatch.setattr(Path, "unlink", selective_unlink)
    
    deleted = deleter.delete_all(usb_folder)
    
    # Only file1 and file3 should be deleted
    assert len(deleted) == 2
    assert not f1.exists()
    assert f2.exists()  # This one failed
    assert not f3.exists()


def test_delete_newest(usb_folder, sample_text_files):
    """Test deleting the newest file in a folder.
    
    Verifies that the most recently modified file is deleted.
    """
    # sample_text_files creates file1.txt, file2.txt, file3.txt
    # file3.txt is the newest
    
    result = deleter.delete_newest(usb_folder)
    
    assert result is not None
    assert result.name == "file3.txt"
    assert not result.exists()
    
    # Other files should still exist
    assert (usb_folder / "file1.txt").exists()
    assert (usb_folder / "file2.txt").exists()


def test_delete_newest_empty_folder(usb_folder):
    """Test delete_newest on an empty folder.
    
    Verifies that None is returned when no files exist.
    """
    result = deleter.delete_newest(usb_folder)
    
    assert result is None


def test_delete_newest_single_file(usb_folder):
    """Test delete_newest with only one file.
    
    Verifies correct behavior with a single file.
    """
    single = usb_folder / "only.txt"
    single.write_text("only content")
    
    result = deleter.delete_newest(usb_folder)
    
    assert result == single
    assert not single.exists()


def test_delete_newest_with_failure(usb_folder, sample_text_files, monkeypatch):
    """Test delete_newest when deletion fails.
    
    Verifies that None is returned if the deletion fails.
    """
    original_unlink = Path.unlink
    
    def fail_unlink(self):
        raise OSError("Permission denied")
    
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    
    result = deleter.delete_newest(usb_folder)
    
    # Should return None because deletion failed
    assert result is None
