"""Check the shipped v1.2 archive itself; not a Huawei compatibility test."""
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import unittest
from PIL import Image

ARCHIVE = Path(__file__).resolve().parent / 'Sunset-Sky-EMUI91-v1.2.hwt'


class ThemePackageTest(unittest.TestCase):
    def test_package(self):
        with ZipFile(ARCHIVE) as theme:
            self.assertIsNone(theme.testzip())
            required = {'description.xml', 'icons',
                        'com.huawei.android.launcher', 'com.android.systemui',
                        'framework-res', 'framework-res-hwext',
                        'unlock/theme.xml', 'unlock/layout-hdpi/layout1.xml',
                        'unlock/drawable-hdpi/arrow.png',
                        'wallpaper/home_wallpaper_0.jpg', 'wallpaper/unlock_wallpaper_0.jpg',
                        'preview/cover.jpg', 'preview/icon_small.jpg',
                        'preview/preview_wallpaper_0.jpg', 'preview/preview_unlock_0.jpg',
                        'preview/preview_icons_0.jpg'}
            names = set(theme.namelist())
            self.assertTrue(required.issubset(names), required - names)
            for d in ('unlock/', 'wallpaper/', 'preview/'):
                self.assertIn(d, names)

            raw = theme.read('description.xml')
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'), 'description.xml should have a UTF-8 BOM')
            desc = ET.fromstring(raw[3:])
            self.assertEqual(desc.tag, 'HwTheme')
            self.assertEqual(desc.findtext('title'), 'Sunset Sky 1.2')
            self.assertEqual(desc.findtext('version'), '9.1.0')
            self.assertEqual(desc.findtext('screen'), 'FHD')

            unlock = ET.fromstring(theme.read('unlock/theme.xml'))
            styles = [i.get('style') for i in unlock.findall('item')]
            self.assertIn('amazing', styles)

            with ZipFile(BytesIO(theme.read('icons'))) as icons:
                self.assertIsNone(icons.testzip())
                self.assertIn('com.android.contacts.activities.DialtactsActivity.png', icons.namelist())
                self.assertIn('icons/com.android.settings.png', icons.namelist())
                for name in icons.namelist():
                    with Image.open(BytesIO(icons.read(name))) as im:
                        self.assertEqual((im.format, im.size), ('PNG', (256, 256)))
                        im.verify()

            for mod in ('com.huawei.android.launcher', 'com.android.systemui',
                        'framework-res', 'framework-res-hwext'):
                with ZipFile(BytesIO(theme.read(mod))) as m:
                    self.assertIsNone(m.testzip())
                    self.assertIn('theme.xml', m.namelist())
                    ET.fromstring(m.read('theme.xml').lstrip(b'\xef\xbb\xbf'))

            for name in ('wallpaper/home_wallpaper_0.jpg', 'wallpaper/unlock_wallpaper_0.jpg'):
                self.assertLess(theme.getinfo(name).file_size, 1000000)
                with Image.open(BytesIO(theme.read(name))) as im:
                    self.assertEqual((im.format, im.size), ('JPEG', (1080, 2280)))
                    im.verify()
            for name in (n for n in theme.namelist() if n.startswith('preview/') and not n.endswith('/')):
                with Image.open(BytesIO(theme.read(name))) as im:
                    self.assertEqual(im.format, 'JPEG')
                    im.verify()


if __name__ == '__main__':
    unittest.main()
