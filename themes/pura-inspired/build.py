#!/usr/bin/env python3
"""Build Sunset Sky v1.2 — an EMUI 9.1 (ANE-LX1 / P20 Lite) .hwt theme.

v1.2 is structured to match a known-working EMUI 9.1 theme package
(`emui91b_dark.hwt`): UTF-8 BOM + CRLF description.xml with an EMUI-matching
<version>, 256x256 icons at the root of the nested icons zip, the standard
"amazing" slide-lock unlock module, framework-res / framework-res-hwext /
com.android.systemui / com.huawei.android.launcher modules, and ZIP directory
entries. The compatibility skeleton under base/ is copied from that package;
all visible artwork (wallpaper, icons, previews) is generated here.
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


def icon(kind):
    im = Image.new('RGBA', (ICON * S, ICON * S))
    d = ImageDraw.Draw(im)

    def box(b):
        return tuple(round(x * S) for x in b)

    def line(points, fill, width=8):
        d.line([(int(x * S), int(y * S)) for x, y in points], fill=fill, width=width * S, joint='curve')

    def ellipse(b, fill, outline=None, width=1):
        d.ellipse(box(b), fill=fill, outline=outline, width=width * S)

    def rect(b, r, fill, outline=None, width=1):
        d.rounded_rectangle(box(b), r * S, fill=fill, outline=outline, width=width * S)

    colors = {'phone': '#30c95e', 'messages': '#259df4', 'camera': '#e9edf1',
              'gallery': '#f8fafc', 'settings': '#edf1f4', 'music': '#f64673'}
    rect((12, 12, 180, 180), 42, colors[kind])
    if kind == 'phone':
        line([(49, 53), (48, 70), (55, 90), (68, 108), (84, 122), (103, 132), (123, 134), (137, 126)], 'white', 16)
        rect((38, 43, 66, 76), 10, 'white')
        rect((119, 112, 150, 139), 10, 'white')
    elif kind == 'messages':
        rect((38, 47, 154, 125), 23, 'white')
        d.polygon([box((57, 118))[:2], box((54, 145))[:2], box((82, 120))[:2]], fill='white')
        for x in (70, 96, 122):
            ellipse((x - 5, 83, x + 5, 93), '#259df4')
    elif kind == 'camera':
        rect((32, 58, 160, 139), 20, '#44515e')
        rect((57, 46, 102, 65), 8, '#44515e')
        ellipse((63, 67, 130, 134), '#cbd5de')
        ellipse((72, 76, 121, 125), '#273a4f')
        ellipse((86, 83, 104, 101), '#85b9dc')
        ellipse((139, 69, 148, 78), 'white')
    elif kind == 'gallery':
        for b, c in [((71, 32, 120, 105), '#ee487a'), ((98, 54, 158, 101), '#fdad37'),
                     ((94, 91, 140, 151), '#62b768'), ((52, 93, 99, 151), '#39a8d8'),
                     ((33, 54, 97, 102), '#a56ccc')]:
            ellipse(b, c)
        ellipse((80, 79, 112, 111), '#ffdc55')
    elif kind == 'settings':
        import math
        for a in range(0, 360, 45):
            t = math.radians(a)
            line([(96 + 44 * math.cos(t), 96 + 44 * math.sin(t)), (96 + 61 * math.cos(t), 96 + 61 * math.sin(t))], '#718293', 14)
        ellipse((48, 48, 144, 144), '#718293')
        ellipse((69, 69, 123, 123), '#edf1f4')
        ellipse((82, 82, 110, 110), '#718293')
    elif kind == 'music':
        line([(106, 50), (106, 123)], 'white', 10)
        line([(106, 53), (139, 44), (139, 110)], 'white', 10)
        ellipse((65, 112, 108, 139), 'white')
        ellipse((99, 98, 141, 125), 'white')
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
           'messages': ['com.android.mms'],
           'camera': ['com.huawei.camera', 'com.android.camera'],
           'gallery': ['com.android.gallery3d'],
           'settings': ['com.android.settings'],
           'music': ['com.android.mediacenter']}

wall = ImageOps.fit(Image.open(ROOT / 'source/sunset.png').convert('RGB'), (1080, 2280), Image.Resampling.LANCZOS)
wall_bytes = jpg(wall)
assert len(wall_bytes) < 1000000

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
sheet = Image.new('RGB', (756, 1428), '#f1f3f6')
d = ImageDraw.Draw(sheet)
kinds = list(mapping)
for i, kind in enumerate(kinds):
    x = 88 + (i % 3) * 200
    y = 200 + (i // 3) * 520
    ic = icon(kind).resize((128, 128), Image.Resampling.LANCZOS)
    sheet.paste(ic, (x, y), ic)
    d.text((x + 24, y + 150), kind.title(), fill='#263648')
icon_sheet_bytes = jpg(sheet, 85)
wall.resize((540, 1140), Image.Resampling.LANCZOS).save(ROOT / 'wallpaper-preview.jpg', quality=88)
sheet.save(ROOT / 'icon-assets.png')

# description.xml: UTF-8 BOM + CRLF, like hwtTool-produced packages. Unique
# title so the Themes app does not dedupe it against v1.0/v1.1 ("Sunset Sky").
desc_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<HwTheme>',
              '    <title>Sunset Sky 1.2</title>',
              '    <title-cn>Sunset Sky 1.2</title-cn>',
              '    <author>Independent design</author>',
              '    <designer>Independent design</designer>',
              '    <screen>FHD</screen>',
              '    <version>9.1.0</version>',
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
             b'<resources>\t\n    <color name="emui_accent">#33cccc</color>\n</resources>')

out = ROOT / 'Sunset-Sky-EMUI91-v1.2.hwt'
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
    zip_entry(z, 'wallpaper/unlock_wallpaper_0.jpg', wall_bytes)
    dir_entry(z, 'preview')
    zip_entry(z, 'preview/cover.jpg', jpg(ImageOps.fit(wall, (1080, 1920)), 80))
    zip_entry(z, 'preview/icon_small.jpg', jpg(ImageOps.fit(wall, (714, 424)), 80))
    zip_entry(z, 'preview/preview_wallpaper_0.jpg', jpg(ImageOps.fit(wall, (1080, 2160)), 80))
    zip_entry(z, 'preview/preview_unlock_0.jpg', jpg(ImageOps.fit(wall, (756, 1428)), 80))
    zip_entry(z, 'preview/preview_icons_0.jpg', icon_sheet_bytes)
    # nested module archives
    zip_entry(z, 'icons', icons.getvalue())
    zip_entry(z, 'com.huawei.android.launcher', module_zip([('theme.xml', launcher_xml)]))
    zip_entry(z, 'com.android.systemui', module_zip([('theme.xml', (BASE / 'systemui/theme.xml').read_bytes())]))
    zip_entry(z, 'framework-res', module_zip([('theme.xml', (BASE / 'framework-res/theme.xml').read_bytes())]))
    zip_entry(z, 'framework-res-hwext', module_zip([('theme.xml', hwext_xml)]))

# ---- self-checks ----
with ZipFile(out) as z:
    assert z.testzip() is None
    names = z.namelist()
    for req in ('description.xml', 'unlock/theme.xml', 'unlock/layout-hdpi/layout1.xml',
                'wallpaper/home_wallpaper_0.jpg', 'wallpaper/unlock_wallpaper_0.jpg',
                'preview/cover.jpg', 'preview/icon_small.jpg', 'preview/preview_icons_0.jpg',
                'preview/preview_unlock_0.jpg', 'icons', 'com.huawei.android.launcher',
                'com.android.systemui', 'framework-res', 'framework-res-hwext'):
        assert req in names, req
    for d in ('unlock/', 'wallpaper/', 'preview/'):
        assert d in names, d
    raw = z.read('description.xml')
    assert raw.startswith(b'\xef\xbb\xbf')
    root = ET.fromstring(raw[3:])
    assert root.tag == 'HwTheme'
    assert root.findtext('title') == 'Sunset Sky 1.2'
    assert root.findtext('version') == '9.1.0'
    unlock = ET.fromstring(z.read('unlock/theme.xml'))
    styles = [i.get('style') for i in unlock.findall('item')]
    assert 'amazing' in styles, styles
    with ZipFile(BytesIO(z.read('icons'))) as icons_z:
        assert icons_z.testzip() is None
        for n in icons_z.namelist():
            im = Image.open(BytesIO(icons_z.read(n)))
            assert (im.format, im.size) == ('PNG', (ICON, ICON)), n
            im.verify()
        assert 'com.android.settings.png' in icons_z.namelist()
        assert 'icons/com.android.settings.png' in icons_z.namelist()
    for mod in ('com.huawei.android.launcher', 'com.android.systemui', 'framework-res', 'framework-res-hwext'):
        with ZipFile(BytesIO(z.read(mod))) as m:
            assert m.testzip() is None
            assert 'theme.xml' in m.namelist()
            ET.fromstring(m.read('theme.xml').lstrip(b'\xef\xbb\xbf'))
    for n in ('wallpaper/home_wallpaper_0.jpg', 'wallpaper/unlock_wallpaper_0.jpg'):
        assert z.getinfo(n).file_size < 1000000
        im = Image.open(BytesIO(z.read(n)))
        assert (im.format, im.size) == ('JPEG', (1080, 2280))
        im.verify()

print(out, out.stat().st_size, 'bytes; icons:', sum(map(len, mapping.values())))
