# SCRUM-26 slice: the dimension is a governed token, the label the bare value (A3b)

> Plan and RED evidence for one slice. The reading is the owner's, recorded as the `RRA-006`
> amendment in `#637` (`99eaf5f`). A3b was recorded in
> `2026-09-29-scrum-21-u1-acceptance-evidence.md`.

## Authority

`RRA-006` §Requirements and §Verification as amended by `#637` (registry `state: active` at
`62f15e3`). `RRA-018` §Exclusions bars `bundle.py` and `BUNDLE_VERSION` changes for `RRA-018`'s
own slices only. This is an `RRA-006` slice under the amended text.

## Change

- **The figure.** `CitedFigure.dimension` is a token from the basket dimension vocabulary
  (`basket.GOVERNED_DIMENSIONS`: `product`, `category`), or `None`. It is in the figure's
  document, so every bundle id moves, and `BUNDLE_VERSION` advances to `rra006.bundle.v9`.
- **The label.** `basket.attached_label_of` returns the bare value, and the new
  `attached_dimension_of` returns the token. `_Family.dimension_of` carries the token from the
  family to `_analysis_figure`. Only basket has one.
- **The qualifier.** The wording is `wording.DIMENSION_QUALIFIERS` (EN `product` / `category`,
  AR `منتج` / `فئة`), composed by `wording.qualified` as "value (qualifier)". It is asserted at
  import over the dimension vocabulary, and it is distinct from `DIMENSION_NAMES`' "each
  category".
- **The surfaces.**
  - Every customer label goes through `wording.category_of` and `worded`: the page's rows, the
    workbook's business rows and native chart. `ChartCategory` carries the token.
  - The SVG chart's `ChartLabel` carries the token, and `html._chart_of` composes it in the
    page's language.
  - The semantic projection's `dimension` column reads the token where a figure carries one.
- **Reconciliation.** Reconciliation compares figure text and identities, never a composed label.
  The token is on the identity document, so two figures that differ only in dimension have
  different documents.
- **Stored bundles.** A delivered report is never rebuilt: its `BundleAttempt` and delivery
  record carry their own version string and `bundle_id`. A v8 report keeps v8.

## Not in this slice

- `aggregates._discriminator` also composes `label (…)`, but with a six-hex digest that breaks a
  label collision, not a dimension word. It never names a dimension, so the amendment does not
  reach it.
- `projection._matches` still keys a filter's dimension on the metric code. Matching attach rates
  by their token would widen what a semantic-view filter returns, and that is not this slice.
- The workbook's audit trail prints the bare label beside the figure and citation ids, which
  already tell two rows apart.

## Tests (RED at `7e54564`)

`tests/test_rra006_dimension_token.py`, over real CSV bytes in which a product `Water` and a
category `Water` share one value:

- each attach rate carries its token and a bare label, and both are in its document;
- other figures carry `None`;
- the identity records `rra006.bundle.v9`, and a stored v8 attempt keeps v8;
- the page and the workbook name `Water (product)` / `Water (category)` in English and
  `Water (منتج)` / `Water (فئة)` in Arabic, and the Arabic page prints no English qualifier;
- the chart names each bar with its qualifier in both languages. A mutant that skips the
  composition turns this test red;
- the projection reads the token.

`test_rra008_basket.py::test_attach_labels_name_the_dimension_they_belong_to` now asserts the
`(token, label)` pair, which is the amended contract.
