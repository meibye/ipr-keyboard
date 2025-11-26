"""Tests for USB file detection functionality.

Tests the detector module for finding and monitoring files.
"""
import time
import threading
from pathlib import Path

from ipr_keyboard.usb import detector


def test_list_files(usb_folder, sample_text_files):
    """Test listing files sorted by modification time.
    
    Verifies that files are returned in order of modification time.
    """
    files = detector.list_files(usb_folder)
    
    assert len(files) == 3
    # Files should be sorted oldest first
    assert files[0].name == "file1.txt"
    assert files[-1].name == "file3.txt"


def test_list_files_empty_folder(usb_folder):
    """Test listing files in an empty folder.
    
    Verifies that an empty list is returned for empty directories.
    """
    files = detector.list_files(usb_folder)
    
    assert files == []


def test_list_files_nonexistent_folder(tmp_path):
    """Test listing files in a non-existent folder.
    
    Verifies that an empty list is returned for missing directories.
    """
    nonexistent = tmp_path / "does_not_exist"
    files = detector.list_files(nonexistent)
    
    assert files == []


def test_list_files_excludes_directories(usb_folder):
    """Test that directories are excluded from the file list.
    
    Verifies that only files (not subdirectories) are returned.
    """
    # Create a file and a subdirectory
    (usb_folder / "test.txt").write_text("content")
    (usb_folder / "subdir").mkdir()
    
    files = detector.list_files(usb_folder)
    
    assert len(files) == 1
    assert files[0].name == "test.txt"


def test_newest_file(usb_folder, sample_text_files):
    """Test getting the newest file by modification time.
    
    Verifies that the most recently modified file is returned.
    """
    newest = detector.newest_file(usb_folder)
    
    assert newest is not None
    assert newest.name == "file3.txt"


def test_newest_file_empty_folder(usb_folder):
    """Test getting newest file from empty folder.
    
    Verifies that None is returned for empty directories.
    """
    newest = detector.newest_file(usb_folder)
    
    assert newest is None


def test_newest_file_nonexistent_folder(tmp_path):
    """Test getting newest file from non-existent folder.
    
    Verifies that None is returned for missing directories.
    """
    nonexistent = tmp_path / "does_not_exist"
    newest = detector.newest_file(nonexistent)
    
    assert newest is None


def test_newest_file_single_file(usb_folder):
    """Test getting newest file when only one file exists.
    
    Verifies correct behavior with a single file.
    """
    single = usb_folder / "only_file.txt"
    single.write_text("single content")
    
    newest = detector.newest_file(usb_folder)
    
    assert newest == single


def test_wait_for_new_file_immediate(usb_folder, sample_text_files):
    """Test waiting for a new file that already exists.
    
    Verifies that a file newer than last_seen_mtime is detected immediately.
    """
    # Get the mtime of the second file
    second_file = sample_text_files[1]
    old_mtime = second_file.stat().st_mtime
    
    # The third file is newer, should be detected immediately
    result = detector.wait_for_new_file(usb_folder, old_mtime, interval=0.01)
    
    assert result is not None
    assert result.name == "file3.txt"


def test_wait_for_new_file_polling(usb_folder):
    """Test polling for a new file that appears after start.
    
    Verifies that the function polls and detects a newly created file.
    """
    initial_mtime = time.time()
    result_holder = {"result": None}
    
    def wait_task():
        result_holder["result"] = detector.wait_for_new_file(
            usb_folder, initial_mtime, interval=0.05
        )
    
    # Start the wait in a thread
    thread = threading.Thread(target=wait_task)
    thread.start()
    
    # Give it a moment to start polling
    time.sleep(0.1)
    
    # Create a new file
    new_file = usb_folder / "new_file.txt"
    new_file.write_text("new content")
    
    # Wait for the thread to complete (with timeout)
    thread.join(timeout=2.0)
    
    assert not thread.is_alive(), "Thread should have completed"
    assert result_holder["result"] is not None
    assert result_holder["result"].name == "new_file.txt"


def test_wait_for_new_file_nonexistent_folder(tmp_path):
    """Test waiting on a folder that doesn't initially exist.
    
    Verifies that the function handles non-existent folders gracefully.
    """
    folder = tmp_path / "future_folder"
    result_holder = {"result": None}
    
    def wait_task():
        result_holder["result"] = detector.wait_for_new_file(
            folder, 0.0, interval=0.05
        )
    
    thread = threading.Thread(target=wait_task)
    thread.start()
    
    # Give it a moment to start polling
    time.sleep(0.1)
    
    # Create the folder and add a file
    folder.mkdir()
    (folder / "appeared.txt").write_text("content")
    
    thread.join(timeout=2.0)
    
    assert not thread.is_alive()
    assert result_holder["result"] is not None
    assert result_holder["result"].name == "appeared.txt"
