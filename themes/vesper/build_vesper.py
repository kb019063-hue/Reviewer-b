#!/usr/bin/env python3
"""Build "Vesper" — an original warm-dark EMUI 9.1 theme for Huawei P20 Lite (ANE-LX1).

Every pixel here is drawn by this script: gradient wallpaper, icon glyphs, launcher
art and previews. No photographs, no AI image generation, no copied assets.

The Inter variable font in source/fonts/ is redistributed under the SIL Open Font
License 1.1; its license text is packaged next to the generated font instances.

Two archives are produced:

  Vesper-EMUI91.hwt        full theme: wallpaper + icons + fonts + system colour overrides
  Vesper-Safe-EMUI91.hwt   conservative variant: wallpaper + icons + fonts only

The safe variant exists because EMUI 9.1 does not reliably repaint every system
surface from a theme. If firmware keeps a panel white while this theme asks for
light text on it, the safe archive avoids that class of unreadable text.

Requires Pillow and fonttools.
"""
from __future__ import annotations

import math
import random
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent
SOURCE_FONT = ROOT / "source" / "fonts" / "Inter-Variable.ttf"
OFL = ROOT / "source" / "fonts" / "OFL-Inter.txt"
WORK = ROOT / ".work"
OUT_FULL = ROOT / "Vesper-EMUI91.hwt"
OUT_SAFE = ROOT / "Vesper-Safe-EMUI91.hwt"
PREVIEW = ROOT / "Vesper-preview.png"
LOCK_PREVIEW = ROOT / "Vesper-lockscreen-preview.png"

# --- Palette -----------------------------------------------------------------
# A warm dusk: charcoal with an ember cast, copper accent, muted sage counterpoint.
BG = "#100E0D"            # deepest background
SURFACE = "#1B1817"       # cards, panels
SURFACE_2 = "#241F1D"     # raised panels
ELEVATED = "#2C2623"      # dialogs, sheets
BORDER = "#3A322E"        # hairlines on dark
TEXT = "#F6F1E9"          # primary text
TEXT_2 = "#C9C0B5"        # secondary text
MUTED = "#9B9188"         # hints, disabled
COPPER = "#E29A4B"        # accent
COPPER_HI = "#F5C487"     # accent highlight
COPPER_DEEP = "#B06A22"   # accent pressed / deep
SAGE = "#7FB3A0"          # secondary accent
EMBER = "#E0736B"         # warm red (health, alerts)
CREAM = "#F2E9DC"         # icon glyph ink

ICON_PLATE = "#211D1B"
ICON_PLATE_2 = "#282220"
ICON_EDGE = "#3F3631"

W, H = 1080, 2280  # P20 Lite: FHD+ 1080x2280, 19:9

FONT_PATHS: dict[int, Path] = {}
FONT_WEIGHT_FILES = {
    300: "Roboto-Light.ttf",
    400: "Roboto-Regular.ttf",
    500: "Roboto-Medium.ttf",
    600: "Roboto-SemiBold.ttf",
    700: "Roboto-Bold.ttf",
}


def font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATHS[weight]), size)


def rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def argb(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    r, g, b = rgb(hex_color)
    return (r, g, b, alpha)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


# --- Drawing pen -------------------------------------------------------------
class Pen:
    """Small vector helper: glyphs are described in an 80x80 design space."""

    def __init__(self, draw: ImageDraw.ImageDraw, ox: int, oy: int, s: float, stroke: float,
                 image: Image.Image | None = None):
        self.d = draw
        self.im = image
        self.ox = ox
        self.oy = oy
        self.s = s
        self.stroke = stroke
        self.ink = CREAM
        self.accent = COPPER

    def p(self, x: float, y: float) -> tuple[int, int]:
        return int(self.ox + x * self.s), int(self.oy + y * self.s)

    def w(self, mult: float = 1.0) -> int:
        return max(2, int(round(self.stroke * mult * self.s)))

    def line(self, pts, color=None, width=None, joint="curve"):
        color = color or self.ink
        width = width or self.w()
        coords = [self.p(x, y) for x, y in pts]
        if len(coords) > 1:
            self.d.line(coords, fill=color, width=width, joint=joint)
        # round caps so thin strokes do not look chopped at this scale
        r = width / 2
        for x, y in coords:
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=color)

    def closed(self, pts, color=None, width=None):
        color = color or self.ink
        width = width or self.w()
        coords = [self.p(x, y) for x, y in pts]
        self.d.polygon(coords, outline=color)
        for i in range(len(coords)):
            self.line([pts[i], pts[(i + 1) % len(pts)]], color, width)

    def poly(self, pts, fill=None):
        self.d.polygon([self.p(x, y) for x, y in pts], fill=fill or self.accent)

    def circle(self, cx, cy, r, color=None, fill=None, width=None):
        color = color or self.ink
        width = width or self.w()
        x, y = self.p(cx, cy)
        rr = r * self.s
        if fill:
            self.d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=fill)
        else:
            self.d.ellipse((x - rr, y - rr, x + rr, y + rr), outline=color, width=width)

    def dot(self, cx, cy, r, fill=None):
        self.circle(cx, cy, r, fill=fill or self.accent)

    def rrect(self, x1, y1, x2, y2, r, color=None, fill=None, width=None):
        color = color or self.ink
        width = width or self.w()
        box = (*self.p(x1, y1), *self.p(x2, y2))
        if fill:
            self.d.rounded_rectangle(box, radius=r * self.s, fill=fill, outline=color, width=width)
        else:
            self.d.rounded_rectangle(box, radius=r * self.s, outline=color, width=width)

    def arc(self, cx, cy, r, a0, a1, color=None, width=None):
        color = color or self.ink
        width = width or self.w()
        x, y = self.p(cx, cy)
        rr = r * self.s
        self.d.arc((x - rr, y - rr, x + rr, y + rr), a0, a1, fill=color, width=width)


# --- Glyph library -----------------------------------------------------------
def g_phone(p: Pen):
    # Geometric handset: a tilted capsule with two rounded earpieces.
    layer = Image.new("RGBA", (int(80 * p.s), int(80 * p.s)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sub = Pen(d, 0, 0, p.s, p.stroke)
    sub.line([(27, 53), (53, 27)], COPPER, sub.w(1.7))
    sub.dot(27, 53, 7.5, CREAM)
    sub.dot(53, 27, 7.5, CREAM)
    if p.im is not None:
        p.im.alpha_composite(layer, (p.ox, p.oy))
    else:
        p.d.bitmap((p.ox, p.oy), layer)


def g_message(p: Pen):
    p.rrect(10, 15, 70, 55, 14, CREAM)
    p.line([(26, 55), (20, 68), (38, 56)], COPPER)
    for x in (28, 40, 52):
        p.dot(x, 35, 2.6, COPPER)


def g_contacts(p: Pen):
    p.circle(40, 29, 12, CREAM)
    p.arc(40, 62, 23, 195, 345, COPPER, p.w(1.15))
    p.line([(19, 60), (19, 66), (61, 66), (61, 60)], CREAM)


def g_camera(p: Pen):
    p.line([(27, 20), (32, 12), (50, 12), (55, 20)], COPPER)
    p.rrect(9, 20, 71, 64, 13, CREAM)
    p.circle(40, 42, 14, CREAM)
    p.circle(40, 42, 6.5, fill=COPPER)
    p.dot(63, 28, 2.4, COPPER)


def g_photos(p: Pen):
    p.rrect(10, 14, 70, 66, 12, CREAM)
    p.line([(16, 56), (32, 38), (44, 50), (54, 40), (64, 52)], COPPER, p.w(0.95))
    p.dot(26, 27, 5.5, COPPER)


def g_settings(p: Pen):
    p.circle(40, 40, 22, COPPER, width=p.w(1.1))
    p.circle(40, 40, 9, CREAM)
    for a in range(0, 360, 45):
        ang = math.radians(a)
        p.line(
            [(40 + math.cos(ang) * 22, 40 + math.sin(ang) * 22),
             (40 + math.cos(ang) * 32, 40 + math.sin(ang) * 32)],
            CREAM, p.w(0.95),
        )


def g_calendar(p: Pen):
    p.rrect(12, 16, 68, 68, 11, CREAM)
    p.line([(12, 30), (68, 30)], COPPER, p.w(1.1))
    p.line([(26, 9), (26, 22)], CREAM)
    p.line([(54, 9), (54, 22)], CREAM)
    for x, y in ((26, 41), (40, 41), (54, 41), (26, 55), (40, 55)):
        p.dot(x, y, 2.9, COPPER if (x, y) == (40, 41) else CREAM)


def g_clock(p: Pen):
    p.circle(40, 40, 30, CREAM, width=p.w(1.05))
    p.line([(40, 40), (40, 21)], COPPER, p.w(1.15))
    p.line([(40, 40), (55, 49)], CREAM, p.w(1.05))
    p.dot(40, 40, 3.2, COPPER)


def g_browser(p: Pen):
    p.circle(40, 40, 29, CREAM, width=p.w(1.05))
    p.line([(12, 40), (68, 40)], CREAM, p.w(0.85))
    p.line([(40, 11), (40, 69)], CREAM, p.w(0.7))
    p.d.ellipse((int(p.ox + 25 * p.s), int(p.oy + 11 * p.s),
                 int(p.ox + 55 * p.s), int(p.oy + 69 * p.s)), outline=COPPER, width=p.w(0.95))
    p.dot(40, 40, 2.6, COPPER)


def g_maps(p: Pen):
    p.closed([(14, 20), (33, 12), (52, 21), (68, 13), (68, 60), (51, 68), (32, 59), (14, 67)],
             CREAM, p.w(0.95))
    p.line([(33, 13), (33, 59)], COPPER, p.w(0.8))
    p.line([(52, 21), (52, 67)], COPPER, p.w(0.8))
    p.poly([(43, 30), (49, 40), (37, 40)], COPPER_HI)


def g_music(p: Pen):
    p.line([(50, 16), (50, 52)], CREAM, p.w(1.2))
    p.line([(50, 16), (66, 12), (66, 44), (50, 48)], COPPER, p.w(1.2))
    p.circle(24, 54, 11, fill=CREAM)
    p.circle(56, 50, 10, fill=COPPER)


def g_weather(p: Pen):
    p.circle(29, 32, 12, COPPER, width=p.w(1.05))
    for a in range(0, 360, 60):
        ang = math.radians(a)
        p.line([(29 + math.cos(ang) * 16, 32 + math.sin(ang) * 16),
                (29 + math.cos(ang) * 21, 32 + math.sin(ang) * 21)], COPPER, p.w(0.8))
    p.circle(34, 54, 13, CREAM, width=p.w(1.0))
    p.circle(51, 52, 15, CREAM, width=p.w(1.0))
    p.line([(22, 66), (64, 66)], CREAM, p.w(1.0))


def g_store(p: Pen):
    p.rrect(14, 28, 66, 68, 10, CREAM)
    p.arc(40, 30, 15, 180, 360, COPPER, p.w(1.15))
    p.line([(14, 40), (66, 40)], BORDER, p.w(0.7))


def g_video(p: Pen):
    p.rrect(9, 16, 71, 64, 14, CREAM)
    p.poly([(33, 28), (33, 52), (55, 40)], COPPER)


def g_mail(p: Pen):
    p.rrect(9, 18, 71, 62, 11, CREAM)
    p.line([(14, 24), (40, 44), (66, 24)], COPPER, p.w(1.05))


def g_folder(p: Pen):
    p.line([(15, 30), (15, 20), (34, 20), (40, 28)], COPPER, p.w(1.05))
    p.rrect(11, 28, 69, 66, 9, CREAM, fill="#2E2723")
    p.line([(11, 40), (69, 40)], COPPER, p.w(0.85))


def g_compass(p: Pen):
    p.circle(40, 40, 29, CREAM, width=p.w(1.0))
    p.poly([(50, 28), (44, 46), (30, 52), (36, 34)], COPPER)
    p.circle(40, 40, 3.2, fill=CREAM)


def g_calculator(p: Pen):
    p.rrect(17, 9, 63, 71, 9, CREAM)
    p.rrect(24, 17, 56, 30, 4, COPPER, width=p.w(0.9))
    for x, y in ((28, 41), (40, 41), (52, 41), (28, 53), (40, 53), (52, 53), (28, 64), (40, 64)):
        p.dot(x, y, 2.7, CREAM)
    p.dot(52, 59, 2.7, COPPER)
    p.line([(52, 61), (52, 66)], COPPER, p.w(0.9))


def g_downloads(p: Pen):
    p.line([(40, 10), (40, 48)], COPPER, p.w(1.35))
    p.line([(27, 36), (40, 51), (53, 36)], COPPER, p.w(1.35))
    p.line([(18, 58), (18, 68), (62, 68), (62, 58)], CREAM)


def g_cloud(p: Pen):
    p.circle(31, 40, 15, CREAM, width=p.w(1.0))
    p.circle(49, 36, 17, CREAM, width=p.w(1.0))
    p.line([(18, 54), (62, 54)], CREAM, p.w(1.0))
    p.line([(40, 66), (40, 56)], COPPER, p.w(1.1))
    p.line([(34, 61), (40, 55), (46, 61)], COPPER, p.w(1.1))


def g_wallet(p: Pen):
    p.rrect(11, 21, 69, 63, 10, CREAM)
    p.rrect(44, 34, 73, 51, 7, COPPER, width=p.w(1.0))
    p.dot(58, 42, 3.2, COPPER_HI)


def g_shield(p: Pen):
    p.closed([(40, 9), (66, 19), (62, 47), (40, 71), (18, 47), (14, 19)], CREAM, p.w(1.0))
    p.line([(29, 40), (38, 50), (53, 31)], COPPER, p.w(1.2))


def g_notes(p: Pen):
    p.rrect(15, 10, 65, 70, 9, CREAM)
    for y in (27, 39, 51):
        p.line([(26, y), (54, y)], TEXT_2, p.w(0.85))
    p.line([(26, 61), (42, 61)], COPPER, p.w(0.95))


def g_health(p: Pen):
    p.poly([(40, 68), (15, 44), (15, 28), (25, 18), (34, 19), (40, 28), (46, 19), (55, 18),
            (65, 28), (65, 44)], EMBER)
    p.line([(22, 44), (33, 44), (38, 34), (44, 52), (50, 44), (58, 44)], CREAM, p.w(0.9))


def g_radio(p: Pen):
    p.dot(40, 40, 7, COPPER)
    for r in (17, 28):
        p.arc(40, 40, r, 215, 325, CREAM, p.w(0.95))
        p.arc(40, 40, r, 35, 145, CREAM, p.w(0.95))


def g_bolt(p: Pen):
    p.poly([(46, 8), (22, 44), (38, 44), (33, 72), (59, 34), (43, 34)], COPPER)
    p.line([(46, 8), (22, 44), (38, 44), (33, 72), (59, 34), (43, 34), (46, 8)], CREAM, p.w(0.75))


def g_mic(p: Pen):
    p.rrect(31, 10, 49, 44, 9, CREAM)
    p.arc(40, 42, 19, 0, 180, COPPER, p.w(1.05))
    p.line([(40, 61), (40, 68)], CREAM)
    p.line([(29, 68), (51, 68)], CREAM)


def g_files(p: Pen):
    p.rrect(23, 8, 61, 54, 6, CREAM)
    p.line([(32, 22), (52, 22)], TEXT_2, p.w(0.8))
    p.line([(32, 32), (52, 32)], TEXT_2, p.w(0.8))
    p.rrect(15, 26, 53, 72, 6, COPPER, fill="#2A2320")
    p.line([(25, 42), (43, 42)], COPPER_HI, p.w(0.9))
    p.line([(25, 53), (43, 53)], COPPER_HI, p.w(0.9))


def g_default(p: Pen):
    for x, y in ((23, 23), (47, 23), (23, 47), (47, 47)):
        p.rrect(x, y, x + 17, y + 17, 5, CREAM, width=p.w(0.9))
    p.dot(40, 40, 4.5, COPPER)


GLYPHS = {
    "phone": g_phone, "message": g_message, "contacts": g_contacts, "camera": g_camera,
    "photos": g_photos, "settings": g_settings, "calendar": g_calendar, "clock": g_clock,
    "browser": g_browser, "maps": g_maps, "music": g_music, "weather": g_weather,
    "store": g_store, "video": g_video, "mail": g_mail, "folder": g_folder,
    "compass": g_compass, "calculator": g_calculator, "downloads": g_downloads,
    "cloud": g_cloud, "wallet": g_wallet, "shield": g_shield, "notes": g_notes,
    "health": g_health, "radio": g_radio, "bolt": g_bolt, "mic": g_mic, "files": g_files,
}

# Icon kind -> Android/EMUI package ids that should receive that artwork.
ICON_MAP = {
    "phone": ["com.android.phone", "com.android.dialer",
              "com.android.contacts.activities.DialtactsActivity"],
    "message": ["com.android.mms", "com.google.android.apps.messaging",
                "com.android.messaging", "com.whatsapp", "com.facebook.orca"],
    "contacts": ["com.android.contacts", "com.google.android.contacts"],
    "camera": ["com.android.camera", "com.huawei.camera", "com.huawei.camera2"],
    "photos": ["com.android.gallery3d", "com.huawei.photos",
               "com.google.android.apps.photos"],
    "settings": ["com.android.settings", "com.huawei.systemmanager",
                 "com.huawei.android.internal.app"],
    "calendar": ["com.android.calendar", "com.google.android.calendar"],
    "clock": ["com.android.deskclock", "com.huawei.deskclock",
              "com.google.android.deskclock"],
    "browser": ["com.huawei.browser", "com.android.chrome", "com.android.browser",
                "com.google.android.chrome"],
    "maps": ["com.google.android.apps.maps", "com.huawei.maps.app", "com.huawei.maps"],
    "music": ["com.android.mediacenter", "com.huawei.music", "com.spotify.music",
              "com.google.android.music"],
    "weather": ["com.huawei.android.totemweather", "com.huawei.android.totemweatherapp"],
    "store": ["com.huawei.appmarket", "com.android.vending"],
    "video": ["com.google.android.youtube", "com.google.android.videos",
              "com.huawei.videos", "com.netflix.mediaclient"],
    "mail": ["com.google.android.gm", "com.android.email",
             "com.microsoft.office.outlook"],
    "folder": ["com.huawei.hidisk", "com.android.documentsui"],
    "compass": ["com.huawei.compass"],
    "calculator": ["com.android.calculator2", "com.huawei.calculator"],
    "downloads": ["com.android.providers.downloads.ui"],
    "cloud": ["com.google.android.apps.docs", "com.dropbox.android", "com.huawei.cloud"],
    "wallet": ["com.huawei.wallet", "com.google.android.apps.walletnfcrel"],
    "shield": ["com.huawei.android.findmyphone", "com.huawei.trustspace",
               "com.huawei.phoneservice"],
    "notes": ["com.huawei.notepad", "com.google.android.keep"],
    "health": ["com.huawei.health", "com.huawei.bone"],
    "radio": ["com.huawei.android.FMRadio"],
    "bolt": ["com.huawei.android.thememanager", "com.huawei.android.tips",
             "com.huawei.android.hwouui"],
    "mic": ["com.huawei.soundrecorder", "com.android.soundrecorder"],
    "files": ["com.huawei.filemanager", "com.google.android.apps.nbu.files"],
}


def make_icon(kind: str, out_path: Path, size: int = 192) -> None:
    """Render one icon at 4x supersample and downscale for clean thin strokes."""
    ss = 4
    canvas = size * ss
    im = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = canvas / 192  # unit scale for the 192 design grid

    # Rounded-square plate with a faint top light, warm edge.
    d.rounded_rectangle((14 * u, 14 * u, 178 * u, 178 * u), radius=44 * u,
                        fill=ICON_PLATE, outline=ICON_EDGE, width=int(2 * u))
    sheen = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    sd.ellipse((-30 * u, -70 * u, 220 * u, 96 * u), fill=(255, 236, 214, 16))
    sheen = sheen.filter(ImageFilter.GaussianBlur(26 * u))
    plate_mask = rounded_mask((canvas, canvas), int(44 * u))
    sheen.putalpha(ImageChops.multiply(sheen.getchannel("A"), plate_mask))
    im.alpha_composite(sheen)

    # Deterministic wash so the grid is not monotonous but stays calm.
    wash = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wash)
    if kind in {"phone", "message", "music", "bolt", "wallet"}:
        wd.ellipse((30 * u, 30 * u, 162 * u, 162 * u), fill=argb(COPPER, 26))
    elif kind in {"photos", "maps", "compass", "cloud", "health"}:
        wd.rounded_rectangle((32 * u, 32 * u, 160 * u, 160 * u), radius=34 * u,
                             fill=argb(SAGE, 22))
    else:
        wd.rounded_rectangle((34 * u, 34 * u, 158 * u, 158 * u), radius=32 * u,
                             fill=(255, 246, 233, 10))
    im.alpha_composite(wash)

    pen = Pen(ImageDraw.Draw(im), int(56 * u), int(56 * u), 1.0 * u, 4.2, image=im)
    GLYPHS.get(kind, g_default)(pen)

    im.resize((size, size), Image.Resampling.LANCZOS).save(out_path, format="PNG", optimize=True)


# --- Wallpaper ---------------------------------------------------------------
def make_wallpaper(lock: bool = False) -> Image.Image:
    im = Image.new("RGB", (W, H))
    px = im.load()
    top = rgb("#0E0C0B")
    mid = rgb("#1B1715")
    low = rgb("#2C211A")
    bot = rgb("#150F0C")
    for y in range(H):
        t = y / (H - 1)
        if t < 0.45:
            k = t / 0.45
            k = k * k * (3 - 2 * k)
            c = [top[i] * (1 - k) + mid[i] * k for i in range(3)]
        elif t < 0.80:
            k = (t - 0.45) / 0.35
            c = [mid[i] * (1 - k) + low[i] * k for i in range(3)]
        else:
            k = (t - 0.80) / 0.20
            k = k * k * (3 - 2 * k)
            c = [low[i] * (1 - k) + bot[i] * k for i in range(3)]
        for x in range(W):
            px[x, y] = (round(c[0]), round(c[1]), round(c[2]))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    if lock:
        # Lockscreen: ember sits centred and lower, clear space for the clock.
        gd.ellipse((140, 1420, 940, 2120), fill=argb(COPPER, 54))
        gd.ellipse((-330, 1720, 520, 2420), fill=argb(SAGE, 30))
        gd.ellipse((620, 1840, 1290, 2450), fill=argb(COPPER_DEEP, 46))
    else:
        # Home: ember to the right and low, so widgets and labels stay legible.
        gd.ellipse((520, 1450, 1360, 2170), fill=argb(COPPER, 44))
        gd.ellipse((-360, 1700, 560, 2440), fill=argb(SAGE, 26))
        gd.ellipse((300, 1900, 1080, 2480), fill=argb(COPPER_DEEP, 38))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    im = Image.alpha_composite(im.convert("RGBA"), glow)

    # Concentric "sun path" arcs, kept entirely below the clock region.
    arcs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arcs)
    cx, cy = (760, 1900) if not lock else (540, 1930)
    for i, r in enumerate((300, 420, 545)):
        alpha = (46, 34, 24)[i]
        ad.ellipse((cx - r, cy - r, cx + r, cy + r), outline=argb(COPPER_HI, alpha), width=3)
    arcs = arcs.filter(ImageFilter.GaussianBlur(2.5))
    im = Image.alpha_composite(im, arcs)

    # Film grain + vignette, deterministic so rebuilds are byte-identical.
    rng = random.Random(20260214)
    grain = Image.new("L", (W // 3, H // 3))
    gpx = grain.load()
    for y in range(H // 3):
        for x in range(W // 3):
            gpx[x, y] = 128 + rng.randint(-26, 26)
    grain = grain.resize((W, H), Image.Resampling.BILINEAR)
    im = Image.merge("RGBA", (*im.convert("RGB").split(), Image.new("L", (W, H), 255)))
    tinted = Image.merge("RGBA", (grain, grain, grain, Image.new("L", (W, H), 14)))
    im = Image.blend(im, Image.alpha_composite(im, tinted), 0.5)

    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse((-W * 0.35, -H * 0.10, W * 1.35, H * 1.05), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(220)).point(lambda v: 255 - v)
    shade = Image.new("RGBA", (W, H), (8, 6, 5, 255))
    shade.putalpha(vig.point(lambda v: int(v * 0.62)))
    im = Image.alpha_composite(im, shade)
    return im.convert("RGB")


# --- Previews ----------------------------------------------------------------
def make_preview(home: Image.Image, lock: Image.Image, icons: dict[str, Path]) -> Image.Image:
    """Mock home screen for the Themes cover — an illustration, not a device capture."""
    screen = home.resize((540, 1140), Image.Resampling.LANCZOS).convert("RGBA")
    ov = Image.new("RGBA", screen.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    d.rounded_rectangle((28, 60, 512, 258), radius=30, fill=(28, 24, 22, 178),
                        outline=(74, 64, 57, 200), width=2)
    d.text((52, 84), "TUESDAY, 18:42", font=font(500, 13), fill=MUTED)
    d.text((52, 110), "Good evening", font=font(600, 25), fill=TEXT)
    d.text((52, 152), "Dusk settles over Accra.", font=font(400, 15), fill=TEXT_2)
    d.text((452, 108), "31°", font=font(300, 38), fill=COPPER_HI)
    d.text((452, 158), "clear", font=font(400, 12), fill=MUTED)

    items = [("Phone", "phone"), ("Messages", "message"), ("Camera", "camera"),
             ("Photos", "photos"), ("Calendar", "calendar"), ("Settings", "settings"),
             ("Browser", "browser"), ("Music", "music"), ("Maps", "maps"),
             ("Files", "files"), ("Clock", "clock"), ("Store", "store")]
    start_y, xs = 372, [76, 206, 336, 466]
    for i, (label, kind) in enumerate(items):
        row, col = divmod(i, 4)
        x, y = xs[col], start_y + row * 158
        p = icons.get(kind)
        if p:
            ov.alpha_composite(Image.open(p).convert("RGBA").resize((70, 70),
                                                                    Image.Resampling.LANCZOS),
                               (x - 35, y - 35))
        d.text((x, y + 48), label, anchor="mm", font=font(400, 13), fill=TEXT)

    d.rounded_rectangle((28, 968, 512, 1082), radius=36, fill=(28, 24, 22, 190),
                        outline=(74, 64, 57, 210), width=2)
    for i, kind in enumerate(("phone", "message", "browser", "music")):
        p = icons.get(kind)
        if p:
            ov.alpha_composite(Image.open(p).convert("RGBA").resize((70, 70),
                                                                    Image.Resampling.LANCZOS),
                               (62 + i * 120, 990))
    screen = Image.alpha_composite(screen, ov).convert("RGB")
    return frame(screen)


def make_lock_preview(lock: Image.Image) -> Image.Image:
    screen = lock.resize((540, 1140), Image.Resampling.LANCZOS).convert("RGBA")
    ov = Image.new("RGBA", screen.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.text((270, 300), "18:42", anchor="mm", font=font(300, 92), fill=TEXT)
    d.text((270, 372), "Tuesday, 14 February", anchor="mm", font=font(400, 19), fill=TEXT_2)
    d.rounded_rectangle((150, 430, 390, 486), radius=28, fill=(28, 24, 22, 160),
                        outline=(74, 64, 57, 190), width=2)
    d.text((270, 458), "31°  Clear  ·  Accra", anchor="mm", font=font(400, 15), fill=COPPER_HI)
    for i, (title, sub) in enumerate((("Messages", "Ada: are you coming?"),
                                      ("Calendar", "Team standup · 09:00"))):
        y = 806 + i * 96
        d.rounded_rectangle((40, y, 500, y + 80), radius=24, fill=(28, 24, 22, 168),
                            outline=(74, 64, 57, 190), width=2)
        d.text((64, y + 20), title, font=font(600, 16), fill=TEXT)
        d.text((64, y + 45), sub, font=font(400, 13), fill=MUTED)
    d.ellipse((246, 1058, 294, 1106), outline=COPPER, width=3)
    screen = Image.alpha_composite(screen, ov).convert("RGB")
    return frame(screen)


def frame(screen: Image.Image) -> Image.Image:
    outer = Image.new("RGB", (620, 1220), "#191513")
    d = ImageDraw.Draw(outer)
    d.rounded_rectangle((25, 18, 595, 1202), radius=58, fill="#0B0908")
    outer.paste(screen, (40, 31), rounded_mask(screen.size, 38))
    d.rounded_rectangle((40, 31, 580, 1171), radius=38, outline="#3A322E", width=2)
    return outer


# --- Package helpers ---------------------------------------------------------
def zip_folder(folder: Path, out_path: Path) -> None:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(folder).as_posix())


def xml_colors(colors: dict) -> str:
    rows = ['<?xml version="1.0" encoding="UTF-8"?>', "<hwthemes>"]
    for name, value in colors.items():
        if isinstance(value, tuple):
            tag, literal = value
        else:
            tag, literal = "color", value
        rows.append(f'  <{tag} name="{name}">{literal}</{tag}>')
    rows.append("</hwthemes>")
    return "\n".join(rows) + "\n"


def build_static_fonts(package: Path) -> None:
    """Instance the Inter variable font at each weight EMUI asks for."""
    var = TTFont(SOURCE_FONT)
    axes = {a.axisTag: a.defaultValue for a in var["fvar"].axes}
    out = package / "fonts"
    out.mkdir(parents=True, exist_ok=True)
    for weight, filename in FONT_WEIGHT_FILES.items():
        loc = dict(axes)
        loc["wght"] = weight
        if "opsz" in loc:
            loc["opsz"] = 14
        static = instantiateVariableFont(var, loc, inplace=False)
        static.save(out / filename)
        FONT_PATHS[weight] = out / filename
    shutil.copy2(OFL, out / "OFL-Inter.txt")

    card = Image.new("RGB", (500, 520), "#191514")
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 0, 499, 519), radius=0, outline=BORDER, width=2)
    cd.text((34, 40), "Vesper Sans", font=font(600, 34), fill=TEXT)
    cd.text((34, 104), "Aa Bb Cc 123", font=font(400, 30), fill=TEXT_2)
    cd.text((34, 156), "Light · Regular · Medium · Bold", font=font(400, 18), fill=MUTED)
    cd.rounded_rectangle((30, 228, 470, 296), radius=22, fill="#241F1D")
    cd.text((52, 248), "Quiet light on warm dark", font=font(500, 22), fill=COPPER_HI)
    cd.text((34, 330), "The quick brown fox jumps", font=font(400, 20), fill=TEXT_2)
    cd.text((34, 372), "0123456789 !@#$%&*()?", font=font(400, 20), fill=MUTED)
    cd.text((34, 430), "Designed for EMUI 9.1 · ANE-LX1", font=font(400, 16), fill=COPPER)
    card.save(out / "pic_font_default.jpg", quality=92)


def build_package(safe: bool) -> Path:
    tag = "safe" if safe else "full"
    root = WORK / tag
    if root.exists():
        shutil.rmtree(root)
    work = root / "src"
    package = root / "package"
    work.mkdir(parents=True)
    package.mkdir(parents=True)
    FONT_PATHS.clear()

    build_static_fonts(package)

    home = make_wallpaper(False)
    lock = make_wallpaper(True)
    (package / "wallpaper").mkdir(parents=True)
    home.save(package / "wallpaper" / "home_wallpaper_0.jpg", quality=93, optimize=True)
    home.save(package / "wallpaper" / "home_wallpaper_1.jpg", quality=93, optimize=True)
    lock.save(package / "wallpaper" / "unlock_wallpaper_0.jpg", quality=93, optimize=True)

    icon_src = work / "icon_src" / "icons"
    icon_src.mkdir(parents=True)
    icon_paths: dict[str, Path] = {}
    for kind in ICON_MAP:
        dest = icon_src / f"{kind}.png"
        make_icon(kind, dest)
        icon_paths[kind] = dest
        for package_id in ICON_MAP[kind]:
            shutil.copyfile(dest, icon_src / f"{package_id}.png")
    for fname, fill in (("icon_background_01.png", ICON_PLATE), ("icon_mask.png", "#FFFFFF"),
                        ("icon_border.png", ICON_EDGE), ("icon_shortcut.png", "#2A2320"),
                        ("icon_shortcut_mask.png", "#FFFFFF"),
                        ("icon_shortcut_arrow.png", COPPER)):
        art = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
        ad = ImageDraw.Draw(art)
        ad.rounded_rectangle((13, 13, 179, 179), radius=44, fill=fill,
                             outline=ICON_EDGE, width=2)
        art.save(icon_src / fname, optimize=True)
    zip_folder(work / "icon_src", package / "icons")

    # Launcher affordances: app-label colour and page dots.
    launcher = work / "com.huawei.android.launcher"
    (launcher / "res" / "drawable-xxhdpi").mkdir(parents=True)
    launcher_colors = {
        "workspace_app_text_color": TEXT, "workspace_app_text_shadowColor": "#00000000",
        "workspace_app_text_shadow": ("bool", "false"),
        "folder_app_text_color": TEXT, "folder_app_text_shadowColor": "#00000000",
        "folder_app_text_shadow": ("bool", "false"),
        "folder_background_simple": "#E6241F1D",
        "navigation_deskspot_current": COPPER, "navigation_deskspot_normal": "#FF6B615A",
        "clock_dynamic_icon_color": TEXT, "calendar_dynamic_date": COPPER,
        "home_pinch_in_gesture_color": COPPER, "ic_home_bg_pressed_color": "#33E29A4B",
    }
    (launcher / "theme.xml").write_text(xml_colors(launcher_colors), encoding="utf-8")
    for name, color in (("ic_allapps.png", COPPER), ("ic_allapps_pressed.png", COPPER_HI),
                        ("ic_arrow.png", MUTED)):
        art = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        ad = ImageDraw.Draw(art)
        if name.startswith("ic_allapps"):
            for x in (26, 48, 70):
                for y in (26, 48, 70):
                    ad.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)
        else:
            ad.line((30, 24, 59, 48, 30, 72), fill=color, width=7, joint="curve")
        art.save(launcher / "res" / "drawable-xxhdpi" / name, optimize=True)
    zip_folder(launcher, package / "com.huawei.android.launcher")

    if not safe:
        common = {
            "hw_title_header_background": SURFACE, "hw_title_header_text": TEXT,
            "hw_button_text": TEXT, "emui_tab_title_off": MUTED,
            "emui_tab_title_on": COPPER, "emui_list_primary_default": TEXT,
            "emui_list_separator_default": BORDER, "menuitem_default_checkedcolor": COPPER,
            "menuitem_default_uncheckedcolor": TEXT_2, "emui_text_light": TEXT,
            "emui_text_dark": TEXT, "emui_hint_foreground": MUTED,
            "emui_highlighted_text": COPPER, "emui_blue_light": COPPER_HI,
            "hw_button_pressed": "#33E29A4B", "hw_dialog_background": ELEVATED,
            "hw_popup_background": SURFACE_2, "hw_control_activated": COPPER,
            "hw_switch_on": COPPER, "hw_checkbox_checked": COPPER,
        }
        for module in ("com.android.systemui", "com.android.settings",
                       "framework-res", "framework-res-hwext"):
            d = work / module
            d.mkdir(parents=True)
            colors = dict(common)
            if module == "com.android.systemui":
                colors.update({
                    "status_bar_background": BG, "notification_panel_background": SURFACE,
                    "notification_text_color": TEXT, "qs_tile_active": COPPER,
                    "qs_tile_inactive": SURFACE_2, "qs_tile_text": TEXT,
                })
            (d / "theme.xml").write_text(xml_colors(colors), encoding="utf-8")
            zip_folder(d, package / module)

    unlock = package / "unlock"
    unlock.mkdir()
    (unlock / "theme.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<HWTheme>\n"
        f'  <item maxHeight="{H}" />\n'
        '  <item style="amazing" />\n'
        "</HWTheme>\n",
        encoding="utf-8",
    )

    preview_dir = package / "preview"
    preview_dir.mkdir()
    home_preview = make_preview(home, lock, icon_paths)
    lock_preview = make_lock_preview(lock)
    home_preview.save(preview_dir / "cover.jpg", quality=91, optimize=True)
    lock_preview.save(preview_dir / "preview_unlock_0.jpg", quality=91, optimize=True)
    home_preview.save(preview_dir / "preview_wallpaper_0.jpg", quality=91, optimize=True)
    home_preview.save(preview_dir / "preview_icons_0.jpg", quality=91, optimize=True)
    home_preview.save(PREVIEW, quality=93, optimize=True)
    lock_preview.save(LOCK_PREVIEW, quality=93, optimize=True)

    title = "Vesper" if not safe else "Vesper Safe"
    description = f'''<?xml version="1.0" encoding="UTF-8"?>
<HwTheme>
    <title>{title}</title>
    <title-cn>{title}</title-cn>
    <author>AnneControl</author>
    <designer>AnneControl</designer>
    <screen>FHD</screen>
    <version>1.0.0</version>
    <font>Vesper Sans</font>
    <font-cn>Vesper Sans</font-cn>
</HwTheme>
'''
    (package / "description.xml").write_text(description, encoding="utf-8")

    out_path = OUT_SAFE if safe else OUT_FULL
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package).as_posix())
    with zipfile.ZipFile(out_path) as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError("Bad archive member: " + bad)
    return out_path


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    for safe in (False, True):
        out = build_package(safe)
        print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
    print(f"Wrote {PREVIEW} ({PREVIEW.stat().st_size:,} bytes)")
    print(f"Wrote {LOCK_PREVIEW} ({LOCK_PREVIEW.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
