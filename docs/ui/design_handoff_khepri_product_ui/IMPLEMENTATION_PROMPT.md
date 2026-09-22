> ## Repository authority notice
>
> **This is supplied design and handoff material. It is not implementation authority.**
>
> It was imported verbatim as the owner supplied it, and its content below this notice is
> unmodified. It records an approved *visual direction*. It does not, and cannot, authorize any
> change to product code.
>
> **Any list of source files in this package — notably §5 "Files expected to change" and §6
> "Registration (mandatory)" — is blast-radius and design guidance only.** Where such a list names
> a repository path, it is describing where the design is expected to land, not granting permission
> to edit it. Phrases in this package such as "the only permitted edits", "mandatory", or "expected
> to change" carry no authority in this repository.
>
> **Active specifications and their `§Scope` always govern what product code may actually change**
> (Constitution Article IV; `governance/registry.yaml` is authoritative for artifact state). Where
> this package and an active specification disagree about whether a file may be touched, the
> specification governs and this package yields.
>
> Two concrete instances, true at import (2026-09-22), recorded so the conflict is not discovered
> mid-slice:
>
> - This package states that allow-list additions are "the only permitted edits" to
>   `src/khepri/rra/journey/routes.py` and `src/khepri/runtime/shell_api.py`. Active `RCA-010`
>   §Scope places `shell_api.py` **and every other `src/khepri/runtime/*.py` module** under
>   *Not in scope*. `RCA-010` governs; those edits are **not** authorized by this package.
> - §5 additionally names `journey.css`, the journey templates and `rendering/html.py`. Those are
>   `RRA-010`'s and `RRA-015`'s surfaces, not `RCA-010`'s. Each needs its own active specification
>   naming it before any slice touches it.
>
> Importing this package starts no implementation. Product code changes only under an
> active specification naming the files, in bounded, independently verifiable slices.
>
> The palette recorded here as §8 is transcribed into `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md`
> §16.5, which is the citable record for those token values.

# Implementation prompt — Khepri Product UI

Paste this into Claude Code with this folder present at
`docs/ui/design_handoff_khepri_product_ui/`.

`README.md` beside this file is part of the brief, not optional background. It carries the verified
repository orientation, the exact screen→route map, the exact file list, token values, asset
registration points and the gate list. Read it before writing code.

All open questions are closed. Nothing in this task requires returning to design for
interpretation.

---

Implement the approved Khepri UI/UX in the actual Khepri repository.

You have been provided with:

* `design-files/Khepri Product UI.dc.html` — visual source of truth.
* `design-files/Khepri Handoff.dc.html` — implementation rules, tokens, components, responsive behavior, states, RTL behavior, per-screen inventory.
* `design-files/Khepri Design Language.dc.html` — palette, type and motif rationale.
* `references/01-home.png` … `06-report.png`, `icons.png`, `motifs.png` — approved renders.
* `assets/khepri-hero.png` — the approved hero artwork (1400×900).
* `README.md` — the implementation contract.

This is an implementation task, not a redesign task.

## 0. Method — CONTROLLED VISUAL REPLACEMENT

Preserve behavior, contracts, read models, routes and tests. Replace the visible presentation
screen by screen. Remove a screen's old presentation only after its replacement passes validation.

Do not redesign backend behavior, product semantics, routes, read models or architecture to match
the prototype. Where the prototype and the product disagree about what exists, the product wins.

## 1. Pre-flight

```bash
git status --short
git branch --show-current
git fetch origin
git checkout main
git pull --ff-only origin main
git log -1 --oneline
```

Then read before editing — `README.md` §5 lists the exact files, but confirm them yourself:

* `src/khepri/rra/journey/` — `routes.py`, `templates/`, `assets/`
* `src/khepri/runtime/` — `shell_api.py`, `shell_frame.py`, `shell_templates/`, `shell_assets/`
* `src/khepri/rra/rendering/` — `html.py`, `templates/report.css`, `typefaces/`
* the gates in `tests/` listed in `README.md` §16
* the repo's lint/typecheck/build configuration

The frontend is FastAPI + Jinja2, server-rendered, with hand-authored CSS served through explicit
asset allow-lists. There is no React, no npm, no bundler. Do not port prototype markup — recreate
the designs in the repository's own idiom.

Preserve current product semantics and existing governed behavior.

## 2. Authority

1. Existing Khepri product semantics, route contracts, read models and repository invariants
2. `Khepri Product UI.dc.html` for visual appearance
3. `Khepri Handoff.dc.html` for implementation rules
4. Existing frontend architecture where it does not conflict with the approved design

Do not invent product functionality to match prototype placeholder content. Prototype data is
illustrative, never canonical. `README.md` §3 draws the governed/visual line explicitly — apply it.

## 3. Screens and routes — settled

| Prototype screen | Route | Template |
|---|---|---|
| Home / Dashboard | `/app/{language}/{organization}/overview` | `shell_templates/overview.html.j2` |
| Upload / New Analysis | `/beta/{language}/upload` | `journey/templates/upload.html.j2` |
| Review & Map | `/beta/{language}/review` | `review.html.j2` |
| Analysis in Progress | `/beta/{language}/processing` | `processing.html.j2` |
| Insights / Results | `/app/{language}/{organization}/analyses` + analysis detail | `analyses.html.j2`, `analysis.html.j2`, `decision.html.j2` |
| Report / Report Viewer | `/beta/{language}/report` | `report.html.j2`, `rendering/html.py` |

* Treat prototype "Home" as the existing workspace Overview. Map "Insights" onto the existing
  Analyses / analysis-detail experience where semantically appropriate.
* **Do not create new routes to reproduce prototype naming.**
* Existing route contracts and product semantics win over prototype labels.

**Shell strategy — settled.** Do NOT unify the `/beta` journey shell and the `/app` workspace shell
architecturally. Restyle both within their current architecture so they share the approved visual
language. Architectural unification is out of scope.

Implement the shared system first — AppFrame, SideNav, TopBar, tokens, typography, button variants,
cards, status badges, form controls, tabs, steppers, tables, banners and feedback states, chart
styling, responsive behavior, RTL — then apply those primitives to the six surfaces.

## 4. Visual requirements

Midnight navy shell · warm gold accents · ivory/sand surfaces · the specified display hierarchy ·
Noto Sans Arabic for UI and Arabic · restrained borders and shadows · data-dense enterprise layout ·
one consistent icon stroke language · subtle Egyptian identity · no generic SaaS redesign.

Exact values: `README.md` §8 (tokens), §9 (typography), §10 (shell), §11 (components).

Do not: introduce purple/blue startup gradients · nest cards unnecessarily · overuse rounded icon
tiles · put Egyptian motifs on ordinary UI controls · reduce analytical density · give each page a
different visual system.

Non-authoritative material is listed in `README.md` §7. Do not follow it.

## 5. Typography — settled

Do NOT introduce Source Serif 4. No new font dependency and no external font CDN. Preserve the
currently approved/vendored local stack (Noto Sans Arabic, already served to both `/beta/assets/`
and `/app/assets/`, plus the system stacks already declared). Source Serif 4 may only be introduced
later through the repository's required font asset/approval path.

The display *scale, weight and rhythm* in `README.md` §9 are authoritative; the serif *face* is not
available. Hold the display/UI contrast with size, weight and tracking, and report the substitution
as a known visual difference.

## 6. Asset policy

Use the supplied hero artwork as a real image asset. Do not recreate the monument, pyramid, sun,
water or hero artwork with CSS drawing, geometric div compositions, generated SVG, or gradients
pretending to be the illustration. Crop and reposition only, per `README.md` §6.

Ship compressed derivatives (jpg/webp, 1× and 2×) rather than the 2.3 MB PNG.

**Register every new asset.** `journey/routes.py::_ASSETS` for `/beta/assets/`,
`shell_api.py::_ASSETS` for `/app/assets/`. Unregistered files 404. These allow-list additions are
the only permitted edits to those two Python files.

Small UI icons, logo marks, chevrons, controls and small decorative motifs may be inline SVG. Do
not rasterize charts, tables, text or product UI.

## 7. Responsive + RTL

Desktop ≥1280 / tablet 768–1279 / mobile <768; behavior table in `README.md` §13. Verify at 1440,
1024 and 390.

RTL must be structural, not a duplicated layout — the repo already derives direction per request;
extend it. Logical CSS properties throughout; no `left`/`right`. Support `dir="ltr"`, `dir="rtl"`,
`lang="en"`, `lang="ar"`. Do not mirror the hero artwork. Handle mixed-direction values —
filenames, currency, percentages, dates, numbers — per `README.md` §14. Arabic strings come from
the existing copy dictionaries only.

## 8. Product states

Implement loading, processing, success, warning, error, empty, disabled and pending as specified in
`README.md` §12. Connect existing real states where available. Do not add placeholder state
implementations that violate existing application behavior or the state contracts in `test_r808` /
`test_r809`.

## 9. Accessibility

Preserve or improve keyboard navigation, visible focus states, semantic controls, progressbar ARIA
attributes, live processing announcements, contrast, touch target sizes and reduced-motion
behavior. Specifics and the gold-on-ivory contrast constraint: `README.md` §15.

## 10. Scope constraints

Frontend UI implementation only. Do not change backend behavior, database/schema/migrations, the
authentication model, API contracts, CI/workflows or unrelated product features. Do not add
dependencies or modify lockfiles. Prefer existing components and stylesheets. No broad
architectural refactors. Full list: `README.md` §18.

## 11. Execution order

Follow `README.md` §17 exactly: shared system first (tokens → typography → shell → primitives),
then screens in the order Upload → Review → Processing → Report → Home/Overview → Insights, then
the responsive / RTL / state sweeps.

Each step is a checkpoint. Do not begin the next until the current one renders correctly, passes
its gates in both directions at all three breakpoints, and its superseded presentation has been
removed.

## 12. Validation

Run the gates listed in `README.md` §16 plus the repo's existing lint/typecheck/build. Then verify
all six screens, desktop/tablet/mobile, LTR and RTL, and every state, and compare side by side
against `Khepri Product UI.dc.html` and `references/*.png`.

Use the repo's existing browser/visual-regression tests (`test_r812`, `test_rra015_*`) rather than
ad-hoc screenshots. Regenerate baselines deliberately, screen by screen, and state which moved and
why. Read each assertion's docstring before changing it — this repo encodes product rules in test
prose. If a test's *intent* would have to change, stop and report.

Report any visual difference that could not safely be reproduced.

## 13. Git safety

Stage only named files. Never `git add -A`. Never stage unrelated untracked files. Do not commit,
push, open a PR or merge. Stop before all git publication actions.

If unexpected modified files, unrelated failing tests, merge conflicts or scope creep appear, stop
and report the exact blocker rather than widening the task.

## Final report

1. files changed
2. components created/reused
3. screens implemented
4. assets added
5. tests/gates run and results
6. responsive + RTL validation
7. remaining visual differences, if any
8. any genuine blockers

Do not produce another design proposal. Implement the approved design.
