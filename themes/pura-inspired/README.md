# Sunset Sky — P20 Lite theme, version 1.2

A sunset-cloud wallpaper and colourful icons inspired by the look of a recent Huawei flagship. This is an independent interpretation, **not** the original Huawei theme. The wallpaper is AI-generated; the six icon designs are drawn by `build.py`. Versions 1.0 and 1.1 did not show up in Huawei Themes on the user's device.

## Try version 1.2

1. Download **`Sunset-Sky-EMUI91-v1.2.hwt`**, keeping the `.hwt` extension exactly (not `.hwt.zip`).
2. **Remove any older Sunset Sky files** (`Sunset-Sky-EMUI91.hwt`, `Sunset-Sky-EMUI91-v1.1.hwt`) from the phone first. The Themes app identifies local themes by the title inside `description.xml`; v1.0/v1.1 are titled "Sunset Sky" and v1.2 is titled "Sunset Sky 1.2", but keeping only one file avoids any dedup/cache confusion.
3. Copy `Sunset-Sky-EMUI91-v1.2.hwt` to **Internal storage → Huawei → Themes**. Do not extract it. (EMUI 8/9/9.1 use `Huawei/Themes`; only EMUI 5.x uses `HWThemes`.)
4. Delete the **`Huawei/Themes/.cache`** folder if it exists, force-stop the **Themes** app (or clear its app data), reopen Themes, and look under **Me → Themes / My themes** for **Sunset Sky 1.2**. If needed, restart the phone and check again.
5. Apply it and check the wallpaper, lock screen, and individual app icons. Revert by selecting a built-in theme.

**Control test:** if Sunset Sky 1.2 still does not appear, copy a known-good third-party EMUI 9.1 `.hwt` (the kind you applied via zFont before) into the same folder. If that one appears and ours does not, the package is still the problem; if neither appears, the issue is the folder, the Themes app cache, or this firmware build — not the file manager steps.

## What changed in 1.2 (and why)

1.2 is rebuilt to match a **known-working EMUI 9.1 package structure** (a real community `emui91*.hwt`) instead of the hand-rolled v1.0/v1.1 layout:

- `description.xml` now has a **UTF-8 BOM + CRLF** and `<version>9.1.0</version>` (EMUI-matching, like real 9.1 packages) instead of `1.0`/`1.1.0`.
- The internal title is now unique: **"Sunset Sky 1.2"** (v1.0/v1.1 both said "Sunset Sky", which the theme manager can treat as the same theme).
- Icons are **256×256 PNGs at the root of the nested `icons` zip** (EMUI 9.1 convention; 1.0/1.1 used 192×192 under an `icons/` prefix). The `icons/`-prefixed copies are also included for compatibility.
- `unlock/` is now the standard EMUI 9.x **"amazing" slide-lock module** (`theme.xml` + `layout-hdpi/layout1.xml` + `drawable-hdpi` glyphs). v1.1 used `<item style="slide"/>`, which is an EMUI 11 construct and is not a valid 9.1 lock style.
- Added the standard module archives real packages carry: `com.huawei.android.launcher`, `com.android.systemui`, `framework-res`, `framework-res-hwext` (skeleton XML under `base/`, see `base/README.md`).
- Preview set now matches real packages: `cover.jpg`, `icon_small.jpg` (714×424), `preview_wallpaper_0.jpg`, `preview_unlock_0.jpg` (756×1428), `preview_icons_0.jpg`.
- The ZIP itself mimics hwtTool output: directory entries, DOS-style headers, no data descriptors.
- Wallpapers are 1080×2280 (P20 Lite) home + lock.

## What is still uncertain

This package has **not** been imported on a physical ANE-LX1 / EMUI 9.1 device. Local ZIP/XML/image/nested-archive checks pass (`python test_package.py`), but they cannot prove Huawei Themes accepts it. Some P20 Lite EMUI 9.1 builds have a partially broken theme engine (only icons/wallpaper/some colours apply). Package IDs and behavior vary by firmware build. The theme is a visual customization only; it cannot change EMUI 9.1 into a newer version.

The package contains actual icon resources for Phone, Messages, Camera, Gallery, Settings and Music; the launcher still opens the underlying apps. Other apps are not explicitly themed. No replacement clock/calendar is provided. Previews are artwork only, not device screenshots.

## Sources and rebuilding

- Structure ground truth: a real EMUI 9.1 `.hwt` (github.com/nadeemtaj12/dark_emui91_theme, `emui91b_dark.hwt`) and a real EMUI 9/10 theme (github.com/MyCodeIsntWorking/HUAWEI_Theme_Elegance-Advanced). Huawei's tool guide specifies hwtTool for EMUI 5–9.1; the full EMUI 9.1 specification download was not available in this environment.
- Install Pillow and run `python build.py` to rebuild v1.2 (v1.0/v1.1 archives are left untouched). Run `python test_package.py` to check the shipped archive.
