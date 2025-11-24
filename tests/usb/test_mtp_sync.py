"""Tests for MTP sync functionality.

Tests synchronization from MTP mount to local cache.
"""
import os
import time
from pathlib import Path

from ipr_keyboard.usb.mtp_sync import sync_mtp_to_cache, _iter_text_files, SyncResult


def test_iter_text_files(tmp_path):
    """Test iterating text files in a directory.
    
    Verifies that only .txt files are returned.
    """
    # Create various files
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")
    (tmp_path / "file3.doc").write_text("not a txt")
    (tmp_path / "readme.md").write_text("markdown")
    
    txt_files = list(_iter_text_files(tmp_path))
    
    assert len(txt_files) == 2
    names = [f.name for f in txt_files]
    assert "file1.txt" in names
    assert "file2.txt" in names
    assert "file3.doc" not in names


def test_iter_text_files_recursive(tmp_path):
    """Test that text files in subdirectories are found.
    
    Verifies recursive file discovery.
    """
    # Create nested structure
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    deep = subdir / "deep"
    deep.mkdir()
    
    (tmp_path / "root.txt").write_text("root")
    (subdir / "sub.txt").write_text("sub")
    (deep / "deep.txt").write_text("deep")
    
    txt_files = list(_iter_text_files(tmp_path))
    
    assert len(txt_files) == 3
    names = [f.name for f in txt_files]
    assert "root.txt" in names
    assert "sub.txt" in names
    assert "deep.txt" in names


def test_sync_mtp_to_cache_basic(tmp_path):
    """Test basic sync from MTP to cache.
    
    Verifies that files are copied to the cache directory.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "cache"
    mtp_root.mkdir()
    
    # Create source files
    (mtp_root / "file1.txt").write_text("content1")
    (mtp_root / "file2.txt").write_text("content2")
    
    result = sync_mtp_to_cache(mtp_root, cache_root, delete_source=False)
    
    assert isinstance(result, SyncResult)
    assert len(result.copied) == 2
    assert len(result.skipped) == 0
    assert len(result.deleted_source) == 0
    
    # Verify cache files exist
    assert (cache_root / "file1.txt").exists()
    assert (cache_root / "file2.txt").exists()
    
    # Verify content
    assert (cache_root / "file1.txt").read_text() == "content1"


def test_sync_mtp_to_cache_creates_cache_dir(tmp_path):
    """Test that cache directory is created if it doesn't exist.
    
    Verifies that parent directories are created automatically.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "deep" / "nested" / "cache"
    mtp_root.mkdir()
    
    (mtp_root / "file.txt").write_text("content")
    
    result = sync_mtp_to_cache(mtp_root, cache_root)
    
    assert cache_root.exists()
    assert len(result.copied) == 1


def test_sync_mtp_to_cache_skips_unchanged(tmp_path):
    """Test that unchanged files are skipped.
    
    Verifies that files with same size and mtime are not copied again.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "cache"
    mtp_root.mkdir()
    cache_root.mkdir()
    
    # Create source file
    src_file = mtp_root / "file.txt"
    src_file.write_text("content")
    
    # Create matching cache file with same content and mtime
    dst_file = cache_root / "file.txt"
    dst_file.write_text("content")
    
    # Copy mtime from source to destination
    src_stat = src_file.stat()
    os.utime(dst_file, (src_stat.st_atime, src_stat.st_mtime))
    
    result = sync_mtp_to_cache(mtp_root, cache_root)
    
    assert len(result.copied) == 0
    assert len(result.skipped) == 1


def test_sync_mtp_to_cache_updates_changed(tmp_path):
    """Test that changed files are updated.
    
    Verifies that files with different size are copied.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "cache"
    mtp_root.mkdir()
    cache_root.mkdir()
    
    # Create source file
    (mtp_root / "file.txt").write_text("new content - longer")
    
    # Create cache file with different content
    (cache_root / "file.txt").write_text("old")
    
    result = sync_mtp_to_cache(mtp_root, cache_root)
    
    assert len(result.copied) == 1
    assert len(result.skipped) == 0
    
    # Verify content was updated
    assert (cache_root / "file.txt").read_text() == "new content - longer"


def test_sync_mtp_to_cache_delete_source(tmp_path):
    """Test deleting source files after sync.
    
    Verifies that source files are deleted when delete_source=True.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "cache"
    mtp_root.mkdir()
    
    src_file = mtp_root / "file.txt"
    src_file.write_text("content")
    
    result = sync_mtp_to_cache(mtp_root, cache_root, delete_source=True)
    
    assert len(result.copied) == 1
    assert len(result.deleted_source) == 1
    
    # Source should be deleted
    assert not src_file.exists()
    
    # Cache should exist
    assert (cache_root / "file.txt").exists()


def test_sync_mtp_to_cache_preserves_structure(tmp_path):
    """Test that directory structure is preserved in cache.
    
    Verifies that subdirectories are replicated.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "cache"
    mtp_root.mkdir()
    
    # Create nested structure
    subdir = mtp_root / "subdir"
    subdir.mkdir()
    
    (mtp_root / "root.txt").write_text("root content")
    (subdir / "nested.txt").write_text("nested content")
    
    result = sync_mtp_to_cache(mtp_root, cache_root)
    
    assert len(result.copied) == 2
    
    # Verify structure is preserved
    assert (cache_root / "root.txt").exists()
    assert (cache_root / "subdir" / "nested.txt").exists()


def test_sync_mtp_to_cache_empty_mtp(tmp_path):
    """Test syncing from an empty MTP directory.
    
    Verifies that an empty result is returned.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "cache"
    mtp_root.mkdir()
    
    result = sync_mtp_to_cache(mtp_root, cache_root)
    
    assert len(result.copied) == 0
    assert len(result.skipped) == 0
    assert len(result.deleted_source) == 0


def test_sync_mtp_to_cache_delete_source_error(tmp_path, monkeypatch):
    """Test handling errors when deleting source files.
    
    Verifies that sync continues even if source deletion fails.
    """
    mtp_root = tmp_path / "mtp"
    cache_root = tmp_path / "cache"
    mtp_root.mkdir()
    
    src_file = mtp_root / "file.txt"
    src_file.write_text("content")
    
    original_unlink = Path.unlink
    
    def fail_unlink(self):
        if "mtp" in str(self):
            raise OSError("Permission denied")
        original_unlink(self)
    
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    
    result = sync_mtp_to_cache(mtp_root, cache_root, delete_source=True)
    
    # File should be copied but not deleted
    assert len(result.copied) == 1
    assert len(result.deleted_source) == 0
    
    # Source should still exist
    assert src_file.exists()
    
    # Cache should exist
    assert (cache_root / "file.txt").exists()


def test_sync_result_dataclass():
    """Test SyncResult dataclass.
    
    Verifies that the dataclass works correctly.
    """
    result = SyncResult(
        copied=[Path("/a"), Path("/b")],
        skipped=[Path("/c")],
        deleted_source=[Path("/a")]
    )
    
    assert len(result.copied) == 2
    assert len(result.skipped) == 1
    assert len(result.deleted_source) == 1
