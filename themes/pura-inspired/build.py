#!/usr/bin/env python3
"""Build Sunset Sky v1.3 — an EMUI 9.1 (ANE-LX1 / P20 Lite) .hwt theme.

v1.3 keeps the v1.2 structure that matches a known-working EMUI 9.1 package
(BOM + CRLF description.xml with EMUI-line version, 256x256 icons at the root
of the nested icons zip, the standard "amazing" unlock module, framework-res /
framework-res-hwext / systemui / launcher modules, hwtTool-style zip directory
entries) and improves coverage: a 14-app icon set, launcher icon masks, a second
home-screen page wallpaper, and a sunset accent colour. Structural skeleton
under base/ comes from a real EMUI 9.1 theme; all artwork is generated here.
"""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED, ZipInfo
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'base'
S = 4  # supersampling factor for icon artwork
ICON = 256  # EMUI 9.1 launcher icons are 256x256 (EMUI 8 used 192x192)
ACCENT = '#ff7a45'  # sunset accent


def icon(kind):
    im = Image.new('RGBA', (ICON * S, ICON * S))
    d = ImageDraw.Draw(im)

    def box(b):
        return tuple(round(x * S) for x in b)

    def line(points, fill, width=8):
        d.line([(int(x * S), int(y * S)) for x, y in points], fill=fill, width=width * S, joint='curve')

    def ellipse(b, fill=None, outline=None, width=1):
        d.ellipse(box(b), fill=fill, outline=outline, width=width * S)

    def rect(b, r, fill, outline=None, width=1):
        d.rounded_rectangle(box(b), r * S, fill=fill, outline=outline, width=width * S)

    def polygon(points, fill):
        d.polygon([(int(x * S), int(y * S)) for x, y in points], fill=fill)

    colors = {'phone': '#30c95e', 'messages': '#259df4', 'camera': '#e9edf1',
              'gallery': '#f8fafc', 'settings': '#edf1f4', 'music': '#f64673',
              'browser': '#3b82f6', 'clock': '#0ea5e9', 'calendar': '#ef4444',
              'contacts': '#8b5cf6', 'email': '#6366f1', 'files': '#10b981',
              'recorder': '#f43f5e', 'appmarket': '#f97316'}
    rect((12, 12, 180, 180), 42, colors[kind])
    if kind == 'phone':
        line([(49, 53), (48, 70), (55, 90), (68, 108), (84, 122), (103, 132), (123, 134), (137, 126)], 'white', 16)
        rect((38, 43, 66, 76), 10, 'white')
        rect((119, 112, 150, 139), 10, 'white')
    elif kind == 'messages':
        rect((38, 47, 154, 125), 23, 'white')
        polygon([(57, 118), (54, 145), (82, 120)], 'white')
        for x in (70, 96, 122):
            ellipse((x - 5, 83, x + 5, 93), fill='#259df4')
    elif kind == 'camera':
        rect((32, 58, 160, 139), 20, '#44515e')
        rect((57, 46, 102, 65), 8, '#44515e')
        ellipse((63, 67, 130, 134), fill='#cbd5de')
        ellipse((72, 76, 121, 125), fill='#273a4f')
        ellipse((86, 83, 104, 101), fill='#85b9dc')
        ellipse((139, 69, 148, 78), fill='white')
    elif kind == 'gallery':
        for b, c in [((71, 32, 120, 105), '#ee487a'), ((98, 54, 158, 101), '#fdad37'),
                     ((94, 91, 140, 151), '#62b768'), ((52, 93, 99, 151), '#39a8d8'),
                     ((33, 54, 97, 102), '#a56ccc')]:
            ellipse(b, fill=c)
        ellipse((80, 79, 112, 111), fill='#ffdc55')
    elif kind == 'settings':
        import math
        for a in range(0, 360, 45):
            t = math.radians(a)
            line([(96 + 44 * math.cos(t), 96 + 44 * math.sin(t)), (96 + 61 * math.cos(t), 96 + 61 * math.sin(t))], '#718293', 14)
        ellipse((48, 48, 144, 144), fill='#718293')
        ellipse((69, 69, 123, 123), fill='#edf1f4')
        ellipse((82, 82, 110, 110), fill='#718293')
    elif kind == 'music':
        line([(106, 50), (106, 123)], 'white', 10)
        line([(106, 53), (139, 44), (139, 110)], 'white', 10)
        ellipse((65, 112, 108, 139), fill='white')
        ellipse((99, 98, 141, 125), fill='white')
    elif kind == 'browser':  # globe
        ellipse((40, 40, 152, 152), outline='white', width=10)
        line([(40, 96), (152, 96)], 'white', 8)
        ellipse((70, 40, 122, 152), outline='white', width=8)
    elif kind == 'clock':
        ellipse((44, 44, 148, 148), outline='white', width=10)
        line([(96, 96), (96, 58)], 'white', 10)
        line([(96, 96), (126, 108)], 'white', 10)
        ellipse((90, 90, 102, 102), fill='white')
    elif kind == 'calendar':
        rect((38, 50, 154, 148), 12, 'white')
        rect((38, 50, 154, 78), 12, '#fecaca')
        d.rectangle(box((38, 64, 154, 78)), fill='#fecaca')
        for x in (58, 96, 134):
            line([(x, 40), (x, 56)], '#fecaca', 8)
        for x in (60, 82, 104, 126):
            for y in (92, 112, 132):
                ellipse((x - 4, y - 4, x + 4, y + 4), fill='#ef4444')
    elif kind == 'contacts':  # person
        ellipse((76, 52, 116, 92), fill='white')
        d.pieslice(box((56, 84, 136, 164)), 180, 360, fill='white')
    elif kind == 'email':  # envelope
        rect((36, 58, 156, 134), 8, 'white')
        line([(40, 62), (96, 100), (152, 62)], '#6366f1', 8)
    elif kind == 'files':  # folder
        rect((36, 66, 156, 140), 10, 'white')
        d.rectangle(box((36, 66, 156, 84)), fill='white')
        rect((36, 54, 92, 76), 8, '#d1fae5')
    elif kind == 'recorder':  # microphone
        rect((82, 42, 110, 100), 14, 'white')
        d.arc(box((70, 84, 122, 136)), 0, 180, fill='white', width=10)
        line([(96, 136), (96, 152)], 'white', 8)
        line([(78, 152), (114, 152)], 'white', 8)
    elif kind == 'appmarket':  # shopping bag
        d.polygon([(int(56 * S), int(74 * S)), (int(136 * S), int(74 * S)), (int(148 * S), int(150 * S)), (int(44 * S), int(150 * S))], fill='white')
        d.arc(box((76, 46, 116, 86)), 180, 360, fill='white', width=10)
    return im.resize((ICON, ICON), Image.Resampling.LANCZOS)


def png(im):
    b = BytesIO()
    im.save(b, 'PNG', optimize=True)
    return b.getvalue()


def jpg(im, quality=90):
    b = BytesIO()
    im.convert('RGB').save(b, 'JPEG', quality=quality, optimize=True)
    return b.getvalue()


def zip_entry(arc, name, data, method=ZIP_DEFLATED):
    """Write an entry the way Windows/7-zip hwt packages do: DOS create_system,
    no data descriptors (flag 0)."""
    zi = ZipInfo(name, date_time=(2026, 11, 11, 12, 0, 0))
    zi.compress_type = method
    zi.create_system = 0
    arc.writestr(zi, data)


def dir_entry(arc, name):
    zip_entry(arc, name if name.endswith('/') else name + '/', b'', ZIP_STORED)


def module_zip(files):
    """Build a nested module archive (like com.huawei.android.launcher)."""
    b = BytesIO()
    with ZipFile(b, 'w', ZIP_DEFLATED) as z:
        for name, data in files:
            zip_entry(z, name, data)
    return b.getvalue()


# package-name -> icon mapping (Huawei dialer uses the contacts activity)
mapping = {'phone': ['com.android.phone', 'com.android.dialer', 'com.android.contacts.activities.DialtactsActivity'],
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

# Two home-screen pages: render the artwork tall, then take two crops.
src = Image.open(ROOT / 'source/sunset.png').convert('RGB')
tall = ImageOps.fit(src, (1080, 2600), Image.Resampling.LANCZOS)
wall0 = tall.crop((0, 0, 1080, 2280))
wall1 = tall.crop((0, 320, 1080, 2600))
wall_bytes = jpg(wall0)
wall1_bytes = jpg(wall1)
assert len(wall_bytes) < 1000000 and len(wall1_bytes) < 1000000

# icons zip: EMUI 9.1 keeps the PNGs at the zip root; also add the icons/ prefix
# used by some other themes so either lookup convention matches.
icons = BytesIO()
with ZipFile(icons, 'w', ZIP_DEFLATED) as z:
    for kind, names in mapping.items():
        data = png(icon(kind))
        for name in names:
            zip_entry(z, name + '.png', data)
            zip_entry(z, 'icons/' + name + '.png', data)

# An actual asset sheet, not a simulated screen or device screenshot.
kinds = list(mapping)
cols = 5
rows = (len(kinds) + cols - 1) // cols
sheet = Image.new('RGB', (756, 1428), '#f1f3f6')
d = ImageDraw.Draw(sheet)
for i, kind in enumerate(kinds):
    x = 28 + (i % cols) * 144
    y = 120 + (i // cols) * 440
    ic = icon(kind).resize((96, 96), Image.Resampling.LANCZOS)
    sheet.paste(ic, (x, y), ic)
    d.text((x + 18, y + 110), kind.title(), fill='#263648')
icon_sheet_bytes = jpg(sheet, 85)
tall.crop((0, 0, 1080, 2280)).resize((540, 1140), Image.Resampling.LANCZOS).save(ROOT / 'wallpaper-preview.jpg', quality=88)
sheet.save(ROOT / 'icon-assets.png')

# description.xml: UTF-8 BOM + CRLF, like hwtTool-produced packages. Unique
# title so the Themes app does not dedupe it against earlier versions.
desc_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<HwTheme>',
              '    <title>Sunset Sky 1.3</title>',
              '    <title-cn>Sunset Sky 1.3</title-cn>',
              '    <author>Independent design</author>',
              '    <designer>Independent design</designer>',
              '    <screen>FHD</screen>',
              '    <version>9.1.1</version>',
              '    <font>Default</font>',
              '    <font-cn>Default</font-cn>',
              '    <briefinfo>Sunset wallpaper and icons for Huawei EMUI 9.1 (P20 Lite).</briefinfo>',
              '</HwTheme>']
xml = b'\xef\xbb\xbf' + '\r\n'.join(desc_lines).encode('utf-8') + b'\r\n'

launcher_xml = (b'<?xml version="1.0" encoding="UTF-8"?>\r\n<hwthemes>\r\n'
                b'    <color name="workspace_app_text_color">#FFFFFFFF</color>\r\n'
                b'    <color name="workspace_app_text_shadowColor">#8C000000</color>\r\n'
                b'    <bool name="workspace_app_text_shadow">true</bool>\r\n'
                b'</hwthemes>\r\n')
hwext_xml = (b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\r\n'
             b'<resources>\t\n    <color name="emui_accent">' + ACCENT.encode() + b'</color>\n</resources>')
# sunset accent in the systemui skeleton as well
systemui_xml = (BASE / 'systemui/theme.xml').read_bytes().replace(b'#33cccc', ACCENT.encode())

out = ROOT / 'Sunset-Sky-EMUI91-v1.3.hwt'
with ZipFile(out, 'w', ZIP_DEFLATED, compresslevel=9) as z:
    zip_entry(z, 'description.xml', xml)
    # unlock module as a plain folder, exactly like a real EMUI 9.1 package
    dir_entry(z, 'unlock')
    dir_entry(z, 'unlock/drawable-hdpi')
    dir_entry(z, 'unlock/layout-hdpi')
    for p in sorted((BASE / 'unlock').rglob('*')):
        if p.is_file():
            zip_entry(z, str(p.relative_to(BASE)), p.read_bytes())
    dir_entry(z, 'wallpaper')
    zip_entry(z, 'wallpaper/home_wallpaper_0.jpg', wall_bytes)
    zip_entry(z, 'wallpaper/home_wallpaper_1.jpg', wall1_bytes)
    zip_entry(z, 'wallpaper/unlock_wallpaper_0.jpg', wall_bytes)
    dir_entry(z, 'preview')
    zip_entry(z, 'preview/cover.jpg', jpg(ImageOps.fit(wall0, (1080, 1920)), 80))
    zip_entry(z, 'preview/icon_small.jpg', jpg(ImageOps.fit(wall0, (714, 424)), 80))
    zip_entry(z, 'preview/preview_wallpaper_0.jpg', jpg(ImageOps.fit(wall0, (1080, 2160)), 80))
    zip_entry(z, 'preview/preview_unlock_0.jpg', jpg(ImageOps.fit(wall0, (756, 1428)), 80))
    zip_entry(z, 'preview/preview_icons_0.jpg', icon_sheet_bytes)
    # nested module archives
    zip_entry(z, 'icons', icons.getvalue())
    launcher_files = [('theme.xml', launcher_xml)]
    for p in sorted((BASE / 'launcher').rglob('*')):
        if p.is_file():
            launcher_files.append((str(p.relative_to(BASE / 'launcher')), p.read_bytes()))
    zip_entry(z, 'com.huawei.android.launcher', module_zip(launcher_files))
    zip_entry(z, 'com.android.systemui', module_zip([('theme.xml', systemui_xml)]))
    zip_entry(z, 'framework-res', module_zip([('theme.xml', (BASE / 'framework-res/theme.xml').read_bytes())]))
    zip_entry(z, 'framework-res-hwext', module_zip([('theme.xml', hwext_xml)]))

# ---- self-checks ----
with ZipFile(out) as z:
    assert z.testzip() is None
    names = z.namelist()
    for req in ('description.xml', 'unlock/theme.xml', 'unlock/layout-hdpi/layout1.xml',
                'wallpaper/home_wallpaper_0.jpg', 'wallpaper/home_wallpaper_1.jpg',
                'wallpaper/unlock_wallpaper_0.jpg',
                'preview/cover.jpg', 'preview/icon_small.jpg', 'preview/preview_wallpaper_0.jpg',
                'preview/preview_unlock_0.jpg', 'preview/preview_icons_0.jpg', 'icons',
                'com.huawei.android.launcher', 'com.android.systemui', 'framework-res',
                'framework-res-hwext'):
        assert req in names, req
    for d in ('unlock/', 'wallpaper/', 'preview/'):
        assert d in names, d
    raw = z.read('description.xml')
    assert raw.startswith(b'\xef\xbb\xbf')
    root = ET.fromstring(raw[3:])
    assert root.tag == 'HwTheme'
    assert root.findtext('title') == 'Sunset Sky 1.3'
    assert root.findtext('version') == '9.1.1'
    unlock = ET.fromstring(z.read('unlock/theme.xml'))
    assert 'amazing' in [i.get('style') for i in unlock.findall('item')]
    with ZipFile(BytesIO(z.read('icons'))) as icons_z:
        assert icons_z.testzip() is None
        for n in icons_z.namelist():
            im = Image.open(BytesIO(icons_z.read(n)))
            assert (im.format, im.size) == ('PNG', (ICON, ICON)), n
            im.verify()
        assert 'com.huawei.browser.png' in icons_z.namelist()
        assert 'icons/com.android.settings.png' in icons_z.namelist()
    with ZipFile(BytesIO(z.read('com.huawei.android.launcher'))) as lz:
        assert lz.testzip() is None
        assert 'theme.xml' in lz.namelist()
        assert 'res/drawable-xxhdpi/icon_mask.png' in lz.namelist()
        ET.fromstring(lz.read('theme.xml'))
    for mod in ('com.android.systemui', 'framework-res', 'framework-res-hwext'):
        with ZipFile(BytesIO(z.read(mod))) as m:
            assert m.testzip() is None
            assert 'theme.xml' in m.namelist()
            ET.fromstring(m.read('theme.xml').lstrip(b'\xef\xbb\xbf'))
    for n in ('wallpaper/home_wallpaper_0.jpg', 'wallpaper/home_wallpaper_1.jpg', 'wallpaper/unlock_wallpaper_0.jpg'):
        assert z.getinfo(n).file_size < 1000000
        im = Image.open(BytesIO(z.read(n)))
        assert (im.format, im.size) == ('JPEG', (1080, 2280))
        im.verify()

print(out, out.stat().st_size, 'bytes; icon kinds:', len(mapping), '; icon files:', sum(map(len, mapping.values())))
