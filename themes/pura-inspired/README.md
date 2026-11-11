# Sunset Sky — P20 Lite theme, version 1.1

A sunset-cloud wallpaper and colourful icons inspired by the look of a recent Huawei flagship. This is an independent interpretation, **not** the original Huawei theme. The wallpaper is AI-generated; the six icon designs are drawn by `build.py`. The original 1.0 package did not show up in Huawei Themes on the user's device.

## Try version 1.1

1. Download **`Sunset-Sky-EMUI91-v1.1.hwt`**, keeping the `.hwt` extension. It has a new filename so it does not overwrite your original download.
2. Copy it to **Internal storage → Huawei → Themes**. Do not extract it. Close Huawei Themes completely, reopen it, and look under **Me → Themes** for **Sunset Sky**. If necessary, restart the phone and check again. Some devices use `HWThemes` instead.
3. Apply it and check the wallpaper, lock screen, and individual app icons. You can revert by selecting a built-in theme.

If it still does not appear, do not keep repeatedly copying it: the reason is not yet known. Please share a screenshot of the folder showing the file and its name, and whether other locally copied `.hwt` themes appear. Avoid including personal information.

## What changed and what is uncertain

The first file omitted a lock-screen module and a launcher module; version 1.1 adds a standard slide-lock XML, a minimal launcher module, and the common Huawei dialer activity icon target. Those omissions **may** have caused the listing problem; we do not know. This is still a partial icon set and is not a Huawei hwtTool export or a full Huawei template. It has not been tested on a physical ANE-LX1. ZIP, XML, image size and nested archive checks pass locally, but cannot establish whether Huawei Themes accepts it or displays each icon. Package IDs and behavior can vary by build. The theme cannot change EMUI 9.1 into EMUI 16.

The package contains actual icon image resources intended for Phone, Messages, Camera, Gallery, Settings and Music; the launcher still opens the underlying apps. Other apps are not explicitly themed. No replacement clock/calendar is provided. The previews are an artwork-only wallpaper and icon sheet, not device screenshots, widgets, or functional controls.

## Sources and rebuilding

Huawei's [tool guide](https://developer.huawei.com/consumer/en/doc/content/themes-design-tools-0000001054531194) specifies hwtTool for EMUI 5–9.1. Its [EMUI 8 guidance](https://developer.huawei.com/consumer/en/doc/themes-specification8) describes the small-theme modules, 192 × 192 PNG icons, and package-name mapping; the [EMUI 11 guide](https://developer.huawei.com/consumer/en/doc/distribution/content/themes-specification11-0000001054691178) documents the simple slide-lock XML used here. These adjacent-version guides do not prove EMUI 9.1 compatibility. Huawei's [EMUI 9.1 specification download](https://developer.huawei.com/consumer/en/doc/30111) and hwtTool were not available in this environment.

Install Pillow and run `python build.py` to rebuild. It preserves the previous 1.0 file and writes the new 1.1 archive. Run `python test_package.py` to check its structure and resources.
