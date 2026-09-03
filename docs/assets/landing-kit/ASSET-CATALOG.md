# Khepri landing asset catalog

This catalog is the usage guide for `docs/assets/landing-kit/`. It separates production candidates
from visual references, so a future page can select assets without reopening the original boards.

## Production candidates

These are the selected clean files in the asset-kit root. They are not served by the application
yet; moving one into the runtime still requires the landing asset allowlist and a usage-rights
record.

| Asset | Use | Notes |
| --- | --- | --- |
| `hero-scene.jpg` | Wide hero background | Leave sufficient dark space for readable HTML copy. |
| `hero-winged-scarab.png` | Hero or section ornament | Decorative only; never replaces the text wordmark. |
| `register-divider.png` | Section separator | Use sparingly between major content sections. |
| `blueprint-chart.png` | Technical background overlay | Use at low opacity. |
| `blueprint-grid.png` | Technical background overlay | Use at low opacity. |
| `blueprint-orbit.png` | Technical background overlay | Use at low opacity. |
| `blueprint-radial.png` | Technical background overlay | Use at low opacity. |
| `blueprint-side-relief.png` | Side decoration | Place at an outer edge so it does not compete with copy. |
| `texture-blue-stone.jpg` | Dark surface background | Use as a subtle cover/no-repeat layer. |
| `texture-carved.jpg` | Dark surface background | Use as a subtle cover/no-repeat layer. |
| `texture-dark-stone.jpg` | Dark surface background | Use as a subtle cover/no-repeat layer. |
| `texture-gold.jpg` | Accent surface | Use cover/no-repeat; do not use behind body copy. |
| `texture-sandstone.jpg` | Warm accent surface | Use cover/no-repeat; do not use behind body copy. |

## Web-delivery derivatives

`web/` contains smaller WebP copies of the production candidates. The responsive hero, scarab,
divider, and blueprint variants are suitable for `srcset` or CSS media-query selection; the
texture variants retain their native dimensions. These are delivery copies, not integrity sources.
Keep the PNG/JPEG candidates above as the reproducible originals.

The local `optimize.py` helper uses the repository's declared development dependencies. From the
repository root, run `uv run python docs/assets/landing-kit/optimize.py` to reproduce the checked-in
WebP files.

## Exact collection archive

`reference/source-boards/` preserves the three original images exactly as supplied. The following
directories contain their visual groups already cropped out:

| Directory | Contents |
| --- | --- |
| `reference/modules/board-01/` | Hero, wordmark concepts, scarabs, state and feature symbols, frames, dividers, CTA and data treatments, reliefs, diagrams, textures, particles, charts, patterns, mobile hero, palette, and type references. |
| `reference/modules/board-02/` | Alternate hero, brand marks, backgrounds, reliefs, textures, frames, dividers, state and small symbols, navigation, CTA, data cards, loading, ornaments, palette, and type references. |
| `reference/modules/board-03/` | Hero, main icons, state symbols, textures, frames, dividers, diagrams, reliefs, compact icons, CTA, KPI centrepiece, ornaments, and palette references. |
| `reference/modules/board-03/small-icons/` | Twenty individually cropped compact symbols: charts, institution, scales, document, database, shield, people, calendar, search, filter, controls, info, add, navigation, download, and expand. |

## Usage boundary

Reference assets are for design selection only. In particular, the state badges and icon sheets
must not enter the live product until their accessibility, user-facing meaning, licence/usage
rights, and active-specification authority are confirmed. Decorative imagery must not obscure text,
carry product claims, or replace accessible HTML content.

## Web derivatives

`web/` holds WebP derivatives generated from the production candidates above by
`optimize.py`. Sources are never modified; re-running the script rebuilds the folder.
`web/MANIFEST.md` records one row per derivative — source, pixel size, bytes, encoder
quality and SHA-256 — so a served file can be proved to be the reviewed one.

Responsive widths are emitted for the hero, emblem, divider and side relief. Textures
emit their native 512px only to avoid unnecessary resampling. They are bordered crops
for cover/no-repeat use and must not be tiled.
