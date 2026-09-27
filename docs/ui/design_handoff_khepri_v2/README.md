> ## Repository authority notice
>
> **This is design reference material. It is reference-only and non-governing, and it is not
> implementation authority.**
>
> The live design reference is the Claude Design project **Khepri v2**. This folder is a
> repository-local snapshot of it, kept for Claude Code and future UI slices to read.
>
> It records the Khepri v2 design system (Jira `SCRUM-23`) as authored in the temporary repository
> `Kemetra/khepri-ds` (draft PR #1, head `785e01c`, branch `feat/khepri-v2-design-system`). It was
> brought into this repository on 2026-09-27 by owner decision so that `Kemetra/Khepri` stays the
> single technical source of truth. `khepri-ds` is a migration source only.
>
> Nothing here is built, served, tested or imported by product code. It adds no dependency, no
> `package.json`, no lockfile and no CI step. The files below this notice are imported verbatim
> except where the exclusions section says otherwise. "Verbatim" means byte-identical content
> except line endings: the source used CRLF, and `.gitattributes` (`eol=lf`) normalises it.
>
> The imported `.design-sync/NOTES.md` says the design system was "deliberately kept OUT of the
> Khepri repo". That line predates the 2026-09-27 owner decision that brought it here, and this
> notice supersedes it.
>
> **Active specifications and their `§Scope` govern what product code may change**
> (`governance/registry.yaml` is authoritative for artifact state). Where this package and an
> active specification, `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` §16.5, or `shell.css` disagree,
> the governed source wins and this package yields. Adopting any component in a live surface is a
> separate, spec-linked slice (`SCRUM-18` for the `/beta` journey), not something this import does.

# Khepri v2 design system (reference)

A React, RTL-first component library authored from the `khepri ui v.2.pdf` mockups (10 Arabic
pages) and synced to the Claude Design project **Khepri v2**
(`d6072c2c-31d1-454c-805f-34d309a3e63d`). It serves design exploration. It is not a Khepri
package: Khepri's surfaces are server-rendered Jinja with per-surface stylesheets, so these
components describe *what* a v2 surface looks like and are never mounted.

## Contents

| Path | What it is |
|---|---|
| `src/components/*.tsx` | 47 source files, 48 components (`AvatarGroup` lives in `Avatar.tsx`) in 8 groups: Foundations, Layout, Actions, Data Display, Cards, Forms, Navigation, Charts |
| `src/components/chartUtils.ts`, `useChartWidth.ts` | SVG chart helpers (no chart library) |
| `src/lib/` | `cx`, `tone` helpers |
| `src/styles/tokens.css` | `--k-*` tokens. **Non-authoritative** — see conflicts below |
| `src/styles/base.css`, `components.css` | Component styles, logical CSS properties throughout |
| `src/index.ts` | Barrel export as authored (still names the excluded logo and assets) |
| `.design-sync/` | Claude Design converter config, conventions header, NOTES, 48 previews |
| `docs/*.md` | Per-component category stubs used by design sync for grouping |

## Excluded from this import, and why

| Excluded | Reason |
|---|---|
| `KhepriLogo` (component, preview, doc) | A simplified SVG scarab, not the official mark. The skill and `RCA-010 FR-206` forbid implementer-authored SVG illustration standing in for a governed asset; the owner ruled it non-authoritative |
| `src/assets/khepri-hero.webp`, `src/assets/index.ts` | A copy of the governed `RCA-012` hero derivative, and a 143 KB generated base64 module. The governed asset stays at `src/khepri/rra/journey/assets/` under its audited digest; a second copy would be an unaudited duplicate |
| `fonts/` (Noto Sans Arabic 400–800 woff2, `fonts.css`) | Khepri ships the Regular weight only, SHA-256 verified. Extra weights are a typeface change that §16.5 and the licence-plus-digest process govern |
| `package.json`, `package-lock.json`, `tsconfig*.json`, `tsup.config.ts`, `scripts/build-css.mjs`, `.gitignore` | An npm/React/TypeScript toolchain. Adding one is a dependency and CI decision this import does not take |

As a result `src/index.ts`, `Sidebar.tsx` (defaults to `<KhepriLogo />`) and `PageHeader.tsx`
(imports `../assets`) refer to files that are not here. That is expected, because nothing builds
this directory. To render the previews again, use `Kemetra/khepri-ds` while it exists.

## Conflicts with Khepri authority (governed source wins)

None of these divergences may be carried into implementation without first being reconciled
against the governing specification. That covers colours, the token layer, radius, shadows,
icons, upload claims and hard-coded Arabic.

| Topic | This package | Governed Khepri source |
|---|---|---|
| Colour | Values sampled from raster mockups at 72 dpi (±5), e.g. `--k-gold-500 #b98c39`, `--k-ink #16212b` | Master spec §16.5 / `shell.css`, e.g. `--gold-500 #C9A45C`, `--gold-600 #B98C39`, `--ink #202326` |
| Token layer | One `--k-*` layer meant for every surface | `RCA-010 FR-201`: each surface owns its values; no shared token layer |
| Elevation | `--k-shadow-card`, `-raised`, `-gold` | `--shadow: none`; "no elevation ramp" is a recorded deliberate absence |
| Radius | 6 / 8 / 12 / 16 px | `--radius-sm` 3px, `-md` 6px, `-pill` 999px |
| Icons | `Icon` wraps `lucide-react` | "No icon set" is a recorded deliberate absence; any icon family needs licence plus audited digest |
| Typeface weights | 400–800 | Regular only, vendored and digest-checked |
| Capability | `Dropzone` defaults advertise CSV / XLSX / PDF / ZIP up to 500 MB | Intake accepts only what the active intake specification admits. Never copy a format, limit or capability out of this package |

Arabic/English parity also applies. The components default to `dir="rtl"` `lang="ar"` through
`KhepriProvider`. In Khepri, `lang` and `dir` are computed on the server and customer strings
live in copy modules with import-time parity. Several components here (for example
`AnalysisCard`, `Button`, `Card`) carry Arabic default strings in the component source. Those
defaults are design placeholders, and no adoption may carry them into a surface.

## CodeScene: accepted exception (owner decision, 2026-09-28)

`AGENTS.md` requires every new file to score 10.00 in the server-side CodeScene review. Five
files here score below that locally, as authored: `DataTable`, `Stepper`, `StatTile`, `Card` and
`Select` (about 9.66–9.68). Four more could not be scored locally: `Dropzone.tsx`, `lib/tone.ts`,
`index.ts` and `previews/AvatarGroup.tsx`. The server's thresholds can differ from these local
scores.

The owner chose to keep this snapshot as authored rather than rewrite it to satisfy the gate, and
to accept a failed CodeScene check on the pull request that adds it. The exception is recorded
here and nowhere else.

- It covers only the files in this folder, as imported. Any later edit to one of them is new
  authored work and must meet the gate.
- It adds no CodeScene configuration and no exclusion. The gate keeps scoring every other file
  normally.
- It sets no precedent for production code, tests or other docs.

## Status

- Owner visual review in the Claude Design pane: open.
- Owner decision on hero art, logo and exact brand colours: open (see `SCRUM-23`).
- `Kemetra/khepri-ds` PR #1 is left open and unmerged. The repository is not archived.
