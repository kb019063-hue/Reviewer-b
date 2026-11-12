"""Check the shipped variant archives themselves; not a Huawei compatibility test."""
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    'Aurora-Night-EMUI91.hwt': ('Aurora Night', '#F0101A2E'),
    'Ember-Dusk-EMUI91.hwt': ('Ember Dusk', '#F0170D08'),
    'Glacier-EMUI91.hwt': ('Glacier', '#F2FFFFFF'),
    'Mono-Ink-EMUI91.hwt': ('Mono Ink', '#FA101014'),
}


class VariantPackageTest(unittest.TestCase):
    def test_variants(self):
        for fname, (title, panel) in EXPECTED.items():
            with self.subTest(theme=fname):
                with ZipFile(ROOT / fname) as theme:
                    self.assertIsNone(theme.testzip())
                    names = set(theme.namelist())
                    required = {'description.xml', 'icons',
                                'com.huawei.android.launcher', 'com.android.systemui',
                                'com.android.phone', 'com.android.incallui',
                                'framework-res', 'framework-res-hwext',
                                'unlock/theme.xml', 'unlock/layout-hdpi/layout1.xml',
                                'wallpaper/home_wallpaper_0.jpg', 'wallpaper/home_wallpaper_1.jpg',
                                'wallpaper/unlock_wallpaper_0.jpg',
                                'preview/cover.jpg', 'preview/icon_small.jpg',
                                'preview/preview_wallpaper_0.jpg', 'preview/preview_unlock_0.jpg',
                                'preview/preview_icons_0.jpg'}
                    self.assertTrue(required.issubset(names), required - names)
                    for d in ('unlock/', 'wallpaper/', 'preview/'):
                        self.assertIn(d, names)

                    raw = theme.read('description.xml')
                    self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
                    desc = ET.fromstring(raw[3:])
                    self.assertEqual(desc.tag, 'HwTheme')
                    self.assertEqual(desc.findtext('title'), title)
                    self.assertEqual(desc.findtext('version'), '9.1.0')
                    self.assertEqual(desc.findtext('screen'), 'FHD')

                    unlock = ET.fromstring(theme.read('unlock/theme.xml'))
                    self.assertIn('amazing', [i.get('style') for i in unlock.findall('item')])

                    with ZipFile(BytesIO(theme.read('com.huawei.android.launcher'))) as lz:
                        self.assertIsNone(lz.testzip())
                        self.assertIn('theme.xml', lz.namelist())
                        # the on-device fix: no icon masks, so unmapped apps keep native icons
                        self.assertFalse(any('mask' in n for n in lz.namelist()))
                        ET.fromstring(lz.read('theme.xml'))

                    with ZipFile(BytesIO(theme.read('icons'))) as icons:
                        self.assertIsNone(icons.testzip())
                        self.assertIn('com.android.settings.png', icons.namelist())
                        self.assertIn('icons/com.android.settings.png', icons.namelist())
                        for name in icons.namelist():
                            with Image.open(BytesIO(icons.read(name))) as im:
                                self.assertEqual((im.format, im.size), ('PNG', (256, 256)))
                                im.verify()

                    for mod in ('com.android.systemui', 'com.android.phone', 'com.android.incallui',
                                'framework-res', 'framework-res-hwext'):
                        with ZipFile(BytesIO(theme.read(mod))) as m:
                            self.assertIsNone(m.testzip())
                            self.assertIn('theme.xml', m.namelist())
                            body = m.read('theme.xml').lstrip(b'\xef\xbb\xbf')
                            ET.fromstring(body)
                            if mod == 'com.android.systemui':
                                # opaque quick-settings panel for readability
                                self.assertIn(panel.encode(), body)

                    for name in ('wallpaper/home_wallpaper_0.jpg', 'wallpaper/home_wallpaper_1.jpg',
                                 'wallpaper/unlock_wallpaper_0.jpg'):
                        self.assertLess(theme.getinfo(name).file_size, 1000000)
                        with Image.open(BytesIO(theme.read(name))) as im:
                            self.assertEqual((im.format, im.size), ('JPEG', (1080, 2280)))
                            im.verify()
                    for name in (n for n in theme.namelist()
                                 if n.startswith('preview/') and not n.endswith('/')):
                        with Image.open(BytesIO(theme.read(name))) as im:
                            self.assertEqual(im.format, 'JPEG')
                            im.verify()


if __name__ == '__main__':
    unittest.main()
