# #575 — a refused result states the result sentence, not the section sentence

**Specification:** `RRA-009` (registry `active`) §Refusals part 1 ("which business analysis was
unavailable, named as a capability"); `RRA-006` (registry `active`) is unchanged. §Preservation
holds: no figure, caveat, section or code is added, removed or recomputed.

## Defect

`wording.caveat_prose` resolves a joined `<result>:<reason>` code. It checks
`reason in GOVERNED_SECTION_REASONS` first, so every reason the section and result tiers share
takes the section sentence and the refused result is never named. Over a real bundle:

- `basket_items_per_transaction:incomplete_transaction_identifiers` reads "Basket size — not
  available".
- `basket_attach_rate:repeated_row_signature` reads "Basket size — not available".
- `revenue_delta_absolute.period_over_period:coverage_structurally_incompatible` reads "Comparison
  with an earlier period — not available".
- `revenue_delta_percent.period_over_period:required_input_unavailable` reads "This analysis — not
  available".

The issue names three shared codes. The tiers actually share five (`_SHARED_TIER_CODES` in
`tests/test_rra009_wording.py`): the three plus `repeated_row_signature` and
`coverage_structurally_incompatible`. All five have a governed result sentence in both languages,
so all five are routed. No wording is added.

## Fix

In `caveat_prose`, a reason with a governed result sentence takes that sentence. The section
sentence stays for:

- section-only reasons such as `prior_window_absent`, which have no result sentence;
- a left half that is a governed section id rather than a result, such as
  `growth:family_version_pairing_unadmitted`. No production path emits that shape, but
  `test_rra004_version_gate_wiring.py` pins it.

The decision moves into a small helper so `caveat_prose` does not grow.

## Known consequence (`#560` item 2, still deferred)

The `required_input_unavailable` result sentence fills `{column}` with the metric's own name,
because the joined code does not carry the refusing input. So after routing, part 1 is right and
part 4 names the metric ("the file does not contain Revenue change"). The strict xfails in
`tests/test_rra009_refusal_names_the_column.py` move from a count of 0 to a count of 2. They still
fail, so they stay xfailed; only their docstring is updated.

## Tests (RED first)

In `tests/test_rra009_result_refusal_sentence.py`, over real bundles built by
`tests.test_rra008_assembly.package_for(..., published=True)`, in both languages:

- every emitted shared-code result caveat opens with its own metric's business name and the
  governed result wording, pinned literally;
- none of them is the section sentence or names another analysis's heading;
- the `report_api` quality response's `refused_results` words them the same way;
- `family_version_pairing_unadmitted` has no result-tier emitter, so it is checked by a direct call;
- section-only reasons and a section-id left half keep the section sentence.

Mutations: restore the old condition (RED tests fail); route everything to the result tier (the
section-reuse tests fail); drop the section-id branch (the version-gate test fails).
