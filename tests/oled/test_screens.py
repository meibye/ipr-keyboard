"""Screen composition — pure, no Pillow needed."""

from ipr_keyboard.oled import screens as sc
from ipr_keyboard.oled.screens import Line, Snapshot, compose


def ready_snapshot(**kw) -> Snapshot:
    base = dict(
        phase=sc.STATUS,
        ready=True,
        bt_connected=True,
        bt_host="Laptop-MSE",
        pen="ready",
        wifi_connected=True,
        ssid="HomeNet",
        ip="192.168.1.23",
    )
    base.update(kw)
    return Snapshot(**base)


def test_boot_checklist_reflects_ready_and_services():
    s = compose(
        Snapshot(
            phase=sc.BOOT, failed_services=("bt_hid_ble.service",), services_ok=False
        )
    )
    assert s.header == "STARTING…"
    assert [ln.text for ln in s.lines] == ["Services", "Bluetooth", "Dashboard"]
    assert [ln.icon for ln in s.lines] == [sc.ICON_WAIT, sc.ICON_WAIT, sc.ICON_WAIT]
    s = compose(Snapshot(phase=sc.BOOT, ready=True))
    assert [ln.icon for ln in s.lines] == [sc.ICON_OK, sc.ICON_OK, sc.ICON_OK]


def test_ready_screen_shows_host_pen_and_network():
    s = compose(ready_snapshot())
    assert s.header == "READY"
    assert s.badge == ""
    assert s.lines == (
        Line("Laptop-MSE", sc.ICON_BT),
        Line("Pen ready", sc.ICON_PEN),
        Line("HomeNet  192.168.1.23", sc.ICON_NET),
    )


def test_dev_badge():
    assert compose(ready_snapshot(development=True)).badge == "DEV"


def test_problem_header_when_service_down_pen_port_off_or_no_wifi():
    s = compose(
        ready_snapshot(services_ok=False, failed_services=("bt_hid_ble.service",))
    )
    assert s.header == "PROBLEM"
    assert s.lines[0] == Line("Service down: bt_hid_ble", sc.ICON_ERR)

    s = compose(ready_snapshot(pen="disabled"))
    assert s.header == "PROBLEM"
    assert s.lines[1].icon == sc.ICON_ERR and "reboot" in s.lines[1].text

    s = compose(ready_snapshot(wifi_connected=False, ssid="", ip=""))
    assert s.header == "PROBLEM"
    assert s.lines[2] == Line("No Wi-Fi — hold 3 s", sc.ICON_ERR)


def test_waiting_for_pc_and_plug_in_pen():
    s = compose(ready_snapshot(bt_connected=False, bt_host="", pen="missing"))
    assert s.header == "READY"
    assert s.lines[0].text == "Waiting for PC…"
    assert s.lines[1].text == "Plug in the pen"


def test_sending_has_indeterminate_bar_and_character_count():
    s = compose(ready_snapshot(tx_state="sending", tx_chars=142))
    assert s.header == "SENDING…"
    assert s.progress is not None and s.progress < 0
    assert s.lines[0] == Line("Laptop-MSE", sc.ICON_ARROW)
    assert s.lines[1].text == "142 characters"


def test_sent_only_while_recent_then_back_to_status():
    snap = ready_snapshot(
        tx_state="success", tx_chars=1, tx_total=13, tx_last_at=0.0, tx_recent=True
    )
    s = compose(snap)
    assert s.header == "SENT ✓"
    assert s.lines[0].text == "1 character"
    assert s.lines[2].text == "Total 13"
    # transmission keeps state == "success" for ever; the screen must not.
    assert (
        compose(ready_snapshot(tx_state="success", tx_recent=False)).header == "READY"
    )


def test_failed_send_keeps_text_on_pen():
    s = compose(
        ready_snapshot(tx_state="failed", tx_reason="Helper timed out", tx_recent=True)
    )
    assert s.header == "SEND FAILED"
    assert s.lines == (Line("Helper timed out", sc.ICON_ERR), Line("Text kept on pen"))


def test_hotspot_screen_shows_ssid_and_url():
    s = compose(
        ready_snapshot(
            phase=sc.HOTSPOT_ON, hotspot_active=True, hotspot_ssid="ipr-setup-a1b2"
        )
    )
    assert s.header == "SETUP MODE"
    assert s.lines[0].text == "Wi-Fi  ipr-setup-a1b2"
    assert sc.HOTSPOT_URL in s.lines[1].text
    assert s.lines[2].text == "Hold 3 s to stop"


def test_hotspot_busy_and_failed():
    assert (
        compose(ready_snapshot(phase=sc.HOTSPOT_BUSY)).lines[0].text
        == "Starting the hotspot…"
    )
    assert (
        compose(ready_snapshot(phase=sc.HOTSPOT_BUSY, hotspot_active=True))
        .lines[0]
        .text
        == "Stopping the hotspot…"
    )
    assert compose(ready_snapshot(phase=sc.FAIL_FLASH)).header == "HOTSPOT FAILED"


def test_gesture_screen_marks_the_armed_action():
    s = compose(ready_snapshot(held_secs=1.0, armed=None))
    assert s.header == "HOLD…"
    assert all(ln.icon == "" for ln in s.lines)

    s = compose(ready_snapshot(held_secs=4.0, armed="hotspot"))
    assert s.header == "RELEASE → HOTSPOT"
    assert s.lines[0].icon == sc.ICON_MARK and s.lines[1].icon == ""

    s = compose(ready_snapshot(held_secs=4.0, armed="hotspot", hotspot_active=True))
    assert s.header == "RELEASE → HOTSPOT OFF"

    s = compose(ready_snapshot(held_secs=7.0, armed="shutdown"))
    assert s.header == "RELEASE → SHUTDOWN" and s.lines[1].icon == sc.ICON_MARK

    for armed in ("mode", "reset"):
        s = compose(ready_snapshot(held_secs=12.0, armed=armed))
        assert s.lines[2].icon == sc.ICON_MARK

    assert compose(ready_snapshot(held_secs=21.0, armed="cancel")).header == "CANCELLED"


def test_gesture_screen_overrides_sending_but_not_boot():
    s = compose(ready_snapshot(held_secs=1.0, tx_state="sending"))
    assert s.header == "HOLD…"
    s = compose(Snapshot(phase=sc.BOOT, held_secs=5.0, armed="hotspot"))
    assert s.header == "STARTING…"


def test_shutdown_reset_and_mode_confirm():
    assert compose(ready_snapshot(phase=sc.SHUTTING_DOWN)).header == "SHUTTING DOWN"
    assert compose(ready_snapshot(phase=sc.RESETTING)).header == "RESETTING…"
    assert (
        compose(ready_snapshot(phase=sc.MODE_CONFIRM, development=True)).header
        == "MODE: DEVELOPMENT"
    )
    assert compose(ready_snapshot(phase=sc.MODE_CONFIRM)).header == "MODE: PRODUCTION"


def test_wants_display_follows_phase_gesture_and_sending():
    assert sc.wants_display(Snapshot(phase=sc.BOOT))
    assert sc.wants_display(ready_snapshot(phase=sc.STATUS))
    assert not sc.wants_display(ready_snapshot(phase=sc.IDLE))
    assert sc.wants_display(ready_snapshot(phase=sc.IDLE, held_secs=0.5))
    assert sc.wants_display(ready_snapshot(phase=sc.IDLE, tx_state="sending"))
    assert sc.wants_display(ready_snapshot(phase=sc.HOTSPOT_ON))


def test_status_key_changes_on_bt_pen_wifi_services_hotspot_mode():
    base = sc.status_key(ready_snapshot())
    assert sc.status_key(ready_snapshot()) == base
    for change in (
        dict(bt_connected=False),
        dict(pen="missing"),
        dict(wifi_connected=False),
        dict(services_ok=False),
        dict(hotspot_active=True),
        dict(development=True),
    ):
        assert sc.status_key(ready_snapshot(**change)) != base
    # a new IP or a send does not wake the panel
    assert sc.status_key(ready_snapshot(ip="10.0.0.9", tx_state="sending")) == base
