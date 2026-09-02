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

## Where the components live

**As Jinja macros in `_components.html.j2`**, the pattern `report.html.j2:1` already uses for the
chart (`{% from "_chart.svg.j2" import chart %}`). This matters for authority, not taste: `RRA-012`'s
Scope authorizes the rendering templates, `report.css`, `wording.py`'s chrome labels, the `_CHROME`
binding point, and tests. **It authorizes no new Python module.** An earlier draft of these tests
imported `khepri.rra.rendering.components`, which would have required widening the specification a
sixth time — caught in review and corrected here.

## RED tests — the deliverable

23 tests in `tests/test_u1_02_component_layer.py`, each failing now for the stated reason and passing only when its component exists. The headings below group them by requirement, not by file.

**All seven components are covered, parametrized rather than looped.** A loop stops at the first
missing component and reports one failure; parametrized tests report *which* of the seven are absent.
An implementation carrying only the three that were easy to write fails four of them — which is the
gap an earlier draft had, covering figure, refusal panel and status badge alone.

### Components, fail-closed, and value fidelity

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

### Vocabulary, parity, and colour

6. **`test_every_chrome_label_exists_in_both_languages`** — drives the import-time completeness
   assertion FR-095a requires over the new chrome labels. **Fails now:** the labels do not exist.
7. **`test_each_component_renders_in_both_languages[7]`** — FR-099, **per component**. A page-level
   marker check would pass while the refusal, version or coverage components were absent from Arabic
   entirely. Each is asserted present in both documents, and the Arabic document must carry Arabic
   script and `dir="rtl"` — so "renders in Arabic" cannot be satisfied by English text under an `ar`
   label.
8. **`test_no_component_signals_status_by_color_alone`** — asserts every status, refusal and caveat
   carries a text or non-color indicator. FR-100.
9. **`test_keyboard_reachability_is_not_claimed_for_static_components`** — asserts the static
   components are readable without entering the tab order. Guards the round-5 correction: only the
   drawer and its opener are interactive.

### No duplicate truth

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

---

## Status 2026-09-02 -- implemented on `feat/u1-02-components`

All 23 RED tests are green with their `xfail` markers removed, plus three added. Full
suite, `ruff check`, and `khepri-gov validate` pass. The FR-101 mutation check was run:
a bare `<td class="figure">` appended to `report.pdf.html.j2` -- a template no test names
-- fails `test_no_scoped_template_renders_a_figure_outside_the_component_layer`.

**What shipped.** `_components.html.j2` with the seven FR-092 macros; `report.html.j2`
and `_evidence.html.j2` render every figure, refusal, state, version and coverage value
through them; `report.css` gains the component rules (logical properties only);
`wording.py` gains `COMPONENT_CHROME` and `COMPONENT_STATE_WORDING` with an import-time
completeness assertion read from `GOVERNED_SECTION_STATES`; `html.py`'s only change is the
two `_CHROME` registrations (`component`, `component_state`) precondition 4 permits.

**Four design calls made unattended, recorded here for the owner's review at merge:**

1. **Three components render in the evidence region, not on the business page.** The
   RED placement tests looked for all seven on the business page. `RRA-009`'s
   `presentation-visibility-matrix.md` §A.5 puts a citation identifier and every
   `BundleIdentity` field (versions, `row_count`) in tier A, and `RRA-012` FR-095
   restates no `RRA-009` rule and relaxes none. So the evidence link, version label and
   coverage indicator render in `_evidence.html.j2` -- which is both the Technical
   Evidence page and the printed appendix -- and the placement tests carry a
   `COMPONENT_REGION` table saying so. A business page with an evidence link would also
   link to a citation anchor it does not contain, which `report.html.j2:54` already
   refuses as a dead link. This plan's component table said "the colophon's version
   text"; the colophon carries no version and never did.
2. **The colour test was rewritten to render the macros.** As landed it imported
   `khepri.rra.rendering.components`, the Python module the plan itself records
   `RRA-012` does not authorize. It now renders `status_badge` for every state in
   `GOVERNED_SECTION_STATES`, in both languages, and asserts a word survives tag
   stripping.
3. **Fail-closed is the environment's refusal.** The RED test accepted `KeyError` and
   `ValueError`; the layer is macros under `StrictUndefined`, so an unworded state raises
   `UndefinedError`, which the test now also accepts. Chrome stays pure data because
   `test_the_page_furniture_is_one_table_with_one_key_set` walks every `_CHROME` value
   and requires strings or nested tables of strings -- a callable would fail it.
4. **The quality summary groups what the page renders.** It cannot call
   `definitions.summarize` (no context key may be added under precondition 4), so it
   selects with template filters over the section views the page already iterates:
   refused = state is the governed refused constant, caveated = a present section
   rendering a section caveat list, answered = the rest. `summarize` partitions a scoped
   result refusal (`<result>:<reason>` caveat) as answered-with-refused-result rather
   than as caveated, so the two groupings can differ by that case. The deferred
   catalog-supply slice, which carries `summarize`'s output into the context, is where
   the page should switch to the catalog's grouping. Flagged, not hidden.

**Also moved:** `test_rra006_html_surface` and `test_rra006_series_pivot` counted figures
by the literal `<td class="figure">`; both now count by the class attribute, which is the
property they asserted. The evidence figures table's citation column is now the
evidence link (text unchanged: the citation code, now an anchor to its own entry).

**Left out, deliberately:** `U1-04` (the drawer), journey adoption, any print-stylesheet
rule for the new components (`report.print.css` inherits the screen rules; nothing in
them depends on background paint), and the §16 header SHA.

