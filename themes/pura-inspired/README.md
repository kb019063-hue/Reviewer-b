# Sunset Sky — P20 Lite theme, version 1.4

A sunset-cloud wallpaper and colourful icons inspired by the look of a recent Huawei flagship. This is an independent interpretation, **not** the original Huawei theme. The wallpaper is AI-generated; the fourteen icon designs are drawn by `build.py`. Versions 1.0 and 1.1 did not show up in Huawei Themes on the user's device.

## Try version 1.4

1. Download **`Sunset-Sky-EMUI91-v1.4.hwt`**, keeping the `.hwt` extension exactly (not `.hwt.zip`).
2. **Remove any older Sunset Sky files** (`Sunset-Sky-EMUI91.hwt`, `-v1.1.hwt`, `-v1.2.hwt`, `-v1.3.hwt`) from the phone first. The Themes app identifies local themes by the title inside `description.xml`; each version has its own title, but keeping only one file avoids any dedup/cache confusion.
3. Copy `Sunset-Sky-EMUI91-v1.4.hwt` to **Internal storage → Huawei → Themes**. Do not extract it. (EMUI 8/9/9.1 use `Huawei/Themes`; only EMUI 5.x uses `HWThemes`.)
4. Delete the **`Huawei/Themes/.cache`** folder if it exists, force-stop the **Themes** app (or clear its app data), reopen Themes, and look under **Me → Themes / My themes** for **Sunset Sky 1.4**. If needed, restart the phone and check again.
5. Apply it and check the wallpaper, lock screen, and individual app icons. Revert by selecting a built-in theme.

**Control test:** if Sunset Sky 1.4 still does not appear, copy a known-good third-party EMUI 9.1 `.hwt` (the kind you applied via zFont before) into the same folder. If that one appears and ours does not, the package is still the problem; if neither appears, the issue is the folder, the Themes app cache, or this firmware build — not the file manager steps.

## What changed in 1.4 (and why)

1.4 keeps the v1.2/v1.3 structure — which matches a **known-working EMUI 9.1 package structure** (a real community `emui91*.hwt`) instead of the hand-rolled v1.0/v1.1 layout:

All of the v1.2 fixes remain (BOM + CRLF `description.xml` with EMUI-line `<version>`, unique title, 256×256 icons at the `icons`-zip root plus `icons/`-prefixed copies, the standard EMUI 9.x "amazing" unlock module, `framework-res` / `framework-res-hwext` / `com.android.systemui` / launcher modules, real-package preview naming, hwtTool-style zip directory entries). On top of that, 1.3 adds:

- **A 14-app icon set** (21 package/activity mappings): Phone, Contacts, Messages, Camera, Gallery, Settings, Music, Browser, Clock, Calendar, Email, Files, Recorder, AppMarket — up from 6 in v1.1. All drawn by `build.py`; see `icon-assets.png`.
- **Launcher icon masks** (`res/drawable-xxhdpi/icon_mask.png`, `simple_icon_mask.png` in the launcher module) so the icons get the native EMUI rounded-square shape.
- **A second home-screen page wallpaper** (`home_wallpaper_1.jpg`, 1080×2280) alongside `home_wallpaper_0.jpg` and `unlock_wallpaper_0.jpg`.
- A sunset **accent colour** (`emui_accent` #ff7a45) in the systemui / framework-res-hwext modules.
- `<version>9.1.2</version>` and unique title **"Sunset Sky 1.4"**.
- **Font package**: `fonts/` with Inter instantiated as `Roboto-Light/Regular/Medium/SemiBold/Bold.ttf`, the OFL license, and `pic_font_default.jpg`; `description.xml` sets `<font>Sunset Sans</font>` (same mechanism as the Vesper theme in this repo). Apply the theme, then pick the font in **Themes → Me → Fonts** if it does not switch automatically.
- **Dialer colours**: colour-only `com.android.phone` and `com.android.incallui` modules (real EMUI resource names: `dialer_theme_color`, `dialpad_digits_text_color`, `incall_dialpad_background`, …) tinted to the sunset accent, so the keypad/in-call text follows the theme. No dialer PNGs are overridden.

## What is still uncertain

This package has **not** been imported on a physical ANE-LX1 / EMUI 9.1 device. Local ZIP/XML/image/nested-archive checks pass (`python test_package.py`), but they cannot prove Huawei Themes accepts it. Some P20 Lite EMUI 9.1 builds have a partially broken theme engine (only icons/wallpaper/some colours apply). Package IDs and behavior vary by firmware build. The theme is a visual customization only; it cannot change EMUI 9.1 into a newer version.

The package contains actual icon resources for Phone, Contacts, Messages, Camera, Gallery, Settings, Music, Browser, Clock, Calendar, Email, Files, Recorder and AppMarket; the launcher still opens the underlying apps. Other apps are not explicitly themed. No replacement clock/calendar is provided. Previews are artwork only, not device screenshots.

## Sources and rebuilding

- Structure ground truth: a real EMUI 9.1 `.hwt` (github.com/nadeemtaj12/dark_emui91_theme, `emui91b_dark.hwt`) and a real EMUI 9/10 theme (github.com/MyCodeIsntWorking/HUAWEI_Theme_Elegance-Advanced). Huawei's tool guide specifies hwtTool for EMUI 5–9.1; the full EMUI 9.1 specification download was not available in this environment.
- Install Pillow and fonttools, then run `python build.py` to rebuild v1.4 (v1.0–v1.3 archives are left untouched). Run `python test_package.py` to check the shipped archive.
