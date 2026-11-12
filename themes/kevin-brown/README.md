# Ink Crane — original EMUI 9.1 theme for Kevin Brown

Warm rice-paper cream, a gold sun, navy ink, and gold circular icon badges
with a navy ring. The crane-and-mountains wallpaper was generated for this
theme (`art/crane-home.png`); every icon glyph is drawn in code.

## Files
- `Ink-Crane-EMUI91.hwt` — theme archive for Huawei Themes.
- `build_ink_crane.py` — rebuilds the archive (needs Pillow; reuses helpers from `../originals/build_variants.py`).
- `ink-crane-preview.jpg` / `ink-crane-icons.png` — design previews (mockups, not device screenshots).

## Greeting
"Hi, Kevin" and "Good to see you." are baked into home page 0; the lock wallpaper says "Welcome back, Kevin".

## Not done, and why
- **Animated text greeting:** not included. EMUI's animated lockscreen format is not reproduced here and can't be verified without the phone. Options: a frame-animated lockscreen module (needs device testing), or a separate app.
- **Device verification:** nothing here has been run on a physical ANE-LX1. Test by copying the `.hwt` (one theme at a time) to Internal storage → Huawei → Themes.

## Choice to verify on the phone
A circular `icon_mask.png` is included in the launcher module so unmapped apps (Photos, WhatsApp, …) get the same circular shape as the badges. If unmapped apps look wrong, remove that file and rebuild.

## Rebuild
    pip install pillow
    python3 build_ink_crane.py
