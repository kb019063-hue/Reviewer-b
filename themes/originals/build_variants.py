#!/usr/bin/env python3
"""Build four original EMUI 9.1 (ANE-LX1 / P20 Lite) themes — no AI artwork.

Every visual is drawn programmatically here: smooth multi-stop gradient
wallpapers with glow/ribbon/star accents, and 14 launcher icons per theme.
Package structure matches a known-working EMUI 9.1 .hwt (see
themes/pura-inspired), with two fixes learned from on-device feedback:

  * NO icon_mask in the launcher module — masks force every unmapped app
    (Photos, WhatsApp, ...) into a square plate. Without them, unmapped apps
    keep their native icons and our own icons are already rounded squares.
  * Opaque quick-settings / notification shade background with readable text
    colours per theme, instead of a transparent panel over the wallpaper.

v2 fixes (from reviewing the v1 renders):

  * Icon artwork was drawn around (96, 96) instead of the canvas centre, so
    every themed icon sat in the top-left quadrant. Now centred.
  * Icon plates are full-bleed squircles the size of native icons (the old
    168 px plate with a transparent margin looked smaller and "boxed").
  * 8-digit colours are Android #AARRGGBB; the preview code read the alpha
    byte as red, which produced the red sheet. Parsing is now ARGB-aware.
  * Aurora uses soft undulating curtains instead of zigzag polylines.
  * Previews are home-screen mockups built from the real wallpaper and icons.

Requires Pillow.
"""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED, ZipInfo
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageChops, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'pura-inspired' / 'base'  # real EMUI 9.1 unlock skeleton
S = 4
ICON = 256
W, H = 1080, 2280

# ---------------------------------------------------------------- helpers ---


def hex2rgb(h):
    """'#RRGGBB' -> (r,g,b). 8-digit strings are Android '#AARRGGBB' and the
    alpha byte is dropped (the old code read the alpha as red: red sheets)."""
    h = h.lstrip('#')
    if len(h) == 8:
        h = h[2:]
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(c):
    return '#%02X%02X%02X' % c[:3]


def blend(c1, c2, t):
    a, b = hex2rgb(c1) if isinstance(c1, str) else c1, hex2rgb(c2) if isinstance(c2, str) else c2
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rgba(c, a=255):
    return (hex2rgb(c) if isinstance(c, str) else c) + (a,)


def zip_entry(arc, name, data, method=ZIP_DEFLATED):
    zi = ZipInfo(name, date_time=(2026, 11, 12, 12, 0, 0))
    zi.compress_type = method
    zi.create_system = 0
    arc.writestr(zi, data)


def dir_entry(arc, name):
    zip_entry(arc, name if name.endswith('/') else name + '/', b'', ZIP_STORED)


def module_zip(files):
    b = BytesIO()
    with ZipFile(b, 'w', ZIP_DEFLATED) as z:
        for name, data in files:
            zip_entry(z, name, data)
    return b.getvalue()


def jpg(im, quality=90):
    b = BytesIO()
    im.convert('RGB').save(b, 'JPEG', quality=quality, optimize=True)
    return b.getvalue()


def png(im):
    b = BytesIO()
    im.save(b, 'PNG', optimize=True)
    return b.getvalue()


# ------------------------------------------------------------- wallpapers ---


def gradient(size, stops, angle_deg=90):
    """Smooth multi-stop linear gradient: computed at low res, upscaled."""
    import math
    w, h = size
    lw, lh = max(2, w // 24), max(2, h // 24)
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    cx, cy = (lw - 1) / 2, (lh - 1) / 2
    proj = [( (x - cx) * dx + (y - cy) * dy ) for y in range(lh) for x in range(lw)]
    pmin, pmax = min(proj), max(proj)
    img = Image.new('RGB', (lw, lh))
    px = img.load()
    for i, p in enumerate(proj):
        t = 0.0 if pmax == pmin else (p - pmin) / (pmax - pmin)
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                px[i % lw, i // lw] = blend(c0, c1, f)
                break
        else:
            px[i % lw, i // lw] = hex2rgb(stops[-1][1])
    return img.resize(size, Image.Resampling.LANCZOS)


def glow_blob(base, box, color, alpha, blur):
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse(box, fill=hex2rgb(color) + (alpha,))
    ov = ov.filter(ImageFilter.GaussianBlur(blur))
    return ImageChops.screen(base.convert('RGB'), ov.convert('RGB')).convert('RGB')


def ribbon(base, points, color, width, alpha, blur):
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.line([(int(x), int(y)) for x, y in points], fill=hex2rgb(color) + (alpha,),
           width=width, joint='curve')
    ov = ov.filter(ImageFilter.GaussianBlur(blur))
    return ImageChops.screen(base.convert('RGB'), ov.convert('RGB')).convert('RGB')


def stars(base, n, seed, color='#FFFFFF', max_alpha=200, size=(1, 3)):
    import random
    rng = random.Random(seed)
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for _ in range(n):
        x, y = rng.randrange(base.width), rng.randrange(base.height)
        r = rng.randint(*size)
        a = rng.randrange(40, max_alpha)
        d.ellipse((x, y, x + r, y + r), fill=hex2rgb(color) + (a,))
    return Image.alpha_composite(base.convert('RGBA'), ov).convert('RGB')


def rings(base, center, radii, color, alpha, width=6):
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx, cy = center
    for r in radii:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=hex2rgb(color) + (alpha,), width=width)
    return Image.alpha_composite(base.convert('RGBA'), ov).convert('RGB')


def pinstripes(base, spacing=56, color='#FFFFFF', alpha=7, angle=-30):
    import math
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    a = math.radians(angle)
    length = int((base.width + base.height) * 1.5)
    cx, cy = base.width // 2, base.height // 2
    for i in range(-length, length, spacing):
        x0 = cx + i * math.cos(a) - length * math.sin(a)
        y0 = cy + i * math.sin(a) + length * math.cos(a)
        x1 = cx + i * math.cos(a) + length * math.sin(a)
        y1 = cy + i * math.sin(a) - length * math.cos(a)
        d.line((x0, y0, x1, y1), fill=hex2rgb(color) + (alpha,), width=2)
    return Image.alpha_composite(base.convert('RGBA'), ov).convert('RGB')


def curtain(base, y0, amp, wavelen, phase, width, color, alpha, blur):
    """One soft aurora curtain: a gently undulating band, not a zigzag."""
    import math
    pts = [(x, y0 + amp * math.sin(2 * math.pi * x / wavelen + phase))
           for x in range(-80, W + 120, 30)]
    return ribbon(base, pts, color, width, alpha, blur)


def make_wallpaper(spec):
    kind = spec['wall']
    if kind == 'aurora':
        w = gradient((W, H), [(0, '#050818'), (0.38, '#15123A'), (0.70, '#0E2F45'), (1, '#07222E')], 100)
        w = glow_blob(w, (-300, 900, 1400, 1700), '#1E3A8A', 45, 260)
        w = curtain(w, 1180, 120, 1300, 0.4, 210, '#2DD4BF', 50, 90)
        w = curtain(w, 1320, 150, 1100, 2.2, 150, '#818CF8', 42, 80)
        w = curtain(w, 1450, 110, 1600, 1.1, 90, '#6EE7B7', 36, 60)
        w = curtain(w, 1080, 90, 900, 3.4, 60, '#A5F3FC', 22, 40)
        w = glow_blob(w, (300, 1900, 1300, 2700), '#0F766E', 60, 240)
        w = stars(w, 90, 7, max_alpha=150, size=(1, 2))
    elif kind == 'ember':
        w = gradient((W, H), [(0, '#0B0604'), (0.45, '#2A0F08'), (0.80, '#6B2110'), (1, '#1C0905')], 90)
        w = glow_blob(w, (-250, 1650, 1000, 2900), '#F97316', 95, 300)
        w = glow_blob(w, (450, 1950, 1450, 3000), '#DC2626', 50, 220)
        w = glow_blob(w, (380, 1180, 700, 1500), '#FB923C', 30, 90)  # low sun
        w = stars(w, 60, 11, color='#FFD9A0', max_alpha=130, size=(1, 2))
    elif kind == 'glacier':
        w = gradient((W, H), [(0, '#FFFFFF'), (0.55, '#EAF4FF'), (1, '#CFE6FA')], 90)
        w = glow_blob(w, (600, -300, 1700, 900), '#93C5FD', 90, 240)
        w = rings(w, (880, 420), (180, 300, 430), '#60A5FA', 60, 5)
        w = glow_blob(w, (-300, 1800, 700, 2600), '#BFDBFE', 80, 220)
    elif kind == 'mono':
        w = gradient((W, H), [(0, '#0A0A0C'), (1, '#141419')], 135)
        w = pinstripes(w)
        w = rings(w, (540, 760), (260, 420), '#FFFFFF', 36, 4)
        w = glow_blob(w, (300, 1500, 1300, 2500), '#3F3F46', 60, 240)
    else:
        raise ValueError(kind)
    return w


def make_lock_wallpaper(spec):
    """Lock screen uses the home art, except light themes get a darker variant
    so the stock white lock glyphs stay readable."""
    if spec['wall'] == 'glacier':
        w = gradient((W, H), [(0, '#0B2545'), (0.6, '#13315C'), (1, '#0A1E3A')], 100)
        w = glow_blob(w, (400, 1400, 1400, 2600), '#1D4ED8', 70, 240)
        return w
    return make_wallpaper(spec)


# ------------------------------------------------------------------ icons ---

KINDS = ['phone', 'contacts', 'messages', 'camera', 'gallery', 'settings', 'music',
         'browser', 'clock', 'calendar', 'email', 'files', 'recorder', 'appmarket']

MAPPING = {'phone': ['com.android.phone', 'com.android.dialer', 'com.android.contacts.activities.DialtactsActivity'],
           'contacts': ['com.android.contacts'],
           'messages': ['com.android.mms', 'com.google.android.apps.messaging'],
           'camera': ['com.huawei.camera', 'com.android.camera'],
           'gallery': ['com.android.gallery3d'],
           'settings': ['com.android.settings'],
           'music': ['com.android.mediacenter'],
           'browser': ['com.huawei.browser', 'com.android.browser'],
           'clock': ['com.android.deskclock'],
           'calendar': ['com.android.calendar'],
           'email': ['com.android.email', 'com.google.android.gm'],
           'files': ['com.huawei.hidisk', 'com.android.documentsui'],
           'recorder': ['com.android.soundrecorder'],
           'appmarket': ['com.huawei.appmarket']}


def icon(kind, plate, glyph):
    im = Image.new('RGBA', (ICON * S, ICON * S))
    d = ImageDraw.Draw(im)

    # Glyph coordinates were drawn around (96, 96); OFF moves them to the
    # true centre (128, 128) of the 256 px canvas.
    OFF = 32

    def box(b):
        return tuple(round((x + OFF) * S) for x in b)

    def line(points, fill, width=8):
        d.line([(int((x + OFF) * S), int((y + OFF) * S)) for x, y in points], fill=fill, width=width * S, joint='curve')

    def ellipse(b, fill=None, outline=None, width=1):
        d.ellipse(box(b), fill=fill, outline=outline, width=width * S)

    def rect(b, r, fill, outline=None, width=1):
        d.rounded_rectangle(box(b), r * S, fill=fill, outline=outline, width=width * S)

    def polygon(points, fill):
        d.polygon([(int((x + OFF) * S), int((y + OFF) * S)) for x, y in points], fill=fill)

    G = rgba(glyph)
    P = rgba(plate)
    D = rgba(blend(plate, glyph, 0.55))  # detail shade
    # Full-bleed plate, same size as native EMUI icons (no transparent margin).
    d.rounded_rectangle((0, 0, ICON * S - 1, ICON * S - 1), 60 * S, fill=P)
    if kind == 'phone':
        line([(49, 53), (48, 70), (55, 90), (68, 108), (84, 122), (103, 132), (123, 134), (137, 126)], G, 16)
        rect((38, 43, 66, 76), 10, G)
        rect((119, 112, 150, 139), 10, G)
    elif kind == 'messages':
        rect((38, 47, 154, 125), 23, G)
        polygon([(57, 118), (54, 145), (82, 120)], G)
        for x in (70, 96, 122):
            ellipse((x - 5, 83, x + 5, 93), fill=P)
    elif kind == 'camera':
        rect((32, 58, 160, 139), 20, D)
        rect((57, 46, 102, 65), 8, D)
        ellipse((63, 67, 130, 134), fill=D)
        ellipse((72, 76, 121, 125), fill=P)
        ellipse((86, 83, 104, 101), fill=G)
        ellipse((139, 69, 148, 78), fill=G)
    elif kind == 'gallery':
        for i, b in enumerate([((71, 32, 120, 105)), ((98, 54, 158, 101)), ((94, 91, 140, 151)),
                               ((52, 93, 99, 151)), ((33, 54, 97, 102))]):
            ellipse(b, fill=rgba(blend(glyph, plate, 0.15 + i * 0.16)))
        ellipse((80, 79, 112, 111), fill=G)
    elif kind == 'settings':
        import math
        for a in range(0, 360, 45):
            t = math.radians(a)
            line([(96 + 44 * math.cos(t), 96 + 44 * math.sin(t)), (96 + 61 * math.cos(t), 96 + 61 * math.sin(t))], D, 14)
        ellipse((48, 48, 144, 144), fill=D)
        ellipse((69, 69, 123, 123), fill=P)
        ellipse((82, 82, 110, 110), fill=D)
    elif kind == 'music':
        line([(106, 50), (106, 123)], G, 10)
        line([(106, 53), (139, 44), (139, 110)], G, 10)
        ellipse((65, 112, 108, 139), fill=G)
        ellipse((99, 98, 141, 125), fill=G)
    elif kind == 'browser':
        ellipse((40, 40, 152, 152), outline=G, width=10)
        line([(40, 96), (152, 96)], G, 8)
        ellipse((70, 40, 122, 152), outline=G, width=8)
    elif kind == 'clock':
        ellipse((44, 44, 148, 148), outline=G, width=10)
        line([(96, 96), (96, 58)], G, 10)
        line([(96, 96), (126, 108)], G, 10)
        ellipse((90, 90, 102, 102), fill=G)
    elif kind == 'calendar':
        rect((38, 50, 154, 148), 12, G)
        rect((38, 50, 154, 78), 12, D)
        d.rectangle(box((38, 64, 154, 78)), fill=D)
        for x in (58, 96, 134):
            line([(x, 40), (x, 56)], D, 8)
        for x in (60, 82, 104, 126):
            for y in (92, 112, 132):
                ellipse((x - 4, y - 4, x + 4, y + 4), fill=P)
    elif kind == 'contacts':
        ellipse((76, 52, 116, 92), fill=G)
        d.pieslice(box((56, 84, 136, 164)), 180, 360, fill=G)
    elif kind == 'email':
        rect((36, 58, 156, 134), 8, G)
        line([(40, 62), (96, 100), (152, 62)], P, 8)
    elif kind == 'files':
        rect((36, 66, 156, 140), 10, G)
        d.rectangle(box((36, 66, 156, 84)), fill=G)
        rect((36, 54, 92, 76), 8, D)
    elif kind == 'recorder':
        rect((82, 42, 110, 100), 14, G)
        d.arc(box((70, 84, 122, 136)), 0, 180, fill=G, width=10)
        line([(96, 136), (96, 152)], G, 8)
        line([(78, 152), (114, 152)], G, 8)
    elif kind == 'appmarket':
        polygon([(56, 74), (136, 74), (148, 150), (44, 150)], G)
        d.arc(box((76, 46, 116, 86)), 180, 360, fill=G, width=10)
    return im.resize((ICON, ICON), Image.Resampling.LANCZOS)


# ------------------------------------------------------------- theme specs ---

AURORA_PLATES = dict(zip(KINDS, ['#232C4E', '#2A2350', '#1E3A4C', '#1C3346', '#252A55',
                                 '#2E2A4E', '#B03A5B', '#1D4ED8', '#0E7490', '#B91C1C',
                                 '#4338CA', '#047857', '#BE123C', '#C2410C']))
EMBER_PLATES = dict(zip(KINDS, ['#3A2415', '#43200F', '#33170C', '#3D1F10', '#46240F',
                                '#2E1A0E', '#571F14', '#3A2A18', '#4A1A10', '#571B0E',
                                '#402010', '#2F2413', '#4A150D', '#5C2410']))
GLACIER_GLYPHS = {'phone': '#22C55E', 'contacts': '#8B5CF6', 'messages': '#3B82F6', 'camera': '#475569',
                  'gallery': '#F59E0B', 'settings': '#64748B', 'music': '#F43F5E', 'browser': '#2563EB',
                  'clock': '#0EA5E9', 'calendar': '#EF4444', 'email': '#6366F1', 'files': '#10B981',
                  'recorder': '#F43F5E', 'appmarket': '#F97316'}

SPECS = [
    dict(key='aurora', title='Aurora Night', wall='aurora', accent='#6EE7B7',
         panel='#F0101A2E', tile_on='#6EE7B7', tile_off='#8B98B8', text='#F4F7FF', sub='#A7B2CC',
         launcher_text='#FFFFFFFF', launcher_shadow='#8C000000',
         plates=AURORA_PLATES, glyph='#F2F6FF',
         dialpad_bg='#FFFFFF', dialpad_digits='#FF263648'),
    dict(key='ember', title='Ember Dusk', wall='ember', accent='#FF7A45',
         panel='#F0170D08', tile_on='#FF7A45', tile_off='#8A6A5A', text='#F7EFE6', sub='#B39A8A',
         launcher_text='#FFF7EFE6', launcher_shadow='#8C1A0D08',
         plates=EMBER_PLATES, glyph='#FFEDE2',
         dialpad_bg='#FFFFFF', dialpad_digits='#FF3A1C0C'),
    dict(key='glacier', title='Glacier', wall='glacier', accent='#2563EB',
         panel='#F2FFFFFF', tile_on='#2563EB', tile_off='#64748B', text='#1F2937', sub='#6B7280',
         launcher_text='#FF1F2937', launcher_shadow='#1AFFFFFF',
         plates={k: '#FFFFFF' for k in KINDS}, glyph=None,  # per-kind glyphs below
         glyphs=GLACIER_GLYPHS,
         dialpad_bg='#FFFFFF', dialpad_digits='#FF1F2937'),
    dict(key='mono', title='Mono Ink', wall='mono', accent='#FFFFFF',
         panel='#FA101014', tile_on='#FFFFFF', tile_off='#6B7280', text='#F5F5F5', sub='#9CA3AF',
         launcher_text='#FFF5F5F5', launcher_shadow='#8C000000',
         plates={k: '#17171C' for k in KINDS}, glyph='#F5F5F5',
         dialpad_bg='#FFFFFF', dialpad_digits='#FF17171C'),
]


# ------------------------------------------------------------------ build ---


def res_xml(colors):
    body = '\r\n'.join(f'    <color name="{n}">{c}</color>' for n, c in colors)
    return b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\r\n<resources>\r\n' + body.encode() + b'\r\n</resources>\r\n'


def font(size, weight_name='Regular'):
    """Inter (OFL, shipped under themes/vesper/source/fonts) for preview art."""
    from PIL import ImageFont
    path = ROOT.parent / 'vesper' / 'source' / 'fonts' / 'Inter-Variable.ttf'
    try:
        f = ImageFont.truetype(str(path), size)
        try:
            f.set_variation_by_name(weight_name)
        except Exception:
            pass
        return f
    except OSError:
        return ImageFont.load_default(size)


def argb(c):
    """'#AARRGGBB' or '#RRGGBB' -> (r, g, b, a)."""
    h = c.lstrip('#')
    a = int(h[:2], 16) if len(h) == 8 else 255
    r, g, b = hex2rgb(c)
    return (r, g, b, a)


def make_mockup(spec, wall0, ico, clock=True):
    """Home-screen mockup (540x1140) drawn from the real wallpaper + icons."""
    MW, MH = 540, 1140
    canvas = wall0.resize((MW, MH), Image.Resampling.LANCZOS).convert('RGBA')
    text, sub, accent = hex2rgb(spec['text']), hex2rgb(spec['sub']), spec['accent']
    d = ImageDraw.Draw(canvas)
    # clock + date
    if clock:  # placeholder clock; themes with their own greeting pass clock=False
        d.text((MW / 2, 118), '9:41', font=font(92, 'Light'), fill=text + (255,), anchor='mm')
        d.text((MW / 2, 186), 'Monday, 12 November', font=font(24), fill=sub + (255,), anchor='mm')
    # 4 x 3 grid of the first twelve mapped apps
    names = ['Phone', 'Contacts', 'Messages', 'Camera', 'Gallery', 'Settings',
             'Music', 'Browser', 'Clock', 'Calendar', 'Email', 'Files']
    cell = MW / 4
    size = 112
    for i, kind in enumerate(KINDS[:12]):
        cx = cell * (i % 4) + cell / 2
        cy = 330 + (i // 4) * 200
        im = ico[kind].resize((size, size), Image.Resampling.LANCZOS)
        canvas.alpha_composite(im, (round(cx - size / 2), round(cy - size / 2)))
        d.text((cx, cy + size / 2 + 26), names[i], font=font(22), fill=text + (235,), anchor='mm')
    # dock
    dock = Image.new('RGBA', (MW, MH), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dock)
    dd.rounded_rectangle((28, 900, MW - 28, 1040), 46, fill=argb(spec['panel']))
    canvas.alpha_composite(dock)
    for j, kind in enumerate(['phone', 'messages', 'browser', 'music']):
        cx = 28 + (MW - 56) * (j + 0.5) / 4
        im = ico[kind].resize((92, 92), Image.Resampling.LANCZOS)
        canvas.alpha_composite(im, (round(cx - 46), 924))
    return canvas.convert('RGB')


def icon_sheet(spec, ico):
    """Plain icon grid on the theme panel colour (for the repo README)."""
    sheet = Image.new('RGB', (756, 820), blend(spec['panel'], spec['text'], 0.06))
    d = ImageDraw.Draw(sheet)
    d.text((40, 36), spec['title'], font=font(40, 'Medium'), fill=hex2rgb(spec['text']))
    for i, kind in enumerate(KINDS):
        x = 28 + (i % 5) * 144
        y = 120 + (i // 5) * 220
        im = ico[kind].resize((120, 120), Image.Resampling.LANCZOS)
        sheet.paste(im, (x + 12, y), im)
        d.text((x + 72, y + 146), kind.title(), font=font(22), fill=hex2rgb(spec['sub']), anchor='mm')
    return sheet


def build(spec):
    title = spec['title']
    accent = spec['accent']
    panel = spec['panel']
    text = spec['text']
    sub = spec['sub']
    wall = make_wallpaper(spec)
    lock = make_lock_wallpaper(spec)
    tall = ImageOps.fit(wall, (W, H + 320), Image.Resampling.LANCZOS)
    wall0 = tall.crop((0, 0, W, H))
    wall1 = tall.crop((0, 320, W, H + 320))
    wall_bytes, wall1_bytes, lock_bytes = jpg(wall0), jpg(wall1), jpg(lock)
    for b in (wall_bytes, wall1_bytes, lock_bytes):
        assert len(b) < 1000000

    ico = {}
    icons = BytesIO()
    with ZipFile(icons, 'w', ZIP_DEFLATED) as z:
        for kind in KINDS:
            plate = spec['plates'][kind]
            glyph = spec.get('glyphs', {}).get(kind) if spec.get('glyphs') else spec.get('glyph')
            ico[kind] = icon(kind, plate, glyph)
            data = png(ico[kind])
            for name in MAPPING[kind]:
                zip_entry(z, name + '.png', data)
                zip_entry(z, 'icons/' + name + '.png', data)

    sheet = make_mockup(spec, wall0, ico)
    sheet_bytes = jpg(sheet, 85)

    desc_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<HwTheme>',
                  f'    <title>{title}</title>', f'    <title-cn>{title}</title-cn>',
                  '    <author>Independent design</author>', '    <designer>Independent design</designer>',
                  '    <screen>FHD</screen>', '    <version>9.1.0</version>',
                  '    <font>Default</font>', '    <font-cn>Default</font-cn>',
                  f'    <briefinfo>{title} — original theme for Huawei EMUI 9.1 (P20 Lite).</briefinfo>',
                  '</HwTheme>']
    xml = b'\xef\xbb\xbf' + '\r\n'.join(desc_lines).encode() + b'\r\n'

    launcher_xml = (b'<?xml version="1.0" encoding="UTF-8"?>\r\n<hwthemes>\r\n'
                    + f'    <color name="workspace_app_text_color">{spec["launcher_text"]}</color>\r\n'.encode()
                    + f'    <color name="workspace_app_text_shadowColor">{spec["launcher_shadow"]}</color>\r\n'.encode()
                    + b'    <bool name="workspace_app_text_shadow">true</bool>\r\n</hwthemes>\r\n')

    systemui_xml = res_xml([
        ('emui_accent', accent.upper()),
        ('qs_panel_background', panel), ('qs_panel_background_lite', panel),
        ('qs_tile_tint_on', spec['tile_on'].upper()), ('qs_tile_tint_off', spec['tile_off'].upper()),
        ('qs_tile_tint_opening', spec['tile_on'].upper()), ('qs_tile_tint_disable', spec['tile_off'].upper()),
        ('qs_detail_button', accent.upper()),
        ('notification_shade_background_color', panel),
        ('notification_material_background_color', panel),
        ('notification_header_clock_text_color', text),
        ('notification_primary_title_color', text),
        ('notification_sub_text_color', sub),
    ])
    framework_xml = res_xml([
        ('system_bar_background_semi_transparent', panel),  # opaque: fixes see-through shade
        ('status_bar_closed_default_background', panel),
        ('status_bar_opened_default_background', panel),
        ('notification_material_background_color', panel),
        ('notification_primary_title_color', text),
        ('notification_primary_text_color_light', text),
        ('notification_primary_text_color_dark', text),
        ('notification_sub_text_color', accent.upper()),
        ('config_defaultNotificationColor', text),
        ('emui_text_dark', text),
    ])
    hwext_xml = res_xml([('emui_accent', accent.upper())])
    phone_xml = res_xml([
        ('emui_text_dark', text), ('emui_list_primary_default', '#DE' + rgb2hex(blend(panel, text, 0.85)).lstrip('#')),
        ('divider_color', '#1A' + rgb2hex(blend(panel, text, 0.12)).lstrip('#')), ('dialer_theme_color', accent.upper()),
        ('incall_button_text_color_selected', text),
    ])
    incallui_xml = res_xml([
        ('dialer_theme_color', accent.upper()), ('dialer_theme_color_dark', '66' + accent.lstrip('#').upper()),
        ('dialtacts_theme_color', '66' + accent.lstrip('#').upper()),
        ('incall_background_color', '@color/dialer_theme_color'),
        ('dtmf_dialer_display_text', '#FFFFFFFF'), ('dialpad_digits_text_color', spec['dialpad_digits']),
        ('background_dialpad', spec['dialpad_bg']), ('dialpad_background', '#B2000000'),
        ('incall_dialpad_background', spec['dialpad_bg']),
        ('incall_dialpad_background_pressed', '#CC' + rgb2hex(blend(spec['dialpad_bg'], accent, 0.25)).lstrip('#').upper()),
        ('dialtacts_secondary_text_color', sub), ('button_background_color', '@color/incall_background_color'),
        ('button_selected_color', '@color/dialer_theme_color_dark'),
        ('button_default_color', '#B3FFFFFF'), ('button_disabled_color', '#33FFFFFF'),
        ('actionbar_background_color', '@color/dialer_theme_color'),
        ('incall_call_name_light_color', '#FFFFFFFF'), ('incall_call_time_light_color', '#FFFFFFFF'),
        ('incall_call_banner_text_color', '#80FFFFFF'),
    ])

    out = ROOT / f'{title.replace(" ", "-")}-EMUI91.hwt'
    with ZipFile(out, 'w', ZIP_DEFLATED, compresslevel=9) as z:
        zip_entry(z, 'description.xml', xml)
        dir_entry(z, 'unlock')
        dir_entry(z, 'unlock/drawable-hdpi')
        dir_entry(z, 'unlock/layout-hdpi')
        for p in sorted((BASE / 'unlock').rglob('*')):
            if p.is_file():
                zip_entry(z, str(p.relative_to(BASE)), p.read_bytes())
        dir_entry(z, 'wallpaper')
        zip_entry(z, 'wallpaper/home_wallpaper_0.jpg', wall_bytes)
        zip_entry(z, 'wallpaper/home_wallpaper_1.jpg', wall1_bytes)
        zip_entry(z, 'wallpaper/unlock_wallpaper_0.jpg', lock_bytes)
        dir_entry(z, 'preview')
        zip_entry(z, 'preview/cover.jpg', jpg(ImageOps.fit(wall0, (1080, 1920)), 80))
        zip_entry(z, 'preview/icon_small.jpg', jpg(ImageOps.fit(wall0, (714, 424)), 80))
        zip_entry(z, 'preview/preview_wallpaper_0.jpg', jpg(ImageOps.fit(wall0, (1080, 2160)), 80))
        zip_entry(z, 'preview/preview_unlock_0.jpg', jpg(ImageOps.fit(lock, (756, 1428)), 80))
        zip_entry(z, 'preview/preview_icons_0.jpg', sheet_bytes)
        zip_entry(z, 'icons', icons.getvalue())
        # NOTE: no icon_mask here on purpose (see module docstring)
        zip_entry(z, 'com.huawei.android.launcher', module_zip([('theme.xml', launcher_xml)]))
        zip_entry(z, 'com.android.systemui', module_zip([('theme.xml', systemui_xml)]))
        zip_entry(z, 'com.android.phone', module_zip([('theme.xml', phone_xml)]))
        zip_entry(z, 'com.android.incallui', module_zip([('theme.xml', incallui_xml)]))
        zip_entry(z, 'framework-res', module_zip([('theme.xml', framework_xml)]))
        zip_entry(z, 'framework-res-hwext', module_zip([('theme.xml', hwext_xml)]))

    # previews for the repo
    make_mockup(spec, wall0, ico).save(ROOT / f'{spec["key"]}-preview.jpg', quality=90)
    icon_sheet(spec, ico).save(ROOT / f'{spec["key"]}-icons.png')

    # ---- self-checks ----
    with ZipFile(out) as z:
        assert z.testzip() is None
        names = z.namelist()
        for req in ('description.xml', 'unlock/theme.xml', 'wallpaper/home_wallpaper_0.jpg',
                    'wallpaper/home_wallpaper_1.jpg', 'wallpaper/unlock_wallpaper_0.jpg',
                    'preview/cover.jpg', 'preview/icon_small.jpg', 'preview/preview_wallpaper_0.jpg',
                    'preview/preview_unlock_0.jpg', 'preview/preview_icons_0.jpg', 'icons',
                    'com.huawei.android.launcher', 'com.android.systemui', 'com.android.phone',
                    'com.android.incallui', 'framework-res', 'framework-res-hwext'):
            assert req in names, req
        raw = z.read('description.xml')
        assert raw.startswith(b'\xef\xbb\xbf')
        desc = ET.fromstring(raw[3:])
        assert desc.findtext('title') == title and desc.findtext('version') == '9.1.0'
        with ZipFile(BytesIO(z.read('com.huawei.android.launcher'))) as lz:
            assert lz.testzip() is None
            assert 'theme.xml' in lz.namelist()
            assert not any('mask' in n for n in lz.namelist()), 'no icon masks'
            ET.fromstring(lz.read('theme.xml'))
        with ZipFile(BytesIO(z.read('icons'))) as iz:
            assert iz.testzip() is None
            assert 'com.android.settings.png' in iz.namelist()
            assert 'icons/com.android.settings.png' in iz.namelist()
            for n in iz.namelist():
                im = Image.open(BytesIO(iz.read(n)))
                assert (im.format, im.size) == ('PNG', (ICON, ICON)), n
                im.verify()
        for mod in ('com.android.systemui', 'com.android.phone', 'com.android.incallui',
                    'framework-res', 'framework-res-hwext'):
            with ZipFile(BytesIO(z.read(mod))) as m:
                assert m.testzip() is None
                t = m.read('theme.xml').lstrip(b'\xef\xbb\xbf')
                ET.fromstring(t)
                if mod == 'com.android.systemui':
                    assert panel.encode() in t, 'opaque qs panel colour present'
        for n in ('wallpaper/home_wallpaper_0.jpg', 'wallpaper/home_wallpaper_1.jpg',
                  'wallpaper/unlock_wallpaper_0.jpg'):
            assert z.getinfo(n).file_size < 1000000
            im = Image.open(BytesIO(z.read(n)))
            assert (im.format, im.size) == ('JPEG', (W, H))
            im.verify()
    print(out.name, out.stat().st_size, 'bytes')


if __name__ == '__main__':
    for spec in SPECS:
        build(spec)
