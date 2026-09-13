"""Main entry point for the ipr-keyboard application.

This module orchestrates the USB monitoring and Bluetooth forwarding functionality,
along with a web server for configuration and log viewing.
"""

from __future__ import annotations

import os
import signal
import ssl as _ssl
import threading
import time
from pathlib import Path

_TLS_CERT = Path("/etc/ipr-ssl/server.crt")
_TLS_KEY = Path("/etc/ipr-ssl/server.key")

from .config.manager import ConfigManager, log_version_info
from .config import manager as config_manager
from .bluetooth.keyboard import BluetoothKeyboard
from .bluetooth import keyboard as bt_keyboard
from .logging.logger import get_logger, set_log_level
from .usb import detector, reader, deleter
from .usb import detector as usb_detector, reader as usb_reader, deleter as usb_deleter
from . import metrics
from .web.server import create_app
from .web import server as web_server
from .gpio_monitor import GpioMonitor, gpio_available

logger = get_logger()

VERSION = "2026-04-12 19:53:57"


def log_version_info():
    config_manager.log_version_info()
    bt_keyboard.log_version_info()
    usb_detector.log_version_info()
    usb_reader.log_version_info()
    usb_deleter.log_version_info()
    web_server.log_version_info()


_WEB_RETRY_COUNT = 5
_WEB_RETRY_DELAY = 3  # seconds between bind retries


def run_web_server():
    """Run the Flask web server for configuration and log viewing.

    Uses HTTPS when /etc/ipr-ssl/server.crt and server.key are present
    (installed by gen_ipr_ssl_cert.sh).  Falls back to plain HTTP so
    development machines without certs continue to work.

    Retries up to _WEB_RETRY_COUNT times on OSError (e.g. port already in use)
    then terminates the whole process so systemd can restart the service.
    """
    cfg = ConfigManager.instance().get()
    app = create_app()
    try:
        tls_ready = _TLS_CERT.exists() and _TLS_KEY.exists()
    except OSError:
        # /etc/ipr-ssl/ directory not yet accessible to this user
        tls_ready = False

    ssl_ctx = None
    if tls_ready:
        ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(str(_TLS_CERT), str(_TLS_KEY))
    else:
        logger.warning(
            "TLS cert not accessible at %s — falling back to HTTP on port %d",
            _TLS_CERT,
            cfg.LogPort,
        )

    for attempt in range(1, _WEB_RETRY_COUNT + 1):
        try:
            logger.info(
                "Starting %s server on port %d (attempt %d/%d)",
                "HTTPS" if ssl_ctx else "HTTP",
                cfg.LogPort,
                attempt,
                _WEB_RETRY_COUNT,
            )
            app.run(
                host="0.0.0.0",
                port=cfg.LogPort,
                debug=False,
                use_reloader=False,
                ssl_context=ssl_ctx if ssl_ctx else None,
            )
            return  # clean exit
        except OSError as exc:
            if attempt < _WEB_RETRY_COUNT:
                logger.warning(
                    "Web server failed to bind port %d (attempt %d/%d): %s — retrying in %ds",
                    cfg.LogPort,
                    attempt,
                    _WEB_RETRY_COUNT,
                    exc,
                    _WEB_RETRY_DELAY,
                )
                time.sleep(_WEB_RETRY_DELAY)
            else:
                logger.critical(
                    "Web server could not bind port %d after %d attempts: %s — terminating",
                    cfg.LogPort,
                    _WEB_RETRY_COUNT,
                    exc,
                )
                os.kill(os.getpid(), signal.SIGTERM)


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
        # Re-apply every iteration so the dashboard toggle takes effect without
        # a restart.  One attribute assignment; not worth guarding.
        metrics.set_enabled(cfg.MetricsEnabled)
        folders = [Path(p) for p in (cfg.IrisPenFolders or [])]

        poll = cfg.PollIntervalSeconds
        if not folders:
            logger.debug("No folders configured; sleeping")
            time.sleep(poll)
            continue

        found_file = None
        found_mtime = 0.0
        scan_started = time.time()
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
                found_mtime = mtime
                break

        if found_file is None:
            metrics.record_poll_scan(time.time() - scan_started)
            time.sleep(poll)
            continue

        detected_at = time.time()
        logger.info("Detected new file: %s", found_file)

        text = reader.read_file(found_file, cfg.MaxFileSize)
        read_done_at = time.time()
        send_done_at = None
        if text is None:
            logger.warning("File %s is too large or unreadable", found_file)
        else:
            logger.info("Read %d bytes from %s", len(text), found_file)
            if kb.is_available():
                if kb.send_text(text):
                    send_done_at = time.time()
            else:
                logger.info("BT not available; text would have been: %r", text[:100])

        # One call, one lock, no-op when MetricsEnabled is false.
        metrics.record_file_pipeline(
            found_mtime,
            detected_at,
            read_done_at,
            send_done_at,
            len(text) if text else 0,
        )

        if cfg.DeleteFiles:
            ok = deleter.delete_file(found_file)
            if ok:
                logger.info("Deleted file after processing: %s", found_file)
            else:
                logger.error("Failed to delete file: %s", found_file)


_READY_WAIT_SECS = 180


def _signal_ready_when_web_up(gpio_monitor: GpioMonitor, port: int) -> None:
    """End the LED boot phase once the local dashboard answers /health.

    Polls http(s)://127.0.0.1:<port>/health for up to _READY_WAIT_SECS.  The
    LED keeps blinking white if the web server never comes up, which is the
    honest signal for "still starting / startup problem".
    """
    import urllib.request

    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    deadline = time.monotonic() + _READY_WAIT_SECS
    while time.monotonic() < deadline:
        for scheme in ("https", "http"):
            try:
                with urllib.request.urlopen(
                    f"{scheme}://127.0.0.1:{port}/health", timeout=3, context=ctx
                ) as resp:
                    if resp.status == 200:
                        logger.info(
                            "Dashboard answers on port %d — LED leaves boot phase", port
                        )
                        gpio_monitor.set_ready()
                        return
            except Exception:
                pass
        time.sleep(2)
    logger.warning(
        "Dashboard did not answer within %d s — LED stays in boot phase",
        _READY_WAIT_SECS,
    )


def main():
    """Main entry point for the ipr-keyboard application.

    Initializes the configuration, starts the web server, USB monitoring,
    and GPIO monitor threads, then keeps the main thread alive.
    """
    log_version_info()
    cfg = ConfigManager.instance().get()
    set_log_level(cfg.LogLevel)
    logger.info("Starting ipr_keyboard with config: %s", cfg.to_dict())

    # GPIO monitor — reed switch trigger and RGB LED status indicator.
    # Started first so the white boot blink handed over from
    # ipr-led-boot.service continues without a gap; set_ready() ends it once
    # the dashboard answers.  Starts only when GpioEnabled is True and an
    # RPi.GPIO-compatible module is importable.
    gpio_monitor: GpioMonitor | None = None
    if cfg.GpioEnabled:
        gpio_monitor = GpioMonitor(
            reed_pin=cfg.GpioReedPin,
            led_r_pin=cfg.GpioLedRPin,
            led_g_pin=cfg.GpioLedGPin,
            led_b_pin=cfg.GpioLedBPin,
            led_idle_timeout=cfg.GpioLedIdleSeconds,
        )
        gpio_monitor.start()

    t_web = threading.Thread(target=run_web_server, daemon=True)
    t_web.start()

    # Main loop thread (USB + BT)
    t_main = threading.Thread(target=run_usb_bt_loop, daemon=True)
    t_main.start()

    if gpio_monitor is not None and gpio_monitor.active:
        threading.Thread(
            target=_signal_ready_when_web_up,
            args=(gpio_monitor, cfg.LogPort),
            daemon=True,
            name="gpio-ready-wait",
        ).start()

    # systemd stops us with SIGTERM (service restart, or a shutdown started by
    # the magnet).  Route it through the same path as Ctrl-C so the GPIO
    # monitor can leave the LED in the right state (off, or cyan during a
    # shutdown) instead of the process just vanishing.
    def _on_sigterm(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _on_sigterm)

    # Keep the main thread alive
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Shutting down ipr_keyboard")
        if gpio_monitor:
            gpio_monitor.stop()


if __name__ == "__main__":
    main()
