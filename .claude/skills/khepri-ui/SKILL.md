---
name: khepri-ui
description: Use for Khepri UI/UX work - changing, styling, or evidencing any customer-facing page or dashboard (overview, data, analyses, compare, decision, team pages) - the /app commercial shell (shell_templates, shell.css, shell-components.css, workspace.css, shell_copy.py), the /beta journey (journey templates, journey.css, journey JS), the report and evidence render surfaces (report.css, report.print.css, _components.html.j2, charts.py, _chart.svg.j2), or the landing and legal pages; for RTL, Arabic/bilingual, responsive, accessibility, navigation, filter, state-grammar, typeface, hero-artwork, or visual-regression work; and when implementing anything from docs/ui/ design handoffs or docs/product/ui-visual-references/. Not for read models, routes, calculations, metrics, migrations, or governance-only edits. For adversarial review of a UI slice load .grok/skills/khepri-adversarial-review/SKILL.md instead.
user-invocable: true
argument-hint: "[surface or slice] [goal]"
---

# Khepri UI

Control plane for Khepri UI work. It says **where authority lives, what to read for this slice,
and which Khepri-specific traps recur**. It does not restate specs — read the cited sections.

**Presentation may change. Truth may not.** No slice under this skill adds a route, capability,
figure, governed word, filter, retained state, telemetry, dependency, or CSP relaxation.

## 1. Authority — resolve before touching a file

Chain (master spec §A.4): `governance/registry.yaml` → active specs' **§Scope** → roadmap →
blueprint → `docs/product/KHEPRI_DESIGN_LANGUAGE.md` → `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md`
→ approved reference pack / handoff → implementation.

1. Map every file you will edit to its governing spec with
   [references/authority-map.md](references/authority-map.md). Then **re-verify** in the spec's
   §Scope and "Not in scope" — the map is an index, the spec is the bound.
2. Confirm each cited spec is `state: active` in the registry. **Read the registry, not the spec
   header** — at `53f13fd`, `RCA-011`/`RCA-012` headers said "PROPOSED" while registry-active.
3. A file no active spec names is **blocked**. Say so and stop; do not draft authority unless the
   owner asks, and first ask what the page would actually do with it.
4. Read only the sections your slice touches: the governing spec's §Scope, the FRs you claim,
   §Exclusions, §Verification; plus the master-spec sections for your change type (§7 assets,
   §8 charts, §9 RTL, §10 responsive, §11 accessibility, §12 motion, §13 states, §15 anti-patterns,
   §16.3–16.5 binding/pack/palette, §17 acceptance).
5. **Status comes from `git log`, the registry, and the tests** — never from master spec §18/§19,
   roadmap tables, or plan checkboxes. They drift (at `53f13fd`, §18.1 said no U1-05 code existed
   while `u1-05` slices had merged).

**Design material is evidence, never authority.** `docs/ui/design_handoff_khepri_product_ui/` is
the current handoff (README authority notice first, then `INTERACTIONS.md`);
`docs/ui/design_handoff_khepri/` is superseded, history only; `docs/product/ui-visual-references/`
is acceptance evidence for composition. A pack's "files expected to change", "only permitted
edits", or "mandatory" carries **no** authority — its README says so. Never copy a route, figure,
sentence, refusal reason, or capability out of an image or prototype. Controls with no product
backing stay inert or are omitted, and are listed in the report.

**Cite FRs as `<SPEC> FR-nnn`, never bare.** `RRA-015` and `RCA-010` both define an `FR-193`.

## 2. Stable invariants

- **Bilingual/RTL:** Arabic and English are equal surfaces — every state, caveat, refusal, action
  and exit in both. `lang`/`dir` are server-computed, never inferred in a template. **Logical CSS
  properties only**; no literal arrow glyph as a navigation affordance. Language is an address
  segment; the switch is a link, not a JS toggle. Customer strings live in copy modules with
  import-time parity, never in templates or JS.
- **Accessibility floors, by surface:** shell → `RCA-010 FR-200`; report/evidence →
  `RRA-015 FR-189` (+ `RRA-015 FR-193` remediation); `/beta` → `RRA-010` §Invariants. Targets are
  measured on the element the pointer lands on; contrast is computed, not asserted.
- **Reachability:** a new or restyled surface must be linked from the surfaces a reader actually
  arrives through — check every *other* surface for the link. `RCA-010 FR-193`: no "coming soon",
  no nav entry for an unimplemented destination. One nav, exactly one `aria-current="page"`
  (`RCA-010 FR-194`). Every page, refusals included, has an exit.
- **States:** refusal, empty, loading and error are four distinct structures; a refusal never shares
  an element or class with an error and never carries error paint (`RCA-010 FR-202`).
- **Palette/typeface:** colour values come from master spec §16.5 as tokens on `:root` in
  `shell.css` (tokens-only; the test enforcing it stays green). Dark *rail*, not dark *theme* — no
  theme switcher. Typeface is the vendored Noto Sans Arabic; no Source Serif, no font CDN.
- **Per-surface ownership:** shell, journey and report each own their values. No shared token layer
  (`RCA-010 FR-201`), no shell stylesheet naming a `/beta` address (`RCA-011 FR-208`,
  `RCA-012 FR-217`), no shell asset on a `/beta` page.
- **Assets** (master §7, `RCA-010 FR-206`, `RRA-015 FR-192`): no CSS/div/pseudo-element art, emoji
  or Unicode-glyph icons, or implementer-authored inline SVG illustration; no external
  font/image/script; no inline script/style. Assets are served by exact name from an allowlist
  with audited digests (`RCA-012 FR-212`–`FR-215`); the 2.4 MB source PNG is never served. Absent
  approved asset → ship without, never an approximation. Data-driven charts are the only
  programmatic drawing.
- **Visual language:** preserve the approved Khepri direction (warm limestone surfaces, navy rail,
  gold accent, governed density). Drift is a defect even when tests pass (master §16.3). Do not
  "modernize" into generic SaaS.

## 3. Workflow

1. **Inspect** the shipped surface and its tests before designing.
2. **Name the contract:** slice ID, spec, FRs, the files §Scope admits. Reuse settled decisions
   (palette, typeface, hero ownership, skip-link mechanism); do not reopen them.
3. **Implement the minimal slice** inside that scope. No adjacent refactor, no governance or spec
   edit unless implementation is genuinely blocked — then report the block instead.
4. **Validate** with the evidence in §4, then the repo gates: `uv run khepri-gov validate`,
   `uv run ruff check .`, `uv run pytest` (read the counts line; exit 0 can hide errors).

One PR per slice: plan + RED commit, then implementation, in the same PR.

## 4. Evidence

- **`set_content` browser tests are regression evidence only.** The shell/journey/report matrices
  (`test_r810`/`r811`/`r812`, `test_rra015_*`) build pages with no HTTP origin, so a relative
  `url()` resolves to nothing. To prove a font, image, or stylesheet **loads**, run the real app on
  a loopback port and assert the wire — pattern: `tests/test_rca011_shell_font_load.py`,
  `tests/test_rca012_shell_hero_load.py`.
- **A typeface or type-scale change moves metrics:** re-run the whole browser matrix, both
  languages, all viewports (`#489` found a latent overflow this way).
- **Visual regression** (`RCA-010 FR-204`, `RRA-015 FR-190`): judged on hierarchy, density, rhythm,
  typography, states, RTL, responsive, asset fidelity — not pixel identity. Deterministic across two
  runs, repo-only, no hosted baseline. Baselines never supply facts.
- **CI:** browser tests carry `@pytest.mark.browser`; `.github/scripts/require_browser_tests.py`
  fails the job if any skips. A locally skipped browser test is not evidence — install Chromium
  (`uv run playwright install chromium`) and run them.
- **Null case:** a fixture that makes the surface render nothing is "not exercised", not PASS.
- Replace a text-grep assertion with a computed-style assertion on a rendered page, never delete it.

## 5. Repository traps

- **CodeScene scores `docs/`, CSS and tests too.** Never commit vendored/generated output (handoff
  `support.js` scored 2.40). Adding lines to an already-complex function degrades it even if the
  lines are docstrings — move prose to module level.
- **Guards derived from rendered output** fire on correct markup; derive a guard's input from the
  binding (copy tables, `_ASSETS`, destinations), and give every derived set a non-empty assertion.
- **`.impeccable/config.json` side-tab exceptions** are the governed refusal shape
  (`border-inline-start` 4px). Do not "fix" them.
- **Refused sections still render governed prose** — never build fixture expectations from what
  happens to publish.
- **`RRA-013` is a data path, not UI authority:** drawer data comes through
  `src/khepri/rra/bundle.py`, which a presentation slice does not touch.
- **Owner-pending readings** (e.g. the `RRA-010` journey-adoption reading,
  `docs/superpowers/plans/2026-09-03-rra010-journey-adoption-reading.md`): before relying on one,
  check the registry and `git log` for an owner decision. Never act as if an option were chosen.

## 6. Design tooling — delegate, don't duplicate

- **Skill `impeccable:impeccable`** for generic design quality, run in the master spec §17 order:
  critique → audit → harden → polish, against the approved reference, once per new implementation
  evidence. Feed it this skill's constraints and the reference image, not freedom to redirect.
- **Agent type `impeccable:impeccable-finish-reviewer`** for the finished-build check against the
  direction.
- **Skill `frontend-design:frontend-design`** only for implementation mechanics (CSS technique,
  layout craft). Its instinct to invent an aesthetic is exactly what master §16.3 forbids.
- **`.grok/skills/khepri-adversarial-review/SKILL.md`** (load the file; slice layer) for
  independent review of scope, grant, and evidence.

## Red flags — stop

- Editing `shell_api.py`, `journey/routes.py`, `html.py`, `bundle.py`, or any `runtime/*.py`
  because a handoff lists it.
- A colour, sentence, count, or route typed from a screenshot or prototype.
- "Browser tests pass" when they skipped, or when only `set_content` tests exercise a new asset.
- A physical `left`/`right`/`margin-left` property, or a `→` used as navigation.
- A new surface with no inbound link, or a nav entry with nowhere to go.
