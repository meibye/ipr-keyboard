"""Screen -> 128x64 1-bit image, with Pillow.

Layout (rows): 0-15 header (the panel's yellow band), 16 blank, 18/33/48
three body lines, or a progress bar at 19-27 followed by two lines.  Body
lines have a fixed 10 px icon column so text never shifts when an icon
changes.

Long lines roll: a line wider than its slot is not cut but scrolled —
:func:`marquee_offset` holds it 1.5 s, moves it left at 12 px/s, holds 1 s
once the last character is in view, then starts over.  ``render()`` reports
whether anything is rolling so the manager can redraw at the marquee rate
only while it matters.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .screens import (
    ICON_ARROW,
    ICON_BT,
    ICON_ERR,
    ICON_MARK,
    ICON_NET,
    ICON_OK,
    ICON_PEN,
    ICON_WAIT,
    Screen,
)

WIDTH = 128
HEIGHT = 64
HEADER_H = 16
ICON_COL = 12  # text x when the screen uses icons
PLAIN_COL = 2
LINE_Y = (18, 33, 48)
BAR_Y = (19, 27)
LINE_Y_WITH_BAR = (31, 46)

MARQUEE_HOLD_START = 1.5  # s before a long line starts moving
MARQUEE_SPEED = 12.0  # px/s — about two characters per second
MARQUEE_HOLD_END = 1.0  # s with the last character in view, then restart

_FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
_HEADER_SIZE = 12
_BODY_SIZE = 11
_BADGE_SIZE = 8


def marquee_offset(text_px: int, slot_px: int, elapsed: float) -> int | None:
    """Pixels to shift a line left at ``elapsed`` seconds since first shown.

    None when the text fits (no rolling); otherwise 0..overflow following
    hold - roll - hold - restart.
    """
    overflow = text_px - slot_px
    if overflow <= 0:
        return None
    roll_secs = overflow / MARQUEE_SPEED
    cycle = MARQUEE_HOLD_START + roll_secs + MARQUEE_HOLD_END
    t = elapsed % cycle
    if t < MARQUEE_HOLD_START:
        return 0
    if t < MARQUEE_HOLD_START + roll_secs:
        return int((t - MARQUEE_HOLD_START) * MARQUEE_SPEED)
    return overflow


def _load_font(name: str, size: int):
    try:
        return ImageFont.truetype(_FONT_DIR + name, size)
    except OSError:
        pass
    try:
        return ImageFont.truetype(name, size)  # font on the system path (dev host)
    except OSError:
        pass
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:  # pragma: no cover - old Pillow
        return ImageFont.load_default()


class Renderer:
    """Stateful only for the marquee: remembers when each long line appeared."""

    def __init__(self, clock=None) -> None:
        self._header_font = _load_font("DejaVuSans-Bold.ttf", _HEADER_SIZE)
        self._body_font = _load_font("DejaVuSans.ttf", _BODY_SIZE)
        self._badge_font = _load_font("DejaVuSans-Bold.ttf", _BADGE_SIZE)
        self._seen: dict[tuple[str, str], float] = {}

    def reset(self) -> None:
        """Forget marquee positions (the panel went to sleep)."""
        self._seen.clear()

    def render(self, screen: Screen, now: float) -> tuple[Image.Image, bool]:
        """Draw ``screen``; returns (image, at least one line is rolling)."""
        img = Image.new("1", (WIDTH, HEIGHT), 0)
        draw = ImageDraw.Draw(img)
        rolling = False
        live: set[tuple[str, str]] = set()

        # Header -------------------------------------------------------
        slot_right = WIDTH - 2
        if screen.badge:
            bw = int(self._badge_font.getlength(screen.badge)) + 9
            draw.rectangle((WIDTH - bw, 1, WIDTH - 1, 12), fill=1)
            draw.text((WIDTH - bw + 4, 2), screen.badge, font=self._badge_font, fill=0)
            slot_right = WIDTH - bw - 4
        rolling |= self._text_in_slot(
            img,
            ("header", screen.header),
            screen.header,
            self._header_font,
            2,
            1,
            slot_right - 2,
            now,
            live,
        )

        # Body ---------------------------------------------------------
        text_x = ICON_COL if any(ln.icon for ln in screen.lines) else PLAIN_COL
        if screen.progress is not None:
            _draw_progress(draw, screen.progress, now)
            ys = LINE_Y_WITH_BAR
        else:
            ys = LINE_Y
        for i, (line, y) in enumerate(zip(screen.lines, ys)):
            if line.icon:
                _draw_icon(draw, line.icon, 1, y + 2)
            rolling |= self._text_in_slot(
                img,
                (f"line{i}", line.text),
                line.text,
                self._body_font,
                text_x,
                y,
                WIDTH - 2 - text_x,
                now,
                live,
            )

        # Forget lines that are no longer on screen so they restart later.
        for key in list(self._seen):
            if key not in live:
                del self._seen[key]
        return img, rolling

    # -- helpers ----------------------------------------------------------

    def _text_in_slot(self, img, key, text, font, x, y, slot_w, now, live) -> bool:
        """Draw ``text`` clipped to ``slot_w`` px, rolling it when too long."""
        if not text:
            return False
        text_w = int(font.getlength(text)) + 1
        offset = None
        if text_w > slot_w:
            live.add(key)
            first = self._seen.setdefault(key, now)
            offset = marquee_offset(text_w, slot_w, now - first)
        if offset is None:
            ImageDraw.Draw(img).text((x, y), text, font=font, fill=1)
            return False
        strip = Image.new("1", (text_w, HEADER_H), 0)
        ImageDraw.Draw(strip).text((0, 0), text, font=font, fill=1)
        img.paste(strip.crop((offset, 0, offset + slot_w, HEADER_H)), (x, y))
        return True


def _draw_progress(draw: ImageDraw.ImageDraw, progress: float, now: float) -> None:
    x0, x1 = 2, WIDTH - 3
    y0, y1 = BAR_Y
    draw.rectangle((x0, y0, x1, y1), outline=1, fill=0)
    inner_w = x1 - x0 - 3
    if progress < 0:
        # Indeterminate: a block sweeping back and forth once per 2 s.
        block = inner_w // 4
        span = inner_w - block
        t = (now % 2.0) / 2.0
        pos = int(span * (t * 2 if t < 0.5 else 2 - t * 2))
        draw.rectangle((x0 + 2 + pos, y0 + 2, x0 + 2 + pos + block, y1 - 2), fill=1)
    else:
        fill_w = int(inner_w * max(0.0, min(1.0, progress)))
        if fill_w > 0:
            draw.rectangle((x0 + 2, y0 + 2, x0 + 2 + fill_w, y1 - 2), fill=1)


def _draw_icon(draw: ImageDraw.ImageDraw, icon: str, x: int, y: int) -> None:
    """8x8 glyphs at (x, y).  Deliberately simple: they read at 1 px/pixel."""
    if icon == ICON_BT:
        draw.line((x + 3, y, x + 3, y + 7), fill=1)
        draw.line((x + 3, y, x + 6, y + 2, x, y + 6), fill=1)
        draw.line((x + 3, y + 7, x + 6, y + 5, x, y + 1), fill=1)
    elif icon == ICON_PEN:
        draw.line((x + 1, y + 6, x + 6, y + 1), fill=1, width=2)
        draw.point((x, y + 7), fill=1)
        draw.point((x + 7, y), fill=1)
    elif icon == ICON_NET:
        draw.polygon((x, y + 4, x + 4, y, x + 7, y + 4), outline=1)
        draw.rectangle((x + 1, y + 4, x + 6, y + 7), outline=1)
    elif icon == ICON_OK:
        draw.line((x, y + 4, x + 3, y + 7, x + 7, y + 1), fill=1)
    elif icon == ICON_ERR:
        draw.line((x, y, x + 7, y + 7), fill=1)
        draw.line((x, y + 7, x + 7, y), fill=1)
    elif icon == ICON_WAIT:
        for dx in (0, 3, 6):
            draw.point((x + dx, y + 5), fill=1)
    elif icon == ICON_ARROW:
        draw.line((x, y + 4, x + 7, y + 4), fill=1)
        draw.line((x + 4, y + 1, x + 7, y + 4, x + 4, y + 7), fill=1)
    elif icon == ICON_MARK:
        draw.polygon((x + 1, y, x + 7, y + 4, x + 1, y + 8), fill=1)
