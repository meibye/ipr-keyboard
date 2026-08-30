"""Generate the diagrams used by the Danish user and administrator manuals.

Draws simple, high-contrast vector-style block diagrams with Pillow and writes
them as PNG into docs/manuals/figures/.  Everything is drawn at 2x and
downsampled, which gives clean edges without needing an SVG rasteriser.

Run:
    uv run --with pillow --no-project python docs/manuals/_build/make_figures.py
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 2  # supersampling factor
OUT = Path(__file__).resolve().parents[1] / "figures"

# --- palette ---------------------------------------------------------------
INK = (26, 32, 44)
MUTED = (113, 128, 150)
LINE = (160, 174, 192)
BG = (255, 255, 255)
PANEL = (247, 250, 252)
BLUE = (43, 108, 176)
BLUE_BG = (235, 244, 255)
GREEN = (39, 118, 70)
GREEN_BG = (233, 247, 239)
AMBER = (154, 106, 0)
AMBER_BG = (255, 247, 230)
RED = (176, 42, 42)
RED_BG = (254, 240, 240)
PURPLE = (95, 61, 150)
PURPLE_BG = (243, 238, 253)

_FONT_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in (_FONT_DIR / name, Path("/usr/share/fonts/truetype/dejavu") / name):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size * S)
    return ImageFont.load_default()


def F(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return _font("segoeuib.ttf" if bold else "segoeui.ttf", size)


class Canvas:
    """Thin drawing helper working in unscaled (logical) pixel coordinates."""

    def __init__(self, w: int, h: int, bg=BG) -> None:
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * S, h * S), bg)
        self.d = ImageDraw.Draw(self.img)

    # -- primitives --------------------------------------------------------
    def box(self, x, y, w, h, fill=PANEL, outline=LINE, width=2, radius=10):
        self.d.rounded_rectangle(
            [x * S, y * S, (x + w) * S, (y + h) * S],
            radius=radius * S, fill=fill, outline=outline, width=width * S,
        )

    def text(self, x, y, s, font, fill=INK, anchor="la", spacing=4):
        self.d.multiline_text(
            (x * S, y * S), s, font=font, fill=fill, anchor=anchor,
            spacing=spacing * S, align="center" if anchor[0] == "m" else "left",
        )

    def line(self, x1, y1, x2, y2, fill=LINE, width=2):
        self.d.line([x1 * S, y1 * S, x2 * S, y2 * S], fill=fill, width=width * S)

    def circle(self, cx, cy, r, fill, outline=None, width=2):
        self.d.ellipse(
            [(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S],
            fill=fill, outline=outline, width=width * S,
        )

    def arrow(self, x1, y1, x2, y2, fill=BLUE, width=3, head=9):
        self.line(x1, y1, x2, y2, fill=fill, width=width)
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        for sign in (+1, -1):
            a = ang + sign * math.radians(150)
            self.line(x2, y2, x2 + head * math.cos(a), y2 + head * math.sin(a),
                      fill=fill, width=width)

    # -- composites --------------------------------------------------------
    def node(self, x, y, w, h, title, lines=(), accent=BLUE, bg=BLUE_BG,
             title_size=15, body_size=12):
        self.box(x, y, w, h, fill=bg, outline=accent, width=2)
        cx = x + w / 2
        if lines:
            self.text(cx, y + h / 2 - 12, title, F(title_size, True), accent, anchor="mm")
            self.text(cx, y + h / 2 + 12, "\n".join(lines), F(body_size), INK, anchor="mm")
        else:
            self.text(cx, y + h / 2, title, F(title_size, True), accent, anchor="mm")

    def caption(self, y, s):
        self.text(self.w / 2, y, s, F(11), MUTED, anchor="ma")

    def title(self, s, sub=None):
        self.text(self.w / 2, 18, s, F(18, True), INK, anchor="ma")
        if sub:
            self.text(self.w / 2, 44, sub, F(12), MUTED, anchor="ma")

    def save(self, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        self.img.resize((self.w, self.h), Image.LANCZOS).save(OUT / name, "PNG")
        print(f"  wrote figures/{name}")


# ---------------------------------------------------------------------------
# 1. Systemoversigt  (bruger)
# ---------------------------------------------------------------------------
def fig_system_overview():
    c = Canvas(1000, 400)
    c.title("Sådan hænger det sammen",
            "Skanneren gemmer tekst som fil — brotoget sender teksten videre som tastetryk")

    y, h = 130, 120
    c.node(60, y, 220, h, "IRIS-skanner",
           ["Skanner tekst fra papir", "og gemmer den som", "tekstfil i pennen"],
           PURPLE, PURPLE_BG)
    c.node(390, y, 220, h, "IPR Pen Bridge",
           ["Raspberry Pi Zero 2 W", "læser nye filer og", "sender dem videre"],
           BLUE, BLUE_BG)
    c.node(720, y, 220, h, "PC",
           ["Modtager teksten", "som helt almindelige", "tastetryk"],
           GREEN, GREEN_BG)

    c.arrow(290, y + h / 2, 380, y + h / 2)
    c.text(335, y + h / 2 - 34, "USB-kabel", F(12, True), BLUE, anchor="ma")
    c.text(335, y + h / 2 + 22, "tekstfil", F(11), MUTED, anchor="ma")

    c.arrow(620, y + h / 2, 710, y + h / 2)
    c.text(665, y + h / 2 - 34, "Bluetooth", F(12, True), BLUE, anchor="ma")
    c.text(665, y + h / 2 + 22, "tastetryk", F(11), MUTED, anchor="ma")

    # LED marker on the bridge
    c.circle(500, y + h + 26, 9, GREEN_BG, GREEN, 2)
    c.text(500, y + h + 44, "statuslampe (LED)", F(11), MUTED, anchor="ma")

    c.box(60, 320, 880, 56, fill=PANEL, outline=LINE, width=1, radius=8)
    c.text(500, 348,
           "PC'en ser brotoget som et almindeligt Bluetooth-tastatur. "
           "Teksten havner dér, hvor markøren står.",
           F(12), INK, anchor="mm")
    c.save("fig01_systemoversigt.png")


# ---------------------------------------------------------------------------
# 2. Tilslutning (bruger)
# ---------------------------------------------------------------------------
def fig_connections():
    c = Canvas(1000, 470)
    c.title("Tilslutning af udstyret", "Rækkefølgen betyder noget — se trin 1 til 4")

    # Pi body
    c.box(370, 150, 260, 150, fill=BLUE_BG, outline=BLUE, width=2, radius=12)
    c.text(500, 172, "Raspberry Pi Zero 2 W", F(13, True), BLUE, anchor="ma")
    c.text(500, 196, "IPR Pen Bridge", F(11), MUTED, anchor="ma")

    # ports
    c.box(378, 236, 84, 30, fill=BG, outline=MUTED, width=2, radius=5)
    c.text(420, 251, "PWR", F(10, True), MUTED, anchor="mm")
    c.box(474, 236, 84, 30, fill=BG, outline=MUTED, width=2, radius=5)
    c.text(516, 251, "USB", F(10, True), MUTED, anchor="mm")
    # LED + magnet spot
    c.circle(600, 251, 10, GREEN_BG, GREEN, 2)
    c.text(600, 272, "LED", F(10), MUTED, anchor="ma")

    # 1 power
    c.node(60, 90, 230, 80, "1. Strøm", ["USB-strømforsyning", "i PWR-porten"], AMBER, AMBER_BG)
    c.arrow(295, 130, 415, 232, AMBER)

    # 2 pen
    c.node(60, 300, 230, 80, "2. IRIS-skanner", ["USB-kabel fra pennen", "i USB-porten"], PURPLE, PURPLE_BG)
    c.arrow(295, 340, 508, 272, PURPLE)

    # 3 PC bluetooth
    c.node(710, 150, 230, 80, "3. PC", ["Par via Bluetooth", "(kun første gang)"], GREEN, GREEN_BG)
    c.arrow(630, 200, 705, 190, GREEN)
    c.text(668, 152, "((o))", F(13, True), GREEN, anchor="ma")

    # 4 magnet
    c.node(710, 300, 230, 80, "4. Magnet", ["Holdes tæt på LED'en", "for at se status"], BLUE, BLUE_BG)
    c.arrow(705, 340, 615, 268, BLUE)

    c.box(60, 405, 880, 48, fill=PANEL, outline=LINE, width=1, radius=8)
    c.text(500, 429,
           "Vent ca. 1 minut efter strøm er tilsluttet, før du forventer forbindelse. "
           "Brotoget starter selv op.",
           F(12), INK, anchor="mm")
    c.save("fig02_tilslutning.png")


# ---------------------------------------------------------------------------
# 3. LED-farver (bruger)
# ---------------------------------------------------------------------------
def fig_led_colours():
    rows = [
        ((255, 255, 255), "Hvid, hurtigt blink", "Brotoget starter op — vent ca. 30 sekunder", MUTED),
        ((46, 160, 87), "Grøn, konstant", "Alt er klar — netværk og Bluetooth er forbundet", GREEN),
        ((240, 180, 40), "Gul/ravfarvet, konstant", "Netværk OK, men PC'en er ikke forbundet endnu", AMBER),
        ((214, 60, 60), "Rød, langsomt blink", "Intet netværk — kontakt din administrator", RED),
        ((60, 120, 230), "Blå, konstant", "Opsætningsnetværket er tændt (setup-tilstand)", BLUE),
        ((60, 120, 230), "Blå, hurtigt blink", "Magnet holdt i 3 sek. — slip for at tænde/slukke opsætning", BLUE),
        ((214, 60, 60), "Rød, hurtigt blink", "Magnet holdt i 10 sek. — slip for at nulstille netværk", RED),
        ((225, 228, 233), "Slukket", "Normal drift — lampen sparer strøm", MUTED),
    ]
    rh = 46
    c = Canvas(940, 100 + rh * len(rows) + 30)
    c.title("Hvad betyder lampens farve?",
            "Hold magneten tæt på brotoget for at vække lampen i 30 sekunder")

    y = 90
    for colour, name, meaning, accent in rows:
        c.box(50, y, 840, rh - 8, fill=BG, outline=(230, 234, 240), width=1, radius=8)
        c.circle(84, y + (rh - 8) / 2, 12, colour, LINE, 1)
        c.text(114, y + (rh - 8) / 2, name, F(13, True), accent, anchor="lm")
        c.text(400, y + (rh - 8) / 2, meaning, F(12), INK, anchor="lm")
        y += rh
    c.save("fig03_led_farver.png")


# ---------------------------------------------------------------------------
# 4. Magnet-tidslinje (bruger)
# ---------------------------------------------------------------------------
def fig_magnet_timeline():
    c = Canvas(980, 380)
    c.title("Magneten: hvor længe du holder, bestemmer hvad der sker",
            "Lampen skifter farve, før du slipper — så du kan nå at fortryde")

    x0, x1, y = 90, 890, 150
    c.line(x0, y, x1, y, LINE, 3)
    for frac, label in ((0.0, "0 s"), (0.3, "3 s"), (1.0, "10 s")):
        x = x0 + (x1 - x0) * frac
        c.line(x, y - 10, x, y + 10, MUTED, 3)
        c.text(x, y + 18, label, F(11, True), MUTED, anchor="ma")

    seg = [
        (0.0, 0.3, "Kort berøring", "Lampen viser status i 30 sek.", BLUE, BLUE_BG),
        (0.3, 1.0, "Hold i 3 sek.", "Tænder/slukker opsætningsnetværket", GREEN, GREEN_BG),
    ]
    for a, b, t, s, accent, bg in seg:
        xa, xb = x0 + (x1 - x0) * a, x0 + (x1 - x0) * b
        c.box(xa + 4, y - 66, xb - xa - 8, 50, fill=bg, outline=accent, width=2, radius=8)
        c.text((xa + xb) / 2, y - 54, t, F(12, True), accent, anchor="ma")
        c.text((xa + xb) / 2, y - 34, s, F(11), INK, anchor="ma")

    c.line(x1, y + 36, x1 - 24, y + 52, RED, 2)
    c.box(740, y + 52, 190, 82, fill=RED_BG, outline=RED, width=2, radius=8)
    c.text(835, y + 64, "Hold i 10 sek.", F(12, True), RED, anchor="ma")
    c.text(835, y + 88, "Nulstiller alle gemte\nnetværk", F(11), INK, anchor="ma")

    c.box(60, 308, 860, 52, fill=PANEL, outline=LINE, width=1, radius=8)
    c.text(490, 334,
           "Fortryd: hold magneten, indtil lampen skifter væk fra den farve du ikke ønsker — "
           "handlingen udføres først, når du slipper.",
           F(12), INK, anchor="mm")
    c.save("fig04_magnet_tidslinje.png")


# ---------------------------------------------------------------------------
# 5. Dashboard-forsiden (bruger)
# ---------------------------------------------------------------------------
def fig_dashboard():
    c = Canvas(960, 560)
    c.title("Betjeningssiden i browseren", "Sådan ser forsiden ud — status først, detaljer bagefter")

    c.box(60, 80, 840, 440, fill=BG, outline=LINE, width=2, radius=10)
    # top bar
    c.box(60, 80, 840, 46, fill=PANEL, outline=LINE, width=1, radius=10)
    c.text(84, 103, "IPR Pen Bridge", F(14, True), INK, anchor="lm")
    c.box(760, 91, 76, 24, fill=GREEN_BG, outline=GREEN, width=1, radius=12)
    c.text(798, 103, "KLAR", F(11, True), GREEN, anchor="mm")

    # nav
    navs = ["Forside", "Forbindelser", "Aktivitet", "Hændelser", "Indstillinger"]
    x = 84
    for i, n in enumerate(navs):
        w = 16 + len(n) * 8
        if i == 0:
            c.box(x - 8, 136, w, 26, fill=BLUE_BG, outline=BLUE, width=1, radius=6)
        c.text(x, 149, n, F(11, True if i == 0 else False), BLUE if i == 0 else MUTED, anchor="lm")
        x += w + 12

    # hero
    c.box(84, 178, 792, 96, fill=PANEL, outline=(230, 234, 240), width=1, radius=8)
    for cx, label, accent in ((240, "Pen", PURPLE), (480, "Bro", BLUE), (720, "PC", GREEN)):
        c.box(cx - 54, 196, 108, 44, fill=BG, outline=accent, width=2, radius=8)
        c.text(cx, 218, label, F(12, True), accent, anchor="mm")
    c.arrow(300, 218, 420, 218)
    c.arrow(540, 218, 660, 218)
    c.text(480, 250, "Klar til brug", F(12, True), GREEN, anchor="ma")

    # four cards
    cards = [
        ("Bluetooth", "Forbundet", "Parret med Kontor-PC", GREEN, GREEN_BG),
        ("Pen", "Klar", "Skanner fundet", GREEN, GREEN_BG),
        ("Overførsel", "Inaktiv", "Ingen aktiv afsendelse", MUTED, PANEL),
        ("System", "Sund", "Temperatur normal", GREEN, GREEN_BG),
    ]
    for i, (t, state, expl, accent, bg) in enumerate(cards):
        cx = 84 + (i % 2) * 400
        cy = 292 + (i // 2) * 96
        c.box(cx, cy, 392, 84, fill=BG, outline=(230, 234, 240), width=1, radius=8)
        c.circle(cx + 32, cy + 42, 15, bg, accent, 2)
        c.text(cx + 60, cy + 22, t, F(12, True), INK, anchor="lm")
        c.text(cx + 60, cy + 44, state, F(13, True), accent, anchor="lm")
        c.text(cx + 60, cy + 64, expl, F(11), MUTED, anchor="lm")

    c.text(84, 500, "Seneste hændelse: Pen forbundet for 2 min. siden", F(11), MUTED, anchor="lm")
    c.save("fig05_dashboard.png")


# ---------------------------------------------------------------------------
# 6. Brugerens fejlfindingstræ
# ---------------------------------------------------------------------------
def fig_user_troubleshoot():
    c = Canvas(980, 640)
    c.title("Der kommer ingen tekst frem på PC'en", "Gå trinene igennem oppefra og ned")

    def step(y, q, yes, no, accent=BLUE, bg=BLUE_BG):
        c.box(290, y, 350, 62, fill=bg, outline=accent, width=2, radius=10)
        c.text(465, y + 31, q, F(12, True), accent, anchor="mm")
        c.line(640, y + 31, 692, y + 31, LINE, 2)
        c.text(666, y + 20, "nej", F(10, True), RED, anchor="mm")
        c.box(700, y + 4, 250, 54, fill=BG, outline=(230, 234, 240), width=1, radius=8)
        c.text(710, y + 31, no, F(11), INK, anchor="lm")
        if yes:
            c.arrow(465, y + 62, 465, y + 96, LINE)
            c.text(473, y + 74, "ja", F(10, True), GREEN, anchor="lm")

    step(90, "Lyser eller blinker lampen,\nnår du holder magneten tæt på?", True,
         "Kontrollér strømforsyningen.\nEr stikket sat i?", RED, RED_BG)
    step(200, "Er lampen grøn?", True,
         "Gul = PC ikke forbundet.\nRød = intet netværk.\nSe afsnittet om lampens farver.")
    step(310, "Står markøren i det rigtige\nfelt eller dokument på PC'en?", True,
         "Klik i feltet, hvor teksten\nskal stå, og skan igen.")
    step(420, "Er skanneren sat til med\nUSB-kablet?", False,
         "Sæt USB-kablet i igen,\nog vent 30 sekunder.")

    c.box(290, 500, 350, 92, fill=AMBER_BG, outline=AMBER, width=2, radius=10)
    c.text(465, 516, "Stadig ingen tekst?", F(13, True), AMBER, anchor="ma")
    c.text(465, 542, "Sluk for strømmen, vent 10 sek.,\ntænd igen. Hjælper det ikke:\nkontakt din administrator.",
           F(11), INK, anchor="ma")
    c.arrow(465, 482, 465, 498, LINE)
    c.save("fig06_bruger_fejlfinding.png")


# ---------------------------------------------------------------------------
# 7. Softwarearkitektur (admin)
# ---------------------------------------------------------------------------
def fig_architecture():
    c = Canvas(1080, 700)
    c.title("Softwarearkitektur — IPR Pen Bridge",
            "Dataveje (fuldt optrukket) og kontrol/status (stiplet forklaret i teksten)")

    # Outer Pi frame
    c.box(40, 76, 1000, 520, fill=(252, 253, 255), outline=LINE, width=2, radius=12)
    c.text(60, 92, "Raspberry Pi Zero 2 W  ·  Raspberry Pi OS Lite (Bookworm)", F(12, True), MUTED, anchor="la")

    # ipr_keyboard.service group
    c.box(64, 124, 470, 300, fill=BLUE_BG, outline=BLUE, width=2, radius=10)
    c.text(80, 138, "ipr_keyboard.service   (applikationsbruger)", F(12, True), BLUE, anchor="la")

    c.node(84, 168, 200, 62, "usb.detector /", ["usb.reader"], BLUE, BG, 12, 12)
    c.node(304, 168, 210, 62, "bluetooth.keyboard", ["send_text()"], BLUE, BG, 12, 12)
    c.node(84, 248, 200, 62, "web.server (Flask)", ["+ web.api  /api/*"], BLUE, BG, 12, 12)
    c.node(304, 248, 210, 62, "web.setup", ["/setup/*  hotspot-UI"], BLUE, BG, 12, 12)
    c.node(84, 328, 430, 62, "gpio_monitor", ["reed-kontakt · RGB-LED · hotspot-toggle · fabriksnulstilling"], BLUE, BG, 12, 11)
    c.arrow(284, 199, 300, 199)

    # FIFO
    c.box(566, 168, 200, 62, fill=AMBER_BG, outline=AMBER, width=2, radius=10)
    c.text(666, 189, "bt_kb_send", F(12, True), AMBER, anchor="ma")
    c.text(666, 209, "→ /run/ipr_bt_keyboard_fifo", F(10), INK, anchor="ma")
    c.arrow(514, 199, 560, 199)

    # BLE services
    c.box(566, 248, 450, 176, fill=GREEN_BG, outline=GREEN, width=2, radius=10)
    c.text(582, 262, "BLE-lag (root)", F(12, True), GREEN, anchor="la")
    c.node(586, 288, 200, 56, "bt_hid_ble.service", ["HID over GATT"], GREEN, BG, 12, 11)
    c.node(802, 288, 196, 56, "bt_hid_agent_unified", ["BlueZ Agent1"], GREEN, BG, 12, 11)
    c.node(586, 358, 416, 50, "BlueZ / bluetoothd  →  hci0", [], GREEN, BG, 12, 11)
    c.arrow(666, 230, 666, 284, AMBER)
    c.arrow(686, 344, 686, 356, GREEN)
    c.arrow(900, 344, 900, 356, GREEN)

    # hotspot service
    c.box(64, 440, 470, 62, fill=PURPLE_BG, outline=PURPLE, width=2, radius=10)
    c.text(299, 456, "ipr-provision.service", F(12, True), PURPLE, anchor="ma")
    c.text(299, 478, "on-demand hotspot på wlan0  ·  10.42.0.1  ·  /etc/ipr-hotspot.secret", F(10), INK, anchor="ma")

    c.box(566, 440, 450, 62, fill=PANEL, outline=LINE, width=2, radius=10)
    c.text(791, 456, "ipr-cert-renew.timer", F(12, True), MUTED, anchor="ma")
    c.text(791, 478, "årlig fornyelse af servercertifikat i /etc/ipr-ssl/", F(10), INK, anchor="ma")

    # config
    c.box(64, 518, 952, 62, fill=PANEL, outline=LINE, width=1, radius=10)
    c.text(90, 534, "Konfiguration:", F(11, True), INK, anchor="la")
    c.text(90, 556,
           "config.json (app)   ·   users.json (konti)   ·   /opt/ipr_common.env (miljø)   ·   "
           "/etc/default/bt_hid_agent_unified   ·   /etc/default/ipr-provision",
           F(11), MUTED, anchor="la")

    # external — routed outside the Pi frame so no connector crosses a box
    c.node(60, 618, 300, 62, "IRIS-skanner", ["USB · tekstfiler i /mnt/irispen/…"], PURPLE, PURPLE_BG, 12, 11)
    c.line(210, 616, 210, 606, PURPLE, 2)
    c.line(210, 606, 22, 606, PURPLE, 2)
    c.line(22, 606, 22, 199, PURPLE, 2)
    c.arrow(22, 199, 80, 199, PURPLE)

    c.node(720, 618, 300, 62, "PC / vært", ["BLE HID-tastatur"], GREEN, GREEN_BG, 12, 11)
    c.line(1002, 383, 1058, 383, GREEN, 2)
    c.line(1058, 383, 1058, 606, GREEN, 2)
    c.line(1058, 606, 870, 606, GREEN, 2)
    c.arrow(870, 606, 870, 614, GREEN)

    c.save("fig07_arkitektur.png")


# ---------------------------------------------------------------------------
# 8. Provisioneringsflow (admin)
# ---------------------------------------------------------------------------
def fig_provisioning():
    c = Canvas(1020, 470)
    c.title("Førstegangsopsætning — provisioneringsforløb",
            "sudo ./provision/provision_wizard.sh kører hele forløbet med genstartspunkter")

    steps = [
        ("00", "bootstrap", "validerer /opt/ipr_common.env,\nhenter repo"),
        ("01", "os_base", "OS-pakker og\nBluetooth-baseline"),
        ("02", "device_identity", "værtsnavn og\nBluetooth-navn"),
        ("03", "app_install", "Python-miljø\nog pakke"),
        ("04", "enable_services", "installerer og starter\nalle tjenester"),
        ("05", "debug_tools", "valgfrit\ndiagnoseværktøj"),
        ("06", "verify", "verifikations-\nrapport"),
    ]
    x, y, w, h, gap = 40, 110, 128, 130, 12
    for i, (num, name, desc) in enumerate(steps):
        accent, bg = (MUTED, PANEL) if num == "05" else (BLUE, BLUE_BG)
        cx = x + i * (w + gap)
        c.box(cx, y, w, h, fill=bg, outline=accent, width=2, radius=10)
        c.text(cx + w / 2, y + 14, num, F(20, True), accent, anchor="ma")
        c.text(cx + w / 2, y + 46, name, F(12, True), INK, anchor="ma")
        c.text(cx + w / 2, y + 72, desc, F(10), MUTED, anchor="ma")
        if i < len(steps) - 1:
            c.arrow(cx + w, y + h / 2, cx + w + gap, y + h / 2)

    # reboot markers
    for i in (1, 2):
        cx = x + i * (w + gap) + w / 2
        c.text(cx + 70, y + h + 14, "⟳ genstart", F(10, True), AMBER, anchor="ma")

    c.box(40, 300, 940, 70, fill=GREEN_BG, outline=GREEN, width=2, radius=10)
    c.text(510, 316, "Efter trin 04 findes disse enheder", F(12, True), GREEN, anchor="ma")
    c.text(510, 340,
           "ipr_keyboard.service   ·   bt_hid_ble.service   ·   bt_hid_agent_unified.service   ·   ipr-provision.service",
           F(11), INK, anchor="ma")

    c.box(40, 386, 940, 62, fill=PANEL, outline=LINE, width=1, radius=10)
    c.text(510, 404, "Kontrollér til sidst", F(11, True), INK, anchor="ma")
    c.text(510, 426,
           "sudo ./provision/06_verify.sh   ·   ./scripts/diag_status.sh   ·   sudo ./provision/07_show_info.sh (hotspot-oplysninger)",
           F(11), MUTED, anchor="ma")
    c.save("fig08_provisionering.png")


# ---------------------------------------------------------------------------
# 9. Adgangsveje og netværk (admin)
# ---------------------------------------------------------------------------
def fig_access_paths():
    c = Canvas(1000, 560)
    c.title("To adgangsveje til enheden", "Normal drift via hjemmenettet — nødadgang via opsætningshotspot")

    c.box(40, 90, 440, 300, fill=GREEN_BG, outline=GREEN, width=2, radius=12)
    c.text(260, 104, "A · Hjemmenet (normal drift)", F(13, True), GREEN, anchor="ma")
    c.node(70, 140, 180, 60, "Administrator-PC", ["browser"], GREEN, BG, 11, 10)
    c.node(280, 140, 170, 60, "WLAN / LAN", ["DHCP eller statisk"], GREEN, BG, 11, 10)
    c.arrow(252, 170, 276, 170, GREEN)
    c.node(70, 226, 380, 64, "https://<værtsnavn>.local/", ["Dashboard · sessionslogin · /setup/ for administratorer"], GREEN, BG, 12, 10)
    c.arrow(260, 202, 260, 222, GREEN)
    c.text(260, 306, "Port: LogPort i config.json (443 i drift)", F(11), MUTED, anchor="ma")
    c.text(260, 330, "Kræver at enheden har netværksforbindelse", F(11), MUTED, anchor="ma")

    c.box(520, 90, 440, 300, fill=BLUE_BG, outline=BLUE, width=2, radius=12)
    c.text(740, 104, "B · Opsætningshotspot (nødadgang)", F(13, True), BLUE, anchor="ma")
    c.node(550, 140, 180, 60, "Telefon / laptop", ["Wi-Fi"], BLUE, BG, 11, 10)
    c.node(760, 140, 170, 60, "ipr-setup-xxxx", ["WPA2"], BLUE, BG, 11, 10)
    c.arrow(732, 170, 756, 170, BLUE)
    c.node(550, 226, 380, 64, "https://10.42.0.1/setup/", ["bruger: ipr · kode: /etc/ipr-hotspot.secret"], BLUE, BG, 12, 10)
    c.arrow(740, 202, 740, 222, BLUE)
    c.text(740, 306, "Udløses af: magnet 3 sek. · 3× tænd/sluk · IPR_SETUP-fil", F(11), MUTED, anchor="ma")
    c.text(740, 330, "Virker uden netværk og uden kabel", F(11), MUTED, anchor="ma")

    c.box(40, 410, 920, 130, fill=PANEL, outline=LINE, width=1, radius=10)
    c.text(500, 426, "Fælles for begge veje", F(12, True), INK, anchor="ma")
    c.text(500, 452,
           "HTTPS med enhedens eget CA-signerede certifikat fra /etc/ipr-ssl/\n"
           "Installér CA-certifikatet én gang fra https://10.42.0.1/setup/ca.crt for at fjerne browseradvarsler\n"
           "Certifikatet fornyes automatisk af ipr-cert-renew.timer — CA-nøglen bevares, så klienter ikke skal geninstallere",
           F(11), INK, anchor="ma")
    c.save("fig09_adgangsveje.png")


# ---------------------------------------------------------------------------
# 10. Opdateringsflow (admin)
# ---------------------------------------------------------------------------
def fig_update_flow():
    c = Canvas(1000, 500)
    c.title("Opdatering af softwaren", "Kør altid en verifikation efter opdatering")

    steps = [
        ("1", "Sikkerhedskopi", "config.json · users.json\n/etc/ipr-hotspot.secret", AMBER, AMBER_BG),
        ("2", "git pull", "hent ny kode i\nprojektmappen", BLUE, BLUE_BG),
        ("3", "deploy_full_update.sh", "daemons · helpers\nsystemd · genstart", BLUE, BLUE_BG),
        ("4", "Verificér", "diag_status.sh\n+ testafsendelse", GREEN, GREEN_BG),
    ]
    x, y, w, h, gap = 50, 110, 200, 120, 40
    for i, (n, t, d, accent, bg) in enumerate(steps):
        cx = x + i * (w + gap)
        c.box(cx, y, w, h, fill=bg, outline=accent, width=2, radius=10)
        c.circle(cx + 24, y + 24, 14, BG, accent, 2)
        c.text(cx + 24, y + 24, n, F(13, True), accent, anchor="mm")
        c.text(cx + w / 2, y + 50, t, F(12, True), INK, anchor="ma")
        c.text(cx + w / 2, y + 76, d, F(10), MUTED, anchor="ma")
        if i < 3:
            c.arrow(cx + w, y + h / 2, cx + w + gap, y + h / 2)

    c.box(50, 264, 890, 92, fill=PANEL, outline=LINE, width=1, radius=10)
    c.text(70, 280, "Hvornår skal --install-python bruges?", F(12, True), INK, anchor="la")
    c.text(70, 304,
           "Ja: pyproject.toml, entry points eller afhængigheder er ændret.\n"
           "Nej: kun Python-kode, skripts eller templates er ændret — så er en genstart af tjenesterne nok.",
           F(11), MUTED, anchor="la")

    c.box(50, 376, 890, 100, fill=RED_BG, outline=RED, width=2, radius=10)
    c.text(70, 392, "Tilbagerulning", F(12, True), RED, anchor="la")
    c.text(70, 416,
           "git checkout <forrige tag/commit>  →  sudo ./scripts/deploy/deploy_full_update.sh --install-python\n"
           "Gendan config.json og users.json fra sikkerhedskopien, hvis konfigurationsformatet er ændret.\n"
           "Kontrollér derefter: systemctl status ipr_keyboard bt_hid_ble bt_hid_agent_unified",
           F(11), INK, anchor="la")
    c.save("fig10_opdatering.png")


# ---------------------------------------------------------------------------
# 11. Sikkerhedslag (admin)
# ---------------------------------------------------------------------------
def fig_security():
    c = Canvas(980, 560)
    c.title("Sikkerhedslag", "Fra netværkskant til data på disken")

    layers = [
        ("Netværkskant", "Hotspot er slukket som standard (on-demand) · WPA2 · tilfældig SSID og kode i /etc/ipr-hotspot.secret (0600)", BLUE, BLUE_BG),
        ("Transport", "HTTPS via privat CA i /etc/ipr-ssl/ · server.key er root:ipr-ssl 0640 · automatisk fornyelse", GREEN, GREEN_BG),
        ("Autentificering", "Dashboard: sessionslogin, kodeord hashet med pbkdf2:sha256 · Setup-UI: separat konto 'ipr' med rate limiting", PURPLE, PURPLE_BG),
        ("Autorisation", "is_admin-rolle beskytter netværk, brugerstyring og /setup/ · sidste administrator kan ikke fjernes", AMBER, AMBER_BG),
        ("Farlige handlinger", "Genstart, nedlukning og netværksskift kræver confirm=true i API-kaldet", RED, RED_BG),
        ("Data og hemmeligheder", "secret_key.txt (0600) · users.json · admin_initial_password.txt skal slettes efter første login", MUTED, PANEL),
    ]
    y = 92
    for name, desc, accent, bg in layers:
        c.box(50, y, 880, 68, fill=bg, outline=accent, width=2, radius=10)
        c.text(74, y + 18, name, F(13, True), accent, anchor="la")
        c.text(74, y + 42, desc, F(11), INK, anchor="la")
        y += 76
    c.save("fig11_sikkerhed.png")


# ---------------------------------------------------------------------------
# 12. Fejlfindingstræ for administrator
# ---------------------------------------------------------------------------
def fig_admin_troubleshoot():
    c = Canvas(1060, 740)
    c.title("Fejlfinding: teksten når ikke frem til PC'en",
            "Afgrænsning fra Raspberry Pi til vært — start øverst")

    def band(y, title, accent, bg, items):
        h = 34 + 24 * len(items)
        c.box(50, y, 960, h, fill=bg, outline=accent, width=2, radius=10)
        c.text(74, y + 10, title, F(12, True), accent, anchor="la")
        for i, it in enumerate(items):
            c.text(74, y + 36 + i * 24, "•  " + it, F(11), INK, anchor="la")
        return y + h + 22

    y = 86
    y = band(y, "1 · Kører tjenesterne?", BLUE, BLUE_BG, [
        "systemctl status ipr_keyboard bt_hid_ble bt_hid_agent_unified ipr-provision",
        "./scripts/diag_status.sh   —   samlet statusbillede",
        "Fejler en enhed: journalctl -u <enhed> -n 200 --no-pager",
    ])
    y = band(y, "2 · Ser Pi'en filerne fra skanneren?", PURPLE, PURPLE_BG, [
        "mountpoint /mnt/irispen  ·  ls -l \"<IrisPenFolders fra config.json>\"",
        "Er den ikke monteret: sudo ./scripts/usb_mount_mtp.sh eller sudo ./scripts/usb_setup_mount.sh /dev/sdX1",
        "Dashboard → Debug → Pen Files viser, hvad tjenesten faktisk ser",
    ])
    y = band(y, "3 · Kan Pi'en sende via Bluetooth?", GREEN, GREEN_BG, [
        "bt_kb_send \"test\"   —   hænger kommandoen, er FIFO'en blokeret",
        "Kontrollér læser: sudo fuser -v /run/ipr_bt_keyboard_fifo (tom = ingen læser)",
        "Genopretning: sudo systemctl restart bt_hid_ble.service",
        "Parringsdiagnose: sudo ./scripts/ble/diag_pairing.sh  ·  sudo ./scripts/ble/diag_bt_visibility.sh --fix",
    ])
    y = band(y, "4 · Er problemet på PC-siden?", AMBER, AMBER_BG, [
        "Windows: Indstillinger → Bluetooth — fjern enheden og par igen",
        "Enhedshåndtering → HID-enheder: er tastaturet til stede uden fejlmarkering?",
        "Kontrollér at inputfeltet har fokus, og at tastaturlayout matcher det forventede",
        "Bond-konflikt: sudo ./scripts/rpi-debug/dbg_bt_bond_wipe.sh <MAC> og fjern parringen på PC'en",
    ])
    c.box(50, y, 960, 62, fill=RED_BG, outline=RED, width=2, radius=10)
    c.text(530, y + 14, "Eskalationsstige for Bluetooth", F(12, True), RED, anchor="ma")
    c.text(530, y + 38,
           "dbg_bt_restart.sh  →  dbg_bt_soft_reset.sh  →  dbg_bt_bond_wipe.sh <MAC>  →  genstart enheden",
           F(11), INK, anchor="ma")
    c.save("fig12_admin_fejlfinding.png")


def main() -> None:
    print("Generating manual figures…")
    for fn in (
        fig_system_overview, fig_connections, fig_led_colours, fig_magnet_timeline,
        fig_dashboard, fig_user_troubleshoot, fig_architecture, fig_provisioning,
        fig_access_paths, fig_update_flow, fig_security, fig_admin_troubleshoot,
    ):
        fn()
    print("Done.")


if __name__ == "__main__":
    main()
