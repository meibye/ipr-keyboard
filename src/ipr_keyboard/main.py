"""Main entry point for the ipr-keyboard application.

This module orchestrates the USB monitoring and Bluetooth forwarding functionality,
along with a web server for configuration and log viewing.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from .config.manager import ConfigManager, log_version_info
from .config import manager as config_manager
from .bluetooth.keyboard import BluetoothKeyboard
from .bluetooth import keyboard as bt_keyboard
from .logging.logger import get_logger, set_log_level
from .usb import detector, reader, deleter
from .usb import detector as usb_detector, reader as usb_reader, deleter as usb_deleter
from .web.server import create_app
from .web import server as web_server

logger = get_logger()

VERSION = '2026-04-12 19:53:57'

def log_version_info():
    config_manager.log_version_info()
    bt_keyboard.log_version_info()
    usb_detector.log_version_info()
    usb_reader.log_version_info()
    usb_deleter.log_version_info()
    web_server.log_version_info()

def run_web_server():
    """Run the Flask web server for configuration and log viewing.
    
    Starts the web server on the port specified in the configuration,
    binding to all interfaces (0.0.0.0) to allow remote access.
    """
    from .config.manager import ConfigManager

    cfg = ConfigManager.instance().get()
    app = create_app()
    logger.info("Starting web server on port %d", cfg.LogPort)
    # use 0.0.0.0 so you can reach it from your PC
    app.run(host="0.0.0.0", port=cfg.LogPort, debug=False, use_reloader=False)


def run_usb_bt_loop():
    """Main USB monitoring and Bluetooth forwarding loop.

    Continuously monitors all configured IrisPenFolders for new text files,
    reads their content, sends it via Bluetooth keyboard emulation, and
    optionally deletes the processed files.

    This function runs indefinitely and should be executed in a separate thread.
    """
    cfg_mgr = ConfigManager.instance()
    kb = BluetoothKeyboard()

    if not kb.is_available():
        logger.warning(
            "Bluetooth helper not available; will still monitor files but not send text"
        )

    # Per-folder last-seen mtime so each folder is tracked independently.
    last_mtime: dict = {}

    while True:
        cfg = cfg_mgr.get()
        folders = [Path(p) for p in (cfg.IrisPenFolders or [])]

        poll = cfg.PollIntervalSeconds
        if not folders:
            logger.debug("No folders configured; sleeping")
            time.sleep(poll)
            continue

        found_file = None
        for folder in folders:
            if not folder.exists():
                logger.debug("Folder does not exist yet: %s", folder)
                continue

            folder_key = str(folder)
            files = detector.list_files(folder)
            if not files:
                continue

            newest = files[-1]
            try:
                mtime = newest.stat().st_mtime
            except OSError:
                continue

            if mtime > last_mtime.get(folder_key, 0.0):
                last_mtime[folder_key] = mtime
                found_file = newest
                break

        if found_file is None:
            time.sleep(poll)
            continue

        logger.info("Detected new file: %s", found_file)

        text = reader.read_file(found_file, cfg.MaxFileSize)
        if text is None:
            logger.warning("File %s is too large or unreadable", found_file)
        else:
            logger.info("Read %d bytes from %s", len(text), found_file)
            if kb.is_available():
                kb.send_text(text)
            else:
                logger.info("BT not available; text would have been: %r", text[:100])

        if cfg.DeleteFiles:
            ok = deleter.delete_file(found_file)
            if ok:
                logger.info("Deleted file after processing: %s", found_file)
            else:
                logger.error("Failed to delete file: %s", found_file)


def main():
    """Main entry point for the ipr-keyboard application.

    Initializes the configuration, starts the web server and USB monitoring
    threads, and keeps the application running until interrupted with Ctrl+C.
    """
    log_version_info()
    cfg = ConfigManager.instance().get()
    set_log_level(cfg.LogLevel)
    logger.info("Starting ipr_keyboard with config: %s", cfg.to_dict())

    t_web = threading.Thread(target=run_web_server, daemon=True)
    t_web.start()

    # Main loop thread (USB + BT)
    t_main = threading.Thread(target=run_usb_bt_loop, daemon=True)
    t_main.start()

    # Keep the main thread alive
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Shutting down ipr_keyboard")


if __name__ == "__main__":
    main()
