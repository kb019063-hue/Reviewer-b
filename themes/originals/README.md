# Original EMUI 9.1 themes (ANE-LX1 / P20 Lite) — v1

Four original themes, all artwork drawn **programmatically** by
`build_variants.py` (no AI-generated images): smooth gradient wallpapers with
glow/ribbon/star/ring accents, and a 14-app icon set per theme (256×256 PNGs).

| File | Look | Accent |
|---|---|---|
| `Aurora-Night-EMUI91.hwt` | dark night sky, teal/violet aurora ribbons, stars | mint `#6EE7B7` |
| `Ember-Dusk-EMUI91.hwt` | dark warm dusk, ember-orange glow, sparks | orange `#FF7A45` |
| `Glacier-EMUI91.hwt` | light icy-blue gradient, white icon plates with coloured glyphs | blue `#2563EB` |
| `Mono-Ink-EMUI91.hwt` | near-black minimal, pinstripes + rings, white line icons | white |

Preview images: `<key>-preview.jpg` (home-screen mockup) and `<key>-icons.png`
(icon grid) next to the archives.

## Fixes vs. the Sunset Sky v1.4 package (learned from on-device screenshots)

1. **No `icon_mask.png` in the launcher module.** A mask forces *every* icon —
   including unmapped apps like Photos, WhatsApp, TikTok — into a square plate.
   Without masks, unmapped apps keep their native icons; our icons are already
   rounded-square PNGs.
2. **Opaque quick-settings / notification shade** (`qs_panel_background`,
   `notification_shade_background_color`, `system_bar_background_semi_transparent`
   all set to a solid panel colour per theme) with matching text colours, so the
   panel is readable instead of showing the wallpaper through the text.

## v2 changes (rebuilt from review of v1 renders)

- Icons are centred in their 256×256 canvas and use full-bleed rounded plates
  the size of native icons (no transparent margin, no masks).
- Aurora Night's wallpaper uses soft curtains instead of zigzag ribbons; Ember
  Dusk gets a low glow. Glacier and Mono Ink keep their v1 looks.
- `*-preview.jpg` is now a home-screen mockup built from the real wallpaper and
  icons; `*-icons.png` is an icon grid on the theme panel colour.
- Fixed ARGB parsing of `#AARRGGBB` colours in the preview code.

Visual checks here are renders only. They do not prove how EMUI draws them.

## Package structure

Same known-working EMUI 9.1 layout as Sunset Sky v1.2+: BOM+CRLF
`description.xml` (unique title per theme, `<version>9.1.0</version>`,
`<screen>FHD</screen>`), 256×256 icons at the icons-zip root plus `icons/`-prefixed
copies, the standard "amazing" unlock module (skeleton from
`../pura-inspired/base/`), `wallpaper/` (two home pages + lock, 1080×2280; the
light theme gets a darker lock wallpaper so the stock white lock glyphs stay
readable), `preview/` artwork, and `com.huawei.android.launcher` /
`com.android.systemui` / `com.android.phone` / `com.android.incallui` /
`framework-res` / `framework-res-hwext` modules. Dialer modules are
colour-only (dialpad text, dialer accent, in-call text). ZIP layout mimics
hwtTool output (directory entries, DOS headers). No `fonts/` — system font.

## Install

Same as any EMUI 8/9/9.1 local theme: remove other test themes, copy **one**
`.hwt` (exact extension) to **Internal storage → Huawei → Themes**, delete
`Huawei/Themes/.cache` if present, force-stop/clear the Themes app, then
**Themes → Me → My themes → Apply**, reboot if needed.

## Rebuild / test

```bash
pip install pillow
python3 build_variants.py   # writes the four .hwt + previews
python3 test_variants.py    # structural checks on the shipped archives
```

Not yet verified on a physical ANE-LX1 beyond Sunset Sky v1.4 applying there;
structural checks cannot prove device behaviour, and some P20 Lite EMUI 9.1
builds apply only icons/wallpaper.
