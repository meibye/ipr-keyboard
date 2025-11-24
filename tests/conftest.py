"""Shared test fixtures and configuration for pytest.

This module provides common fixtures used across all test modules.
"""
import pytest
from pathlib import Path
from ipr_keyboard.utils.helpers import save_json


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    """Create a temporary config file and patch ConfigManager to use it.
    
    This fixture creates a fresh config file in a temporary directory and
    resets the ConfigManager singleton to ensure test isolation.
    
    Args:
        tmp_path: pytest's temporary directory fixture
        monkeypatch: pytest's monkeypatch fixture
        
    Yields:
        Path to the temporary config file
    """
    cfg_file = tmp_path / "config.json"
    save_json(cfg_file, {
        "IrisPenFolder": str(tmp_path / "irispen"),
        "DeleteFiles": True,
        "Logging": True,
        "MaxFileSize": 1048576,
        "LogPort": 8080,
        "KeyboardBackend": "uinput"
    })
    
    # Patch config_path to return our temp config
    monkeypatch.setattr(
        "ipr_keyboard.config.manager.config_path",
        lambda: cfg_file,
    )
    
    # Reset the ConfigManager singleton
    from ipr_keyboard.config.manager import ConfigManager
    ConfigManager._instance = None
    
    yield cfg_file


@pytest.fixture
def reset_config_manager():
    """Reset the ConfigManager singleton after each test.
    
    This fixture ensures test isolation by resetting the singleton.
    """
    yield
    from ipr_keyboard.config.manager import ConfigManager
    ConfigManager._instance = None


@pytest.fixture
def temp_log_dir(tmp_path, monkeypatch):
    """Create a temporary log directory and patch the logger.
    
    This fixture redirects log output to a temporary directory and
    resets the logger singleton for test isolation.
    
    Args:
        tmp_path: pytest's temporary directory fixture
        monkeypatch: pytest's monkeypatch fixture
        
    Yields:
        Path to the temporary log file
    """
    log_file = tmp_path / "logs" / "test.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Reset the logger singleton first
    import ipr_keyboard.logging.logger as logger_module
    logger_module._LOGGER = None
    
    # Patch the log file path
    monkeypatch.setattr(
        "ipr_keyboard.logging.logger._LOG_FILE",
        log_file,
    )
    
    yield log_file
    
    # Clean up the logger singleton after the test
    logger_module._LOGGER = None


@pytest.fixture
def mock_bt_helper(monkeypatch):
    """Mock the Bluetooth helper subprocess.
    
    This fixture provides a mock for subprocess.run that tracks calls
    to the Bluetooth helper script.
    
    Args:
        monkeypatch: pytest's monkeypatch fixture
        
    Yields:
        Dictionary to track mock calls and configure behavior
    """
    import subprocess
    
    call_tracker = {
        "calls": [],
        "should_fail": False,
        "fail_with_not_found": False,
        "return_code": 0
    }
    
    def fake_run(args, **kwargs):
        call_tracker["calls"].append({"args": args, "kwargs": kwargs})
        
        if call_tracker["fail_with_not_found"]:
            raise FileNotFoundError(f"Helper not found: {args[0]}")
        
        if call_tracker["should_fail"]:
            raise subprocess.CalledProcessError(
                returncode=call_tracker.get("return_code", 1),
                cmd=args
            )
        
        return subprocess.CompletedProcess(args=args, returncode=0)
    
    monkeypatch.setattr("subprocess.run", fake_run)
    
    yield call_tracker


@pytest.fixture
def flask_client(temp_config):
    """Create a Flask test client with temporary configuration.
    
    This fixture initializes the Flask app with a temporary config file
    and returns a test client for making requests.
    
    Args:
        temp_config: The temp_config fixture
        
    Returns:
        Flask test client
    """
    from ipr_keyboard.config.manager import ConfigManager
    from ipr_keyboard.web.server import create_app
    
    # Initialize the singleton with our temp config
    ConfigManager.instance()
    
    app = create_app()
    app.config["TESTING"] = True
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def usb_folder(tmp_path):
    """Create a temporary USB folder with test files.
    
    This fixture creates a temporary directory simulating the IrisPen
    USB mount point with some test files.
    
    Args:
        tmp_path: pytest's temporary directory fixture
        
    Yields:
        Path to the temporary USB folder
    """
    usb_dir = tmp_path / "irispen"
    usb_dir.mkdir(parents=True, exist_ok=True)
    
    yield usb_dir


@pytest.fixture
def sample_text_files(usb_folder):
    """Create sample text files in the USB folder.
    
    This fixture creates multiple test files with different timestamps.
    
    Args:
        usb_folder: The usb_folder fixture
        
    Returns:
        List of created file paths
    """
    import time
    
    files = []
    
    # Create files with slight delay to ensure different mtimes
    for i, content in enumerate(["First file", "Second file", "Third file"]):
        f = usb_folder / f"file{i+1}.txt"
        f.write_text(content, encoding="utf-8")
        files.append(f)
        time.sleep(0.01)  # Small delay for mtime ordering
    
    return files
