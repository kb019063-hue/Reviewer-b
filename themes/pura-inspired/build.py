#!/usr/bin/env python3
"""Build a P20 Lite EMUI 9.1 experimental, Pura-inspired theme."""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image, ImageDraw, ImageOps
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
S = 4

def icon(kind):
    im=Image.new('RGBA',(192*S,192*S)); d=ImageDraw.Draw(im)
    def box(b): return tuple(round(x*S) for x in b)
    def line(points, fill, width=8): d.line([(int(x*S),int(y*S)) for x,y in points],fill=fill,width=width*S,joint='curve')
    def ellipse(b,fill,outline=None,width=1): d.ellipse(box(b),fill=fill,outline=outline,width=width*S)
    def rect(b,r,fill,outline=None,width=1): d.rounded_rectangle(box(b),r*S,fill=fill,outline=outline,width=width*S)
    colors={'phone':'#30c95e','messages':'#259df4','camera':'#e9edf1','gallery':'#f8fafc','settings':'#edf1f4','music':'#f64673'}
    rect((12,12,180,180),42,colors[kind])
    if kind=='phone':
        # Curved handset, not a button or a shortcut.
        line([(49,53),(48,70),(55,90),(68,108),(84,122),(103,132),(123,134),(137,126)],'white',16)
        rect((38,43,66,76),10,'white'); rect((119,112,150,139),10,'white')
    elif kind=='messages':
        rect((38,47,154,125),23,'white'); d.polygon([box((57,118))[:2],box((54,145))[:2],box((82,120))[:2]],fill='white')
        for x in (70,96,122): ellipse((x-5,83,x+5,93),'#259df4')
    elif kind=='camera':
        rect((32,58,160,139),20,'#44515e'); rect((57,46,102,65),8,'#44515e')
        ellipse((63,67,130,134),'#cbd5de'); ellipse((72,76,121,125),'#273a4f'); ellipse((86,83,104,101),'#85b9dc'); ellipse((139,69,148,78),'white')
    elif kind=='gallery':
        for b,c in [((71,32,120,105),'#ee487a'),((98,54,158,101),'#fdad37'),((94,91,140,151),'#62b768'),((52,93,99,151),'#39a8d8'),((33,54,97,102),'#a56ccc')]: ellipse(b,c)
        ellipse((80,79,112,111),'#ffdc55')
    elif kind=='settings':
        import math
        for a in range(0,360,45):
            t=math.radians(a); line([(96+44*math.cos(t),96+44*math.sin(t)),(96+61*math.cos(t),96+61*math.sin(t))],'#718293',14)
        ellipse((48,48,144,144),'#718293'); ellipse((69,69,123,123),'#edf1f4'); ellipse((82,82,110,110),'#718293')
    elif kind=='music':
        line([(106,50),(106,123)],'white',10); line([(106,53),(139,44),(139,110)],'white',10)
        ellipse((65,112,108,139),'white'); ellipse((99,98,141,125),'white')
    return im.resize((192,192),Image.Resampling.LANCZOS)

def png(im):
    b=BytesIO(); im.save(b,'PNG',optimize=True); return b.getvalue()

def jpg(im, quality=90):
    b=BytesIO(); im.convert('RGB').save(b,'JPEG',quality=quality,optimize=True); return b.getvalue()

mapping={'phone':['com.android.phone','com.android.dialer','com.android.contacts.activities.DialtactsActivity'], 'messages':['com.android.mms'], 'camera':['com.huawei.camera','com.android.camera'], 'gallery':['com.android.gallery3d'], 'settings':['com.android.settings'], 'music':['com.android.mediacenter']}
wall=ImageOps.fit(Image.open(ROOT/'source/sunset.png').convert('RGB'),(1080,2280),Image.Resampling.LANCZOS)
wall_bytes=jpg(wall); assert len(wall_bytes)<1000000
icons=BytesIO()
with ZipFile(icons,'w',ZIP_DEFLATED) as z:
    for kind, names in mapping.items():
        for name in names: z.writestr('icons/'+name+'.png',png(icon(kind)))
# An actual asset sheet, not a simulated screen or device screenshot.
sheet=Image.new('RGB',(600,480),'#f1f3f6'); d=ImageDraw.Draw(sheet)
for i,kind in enumerate(mapping):
    x=50+(i%3)*190; y=25+(i//3)*220
    sheet.paste(icon(kind).resize((128,128),Image.Resampling.LANCZOS),(x,y),icon(kind).resize((128,128),Image.Resampling.LANCZOS))
    d.text((x+30,y+140),kind.title(),fill='#263648')
sheet.save(ROOT/'icon-assets.png')
wall.resize((540,1140),Image.Resampling.LANCZOS).save(ROOT/'wallpaper-preview.jpg',quality=88)
xml='''<?xml version="1.0" encoding="UTF-8"?>\n<HwTheme><title>Sunset Sky</title><title-cn>Sunset Sky</title-cn><author>Independent design</author><designer>Independent design</designer><screen>FHD</screen><version>1.1.0</version><font>Default</font><font-cn>默认</font-cn></HwTheme>'''.encode('utf-8')
# Use a regular system slide lock, not a custom or fake lockscreen.
unlock = b'<?xml version="1.0" encoding="UTF-8"?><HWTheme><item style="slide"/></HWTheme>'
launcher_xml = b'''<?xml version="1.0" encoding="UTF-8"?><hwthemes>
<color name="workspace_app_text_color">#FFFFFFFF</color>
<bool name="workspace_app_text_shadow">true</bool>
</hwthemes>'''
launcher = BytesIO()
with ZipFile(launcher, 'w', ZIP_DEFLATED) as z:
    z.writestr('theme.xml', launcher_xml)
out=ROOT/'Sunset-Sky-EMUI91-v1.1.hwt'
with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
    z.writestr('description.xml',xml)
    z.writestr('unlock/theme.xml', unlock)
    z.writestr('com.huawei.android.launcher', launcher.getvalue())
    z.writestr('wallpaper/home_wallpaper_0.jpg',wall_bytes)
    z.writestr('wallpaper/unlock_wallpaper_0.jpg',wall_bytes)
    z.writestr('icons',icons.getvalue())
    # Artwork-only previews, without simulated widgets or icons.
    z.writestr('preview/cover.jpg',jpg(ImageOps.fit(wall,(1080,1920)), 80))
    z.writestr('preview/preview_wallpaper_0.jpg',jpg(ImageOps.fit(wall,(1080,2160)), 80))
    z.writestr('preview/preview_unlock_0.jpg',jpg(ImageOps.fit(wall,(1080,2160)), 80))
    z.writestr('preview/preview_icons_0.jpg',jpg(sheet, 85))
with ZipFile(out) as z:
    assert z.testzip() is None
    ET.fromstring(z.read('description.xml'))
    assert ET.fromstring(z.read('unlock/theme.xml')).find('item').get('style') == 'slide'
    with ZipFile(BytesIO(z.read('com.huawei.android.launcher'))) as module:
        assert module.testzip() is None
        ET.fromstring(module.read('theme.xml'))
    assert all(z.getinfo(n).file_size < 1000000 for n in z.namelist() if n.startswith('wallpaper/'))
    with ZipFile(BytesIO(z.read('icons'))) as nested:
        assert nested.testzip() is None
        for n in nested.namelist():
            im=Image.open(BytesIO(nested.read(n))); assert im.size==(192,192); im.verify()
    for n in ('wallpaper/home_wallpaper_0.jpg','wallpaper/unlock_wallpaper_0.jpg'):
        im=Image.open(BytesIO(z.read(n))); assert im.size==(1080,2280); im.verify()
print(out, out.stat().st_size, 'bytes; icons:', sum(map(len,mapping.values())))
