# U1-02 — the governed data-display component layer

**Authority:** active `RRA-012`. **Scope:** `U1-02` only. `U1-04`'s drawer is half-authorized —
its structure is governed, its catalog data supply is deferred to its own artifact — and this plan
does not touch it.

**Status:** bounded plan. Its RED tests land with it, which is what §15 requires before `U1`'s row
moves from `READY_FOR_PLAN` to `READY_FOR_IMPLEMENTATION`.

---

## Three checks against the tree, run before this plan was written

`RRA-012` needed five review rounds because successive drafts asserted what the code permits without
tracing it. These were run first, and one of them found a defect in that specification.

### 1. `RRA-012`'s "new stylesheet" describes a mechanism that does not exist — **corrected here**

The specification's Scope says *"a new stylesheet for this component layer, under
`src/khepri/rra/rendering/`, **linked by** the templates above."* Nothing links a stylesheet. It is
inlined as **template source** — `{% include stylesheet %}` at `report.html.j2:20` and
`report.evidence.html.j2:16` — and `html.py:23` records why that is deliberate:

> *"The stylesheet is included as template source rather than passed in as a variable, which is what
> keeps `|safe` out of this template entirely: a page with one `|safe` in it has an escaping
> convention, not an escaping guarantee."*

The name comes from `STYLESHEET_NAME` at `html.py:87`, bound into context at `html.py:567`. A second
stylesheet therefore needs a new constant and a new context key in `html.py` — which precondition 4
does not permit, since it allows exactly one `html.py` edit, the `_CHROME` registration.

**Resolution: the component styles go in the existing `report.css`.** No new constant, no new
include, no second `html.py` opening. `RRA-012`'s Scope wording is corrected in this same PR to name
`report.css` rather than a new file, so the specification matches the tree rather than the tree being
bent to the specification. This is the same defect shape as the round-5 `_CHROME` finding: a Scope
line asserting a wiring point that was never checked.

### 2. Refusal prose is already governed chrome — no new wording is needed

`report.html.j2:65` renders `chrome.refusal_prose[section.section_id][section.reason]`, supplied by
`_section_refusal_prose()` at `html.py:99`. The refusal-panel component therefore consumes an
**existing** key. It authors no refusal wording, so FR-095 is satisfied by construction rather than by
discipline, and FR-095a is not stretched to cover something it should not.

### 3. `section.state` is correctly unavailable, and the status badge must not reach for it

`html.py:519` records that `section.state` is not carried — tier Internal, which `RRA-011` excludes
from the audit region. `report.html.j2:64` compares against `refused_state`, a chrome constant. **The
status-badge component consumes that same constant and never a raw state field.** A component
specified against `section.state` would be specified against a field that does not reach the
template.

---

## What is being built

Seven components, per FR-092, extracted from markup that already renders these concepts by hand. The
work is a **consolidation**, not a new surface: `report.html.j2:111` renders
`<td class="figure">{{ cell.text }}</td>` today, and three other places render the same concept
differently.

| Component | Replaces | Consumes |
|---|---|---|
| Figure | `<td class="figure">` at `report.html.j2:111`, `:155` | `FigureCell.text` |
| Status badge | the `refused` paragraph at `:65` | `chrome.refused_state` |
| Quality summary | (new markup, existing data) | section counts already in context |
| Refusal panel | `<p class="refused">` at `:65` | `chrome.refusal_prose[...]` |
| Evidence link | the audit-region links in `_evidence.html.j2` | existing citation ids |
| Version label | the colophon's version text | existing context keys |
| Coverage indicator | (new markup, existing data) | package coverage already in context |

**`FigureCell` carries no `value` field, deliberately** (`html.py:232`): *"a renderer holding the
`Decimal` beside the string is a renderer that can format the number itself."* FR-093 is therefore
already structurally guaranteed for the figure component, and the RED test below proves the guarantee
rather than assuming it.

---

## RED tests — the deliverable

Each fails now, for the stated reason, and passes only when the component exists.

### `test_u1_02_components.py`

1. **`test_every_figure_renders_through_the_figure_component`** — renders a bundle, parses the HTML,
   asserts every element carrying a figure has the component's marker class. **Fails now:** figures
   are bare `<td class="figure">`.
2. **`test_a_refusal_renders_through_the_refusal_panel`** — asserts a refused section's prose sits
   inside the panel component. **Fails now:** it is a bare `<p class="refused">`.
3. **`test_a_component_never_reformats_a_given_value`** — renders a `FigureCell` whose `text` carries
   a precision the component's default would not produce, and asserts the given string survives
   byte-for-byte. **Fails now:** no component. Proves FR-093 against the structural guarantee rather
   than restating it.
4. **`test_an_unknown_code_fails_closed`** — a status badge given a code with no governed rendering
   must raise the governed refusal, not render the code string, an empty element, or a blank.
   **Fails now:** no component. FR-094.
5. **`test_the_status_badge_never_reads_section_state`** — asserts the badge's inputs do not include
   a raw `section.state`, since `html.py:519` records it is not carried. FR guard against check 3's
   trap.

### `test_u1_02_parity.py`

6. **`test_every_chrome_label_exists_in_both_languages`** — drives the import-time completeness
   assertion FR-095a requires over the new chrome labels. **Fails now:** the labels do not exist.
7. **`test_components_render_in_both_languages_with_rtl_parity`** — FR-099, under `RRA-006`'s
   existing parity rule.
8. **`test_no_component_signals_status_by_color_alone`** — asserts every status, refusal and caveat
   carries a text or non-color indicator. FR-100.
9. **`test_keyboard_reachability_is_not_claimed_for_static_components`** — asserts the static
   components are readable without entering the tab order. Guards the round-5 correction: only the
   drawer and its opener are interactive.

### `test_u1_02_no_duplicate_truth.py`

10. **`test_no_scoped_template_renders_a_figure_outside_the_component_layer`** — FR-101's guard, and
    the load-bearing one.

    **It enumerates templates from the directory rather than a hand-written list.** A scan naming its
    own modules reproduces the drift it exists to catch. It walks
    `src/khepri/rra/rendering/templates/*.j2`, and asserts the enumeration is non-empty so a glob that
    matches nothing fails instead of passing vacuously.

    **Mutation check, run before this test is believed:** add a hand-built `<td class="figure">` to a
    template the scan should cover and confirm the test fails. A guard that cannot fail is not a
    guard.

---

## Sequence

1. Land this plan and its RED tests. `U1`'s §16 row moves to `READY_FOR_IMPLEMENTATION`.
2. Correct `RRA-012`'s Scope wording to name `report.css` (same PR — the plan must not be written
   against a specification known to be wrong).
3. Implement the seven components, in `report.css` and the scoped templates.
4. Register the FR-095a chrome labels in `_CHROME` and its context binding — the one `html.py` edit
   precondition 4 permits.
5. Run the FR-101 mutation check.

## Out of scope, and why

- **`U1-04`'s drawer data supply** — deferred to its own artifact; it is a materialization-path
  change, not a component one.
- **Journey adoption** — `journey/templates/base.html.j2` loads only `/beta/assets/journey.css` and
  `RRA-010`:88 excludes a new asset filename; that needs an `RRA-010` slice.
- **`U1-03`, `U1-05`, `U1-06`, `U1-07`** — excluded from `RRA-012` and still `BLOCKED`.
- **Any new figure, code, or metric wording** — `RRA-004`, `RRA-008`, `RRA-009`, `RRA-011`.
