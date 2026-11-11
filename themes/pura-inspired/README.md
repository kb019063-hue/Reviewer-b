# Sunset Sky — experimental P20 Lite theme

An independent interpretation of the colourful icons and sunset-cloud home screen seen in a [Pura 90s Pro Max review](https://petapixel.com/2026/08/03/huawei-pura-90s-pro-max-review-the-cameras-prove-huawei-is-back/). It is **not** Huawei's stock theme or a pixel-identical port. The wallpaper was AI-generated; the icons were drawn for this package.

Target: Huawei P20 Lite ANE-LX1, EMUI 9.1.0.320, Android 9, 1080 × 2280. This is a partial experimental `.hwt`, not a full Huawei-certified theme. It has a home and lock wallpaper and actual launcher icon resources intended for Phone, Messages, Camera, Gallery, Settings and Music. These are image resources associated with package names, not buttons baked into wallpaper. The phone's launcher remains responsible for launching apps. There are no replacements for Clock or Calendar, avoiding static fake times or dates; other apps are not explicitly themed. Different firmware/package names may mean some icons remain unchanged; an incomplete icon module may also be rejected or applied differently by the theme engine.

## Try it

1. Save `Sunset-Sky-EMUI91.hwt` to your phone's internal storage under `Huawei/Themes` (some installations use `HWThemes`).
2. Open Huawei **Themes → Me → Themes**, select **Sunset Sky** and apply. If it doesn't appear, close and reopen Themes.
3. Check each icon opens the correct app, and check the lock and home screens. To revert, apply a built-in theme. If the partial package is rejected or icons do not change, use `wallpaper-preview.jpg` only as a visual preview; apply the full-resolution `source/sunset.png` as wallpaper through Gallery, or wait for a tested package.

No phone-side test or hwtTool export has been performed. ZIP integrity, images, XML and nested icon archive were checked locally; this does **not** prove device compatibility. `wallpaper-preview.jpg` shows only the wallpaper and `icon-assets.png` shows the actual packaged icon designs, not a device screenshot.

## Research and constraints

Huawei's [tool guide](https://developer.huawei.com/consumer/en/doc/content/themes-design-tools-0000001054531194) specifies hwtTool for EMUI 5–9.1. Its [EMUI 8 specification](https://developer.huawei.com/consumer/en/doc/themes-specification8) describes 192 × 192 PNG icons and package-name mapping; the [9.1-to-10.1 migration guide](https://developer.huawei.com/consumer/en/doc/themes-upgrade10) identifies several system package names. Huawei's [design rules](https://developer.huawei.com/consumer/en/devservice/doc/30108) emphasize readable contrast and a complete template. The full EMUI 9.1 specification and Huawei's desktop hwtTool were not accessible/executed here; this partial package does not claim compliance with Huawei's full mandatory icon/template requirements.

Rebuild with Python 3 and Pillow: `python build.py`.
