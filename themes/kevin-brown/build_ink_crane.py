#!/usr/bin/env python3
"""Ink Crane — an original EMUI 9.1 (ANE-LX1 / P20 Lite) theme for Kevin Brown.

Look: warm rice-paper cream, a gold sun, navy ink, and gold circular icon
badges with a navy ring. The crane/mountain artwork (art/crane-home.png) was
generated for this theme; every icon glyph is drawn in code.

Reuses the proven package helpers and unlock skeleton from
../originals/build_variants.py (same structure as the v2 originals).

Known gaps, stated plainly:
  * The greeting is static text on the wallpaper. EMUI's own lockscreen
    animation format is not reproduced here; an animated greeting would need
    either a frame sequence in the unlock module (not verified on device) or a
    separate app.
  * Nothing here has been run on a physical ANE-LX1.

Requires Pillow. Run from this folder: python3 build_ink_crane.py
"""
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'originals'))
import build_variants as bv  # noqa: E402  (helpers + unlock skeleton)

W, H = bv.W, bv.H
ART = HERE / 'art' / 'crane-home.png'
TITLE = 'Ink Crane'
OUT = HERE / 'Ink-Crane-EMUI91.hwt'

CREAM = '#EFE5D0'
GOLD = '#E4BC68'
NAVY = '#2B3550'
SUB = '#6E6A60'

SPEC = dict(
    title=TITLE, accent=GOLD, text=NAVY, sub=SUB,
    panel='#FFF3EAD3',  # ARGB, opaque cream shade
    tile_on=NAVY, tile_off='#8A8478',
    launcher_text='#FF2B3550', launcher_shadow='#00FFFFFF',
    dialpad_bg='#FFF3EAD3', dialpad_digits='#FF2B3550',
)


# ----------------------------------------------------------- wallpapers ---

def full_art(size):
    """Scale the crane art to cover the screen, cropping the sides evenly."""
    art = Image.open(ART).convert('RGB')
    scale = max(size[0] / art.width, size[1] / art.height)
    art = art.resize((round(art.width * scale), round(art.height * scale)), Image.Resampling.LANCZOS)
    x = (art.width - size[0]) // 2
    y = (art.height - size[1]) // 2
    return art.crop((x, y, x + size[0], y + size[1]))


def home_wallpaper(page):
    im = full_art((W, H)).convert('RGBA')
    d = ImageDraw.Draw(im)
    if page == 0:
        d.text((90, 250), 'Hi, Kevin', font=bv.font(118, 'Medium'),
               fill=bv.hex2rgb(NAVY) + (255,))
        d.text((94, 396), 'Good to see you.', font=bv.font(48),
               fill=bv.hex2rgb(SUB) + (255,))
    return im.convert('RGB')


def lock_wallpaper():
    im = full_art((W, H)).convert('RGBA')
    d = ImageDraw.Draw(im)
    d.text((W / 2, 520), '08:08', font=bv.font(300, 'Light'),
           fill=bv.hex2rgb(NAVY) + (255,), anchor='mm')
    d.text((W / 2, 680), 'Welcome back, Kevin', font=bv.font(50),
           fill=bv.hex2rgb(NAVY) + (255,), anchor='mm')
    return im.convert('RGB')


# ---------------------------------------------------------------- icons ---

def badge(kind):
    """Gold circle with a navy ring, glyph in navy (drawn by bv.icon)."""
    glyph = bv.icon(kind, GOLD, NAVY)               # 256 px, rounded square
    out = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    ring = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((2, 2, 253, 253), fill=bv.hex2rgb(NAVY) + (255,))
    out.alpha_composite(ring)
    inner = Image.new('L', (256, 256), 0)
    ImageDraw.Draw(inner).ellipse((13, 13, 242, 242), fill=255)
    gold = Image.new('RGBA', (256, 256), bv.hex2rgb(GOLD) + (255,))
    gold.putalpha(inner)
    out.alpha_composite(gold)
    g = glyph.copy()
    g.putalpha(Image.composite(g.getchannel('A'), Image.new('L', (256, 256), 0), inner))
    out.alpha_composite(g)
    return out


def launcher_mask():
    """Circle alpha mask, so unmapped apps match the badge shape.
    This is the one choice to verify on the phone (see README)."""
    m = Image.new('RGBA', (192, 192), (0, 0, 0, 0))
    ImageDraw.Draw(m).ellipse((4, 4, 187, 187), fill=(255, 255, 255, 255))
    return m


# ---------------------------------------------------------------- build ---

def build():
    home0 = home_wallpaper(0)
    home1 = home_wallpaper(1)
    lock = lock_wallpaper()
    ico = {k: badge(k) for k in bv.KINDS}

    wall_bytes = bv.jpg(home0)
    wall1_bytes = bv.jpg(home1)
    lock_bytes = bv.jpg(lock)
    for b in (wall_bytes, wall1_bytes, lock_bytes):
        assert len(b) < 1000000, len(b)

    icons = BytesIO()
    with ZipFile(icons, 'w', ZIP_DEFLATED) as z:
        for kind in bv.KINDS:
            data = bv.png(ico[kind])
            for name in bv.MAPPING[kind]:
                bv.zip_entry(z, name + '.png', data)
                bv.zip_entry(z, 'icons/' + name + '.png', data)

    desc_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<HwTheme>',
                  f'    <title>{TITLE}</title>', f'    <title-cn>{TITLE}</title-cn>',
                  '    <author>Kevin Brown</author>', '    <designer>Kevin Brown</designer>',
                  '    <screen>FHD</screen>', '    <version>9.1.0</version>',
                  '    <font>Default</font>', '    <font-cn>Default</font-cn>',
                  f'    <briefinfo>{TITLE} — original theme by Kevin Brown for EMUI 9.1.</briefinfo>',
                  '</HwTheme>']
    xml = b'\xef\xbb\xbf' + '\r\n'.join(desc_lines).encode() + b'\r\n'

    launcher_xml = (b'<?xml version="1.0" encoding="UTF-8"?>\r\n<hwthemes>\r\n'
                    + f'    <color name="workspace_app_text_color">{SPEC["launcher_text"]}</color>\r\n'.encode()
                    + f'    <color name="workspace_app_text_shadowColor">{SPEC["launcher_shadow"]}</color>\r\n'.encode()
                    + b'    <bool name="workspace_app_text_shadow">false</bool>\r\n</hwthemes>\r\n')

    panel = SPEC['panel']
    systemui_xml = bv.res_xml([
        ('emui_accent', GOLD.upper()),
        ('qs_panel_background', panel), ('qs_panel_background_lite', panel),
        ('qs_tile_tint_on', NAVY.upper()), ('qs_tile_tint_off', '#8A8478'),
        ('qs_tile_tint_opening', NAVY.upper()), ('qs_tile_tint_disable', '#8A8478'),
        ('qs_detail_button', GOLD.upper()),
        ('notification_shade_background_color', panel),
        ('notification_material_background_color', panel),
        ('notification_header_clock_text_color', NAVY),
        ('notification_primary_title_color', NAVY),
        ('notification_sub_text_color', SUB),
    ])
    framework_xml = bv.res_xml([
        ('system_bar_background_semi_transparent', panel),
        ('status_bar_closed_default_background', panel),
        ('status_bar_opened_default_background', panel),
        ('notification_material_background_color', panel),
        ('notification_primary_title_color', NAVY),
        ('notification_primary_text_color_light', NAVY),
        ('notification_primary_text_color_dark', NAVY),
        ('notification_sub_text_color', GOLD.upper()),
        ('config_defaultNotificationColor', NAVY),
        ('emui_text_dark', NAVY),
    ])
    hwext_xml = bv.res_xml([('emui_accent', GOLD.upper())])
    phone_xml = bv.res_xml([
        ('emui_text_dark', NAVY), ('emui_list_primary_default', '#DE2B3550'),
        ('divider_color', '#1A2B3550'), ('dialer_theme_color', GOLD.upper()),
        ('incall_button_text_color_selected', NAVY),
    ])
    incallui_xml = bv.res_xml([
        ('dialer_theme_color', GOLD.upper()), ('dialer_theme_color_dark', '66E4BC68'),
        ('dialtacts_theme_color', '66E4BC68'),
        ('incall_background_color', '@color/dialer_theme_color'),
        ('dtmf_dialer_display_text', '#FFFFFFFF'), ('dialpad_digits_text_color', SPEC['dialpad_digits']),
        ('background_dialpad', SPEC['dialpad_bg']), ('dialpad_background', '#B2000000'),
        ('incall_dialpad_background', SPEC['dialpad_bg']),
        ('incall_dialpad_background_pressed', '#CCF3EAD3'),
        ('dialtacts_secondary_text_color', SUB), ('button_background_color', '@color/incall_background_color'),
        ('button_selected_color', '@color/dialer_theme_color_dark'),
        ('button_default_color', '#B3FFFFFF'), ('button_disabled_color', '#33FFFFFF'),
        ('actionbar_background_color', '@color/dialer_theme_color'),
        ('incall_call_name_light_color', '#FFFFFFFF'), ('incall_call_time_light_color', '#FFFFFFFF'),
        ('incall_call_banner_text_color', '#80FFFFFF'),
    ])

    with ZipFile(OUT, 'w', ZIP_DEFLATED, compresslevel=9) as z:
        bv.zip_entry(z, 'description.xml', xml)
        bv.dir_entry(z, 'unlock')
        bv.dir_entry(z, 'unlock/drawable-hdpi')
        bv.dir_entry(z, 'unlock/layout-hdpi')
        for p in sorted((bv.BASE / 'unlock').rglob('*')):
            if p.is_file():
                bv.zip_entry(z, str(p.relative_to(bv.BASE)), p.read_bytes())
        bv.dir_entry(z, 'wallpaper')
        bv.zip_entry(z, 'wallpaper/home_wallpaper_0.jpg', wall_bytes)
        bv.zip_entry(z, 'wallpaper/home_wallpaper_1.jpg', wall1_bytes)
        bv.zip_entry(z, 'wallpaper/unlock_wallpaper_0.jpg', lock_bytes)
        bv.dir_entry(z, 'preview')
        bv.zip_entry(z, 'preview/cover.jpg', bv.jpg(ImageOps.fit(home0, (1080, 1920)), 80))
        bv.zip_entry(z, 'preview/icon_small.jpg', bv.jpg(ImageOps.fit(home0, (714, 424)), 80))
        bv.zip_entry(z, 'preview/preview_wallpaper_0.jpg', bv.jpg(ImageOps.fit(home0, (1080, 2160)), 80))
        bv.zip_entry(z, 'preview/preview_unlock_0.jpg', bv.jpg(ImageOps.fit(lock, (756, 1428)), 80))
        bv.zip_entry(z, 'preview/preview_icons_0.jpg', bv.jpg(bv.icon_sheet(SPEC, ico), 85))
        bv.zip_entry(z, 'icons', icons.getvalue())
        bv.zip_entry(z, 'com.huawei.android.launcher', bv.module_zip([
            ('theme.xml', launcher_xml),
            ('res/drawable-xxhdpi/icon_mask.png', bv.png(launcher_mask())),
        ]))
        bv.zip_entry(z, 'com.android.systemui', bv.module_zip([('theme.xml', systemui_xml)]))
        bv.zip_entry(z, 'com.android.phone', bv.module_zip([('theme.xml', phone_xml)]))
        bv.zip_entry(z, 'com.android.incallui', bv.module_zip([('theme.xml', incallui_xml)]))
        bv.zip_entry(z, 'framework-res', bv.module_zip([('theme.xml', framework_xml)]))
        bv.zip_entry(z, 'framework-res-hwext', bv.module_zip([('theme.xml', hwext_xml)]))

    # repo previews
    bv.make_mockup(SPEC, home0, ico, clock=False).save(HERE / 'ink-crane-preview.jpg', quality=90)
    bv.icon_sheet(SPEC, ico).save(HERE / 'ink-crane-icons.png')
    print(OUT.name, OUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
