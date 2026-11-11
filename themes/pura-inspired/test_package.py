"""Check the shipped archive itself; not a Huawei compatibility test."""
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import unittest
from PIL import Image

ARCHIVE = Path(__file__).resolve().parent / 'Sunset-Sky-EMUI91-v1.1.hwt'

class ThemePackageTest(unittest.TestCase):
    def test_package(self):
        with ZipFile(ARCHIVE) as theme:
            self.assertIsNone(theme.testzip())
            required = {'description.xml', 'unlock/theme.xml', 'com.huawei.android.launcher',
                        'icons', 'wallpaper/home_wallpaper_0.jpg', 'wallpaper/unlock_wallpaper_0.jpg',
                        'preview/cover.jpg', 'preview/preview_wallpaper_0.jpg',
                        'preview/preview_unlock_0.jpg', 'preview/preview_icons_0.jpg'}
            self.assertTrue(required.issubset(theme.namelist()))
            self.assertEqual(ET.fromstring(theme.read('description.xml')).findtext('title'), 'Sunset Sky')
            self.assertEqual(ET.fromstring(theme.read('unlock/theme.xml')).find('item').get('style'), 'slide')
            with ZipFile(BytesIO(theme.read('com.huawei.android.launcher'))) as launcher:
                self.assertIsNone(launcher.testzip())
                self.assertEqual(ET.fromstring(launcher.read('theme.xml')).tag, 'hwthemes')
            with ZipFile(BytesIO(theme.read('icons'))) as icons:
                self.assertIsNone(icons.testzip())
                self.assertIn('icons/com.android.contacts.activities.DialtactsActivity.png', icons.namelist())
                for name in icons.namelist():
                    with Image.open(BytesIO(icons.read(name))) as im:
                        self.assertEqual((im.format, im.size), ('PNG', (192, 192)))
                        im.verify()
            for name in ('wallpaper/home_wallpaper_0.jpg', 'wallpaper/unlock_wallpaper_0.jpg'):
                self.assertLess(theme.getinfo(name).file_size, 1000000)
                with Image.open(BytesIO(theme.read(name))) as im:
                    self.assertEqual((im.format, im.size), ('JPEG', (1080, 2280)))
                    im.verify()
            for name in (n for n in theme.namelist() if n.startswith('preview/')):
                with Image.open(BytesIO(theme.read(name))) as im:
                    self.assertEqual(im.format, 'JPEG')
                    im.verify()

if __name__ == '__main__':
    unittest.main()
