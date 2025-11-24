"""Integration tests for USB file handling flow.

Tests the complete flow from file detection to reading and deletion.
"""
import time
from pathlib import Path

from ipr_keyboard.usb import detector, reader, deleter


def test_file_detection_and_read(usb_folder):
    """Test complete flow: detect new file and read content.
    
    Verifies the integration between detector and reader modules.
    """
    # Create a test file
    test_file = usb_folder / "scan_001.txt"
    test_content = "Scanned text from IrisPen"
    test_file.write_text(test_content, encoding="utf-8")
    
    # Detect the file
    newest = detector.newest_file(usb_folder)
    assert newest == test_file
    
    # Read the content
    content = reader.read_file(newest, max_size=1024)
    assert content == test_content


def test_file_detection_and_delete(usb_folder):
    """Test complete flow: detect, read, and delete file.
    
    Verifies the integration between all USB modules.
    """
    # Create a test file
    test_file = usb_folder / "scan_002.txt"
    test_content = "Another scanned text"
    test_file.write_text(test_content, encoding="utf-8")
    
    # Detect and read
    newest = detector.newest_file(usb_folder)
    content = reader.read_file(newest, max_size=1024)
    
    assert content == test_content
    assert test_file.exists()
    
    # Delete after processing
    deleted = deleter.delete_file(test_file)
    
    assert deleted is True
    assert not test_file.exists()


def test_multiple_files_processing(usb_folder):
    """Test processing multiple files in order.
    
    Verifies that files are processed in modification order.
    """
    # Create files with slight delays
    files = []
    for i in range(3):
        f = usb_folder / f"scan_{i:03d}.txt"
        f.write_text(f"Content {i}", encoding="utf-8")
        files.append(f)
        time.sleep(0.01)  # Ensure different mtimes
    
    # Process files in order (oldest to newest)
    processed = []
    while True:
        all_files = detector.list_files(usb_folder)
        if not all_files:
            break
        
        # Get oldest file
        oldest = all_files[0]
        content = reader.read_file(oldest, max_size=1024)
        processed.append((oldest.name, content))
        deleter.delete_file(oldest)
    
    assert len(processed) == 3
    assert processed[0][0] == "scan_000.txt"
    assert processed[1][0] == "scan_001.txt"
    assert processed[2][0] == "scan_002.txt"


def test_file_size_limit(usb_folder):
    """Test that oversized files are rejected.
    
    Verifies that file size limits are enforced.
    """
    # Create a large file
    large_file = usb_folder / "large.txt"
    large_file.write_text("x" * 100, encoding="utf-8")
    
    # Create a small file
    small_file = usb_folder / "small.txt"
    small_file.write_text("small", encoding="utf-8")
    
    # Try to read with a small size limit
    large_content = reader.read_file(large_file, max_size=50)
    small_content = reader.read_file(small_file, max_size=50)
    
    assert large_content is None  # Rejected
    assert small_content == "small"  # Accepted


def test_read_newest_integration(usb_folder):
    """Test read_newest as an integration point.
    
    Verifies that read_newest combines detection and reading.
    """
    # Create multiple files
    for i in range(3):
        (usb_folder / f"file{i}.txt").write_text(f"content{i}", encoding="utf-8")
        time.sleep(0.01)
    
    # read_newest should get the last one
    content = reader.read_newest(usb_folder, max_size=1024)
    
    assert content == "content2"


def test_delete_newest_integration(usb_folder):
    """Test delete_newest as an integration point.
    
    Verifies that delete_newest combines detection and deletion.
    """
    # Create multiple files
    for i in range(3):
        (usb_folder / f"file{i}.txt").write_text(f"content{i}", encoding="utf-8")
        time.sleep(0.01)
    
    # Delete the newest
    deleted = deleter.delete_newest(usb_folder)
    
    assert deleted.name == "file2.txt"
    
    # Verify file is gone
    assert not (usb_folder / "file2.txt").exists()
    
    # Others should still exist
    assert (usb_folder / "file0.txt").exists()
    assert (usb_folder / "file1.txt").exists()


def test_workflow_with_utf8_content(usb_folder):
    """Test workflow with UTF-8 encoded content.
    
    Verifies that special characters are preserved throughout.
    """
    test_file = usb_folder / "utf8.txt"
    utf8_content = "Test æøå ÆØÅ 日本語 emoji: 🎉"
    test_file.write_text(utf8_content, encoding="utf-8")
    
    # Detect and read
    newest = detector.newest_file(usb_folder)
    content = reader.read_file(newest, max_size=1024)
    
    assert content == utf8_content
    
    # Delete
    deleter.delete_file(newest)
    assert not test_file.exists()
