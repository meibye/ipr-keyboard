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
from . import keydelay, metrics
from .web.server import create_app
from .web import server as web_server
from .delivery import STATE_FILE, DeliveryLog
from .gpio_monitor import GpioMonitor, gpio_available
from .menu import MenuLogic
from .oled.manager import OledManager
from .recovery import RecoveryInfo

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


_PEN_STATE_FILE = STATE_FILE


def _pen_state_path() -> Path:
    from .utils.helpers import project_root
    return project_root() / _PEN_STATE_FILE


def _next_new_scan(delivered: DeliveryLog, folder: Path) -> Path | None:
    """The oldest scan in `folder` not yet typed, or None.

    First sight of a folder baselines it: everything already there counts as
    done, so an upgrade or a re-plug types nothing old.  An EMPTY folder is
    baselined too.  It used to be skipped until something appeared in it, and
    then that first scan was the baseline -- on a fresh install, with the
    pen's folder emptied by earlier deliveries, the first scan was never
    typed.
    """
    files = detector.list_files(folder)  # oldest first
    if not delivered.knows(folder):
        delivered.baseline(folder, files)
        return None
    return delivered.next_undelivered(folder, files)


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

    # What has already been typed, recorded by file identity rather than by
    # timestamp.  An MTP listing is not immediately consistent, so a scan can
    # appear after later ones have been delivered, and a high-water mark then
    # skipped it for good -- see delivery.py.  Persisted, so a restart or a
    # re-plug of the pen never types an old scan again.
    delivered = DeliveryLog(_pen_state_path())

    while True:
        cfg = cfg_mgr.get()
        # Re-apply every iteration so the dashboard toggle takes effect without
        # a restart.  One attribute assignment; not worth guarding.
        metrics.set_enabled(cfg.MetricsEnabled)
        # Same for the typing speed: it reaches the BLE daemon through a file
        # it re-reads per send, so a change applies to the next scan without
        # restarting the daemon and dropping the PC's connection.  apply()
        # writes only when the value actually changed, and respects a hold:
        # the Debug trial sets a speed per step, and this loop re-applying the
        # configured one a second later meant the whole ladder ran at the same
        # speed -- which is what it measured.
        keydelay.apply(cfg.TypingDelayMs, respect_hold=True)
        # Wildcards resolve the pen's localized storage folder (see detector.expand_folders).
        folders = detector.expand_folders(cfg.IrisPenFolders)

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

            candidate = _next_new_scan(delivered, folder)
            if candidate is not None:
                try:
                    found_mtime = candidate.stat().st_mtime
                except OSError:
                    continue
                # Marked before the send, not after: a scan that fails to type
                # must not be retried on every poll for ever.  It stays on the
                # pen for the user to see, exactly as before.
                delivered.mark(folder, candidate)
                found_file = candidate
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

        sent = send_done_at is not None
        if cfg.DeleteFiles and (sent or text is None):
            # Delete after a successful send (or an unreadable/oversized file
            # that will never send).  A scan whose send FAILED stays on the pen:
            # deleting it would lose the text; it is not retried automatically
            # (the folder watcher tracks the newest mtime), but it is still
            # there for the user to see and re-scan or copy.
            ok = deleter.delete_file(found_file)
            if ok:
                logger.info("Deleted file after processing: %s", found_file)
            else:
                logger.error("Failed to delete file: %s", found_file)
        elif cfg.DeleteFiles and not sent:
            logger.warning("Send failed — keeping %s on the pen", found_file)


_READY_WAIT_SECS = 180


def _signal_ready_when_web_up(targets: list, port: int) -> None:
    """End the boot phase (LED blink, OLED "Starting…") once /health answers.

    Polls http(s)://127.0.0.1:<port>/health for up to _READY_WAIT_SECS and
    calls ``set_ready()`` on every target.  The LED keeps blinking white if
    the web server never comes up, which is the honest signal for "still
    starting / startup problem".
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
                            "Dashboard answers on port %d — leaving boot phase", port
                        )
                        for target in targets:
                            target.set_ready()
                        return
            except Exception:
                pass
        time.sleep(2)
    logger.warning(
        "Dashboard did not answer within %d s — LED stays in boot phase",
        _READY_WAIT_SECS,
    )


def _attach_menu(gpio_monitor, oled, cfg) -> None:
    """Give the LED logic a menu, and the callbacks its actions need."""
    recovery = RecoveryInfo(limit=cfg.RecoveryRevealLimit)
    logic = gpio_monitor._logic
    probe = logic._probe

    def set_timeout(minutes: int) -> None:
        oled.set_display_timeout(minutes)
        try:
            ConfigManager.instance().update(OledDisplayTimeoutMinutes=minutes)
        except Exception as exc:  # a read-only config must not break the menu
            logger.warning("Could not persist the display timeout: %s", exc)

    def set_menu_timeout(seconds: int) -> None:
        try:
            ConfigManager.instance().update(MenuTimeoutSeconds=seconds)
        except Exception as exc:
            logger.warning("Could not persist the menu timeout: %s", exc)

    def timeout_now() -> int:
        return ConfigManager.instance().get().OledDisplayTimeoutMinutes

    def menu_timeout_now() -> int:
        return ConfigManager.instance().get().MenuTimeoutSeconds

    logic._menu = MenuLogic(
        hotspot_active=lambda: probe.hotspot_active,
        development=lambda: probe.development,
        display_timeout_min=timeout_now,
        reveals_left=recovery.reveals_left,
        menu_timeout_secs=menu_timeout_now,
    )
    logic._on_display_timeout = set_timeout
    logic._on_menu_timeout = set_menu_timeout
    logic._recovery_info = recovery.lines
    logger.info("Magnet menu enabled (display present)")


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

    # OLED status display.  Follows the LED phase (magnet tap, hotspot,
    # shutdown…) through gpio_monitor.snapshot(); without GPIO it keeps a
    # minimal boot → status → idle cycle of its own.  Inert with a warning
    # when Pillow, /dev/i2c-N or the panel itself is missing.
    oled = OledManager(
        enabled=cfg.OledEnabled,
        bus=cfg.OledI2cBus,
        address=cfg.OledI2cAddress,
        contrast=cfg.OledContrast,
        rotate=cfg.OledRotate,
        idle_seconds=cfg.GpioLedIdleSeconds,
        display_timeout_minutes=cfg.OledDisplayTimeoutMinutes,
        send_hold_seconds=cfg.OledSendHoldSeconds,
        marquee_fps=cfg.OledMarqueeFps,
        source=gpio_monitor if (gpio_monitor is not None and gpio_monitor.active) else None,
    )
    oled.start()

    # The magnet menu replaces the timed gesture ladder, but only where it can
    # be read: with no working panel the LED keeps the ladder exactly as it
    # was (docs/architecture/magnet-menu-design.md section 3.2).
    if gpio_monitor is not None and gpio_monitor.active and oled.active:
        _attach_menu(gpio_monitor, oled, cfg)

    t_web = threading.Thread(target=run_web_server, daemon=True)
    t_web.start()

    # Main loop thread (USB + BT)
    t_main = threading.Thread(target=run_usb_bt_loop, daemon=True)
    t_main.start()

    ready_targets = [m for m in (gpio_monitor, oled) if m is not None and m.active]
    if ready_targets:
        threading.Thread(
            target=_signal_ready_when_web_up,
            args=(ready_targets, cfg.LogPort),
            daemon=True,
            name="gpio-ready-wait",
        ).start()

    # systemd stops us with SIGTERM (service restart, or a shutdown started by
    # the magnet).  Route it through the same path as Ctrl-C so the GPIO
    # monitor can leave the LED in the right state (off, or white during a
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
        oled.stop()  # before the LED: it reads the LED phase (SHUTTING_DOWN keeps the screen)
        if gpio_monitor:
            gpio_monitor.stop()


if __name__ == "__main__":
    main()
