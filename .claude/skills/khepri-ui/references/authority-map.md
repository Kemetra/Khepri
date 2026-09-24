# Khepri UI authority map

An **index**, not a grant. Before editing, open the named spec and confirm the file is inside its
§Scope and outside its "Not in scope" / §Exclusions. Confirm `state: active` in
`governance/registry.yaml`. If this map and a spec disagree, the spec wins — fix this map.

## Presentation surfaces

| Surface | Governing spec | Files it admits (presentation only) | Explicitly not in scope | Evidence modules |
|---|---|---|---|---|
| `/app/{lang}` commercial shell | `RCA-010` (+ `RCA-011` typeface, `RCA-012` hero) | `rra/journey/assets/shell.css` (tokens only), `rra/journey/assets/shell-components.css`, `runtime/shell_assets/workspace.css` (shared rules), `runtime/shell_templates/` (markup + ARIA), `runtime/shell_copy.py` (chrome labels only) | `runtime/shell_api.py` and every other `runtime/*.py`, `rca/`, journey, report, landing | `test_r801_shell_tokens`, `test_r807_shell_quality`, `test_r808_shell_state_grammar`, `test_r809_shell_state_contracts`, `test_r810_shell_responsive_rtl`, `test_r811_shell_accessibility`, `test_r812_shell_visual_regression`, `test_u1_05_navigation_and_filters`, `test_u1_slice11_hero_placement` |
| Shell typeface | `RCA-011` | `_ASSETS` allowlist entries in `shell_api.py` **only**, `@font-face` in `shell-components.css` | every other line of `shell_api.py`, `journey.css` | `test_rca011_shell_typeface`, `test_rca011_shell_font_load` (wire) |
| Shell hero artwork | `RCA-012` | derivatives in `rra/journey/assets/`, digest manifest `rra/journey/hero.py`, `_ASSETS` entries; placement is an `RCA-010` slice | source PNG under `docs/`, any `/beta` address, layout/colour changes | `test_rca012_shell_hero_artwork`, `test_rca012_shell_hero_load` (wire) |
| Legal pages | `RCA-010` (presentation), `RCA-003` (inventory) | `runtime/legal_templates/` (markup + ARIA) | routes, the legal inventory | `test_legal1_public_legal_routes`, shell matrix legal cases |
| `/` landing | `RCA-004` | template, bundled assets (`runtime/landing_templates/`, `runtime/landing_assets/`) | `runtime/landing_api.py` route changes (an `RCA-004` slice, not presentation); `RCA-010` excludes `landing.css` | `test_land1_public_landing` |
| `/beta/{lang}/{step}` journey | `RRA-010` | `rra/journey/templates/`, `journey.css`, journey `*.js` (focus/ARIA/disclosure), presentation keys in `journey/copy.py` | `shell.css`, `shell-components.css`, `journey/routes.py`, any shell-owned asset | `test_rra_journey_accessibility`, `test_rra_journey_browser`, `test_rra010_journey_focus`, `test_rra010_journey_type_scale` |
| Report + evidence component layer | `RRA-012` | `rra/rendering/templates/` components, `report.css` component rules, `wording.py` chrome labels, `html.py` `_CHROME` binding | chart grammar, shell stylesheets | `test_u1_02_component_layer`, `test_u1_04_evidence_drawer`, `test_u1_04_drawer_placement` |
| Charts + report a11y/visual evidence | `RRA-015` | `rendering/charts.py`, `_chart.svg.j2`, chart rules in `report.css` / `report.print.css`, one `role` on `refusal_panel` (`RRA-015 FR-193`), `html.py` chart binding, `wording.py` chart codes | fact families, bundle, Excel/PDF beyond chart print rules, shell | `test_rra006_charts`, `test_u1_03_chart_grammar`, `test_rra015_report_accessibility`, `test_rra015_report_visual_regression` |

## Not a presentation slice — route elsewhere

| Change | Owner |
|---|---|
| Shell frame, language rule, parity, refusal-of-entry | `RCA-002` |
| Shell routes, destinations, what a surface reads | `RCA-005`, `RCA-008` (D1 decision surfaces), `RCA-009` (compare) |
| Report bundle and render targets | `RRA-006` |
| Refusal/caveat prose | `RRA-009` |
| Metric meaning, catalog vocabulary | `RRA-011` |
| Drawer data supply via `rra/bundle.py` | `RRA-013` |

## Design direction (evidence, not authority)

| Source | Use for |
|---|---|
| `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` | §A.4 precedence; §7 assets; §8 charts; §9 RTL; §10 responsive; §11 a11y; §12 motion; §13 states; §15 anti-patterns; §16.3 binding rule; §16.4 pack coverage; §16.5 palette; §17 acceptance loop |
| `docs/product/KHEPRI_DESIGN_LANGUAGE.md` | tokens, components, shell composition. Note master §A.5: `KHEPRI_DESIGN_DIRECTION_PROPOSAL.md` is merged but unabsorbed — a slice touching either must close it |
| `docs/product/ui-visual-references/README.md` | per-image binding vs. non-binding content; coverage gaps (#11 narrow/mobile unreferenced) |
| `docs/ui/design_handoff_khepri_product_ui/` | current handoff: README authority notice, §6 hero, §8 palette, `INTERACTIONS.md` behaviour |
| `docs/ui/design_handoff_khepri/` | superseded 2026-09-22; history only |

All paths above are relative to `src/khepri/` for source files and `tests/` for evidence modules
(`.py` omitted) unless shown otherwise.
