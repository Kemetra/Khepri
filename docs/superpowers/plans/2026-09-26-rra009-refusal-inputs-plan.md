# RRA-009 refusal inputs: `repeated_event_key`, and a refused result names its column

**Issues:** `#326` item 4 (the whole remaining scope), `#575` (its last held code), and `#560`
item 2 only.

**Specifications (registry `active`):** `RRA-009` §Refusals, `RRA-004` §Stable contract and
versions, `RRA-003` §Event and transaction identity.

**Owner decisions this slice implements:**

- 2026-09-24, on `#326`: a repeated event key and a repeated canonical row signature get distinct
  governed reason codes.
- 2026-09-26, on `#560`: name the missing column with the journey's column-mapping labels, in
  both languages. `RefusedResult` carries the refusing input (a semantic). The package-document
  version move is approved, and the reader stays lenient when the field is absent.

## 1. `repeated_event_key` (`#326` item 4)

The two causes are exclusive by construction:

- `facts._repeated_signature_kinds` answers only for a contract without event keys.
- `admission._repeated_event_key_kinds` answers only for a keyed contract.

So `_Causes` carries one `repeated_reason`, chosen once from which of the two fired. Every
existing boolean override (`repeated=repeated_sales`) keeps working. The resolver's order does not
move: gap, then repeated (either code), then identifiers, then mapping. `RRA-009`'s cause-order
bullet names only `repeated_row_signature`, and it forbids a slice from ordering other pairs. The
new code takes the slot its cause already occupied, and the bullet's wording is left for the owner
(see "Owner items").

`_collision_kinds` also reports a **blank** key component as a repeat. The new sentence is
therefore true of a shared reference and of a missing one.

The basket family copies the package's transaction refusal verbatim into its section reason, so
the code is governed at both tiers:

- `REASON_REPEATED_EVENT_KEY` goes in `facts.py`.
- `SECTION_REASON_REPEATED_EVENT_KEY` goes in `bundle.py` and in `SECTION_REASONS[basket]`.
- English and Arabic prose go in at both tiers. Each is derived from the shared prose by deleting
  the "identical in every column" alternative and stating the blank case.

The `repeated_row_signature` prose is unchanged.

## 2. A refused result names its missing column (`#560` item 2, `#575`)

- **Carrier.** `RefusedResult.input: str | None`.
  - The writer omits the key when it is `None`.
  - The reader uses `.get`. An absent key reads as `None`, and an unknown semantic refuses as
    `PackageCorrupted`.
  - `_reason_for` returns the reason together with its input. The input is the first unmapped
    input for `required_input_unavailable` and `ambiguous_mapping`, and the first of the result's
    own inputs that is gapped for `incomplete_column_coverage`. A module-level `_refused` builds
    the `RefusedResult`, so `_build` does not grow.
- **Version.**
  - `PACKAGE_VERSION` moves to `rra004.package.v4`.
  - `(mapping.v3, package.v4, formula.v2)` is added as a new row of `ADMITTED_PACKAGE_PAIRS`, and
    no existing row is edited.
  - `RRA-004` §Stable contract gains the successor sentence.
- **Family paths.** Basket reports the package's own recorded refusal and its input: for items per
  sale when units are unavailable, and for the identifier path. Comparison and growth refuse with
  `required_input_unavailable` without knowing a column, so they carry no input.
- **Transport to prose.**
  - `StatedCaveat.refusing_input` is kept out of `as_document()`, for the reason `evidence` and
    `refusals` already give: the bundle identity digests the package the input comes from.
    `BUNDLE_VERSION` therefore does not move.
  - `wording.caveat_proses(caveats, language)` is the one resolver every surface reads: the page,
    the evidence page, the workbook, and both `report_api` responses.
- **Labels.** `{column}`/`{field}` are filled from `journey.copy.JOURNEY_COPY["semantic_<x>"]`, one
  source, with an import-time completeness check over every governed semantic.
- **Fail closed.**
  - `required_input_unavailable` takes the result sentence only when its input is known.
    Otherwise it keeps the section sentence, which is vague but true. The `#575` hold therefore
    becomes conditional rather than a code list.
  - `incomplete_column_coverage` and `ambiguous_mapping` have no section sentence. With no input
    they render as before, which is recorded as a residual.

## Tests (RED first)

`tests/test_rra009_refusal_inputs.py`, over real CSV bytes through the real pipeline:

- An event-key collision and identical rows produce different codes, asserted by code. A blank
  key refuses as `repeated_event_key`.
- A keyed collision refuses the basket section as `repeated_event_key`, worded in both languages
  at both tiers through `refusal_message` and `section_refusal_message`.
- A refused result records its input for `required_input_unavailable`, `ambiguous_mapping`, and
  `incomplete_column_coverage`.
- A bundle without units: the page's basket section and the quality response name the metric
  once and the column literally ("Units" / "الكمية"), in both languages.
- A package document without `input` still loads and re-serializes identically. With `input` it
  round-trips. An unknown semantic refuses.
- A package stamped `rra004.package.v99` refuses to build.

These pins change: `test_rra009_wording.py` (codes, counts, shared set, the Arabic result pin),
the `#560` strict xfail (removed; it now passes the refusing input), the keyed-contract assertions
in `test_rra004_facts.py` and `test_rra003_event_admission.py`, the package-version ratchet, and
the admitted-table extent.

## Owner items (not decided here)

- `RRA-009`'s cause-order bullet names `repeated_row_signature` alone.
- The catalogue counts in `RRA-009` were already stale: the text said 9/8/17/14 with 3 shared
  before this slice. They are recounted from `REFUSAL_WORDING`.
- The new Arabic and English sentences are derived rather than decided copy.
