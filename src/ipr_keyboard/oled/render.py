"""Screen -> 128x64 1-bit image, with Pillow.

Layout (rows): 0-15 header (the panel's yellow band), 16 blank, 18/33/48
three body lines, or a progress bar at 19-27 followed by two lines.  A
screen with four lines — or one marked ``compact``, the magnet activity
list, whose lines drop away one by one — packs them at 18/29/40/51 in a
smaller face instead of cutting one, and keeps that grid as lines are
removed so nothing changes size mid-gesture.  Body lines have a fixed 10 px
icon column so text never shifts when an icon changes.

The header is drawn in the bold 12-px face, or in the 9-px one when it would
not fit beside the badge; only a header too long for both rolls.

A line with ``bold`` set is drawn in the bold face — that is how the gesture
list shows which activity is selected.  Where DejaVu's bold file is missing
(no ``fonts-dejavu-core``, so both faces fall back to Pillow's built-in
font), the line is double-struck one pixel to the right instead, so the
emphasis never disappears.

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
    ICON_WARN,
    Screen,
)

WIDTH = 128
HEIGHT = 64
HEADER_H = 16
ICON_COL = 12  # text x when the screen uses icons
PLAIN_COL = 2
LINE_Y = (18, 33, 48)
LINE_Y_4 = (18, 29, 40, 51)  # four lines: smaller face, tighter pitch
BAR_Y = (19, 27)
LINE_Y_WITH_BAR = (31, 46)
LINE_H = 15  # marquee strip height for a body line
LINE_H_4 = 11

MARQUEE_HOLD_START = 1.5  # s before a long line starts moving
MARQUEE_SPEED = 12.0  # px/s — about two characters per second
MARQUEE_HOLD_END = 1.0  # s with the last character in view, then restart

_FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
_HEADER_SIZE = 12
_BODY_SIZE = 11
_BODY_SIZE_4 = 9  # four lines in the 46 blue rows
_BADGE_SIZE = 8
BADGE_PAD = 5  # px added to the badge text for the inverted box


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


def _truetype(name: str, size: int):
    """The named DejaVu face, or None when it is not installed."""
    for candidate in (_FONT_DIR + name, name):  # packaged, then the system path
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return None


def _load_font(name: str, size: int):
    font = _truetype(name, size)
    if font is not None:
        return font
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:  # pragma: no cover - old Pillow
        return ImageFont.load_default()


class Renderer:
    """Stateful only for the marquee: remembers when each long line appeared."""

    def __init__(self, clock=None) -> None:
        self._header_font = _load_font("DejaVuSans-Bold.ttf", _HEADER_SIZE)
        self._body_font = _load_font("DejaVuSans.ttf", _BODY_SIZE)
        self._body_bold_font = _load_font("DejaVuSans-Bold.ttf", _BODY_SIZE)
        self._small_font = _load_font("DejaVuSans.ttf", _BODY_SIZE_4)
        self._small_bold_font = _load_font("DejaVuSans-Bold.ttf", _BODY_SIZE_4)
        self._badge_font = _load_font("DejaVuSans-Bold.ttf", _BADGE_SIZE)
        # No bold face on this system: emphasise by double-striking instead.
        self._faux_bold = _truetype("DejaVuSans-Bold.ttf", _BODY_SIZE) is None
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
            bw = int(self._badge_font.getlength(screen.badge)) + BADGE_PAD
            draw.rectangle((WIDTH - bw, 1, WIDTH - 1, 12), fill=1)
            draw.text(
                (WIDTH - bw + BADGE_PAD // 2, 2),
                screen.badge,
                font=self._badge_font,
                fill=0,
            )
            slot_right = WIDTH - bw - 3
        slot_w = slot_right - 2
        # A header that does not fit next to the badge is stepped down to the
        # small face before it is rolled: a rolling header is hard to read,
        # and the mode badge takes a third of the band.
        header_font, header_y = self._header_font, 1
        if int(header_font.getlength(screen.header)) + 1 > slot_w:
            header_font, header_y = self._small_bold_font, 3
        rolling |= self._text_in_slot(
            img,
            ("header", screen.header),
            screen.header,
            header_font,
            2,
            header_y,
            slot_w,
            HEADER_H,
            now,
            live,
        )

        # Body ---------------------------------------------------------
        text_x = ICON_COL if any(ln.icon for ln in screen.lines) else PLAIN_COL
        if screen.progress is not None:
            _draw_progress(draw, screen.progress, now)
            ys, slot_h, fonts = LINE_Y_WITH_BAR, LINE_H, self._body_fonts()
        elif screen.compact or len(screen.lines) > len(LINE_Y):
            ys, slot_h, fonts = LINE_Y_4, LINE_H_4, self._small_fonts()
        else:
            ys, slot_h, fonts = LINE_Y, LINE_H, self._body_fonts()
        for i, (line, y) in enumerate(zip(screen.lines, ys)):
            if line.icon:
                _draw_icon(draw, line.icon, 1, y + 2)
            rolling |= self._text_in_slot(
                img,
                (f"line{i}", line.text),
                line.text,
                fonts[line.bold],
                text_x,
                y,
                WIDTH - 2 - text_x,
                slot_h,
                now,
                live,
                bold=line.bold,
            )

        # Forget lines that are no longer on screen so they restart later.
        for key in list(self._seen):
            if key not in live:
                del self._seen[key]
        return img, rolling

    # -- helpers ----------------------------------------------------------

    def _body_fonts(self):
        return {False: self._body_font, True: self._body_bold_font}

    def _small_fonts(self):
        return {False: self._small_font, True: self._small_bold_font}

    def _text_in_slot(
        self, img, key, text, font, x, y, slot_w, slot_h, now, live, bold=False
    ) -> bool:
        """Draw ``text`` clipped to ``slot_w`` px, rolling it when too long."""
        if not text:
            return False
        strike = 2 if (bold and self._faux_bold) else 1
        text_w = int(font.getlength(text)) + 1
        offset = None
        if text_w > slot_w:
            live.add(key)
            first = self._seen.setdefault(key, now)
            offset = marquee_offset(text_w, slot_w, now - first)
        if offset is None:
            draw = ImageDraw.Draw(img)
            for dx in range(strike):
                draw.text((x + dx, y), text, font=font, fill=1)
            return False
        strip = Image.new("1", (text_w + strike, slot_h), 0)
        strip_draw = ImageDraw.Draw(strip)
        for dx in range(strike):
            strip_draw.text((dx, 0), text, font=font, fill=1)
        img.paste(strip.crop((offset, 0, offset + slot_w, slot_h)), (x, y))
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
    elif icon == ICON_WARN:
        # A filled triangle with a notch for the bar and a dot for the point.
        # Solid, because the whole purpose is to be seen without being read,
        # and an 8x8 outline triangle is easy to mistake for the net icon.
        draw.polygon((x + 3, y, x + 7, y + 7, x, y + 7), fill=1)
        draw.line((x + 3, y + 3, x + 3, y + 4), fill=0)
        draw.point((x + 3, y + 6), fill=0)
    elif icon == ICON_WAIT:
        for dx in (0, 3, 6):
            draw.point((x + dx, y + 5), fill=1)
    elif icon == ICON_ARROW:
        draw.line((x, y + 4, x + 7, y + 4), fill=1)
        draw.line((x + 4, y + 1, x + 7, y + 4, x + 4, y + 7), fill=1)
    elif icon == ICON_MARK:
        draw.polygon((x + 1, y, x + 7, y + 4, x + 1, y + 8), fill=1)
