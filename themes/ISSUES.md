# Theme on-device issue tracker

Reported 2026-11-12 from screenshots on the target device (Huawei P20 Lite
ANE-LX1, EMUI 9.1, Android 9). Sunset Sky v1.4 (`themes/pura-inspired/`) was
confirmed to **list and apply** in Huawei Themes when copied to
`Internal storage/Huawei/Themes` — the package structure works on-device.

Items below are **unmarked** on purpose: the code-side fix candidates are
shipped in `themes/originals/` (Aurora Night, Ember Dusk, Glacier, Mono Ink),
but each item stays open until the user verifies the fix on the phone and asks
to mark it `- [x]`.

## Open issues

- [ ] **Square plates around unmapped app icons.** In the app drawer, apps the
  theme does not map (Google Photos, WhatsApp, TikTok, Pinterest, …) rendered
  with a big square plate around the glyph. Cause: Sunset Sky v1.2–v1.4 ship
  `res/drawable-xxhdpi/icon_mask.png` / `simple_icon_mask.png` in the launcher
  module, which forces a square mask onto *every* icon. Fix candidate: masks
  removed in all `themes/originals/*.hwt` (our icons are pre-rounded PNGs;
  unmapped apps should keep their native shapes). **Verify on device.**
- [ ] **Quick-settings / notification shade hard to read.** The shade was
  transparent over the wallpaper (`system_bar_background_semi_transparent`
  `#00000000`), so tile labels and notification text had low contrast. Fix
  candidate: every `themes/originals/*.hwt` sets an opaque panel
  (`qs_panel_background`, `notification_shade_background_color`,
  `notification_material_background_color`, status-bar backgrounds) plus
  matching text/tile colours per theme. **Verify on device.**
- [ ] **Sunset Sky v1.4 overall look "kinda ugly"** (AI-generated sunset
  wallpaper read as muddy on the 1080×2280 screen). Fix candidate: replaced by
  four code-drawn wallpapers in `themes/originals/` (gradient + glow/ribbon/
  star/ring accents, previews in `*-preview.jpg`). **User to pick a favorite
  on device.**

## Known limitations (informational, not bugs)

- Status-bar icon glyphs (wifi/signal/battery) are not overridden — only
  colours are themed; replacing glyphs would need system vector drawables.
- Dialer/in-call modules are colour-only (no PNG skinning of the keypad).
- Variants ship no `fonts/` package (system font); Sunset Sky v1.4's
  "Sunset Sans" font package remains available there.
- Some P20 Lite EMUI 9.1 builds have a partially broken theme engine and may
  apply only icons/wallpaper even for store themes.
- Local themes are keyed by the `description.xml` title: keep only one `.hwt`
  per title in `Huawei/Themes`, and delete `Huawei/Themes/.cache` after
  copying a new file.
