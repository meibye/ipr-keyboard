"""Renderer and marquee — needs Pillow (dev dependency; skipped without it)."""

import pytest

pytest.importorskip("PIL")

from ipr_keyboard.oled import render as rd  # noqa: E402
from ipr_keyboard.oled import screens as sc  # noqa: E402
from ipr_keyboard.oled.screens import Line, Screen  # noqa: E402


def lit_pixels(img, box=None) -> int:
    region = img.crop(box) if box else img
    return region.convert("L").histogram()[255]


# -- marquee_offset (pure) ---------------------------------------------------


def test_marquee_none_when_text_fits():
    assert rd.marquee_offset(100, 116, 5.0) is None
    assert rd.marquee_offset(116, 116, 5.0) is None


def test_marquee_holds_rolls_holds_and_restarts():
    text, slot = 176, 116  # overflow 60 px -> 5 s at 12 px/s
    assert rd.marquee_offset(text, slot, 0.0) == 0
    assert rd.marquee_offset(text, slot, rd.MARQUEE_HOLD_START - 0.01) == 0
    mid = rd.MARQUEE_HOLD_START + 2.5
    assert rd.marquee_offset(text, slot, mid) == 30
    end = rd.MARQUEE_HOLD_START + 5.0
    assert (
        rd.marquee_offset(text, slot, end + 0.1) == 60
    )  # last character in view, held
    assert rd.marquee_offset(text, slot, end + rd.MARQUEE_HOLD_END - 0.01) == 60
    assert (
        rd.marquee_offset(text, slot, end + rd.MARQUEE_HOLD_END + 0.01) == 0
    )  # restart


def test_marquee_speed_is_slow():
    assert rd.MARQUEE_SPEED <= 16  # about two characters per second, readable


# -- Renderer ---------------------------------------------------------------


@pytest.fixture
def renderer():
    return rd.Renderer()


def test_render_size_mode_and_header_in_yellow_band(renderer):
    img, rolling = renderer.render(
        Screen("READY", "", (Line("Pen ready", sc.ICON_PEN),)), 0.0
    )
    assert img.size == (rd.WIDTH, rd.HEIGHT) and img.mode == "1"
    assert not rolling
    assert lit_pixels(img, (0, 0, 128, 16)) > 0  # header
    assert lit_pixels(img, (0, 16, 128, 18)) == 0  # separator row stays dark
    assert lit_pixels(img, (0, 18, 10, 30)) > 0  # icon column


def test_badge_is_drawn_inverted_top_right(renderer):
    img, _ = renderer.render(Screen("READY", "DEV"), 0.0)
    assert lit_pixels(img, (100, 0, 128, 14)) > 40


def test_progress_bar_and_two_lines(renderer):
    scr = Screen(
        "SENDING…", "", (Line("PC", sc.ICON_ARROW), Line("5 characters")), progress=-1.0
    )
    img, _ = renderer.render(scr, 0.0)
    y0, y1 = rd.BAR_Y
    assert lit_pixels(img, (0, y0, 128, y1 + 1)) > 100
    img2, _ = renderer.render(scr, 0.5)
    assert img2.tobytes() != img.tobytes()  # the sweep moves
    img3, _ = renderer.render(Screen("X", "", (), progress=0.5), 0.0)
    assert (
        0 < lit_pixels(img3, (2, y0 + 2, 64, y1 - 1))
        and lit_pixels(img3, (70, y0 + 2, 120, y1 - 1)) == 0
    )


def test_long_line_rolls_and_short_line_does_not(renderer):
    long_text = "A rather long network name 192.168.100.200"
    scr = Screen(
        "READY", "", (Line(long_text, sc.ICON_NET), Line("Pen ready", sc.ICON_PEN))
    )
    img0, rolling = renderer.render(scr, 10.0)
    assert rolling
    # still held at the start
    img1, _ = renderer.render(scr, 10.0 + rd.MARQUEE_HOLD_START - 0.1)
    assert img1.tobytes() == img0.tobytes()
    # moved after the hold; the short line and the header are untouched
    img2, _ = renderer.render(scr, 10.0 + rd.MARQUEE_HOLD_START + 1.0)
    assert (
        img2.crop((0, 18, 128, 32)).tobytes() != img0.crop((0, 18, 128, 32)).tobytes()
    )
    assert (
        img2.crop((0, 33, 128, 47)).tobytes() == img0.crop((0, 33, 128, 47)).tobytes()
    )
    assert img2.crop((0, 0, 128, 16)).tobytes() == img0.crop((0, 0, 128, 16)).tobytes()
    # nothing is drawn over the icon column while rolling
    assert (
        img2.crop((0, 18, rd.ICON_COL, 32)).tobytes()
        == img0.crop((0, 18, rd.ICON_COL, 32)).tobytes()
    )


def test_reset_restarts_a_rolling_line(renderer):
    scr = Screen(
        "READY", "", (Line("A rather long network name 192.168.100.200", sc.ICON_NET),)
    )
    img0, _ = renderer.render(scr, 0.0)
    renderer.render(scr, 4.0)
    renderer.reset()
    img_after, _ = renderer.render(scr, 4.0)
    assert img_after.tobytes() == img0.tobytes()


def test_every_composed_screen_renders(renderer):
    snaps = [
        sc.Snapshot(),
        sc.Snapshot(
            phase=sc.STATUS,
            ready=True,
            bt_connected=True,
            bt_host="PC",
            pen="ready",
            wifi_connected=True,
            ssid="Net",
            ip="10.0.0.2",
        ),
        sc.Snapshot(
            phase=sc.STATUS, services_ok=False, failed_services=("bt_hid_ble.service",)
        ),
        sc.Snapshot(phase=sc.STATUS, tx_state="sending", tx_chars=12),
        sc.Snapshot(
            phase=sc.STATUS, tx_state="success", tx_recent=True, tx_last_at=0.0
        ),
        sc.Snapshot(phase=sc.STATUS, tx_state="failed", tx_recent=True, tx_reason="x"),
        sc.Snapshot(
            phase=sc.HOTSPOT_ON, hotspot_active=True, hotspot_ssid="ipr-setup-abcd"
        ),
        sc.Snapshot(phase=sc.STATUS, held_secs=4.0, armed="hotspot"),
        sc.Snapshot(phase=sc.SHUTTING_DOWN),
        sc.Snapshot(phase=sc.MODE_CONFIRM, development=True),
    ]
    for snap in snaps:
        img, _ = renderer.render(sc.compose(snap), 0.0)
        assert lit_pixels(img) > 0


def test_four_lines_are_drawn_in_the_smaller_face(renderer):
    scr = Screen(
        "HOLD…",
        "PROD",
        tuple(
            Line(t)
            for t in ("3 s  Hotspot", "6 s  Shutdown", "10 s  Mode", "15 s  Reset")
        ),
    )
    img, rolling = renderer.render(scr, 0.0)
    assert not rolling, "the gesture lines fit at this size"
    for y in rd.LINE_Y_4:
        assert lit_pixels(img, (0, y, 128, y + rd.LINE_H_4)) > 0
    assert lit_pixels(img, (0, rd.HEIGHT - 1, 128, rd.HEIGHT)) == 0  # nothing clipped


def test_bold_line_is_heavier_than_the_plain_one(renderer):
    plain, _ = renderer.render(Screen("HOLD…", "", (Line("6 s  Shutdown"),)), 0.0)
    renderer.reset()
    bold, _ = renderer.render(
        Screen("HOLD…", "", (Line("6 s  Shutdown", bold=True),)), 0.0
    )
    assert lit_pixels(bold, (0, 18, 128, 33)) > lit_pixels(plain, (0, 18, 128, 33))


def test_a_rolling_line_stays_inside_its_own_four_line_slot(renderer):
    long_text = "15 s  Factory reset of every Wi-Fi profile"
    lines = (Line("a"), Line(long_text), Line("c"), Line("d"))
    scr = Screen("HOLD…", "", lines)
    img0, rolling = renderer.render(scr, 0.0)
    assert rolling
    img1, _ = renderer.render(scr, rd.MARQUEE_HOLD_START + 1.0)
    y = rd.LINE_Y_4[2]  # the slot below the rolling line is untouched
    assert (
        img1.crop((0, y, 128, y + rd.LINE_H_4)).tobytes()
        == img0.crop((0, y, 128, y + rd.LINE_H_4)).tobytes()
    )


def test_every_gesture_stage_renders(renderer):
    for armed in (None, "hotspot", "shutdown", "mode", "reset", "cancel"):
        renderer.reset()
        snap = sc.Snapshot(phase=sc.STATUS, held_secs=4.0, armed=armed)
        img, _ = renderer.render(sc.compose(snap), 0.0)
        assert lit_pixels(img) > 0


def test_the_gesture_grid_does_not_change_size_as_the_list_shrinks(renderer):
    """A compact screen keeps the four-line grid, so nothing jumps or rolls."""
    four = sc.compose(sc.Snapshot(phase=sc.STATUS, held_secs=4.0, armed="hotspot"))
    one = sc.compose(sc.Snapshot(phase=sc.STATUS, held_secs=16.0, armed="reset"))
    assert four.compact and one.compact
    img4, rolling4 = renderer.render(four, 0.0)
    renderer.reset()
    img1, rolling1 = renderer.render(one, 0.0)
    assert not rolling4 and not rolling1
    # The last activity sits in the top slot in both, drawn the same way.
    band = (0, rd.LINE_Y_4[0], 128, rd.LINE_Y_4[0] + rd.LINE_H_4)
    assert lit_pixels(img1, band) > 0
    assert lit_pixels(img1, (0, rd.LINE_Y_4[1], 128, 64)) == 0  # nothing below
    assert lit_pixels(img4, (0, rd.LINE_Y_4[3], 128, 64)) > 0  # four slots used
