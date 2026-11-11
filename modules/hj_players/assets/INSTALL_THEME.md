# Installing a new HJ graphical theme (without rebuilding the EXE)

Add a new folder under `%LOCALAPPDATA%/HiJackLive/themes/` (e.g. `%LOCALAPPDATA%/HiJackLive/themes/ice-copper/`) for the Windows EXE, or under the configured `HJ_THEME_DIR` for the source application. Include **both** `theme.json` and `frame.svg`.

```json
{
  "id": "ice-copper",
  "name": "ICE COPPER",
  "frame": "frame.svg",
  "color": "#ffffff",
  "glow": "#66ddee",
  "accent": "#88aaaa",
  "version": 1
}
```

`id` must match the lowercase folder name (`[a-z][a-z0-9-]*`, at most 48 characters). Copy an existing `frame.svg` as a starting point and adjust vector paths, fills and gradients. Text is **never part of the SVG**: HTML renders it separately. Reopen the control panel (or restart the EXE) and select the new theme in the theme gallery. No Python or executable recompilation is needed.

For PyInstaller one-file Windows packages, the bundled `assets/` lives in the temporary extraction directory and cannot be permanently changed. The application loads additional external theme packs from `%LOCALAPPDATA%/HiJackLive/themes/` instead; do not edit the executable. Keep resources local and trusted. Future theme packs should use only local static SVG/PNG and JSON files.
