from __future__ import annotations

import threading
import time
from pathlib import Path

from .config.manager import ConfigManager
from .bluetooth.keyboard import BluetoothKeyboard
from .logging.logger import get_logger
from .usb import detector, reader, deleter
from .web.server import create_app

logger = get_logger()


def run_web_server():
    from .config.manager import ConfigManager

    cfg = ConfigManager.instance().get()
    app = create_app()
    logger.info("Starting web server on port %d", cfg.LogPort)
    # use 0.0.0.0 so you can reach it from your PC
    app.run(host="0.0.0.0", port=cfg.LogPort, debug=False, use_reloader=False)


def run_usb_bt_loop():
    cfg_mgr = ConfigManager.instance()
    kb = BluetoothKeyboard()

    if not kb.is_available():
        logger.warning(
            "Bluetooth helper not available; will still monitor files but not send text"
        )

    last_mtime = 0.0

    while True:
        cfg = cfg_mgr.get()
        folder = Path(cfg.IrisPenFolder)

        if not folder.exists():
            logger.debug("IrisPenFolder does not exist yet: %s", folder)
            time.sleep(1.0)
            continue

        logger.debug("Waiting for new file in %s", folder)
        new_file = detector.wait_for_new_file(folder, last_mtime, interval=1.0)
        if new_file is None:
            time.sleep(1.0)
            continue

        last_mtime = new_file.stat().st_mtime
        logger.info("Detected new file: %s", new_file)

        text = reader.read_file(new_file, cfg.MaxFileSize)
        if text is None:
            logger.warning("File %s is too large or unreadable", new_file)
        else:
            logger.info("Read %d bytes from %s", len(text), new_file)
            if kb.is_available():
                kb.send_text(text)
            else:
                logger.info("BT not available; text would have been: %r", text[:100])

        if cfg.DeleteFiles:
            ok = deleter.delete_file(new_file)
            if ok:
                logger.info("Deleted file after processing: %s", new_file)
            else:
                logger.error("Failed to delete file: %s", new_file)


def main():
    cfg = ConfigManager.instance().get()
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
