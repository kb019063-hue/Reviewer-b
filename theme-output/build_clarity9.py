#!/usr/bin/env python3
"""Build an original, hand-designed EMUI 9.1 theme package (no AI-generated art).

Requires Pillow and fonttools. The Inter font is distributed under SIL OFL; its
license and source variable font live in source/fonts/.
"""
from __future__ import annotations

import io
import math
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent
SOURCE_FONT = ROOT / "source" / "fonts" / "Inter-Variable.ttf"
OUT = ROOT / "Clarity9-EMUI91.hwt"
PREVIEW = ROOT / "Clarity9-preview.png"
WORK = ROOT / ".work"

W, H = 1080, 2280
INK = "#1D2939"
MUTED = "#75849A"
BLUE = "#3978E5"
PALE = "#EAF2FF"

FONT_PATHS = {}


def font(path, size):
    return ImageFont.truetype(str(path), size)


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


def make_wallpaper(lock=False):
    im = Image.new("RGB", (W, H))
    px = im.load()
    top = (248, 250, 255) if not lock else (239, 245, 255)
    bottom = (222, 234, 251) if not lock else (205, 224, 250)
    for y in range(H):
        t = y / (H - 1)
        # A soft, uninterrupted cool-white gradient, drawn deterministically.
        t = t * t * (3 - 2 * t)
        c = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = c

    # Hand-built translucent glass forms, intentionally kept below the clock area.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    if lock:
        gd.ellipse((230, 1010, 1120, 1900), fill=(90, 151, 238, 64))
        gd.ellipse((-360, 1450, 570, 2380), fill=(177, 203, 244, 88))
    else:
        gd.ellipse((590, 1180, 1320, 1910), fill=(117, 166, 238, 50))
        gd.ellipse((-340, 1450, 620, 2410), fill=(175, 205, 247, 76))
    glow = glow.filter(ImageFilter.GaussianBlur(92))
    im = Image.alpha_composite(im.convert("RGBA"), glow)
    shapes = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shapes)
    sd.ellipse((525, 1460, 1135, 2070), fill=(255, 255, 255, 35), outline=(255, 255, 255, 88), width=3)
    sd.ellipse((-170, 1690, 535, 2395), fill=(255, 255, 255, 30), outline=(255, 255, 255, 64), width=3)
    shapes = shapes.filter(ImageFilter.GaussianBlur(3))
    im = Image.alpha_composite(im, shapes).convert("RGB")
    return im


def glyph(draw, kind, xy, scale=1, color=INK, accent=BLUE, width=9):
    ox, oy = xy
    s = scale
    w = max(3, int(width * s))

    def pt(a, b):
        return int(ox + a * s), int(oy + b * s)

    def line(points, fill=color, joint="curve", wd=w):
        draw.line([pt(a, b) for a, b in points], fill=fill, width=wd, joint=joint)

    def box(coords, outline=color, fill=None, radius=0, wd=w):
        x1, y1, x2, y2 = coords
        c = (int(ox+x1*s), int(oy+y1*s), int(ox+x2*s), int(oy+y2*s))
        r = int(radius*s)
        if r:
            draw.rounded_rectangle(c, radius=r, outline=outline, fill=fill, width=wd)
        else:
            draw.rectangle(c, outline=outline, fill=fill, width=wd)

    def ellipse(coords, outline=color, fill=None, wd=w):
        x1, y1, x2, y2 = coords
        c = (int(ox+x1*s), int(oy+y1*s), int(ox+x2*s), int(oy+y2*s))
        draw.ellipse(c, outline=outline, fill=fill, width=wd)

    def polygon(points, fill=None, outline=None):
        draw.polygon([pt(a, b) for a, b in points], fill=fill, outline=outline)

    def arc(coords, start, end, fill=color, wd=w):
        x1, y1, x2, y2 = coords
        c = (int(ox+x1*s), int(oy+y1*s), int(ox+x2*s), int(oy+y2*s))
        draw.arc(c, start, end, fill=fill, width=wd)

    if kind in ("phone", "call"):
        line([(26, 10), (18, 20), (24, 38), (38, 53), (56, 60), (66, 51)], accent, wd=w + 2)
        line([(25, 10), (17, 17), (28, 30)], color)
        line([(54, 47), (67, 53), (61, 63)], color)
    elif kind in ("message", "mail"):
        box((8, 12, 72, 58), outline=accent, radius=20)
        line([(22, 60), (15, 72), (34, 61)], accent)
        for xx in (24, 39, 54): ellipse((xx, 32, xx + 4, 36), fill=color, outline=color, wd=1)
    elif kind == "contacts":
        ellipse((29, 10, 51, 32), outline=accent)
        arc((13, 28, 67, 78), 190, 350, fill=color, wd=w)
        line([(20, 55), (20, 67), (60, 67), (60, 55)], color)
    elif kind in ("camera", "photos"):
        box((8, 18, 72, 62), outline=accent, radius=12)
        line([(21, 18), (27, 10), (45, 10), (52, 18)], color)
        ellipse((27, 27, 53, 53), outline=color, wd=w)
        if kind == "photos":
            ellipse((34, 34, 46, 46), fill=accent, outline=accent, wd=1)
    elif kind == "settings":
        ellipse((20, 20, 60, 60), outline=accent, wd=w + 1)
        ellipse((33, 33, 47, 47), outline=color, wd=w)
        for a in range(0, 360, 45):
            ang = math.radians(a)
            line([(40 + math.cos(ang)*23, 40 + math.sin(ang)*23),
                  (40 + math.cos(ang)*34, 40 + math.sin(ang)*34)], color, wd=w)
    elif kind == "calendar":
        box((11, 15, 69, 67), outline=accent, radius=10)
        line([(11, 28), (69, 28)], accent)
        line([(25, 9), (25, 22)], color)
        line([(55, 9), (55, 22)], color)
        for xx, yy in ((24,39),(40,39),(56,39),(24,54),(40,54)):
            ellipse((xx-2,yy-2,xx+2,yy+2), fill=color, outline=color, wd=1)
    elif kind == "clock":
        ellipse((9, 9, 71, 71), outline=accent)
        line([(40, 20), (40, 41), (55, 49)], color)
        ellipse((36, 37, 44, 45), fill=accent, outline=accent, wd=1)
    elif kind == "browser":
        box((8, 12, 72, 68), outline=accent, radius=13)
        line([(8, 28), (72, 28)], accent)
        for xx in (18, 27, 36): ellipse((xx, 18, xx+3, 21), fill=BLUE, outline=BLUE, wd=1)
        line([(22, 51), (37, 37), (52, 52), (61, 43)], color)
    elif kind == "maps":
        line([(14, 18), (33, 11), (50, 20), (67, 12), (67, 61), (49, 69), (32, 60), (14, 68), (14, 18)], accent)
        line([(32, 16), (32, 60)], color)
        line([(50, 20), (50, 68)], color)
        ellipse((34, 24, 49, 39), fill=BLUE, outline=BLUE, wd=1)
        ellipse((39, 29, 44, 34), fill="#FFFFFF", outline="#FFFFFF", wd=1)
    elif kind == "music":
        line([(50, 14), (50, 51), (31, 56)], accent, wd=w + 2)
        line([(50, 14), (67, 10), (67, 45), (50, 49)], accent, wd=w + 2)
        ellipse((17, 48, 37, 66), fill=color, outline=color, wd=1)
        ellipse((48, 43, 68, 61), fill=color, outline=color, wd=1)
    elif kind == "weather":
        ellipse((20, 32, 48, 60), outline=accent, fill="#F8FBFF")
        ellipse((34, 19, 62, 50), outline=accent, fill="#F8FBFF")
        line([(18, 58), (62, 58)], color)
        line([(25, 70), (55, 70)], accent)
    elif kind == "store":
        line([(20, 18), (40, 10), (60, 18)], accent)
        line([(20, 18), (40, 70), (60, 18)], color)
        line([(27, 36), (53, 36)], accent)
        line([(33, 51), (47, 51)], color)
    elif kind == "video":
        box((9, 15, 71, 65), outline=accent, radius=15)
        polygon([(33, 27), (33, 53), (54, 40)], fill=BLUE)
    elif kind == "mailicon":
        box((9, 17, 71, 63), outline=accent, radius=10)
        line([(13, 22), (40, 44), (67, 22)], color)
    elif kind == "folder":
        box((10, 22, 70, 64), outline=accent, fill="#DBEAFE", radius=10)
        line([(13, 25), (13, 16), (35, 16), (42, 24)], accent)
    elif kind == "compass":
        ellipse((10, 10, 70, 70), outline=accent)
        polygon([(48, 24), (41, 45), (22, 56), (30, 36)], fill=BLUE)
        ellipse((37, 37, 43, 43), fill="#FFFFFF", outline="#FFFFFF", wd=1)
    elif kind == "calculator":
        box((18, 8, 62, 72), outline=accent, radius=8)
        box((25, 16, 55, 29), outline=accent, radius=4)
        for xx, yy in ((27,39),(40,39),(53,39),(27,53),(40,53),(53,53),(27,66),(40,66),(53,66)):
            ellipse((xx-2,yy-2,xx+2,yy+2), fill=color, outline=color, wd=1)
    elif kind == "downloads":
        line([(40, 10), (40, 48)], accent, wd=w + 2)
        line([(25, 34), (40, 50), (55, 34)], accent, wd=w + 2)
        line([(16, 62), (64, 62), (64, 70), (16, 70), (16, 62)], color)
    elif kind == "cloud":
        ellipse((16, 31, 48, 62), outline=accent, fill="#F8FBFF")
        ellipse((31, 18, 61, 55), outline=accent, fill="#F8FBFF")
        line([(18, 57), (63, 57)], color)
        line([(40, 30), (40, 52), (32, 45)], accent)
        line([(40, 52), (48, 45)], accent)
    elif kind == "wallet":
        box((12, 19, 68, 64), outline=accent, radius=9)
        box((42, 31, 71, 52), outline=accent, radius=8)
        ellipse((50, 39, 57, 46), fill=BLUE, outline=BLUE, wd=1)
    elif kind == "shield":
        polygon([(40, 10), (65, 20), (62, 47), (40, 70), (18, 47), (15, 20)], outline=accent, fill="#E8F1FF")
        line([(27, 40), (37, 50), (55, 30)], color, wd=w+1)
    elif kind == "notes":
        box((15, 10, 65, 70), outline=accent, radius=9, fill="#FFFDF7")
        for yy in (27, 40, 53): line([(26, yy), (54, yy)], MUTED, wd=max(2,w-3))
    elif kind == "sun":
        ellipse((26, 26, 54, 54), outline=accent, fill="#FFD877")
        for a in range(0, 360, 45):
            ang = math.radians(a)
            line([(40+math.cos(ang)*21,40+math.sin(ang)*21),(40+math.cos(ang)*30,40+math.sin(ang)*30)], BLUE, wd=max(3,w-2))
    elif kind == "heart":
        polygon([(40, 68), (13, 42), (13, 27), (22, 17), (33, 17), (40, 27), (47, 17), (58, 17), (67, 27), (67, 42)], fill="#F67D93")
    elif kind == "camera_flash":
        box((8, 20, 72, 62), outline=accent, radius=10)
        polygon([(27, 33), (38, 33), (32, 45), (43, 45), (26, 58), (31, 46), (22, 46)], fill=BLUE)
    else:
        for xx, yy in ((21,21),(47,21),(21,47),(47,47)):
            box((xx, yy, xx+17, yy+17), outline=accent, radius=5, wd=max(3,w-2))
        ellipse((35, 35, 45, 45), fill=BLUE, outline=BLUE, wd=1)

def make_icon(kind, output, variant=0):
    size = 192
    scale = 2
    im = Image.new("RGBA", (size*scale, size*scale), (0,0,0,0))
    d = ImageDraw.Draw(im)
    # Rounded-square icon treatment, with a white surface and cool outline.
    d.rounded_rectangle((13*scale, 13*scale, 179*scale, 179*scale), radius=43*scale,
                        fill="#F8FAFD", outline="#DFE8F4", width=2*scale)
    # A restrained wash behind the glyph; deterministic variation by icon category.
    if variant % 4 == 1:
        d.ellipse((28*scale, 28*scale, 164*scale, 164*scale), fill="#EAF2FF")
    elif variant % 4 == 2:
        d.rounded_rectangle((29*scale, 29*scale, 163*scale, 163*scale), radius=35*scale, fill="#F1F6FF")
    glyph(d, kind, (56*scale, 56*scale), 1.0*scale, color=INK, accent=BLUE, width=4)
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    im.save(output, format="PNG", optimize=True)


def make_preview(home_wallpaper, icon_paths):
    # A hand-composed mock home screen for the Themes preview, not a screenshot.
    scale = 0.5
    canvas = home_wallpaper.copy().resize((540, 1140), Image.Resampling.LANCZOS).convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    # Mock status strip and soft translucent widget.
    d.rounded_rectangle((28, 56, 512, 252), radius=29, fill=(255,255,255,128), outline=(255,255,255,180), width=2)
    f_regular = font(FONT_PATHS[400], 18)
    f_medium = font(FONT_PATHS[500], 22)
    f_small = font(FONT_PATHS[400], 13)
    d.text((51, 76), "MONDAY, 9:41", font=f_small, fill="#75849A")
    d.text((51, 104), "Good morning", font=f_medium, fill=INK)
    d.text((51, 148), "A calm, clear start.", font=f_regular, fill="#53657E")
    d.text((430, 96), "24°", font=font(FONT_PATHS[400], 33), fill=BLUE)

    items = [
        ("Phone", "phone"), ("Messages", "message"), ("Camera", "camera"), ("Photos", "photos"),
        ("Calendar", "calendar"), ("Settings", "settings"), ("Browser", "browser"), ("Music", "music"),
        ("Maps", "maps"), ("Files", "folder"), ("Clock", "clock"), ("Store", "store"),
    ]
    by_kind = {}
    for path, kind in icon_paths:
        by_kind.setdefault(kind, path)
    start_y = 344
    xs = [74, 204, 334, 464]
    for index, (label, kind) in enumerate(items):
        row, col = divmod(index, 4)
        x, y = xs[col], start_y + row*150
        p = by_kind.get(kind)
        if p:
            icon = Image.open(p).convert("RGBA").resize((68,68), Image.Resampling.LANCZOS)
            overlay.alpha_composite(icon, (x-34, y-34))
        d.text((x, y+43), label, anchor="mm", font=f_small, fill=INK)
    # Light translucent dock.
    d.rounded_rectangle((28, 956, 512, 1068), radius=35, fill=(255,255,255,154), outline=(255,255,255,190), width=2)
    for i, kind in enumerate(("phone", "message", "browser", "music")):
        p = by_kind.get(kind)
        if p:
            icon = Image.open(p).convert("RGBA").resize((68,68), Image.Resampling.LANCZOS)
            overlay.alpha_composite(icon, (62+i*119, 978))
    canvas = Image.alpha_composite(canvas, overlay).convert("RGB")
    # Phone bezel, for a compact store-like preview.
    frame = Image.new("RGB", (620, 1220), "#E8EDF5")
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle((25, 18, 595, 1202), radius=58, fill="#15243A")
    screen = canvas.resize((540,1140), Image.Resampling.LANCZOS)
    mask = rounded_mask(screen.size, 38)
    frame.paste(screen, (40,31), mask)
    return frame


def zip_folder(folder, out_path, compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(out_path, "w", compression=compression, compresslevel=8) as zf:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(folder).as_posix())


def xml_colors(colors):
    rows = ['<?xml version="1.0" encoding="UTF-8"?>', '<hwthemes>']
    for name, value in colors.items():
        if isinstance(value, tuple):
            tag, literal = value
        else:
            tag, literal = "color", value
        rows.append(f'  <{tag} name="{name}">{literal}</{tag}>')
    rows.append('</hwthemes>')
    return "\n".join(rows) + "\n"


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    work = WORK / "src"
    package = WORK / "package"
    if WORK.exists():
        import shutil
        shutil.rmtree(WORK)
    work.mkdir(parents=True)
    package.mkdir(parents=True)
    FONT_PATHS.clear()

    variable = TTFont(SOURCE_FONT)
    for weight in (300, 400, 500, 600, 700):
        static = instantiateVariableFont(variable, {"wght": weight, "opsz": 14}, inplace=False)
        filename = {300:"Roboto-Light.ttf", 400:"Roboto-Regular.ttf", 500:"Roboto-Medium.ttf",
                    600:"Roboto-SemiBold.ttf", 700:"Roboto-Bold.ttf"}[weight]
        target = package / "fonts" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        static.save(target)
        FONT_PATHS[weight] = target
    (package / "fonts" / "pic_font_default.jpg").parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(ROOT / "source" / "fonts" / "OFL-Inter.txt", package / "fonts" / "OFL-Inter.txt")
    font_card = Image.new("RGB", (500, 520), "#F7F9FC")
    fdraw = ImageDraw.Draw(font_card)
    fdraw.text((34, 42), "Clarity Sans", font=font(FONT_PATHS[600], 34), fill=INK)
    fdraw.text((34, 106), "Aa Bb Cc 123", font=font(FONT_PATHS[400], 29), fill="#53657E")
    fdraw.text((34, 156), "Light · Regular · Medium · Bold", font=font(FONT_PATHS[400], 19), fill=MUTED)
    fdraw.rounded_rectangle((30, 230, 470, 296), radius=22, fill="#E8F0FF")
    fdraw.text((52, 248), "A clear, quiet interface", font=font(FONT_PATHS[500], 24), fill=BLUE)
    font_card.save(package / "fonts" / "pic_font_default.jpg", quality=92)

    home = make_wallpaper(False)
    lock = make_wallpaper(True)
    (package / "wallpaper").mkdir(parents=True)
    home.save(package / "wallpaper" / "home_wallpaper_0.jpg", quality=93, optimize=True)
    home.save(package / "wallpaper" / "home_wallpaper_1.jpg", quality=93, optimize=True)
    lock.save(package / "wallpaper" / "unlock_wallpaper_0.jpg", quality=93, optimize=True)

    icon_map = {
        "phone": ["com.android.phone", "com.android.dialer", "com.android.contacts.activities.DialtactsActivity"],
        "message": ["com.android.mms", "com.google.android.apps.messaging", "com.android.messaging", "com.facebook.orca", "com.whatsapp"],
        "contacts": ["com.android.contacts", "com.google.android.contacts"],
        "camera": ["com.android.camera", "com.huawei.camera"],
        "photos": ["com.android.gallery3d", "com.google.android.apps.photos", "com.huawei.photos"],
        "settings": ["com.android.settings", "com.huawei.systemmanager"],
        "calendar": ["com.android.calendar", "com.google.android.calendar"],
        "clock": ["com.android.deskclock", "com.google.android.deskclock", "com.huawei.deskclock"],
        "browser": ["com.android.chrome", "com.huawei.browser", "com.android.browser", "com.google.android.chrome"],
        "maps": ["com.google.android.apps.maps", "com.huawei.maps.app"],
        "music": ["com.android.mediacenter", "com.google.android.music", "com.spotify.music"],
        "weather": ["com.huawei.android.totemweather", "com.huawei.android.totemweatherapp"],
        "store": ["com.android.vending", "com.huawei.appmarket"],
        "video": ["com.google.android.youtube", "com.google.android.videos", "com.netflix.mediaclient"],
        "mailicon": ["com.google.android.gm", "com.android.email", "com.microsoft.office.outlook"],
        "folder": ["com.android.documentsui", "com.huawei.hidisk", "com.google.android.apps.docs"],
        "compass": ["com.huawei.compass"],
        "calculator": ["com.android.calculator2", "com.huawei.calculator"],
        "downloads": ["com.android.providers.downloads.ui"],
        "cloud": ["com.dropbox.android", "com.google.android.apps.docs"],
        "wallet": ["com.google.android.apps.walletnfcrel", "com.huawei.wallet"],
        "shield": ["com.huawei.android.findmyphone", "com.huawei.trustspace"],
        "notes": ["com.google.android.keep", "com.huawei.notepad"],
        "sun": ["com.huawei.android.FMRadio"],
        "heart": ["com.huawei.health", "com.huawei.bone"],
        "camera_flash": ["com.huawei.android.thememanager", "com.huawei.android.tips"],
    }
    icon_src = work / "icon_src"
    (icon_src / "icons").mkdir(parents=True)
    icon_paths = []
    for index, (kind, packages) in enumerate(icon_map.items()):
        for package_id in packages:
            dest = icon_src / "icons" / (package_id + ".png")
            make_icon(kind, dest, index)
            icon_paths.append((dest, kind))
    # Original mask/backplate assets; launcher can apply these to unmapped apps.
    for fname, fill in (("icon_background_01.png", "#F8FAFD"), ("icon_mask.png", "#FFFFFF"),
                        ("icon_border.png", "#DCE7F5"), ("icon_shortcut.png", "#EAF2FF"),
                        ("icon_shortcut_mask.png", "#FFFFFF"), ("icon_shortcut_arrow.png", "#3978E5")):
        img = Image.new("RGBA", (192,192), (0,0,0,0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((13,13,179,179), radius=43, fill=fill, outline="#DCE7F5", width=2)
        img.save(icon_src / "icons" / fname, optimize=True)
    zip_folder(icon_src, package / "icons")

    # Theme colors: bright surfaces, slate text and a restrained blue accent.
    common_colors = {
        "hw_title_header_background":"#FFF8FAFD", "hw_title_header_text":"#FF1D2939",
        "hw_button_text":"#FF1D2939", "emui_tab_title_off":"#FF75849A",
        "emui_tab_title_on":"#FF3978E5", "emui_list_primary_default":"#FF1D2939",
        "emui_list_separator_default":"#FFE7EDF5", "menuitem_default_checkedcolor":"#FF3978E5",
        "menuitem_default_uncheckedcolor":"#FF53657E", "emui_text_light":"#FFFFFFFF",
        "emui_text_dark":"#FF1D2939", "emui_hint_foreground":"#FF75849A",
        "emui_highlighted_text":"#FF3978E5", "emui_blue_light":"#FF6A9AF0",
        "hw_button_pressed":"#FFE7F0FF", "hw_dialog_background":"#FFF8FAFD",
        "hw_popup_background":"#FFFFFFFF", "hw_control_activated":"#FF3978E5",
        "hw_switch_on":"#FF3978E5", "hw_checkbox_checked":"#FF3978E5",
    }
    launcher = work / "com.huawei.android.launcher"
    (launcher / "res" / "drawable-xxhdpi").mkdir(parents=True)
    launcher_colors = dict(common_colors)
    launcher_colors.update({
        "folder_background_simple":"#F2F6FC", "workspace_app_text_color":"#FF1D2939",
        "workspace_app_text_shadowColor":"#00FFFFFF", "workspace_app_text_shadow":("bool", "false"),
        "folder_app_text_color":"#FF1D2939", "folder_app_text_shadowColor":"#00FFFFFF",
        "folder_app_text_shadow":("bool", "false"), "navigation_deskspot_current":"#FF3978E5",
        "navigation_deskspot_normal":"#FFAAB7C9", "clock_dynamic_icon_color":"#FF1D2939",
        "calendar_dynamic_date":"#FF3978E5", "home_pinch_in_gesture_color":"#FF3978E5",
        "ic_home_bg_pressed_color":"#333978E5", "checked":"#FF3978E5",
    })
    (launcher / "theme.xml").write_text(xml_colors(launcher_colors), encoding="utf-8")
    # Keep a small set of original, low-risk launcher affordances.
    for name, color in (("ic_allapps.png", "#3978E5"), ("ic_allapps_pressed.png", "#6A9AF0"),
                        ("ic_arrow.png", "#75849A")):
        art = Image.new("RGBA", (96,96), (0,0,0,0))
        ad = ImageDraw.Draw(art)
        if name.startswith("ic_allapps"):
            for xx in (24,48,72):
                for yy in (24,48,72):
                    ad.ellipse((xx-5,yy-5,xx+5,yy+5), fill=color)
        else:
            ad.line((29,24,58,48,29,72), fill=color, width=7, joint="curve")
        art.save(launcher / "res" / "drawable-xxhdpi" / name, optimize=True)
    zip_folder(launcher, package / "com.huawei.android.launcher")

    for module in ("com.android.systemui", "com.android.settings", "framework-res", "framework-res-hwext"):
        d = work / module
        d.mkdir(parents=True)
        colors = dict(common_colors)
        if module == "com.android.systemui":
            colors.update({"status_bar_background":"#FFF8FAFD", "notification_panel_background":"#FFF8FAFD",
                           "notification_text_color":"#FF1D2939", "qs_tile_active":"#FF3978E5",
                           "qs_tile_inactive":"#FFE7EDF5", "qs_tile_text":"#FF1D2939"})
        (d / "theme.xml").write_text(xml_colors(colors), encoding="utf-8")
        zip_folder(d, package / module)

    unlock = package / "unlock"
    unlock.mkdir()
    (unlock / "theme.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<HWTheme>\n  <item maxHeight="2280" />\n  <item style="amazing" />\n</HWTheme>\n',
        encoding="utf-8")

    # Previews: original mockups, deliberately labeled as design previews rather than device captures.
    preview_dir = package / "preview"
    preview_dir.mkdir()
    preview = make_preview(home, icon_paths)
    preview.save(preview_dir / "cover.jpg", quality=91, optimize=True)
    preview.save(preview_dir / "preview_unlock_0.jpg", quality=91, optimize=True)
    preview.save(preview_dir / "preview_wallpaper_0.jpg", quality=91, optimize=True)
    preview.save(preview_dir / "preview_icons_0.jpg", quality=91, optimize=True)
    preview.save(PREVIEW, quality=93, optimize=True)

    description = '''<?xml version="1.0" encoding="UTF-8"?>
<HwTheme>
    <title>Clarity 9</title>
    <title-cn>Clarity 9</title-cn>
    <author>AnneControl</author>
    <designer>AnneControl</designer>
    <screen>FHD</screen>
    <version>1.0.0</version>
    <font>Clarity Sans</font>
    <font-cn>Clarity Sans</font-cn>
</HwTheme>
'''
    (package / "description.xml").write_text(description, encoding="utf-8")

    # The theme archive is itself a ZIP file with Huawei's .hwt extension.
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(package).as_posix())
    with zipfile.ZipFile(OUT, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError("Bad archive member: " + bad)
    print("Wrote", OUT, f"({OUT.stat().st_size:,} bytes)")
    print("Wrote", PREVIEW, f"({PREVIEW.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
