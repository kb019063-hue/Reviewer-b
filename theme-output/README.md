# Clarity 9 — EMUI 9.1 theme draft

An original, clean, light theme inspired by modern iPhone interface conventions: pale surfaces, quiet blue accents, rounded-square line icons, and the Inter typeface. All wallpaper and icon artwork in this package was drawn programmatically for this theme; no AI-generated images or copied Apple assets are included.

## Files

- `Clarity9-EMUI91.hwt` — theme archive for Huawei Themes.
- `Clarity9-preview.png` — illustrative home-screen mockup. It is a design preview, not a screenshot from a real P20 Lite.
- `build_clarity9.py` — reproducible artwork/package builder; requires Pillow and fonttools.
- `source/fonts/` — Inter variable font and its SIL Open Font License. The generated theme contains static Inter font instances under EMUI's common Roboto-style font filenames.

## Important: device validation required

The `.hwt` archive and its nested ZIP/XML/image files pass local structural checks, but this theme has **not** been imported or applied on a physical ANE-LX1 / EMUI 9.1 device. Huawei's theme parser can ignore unsupported resources, and exact font/theme behavior varies by firmware build. Back up the current theme before testing; if the preview or text becomes unreadable, switch back using Huawei Themes.

To test, copy the `.hwt` to the device and import it through AnneControl's Themes flow (once that APK build is installed), or place it in the device's Huawei theme folder and choose it in Huawei Themes. The user must confirm **Apply** in Huawei Themes; AnneControl cannot silently apply a full system theme.

The theme is a visual customization only. It does not modify or repair Android/EMUI system code.
