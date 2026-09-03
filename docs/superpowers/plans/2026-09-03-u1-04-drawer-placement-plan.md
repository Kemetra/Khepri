# U1-04 — placing the evidence drawer beside each figure

**Authority:** active `RRA-012` FR-096, FR-096a, FR-097, FR-098, FR-099, FR-101. **Scope:** the
`U1-04` placement slice — `_evidence.html.j2`, the drawer macro in `_components.html.j2`,
`report.css`, and tests. **Preconditions met:** the drawer's structure (`#352`) and its supply
(`RRA-013`, `#355`) are merged, so the audit context carries `evidence` and `coverage`, and the print
context carries `evidence_open`.

**Status:** bounded plan. Its RED tests land with it (`tests/test_u1_04_drawer_placement.py`), which is
what §15 requires before `U1`'s row moves to `READY_FOR_IMPLEMENTATION`.

---

## Three checks against the tree, run before this plan was written

### 1. "Beside that figure" means one drawer per figure row, and the cost is accepted

The evidence figures table (`_evidence.html.j2:27-36`) renders one `<tr>` per `audit.figures` cell,
and several cells share a citation — every point of a series cites one record. Two placements were
weighed. **Per citation, at the `#citation-…` anchor** the evidence link already targets: one drawer
per record, reached by a click from the figure. **Per figure row**, as a second `<tr>` spanning the
table directly below each figure. FR-096 says *"for one figure, beside that figure"*, and a drawer a
reader reaches by leaving the row is not beside it. **Per figure row it is.** A series of twelve
points renders twelve drawers of one record; that repetition is the literal requirement's price, and a
`<details>` closed by default keeps the table readable.

### 2. Coverage arrives separately, and the macro's signature changes here

`RRA-013` FR-106 carries `coverage` once at bundle level and forbids copying it into an entry. The
merged macro (`_components.html.j2:192`) reads `given.coverage_manifest_identity` and
`given.coverage_signatures`. **The macro gains a `coverage` argument** — `evidence_drawer(given, chrome,
coverage, open=false)` — and reads `coverage.manifest_identity` and `coverage.signatures`. This is the
change `RRA-013`'s Scope named for the placement slice, and `_components.html.j2` is `RRA-012`'s file.
`test_u1_04_evidence_drawer.py`'s fixtures split accordingly.

### 3. `evidence_open` is absent on the web, by requirement

`RRA-013` FR-107, read literally: the web contexts do not carry the key; the print context sets it
true. The template reads `evidence_open | default(false)`. Jinja's `default` filter tests for
`Undefined` and is therefore defined for `StrictUndefined`, which `test_the_default_filter_survives_
strict_undefined` proves before anything depends on it.

---

## What is being built

- **`_evidence.html.j2`** — after each figure `<tr>`, a `<tr class="evidence-drawer-row">` with one
  `<td colspan="7">` holding `evidence_drawer(audit.evidence[cell.citation_id], chrome,
  audit.coverage, open=evidence_open | default(false))`. The import line gains `evidence_drawer`.
- **`_components.html.j2`** — the macro's `coverage` argument (check 2). Nothing else.
- **`report.css`** — the shared `th, td` rule puts the divider under every cell, so the figure row
  marks itself `evidence-figure-row` and **loses** its bottom rule while the drawer row **keeps**
  its own: the line then falls under the pair, grouping each drawer with the figure above it and not
  with the figure below (`#356` review). Logical properties only. **`report.print.css`** gains
  `.evidence-figure-row { break-after: avoid; }`: its `tr { break-inside: avoid }` keeps each row
  whole and lets the table break, so without this a drawer could open the next page away from its
  figure (`#356` review). Chromium's actual pagination is exercised only by the local-only browser
  tests; the RED test reads the rule.
- **Tests** — `test_no_surface_places_the_drawer_before_its_supply_exists` is **deleted**; this is the
  PR entitled to. The U1-04 fixtures split coverage out of `STORED_FIGURE`/`DERIVED_FIGURE`.

## RED tests — the deliverable

`tests/test_u1_04_drawer_placement.py`, strict-xfail, on rendered documents.

1. `test_every_evidence_figure_row_is_followed_by_its_drawer` — FR-096: as many drawers as figure
   rows, each carrying the evidence link of the row above it.
2. `test_the_business_page_carries_no_drawer` — tier boundary.
3. `test_the_drawer_reads_coverage_once_from_the_bundle` — FR-104/FR-097: every drawer's coverage is
   the identity's, and no per-figure population appears.
4. `test_a_derived_figure_drawer_states_absent_inputs` — FR-096a, on the page.
5. `test_drawers_render_in_arabic_with_arabic_labels` — FR-099.
6. `test_print_drawers_are_open_and_web_drawers_are_closed` — `RRA-013` FR-107 meets FR-098.
7. `test_the_stylesheet_groups_each_row_pair` — the screen rules that group each pair and the print
   rule that keeps the pair on one page, read from the stylesheets (`#356` review).
8. `test_the_default_filter_survives_strict_undefined` — check 3's premise (not RED; holds today).

## Out of scope, and why

- The citation route reading `bundle.evidence` — `RRA-011`'s.
- Journey adoption — `RRA-010`:88.
- Any change to what the drawer renders — merged at `#352` and not reopened here.
