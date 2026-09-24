# #531 — the report bundle carries the package's per-result refusals

**Authority:** the owner's decision on `#531` (2026-09-24): "approve a narrow extension of
`RenderableBundle`" carrying governed `availability`/`reason` sources, with no new fact derived and
no reach past the bundle to the package. `RRA-006` gains the one Requirements clause below;
`RRA-014` `FR-136` admits a *source shape* by name and `FR-140` already requires that "every source
refusal … survives projection", so `RRA-014` needs no amendment. The amendment is approved when the
owner merges this PR (Constitution II).

**Vehicle:** one PR — this plan and its RED tests, then the amendment and implementation.

## Why

`#551` (slice 5a + 5b) probed `ReportBundle.of(package(GOLDEN))`: the package holds nine
`RefusedResult`s (`cost`, `discount`, `gross_margin`, `gross_profit`, `returns`,
`revenue_by_product`, `units_by_product`, `revenue_by_channel`, `units_by_channel`) and the bundle
carries none of them. The `<result>:<reason>` caveat channel (`bundle._scoped`) covers only results
refused inside a family section. So `MetricAvailabilityView` states nothing about a refused gross
margin, and `FR-140` is unmet for the headline metrics.
`test_headline_refusals_do_not_travel_on_the_bundle_so_no_row_states_them` pinned the gap to fail
once they travel.

## Design

- **A member, not the caveat channel.** `ReportBundle.refusals: tuple[RefusedResult, ...]` is
  `package.refusals`, verbatim and in package order. It uses an existing governed type and adds no
  vocabulary. Routing these through `caveats` would put nine new codes on every web, PDF and Excel
  surface and into `definitions.summarize`'s refused-result count, which is a customer-surface
  change nobody authorized.
- **Not in `as_document()`, so no bundle-version bump.** The refusals are a function of the package,
  and the identity already digests everything the package is derived from: source digest, profile
  digest, the three versions, and coverage. This follows the precedent `evidence` sets. Adding the
  refusals to the document would rename every stored report with no change in what was published.
  `BUNDLE_VERSION` stays `rra006.bundle.v8`.
- **`RenderableBundle` declares `refusals`.** `CrossVersionBundle` states `()`. `RRA-006`
  §Two-population → Refusal gives a refused pair no bundle at all, and an admitted pair's own
  refused cells travel on its caveats as today. Its `as_document()` is unchanged, so
  `rra006.crossversion.bundle.v1` stands.
- **The projection requires the member.** `refusals` joins `_REQUIRED_MEMBERS`, so a source without
  it fails closed as `unrecognized_source`; it is never read with a `getattr` default. The headline
  refusals are read in the result tier: after figures, beside `_result_refusals`, and before the
  refused-section tier.
- **Customer effect.** Runtime availability reaches a customer only through `read_cards`, and a card
  is keyed on an overview figure. A refused metric has no figure, so it gains no card and no rendered
  row. The new rows reach `MetricAvailabilityView` and `read_limits`, and no surface renders them.
  No template, copy or wording changes.

## RED tests (`tests/test_issue531_bundle_refusals.py`)

1. The real bundle's `refusals` names exactly the nine metrics above, written as a literal rather
   than derived from `package.refusals`.
2. `MetricAvailabilityView` over the real bundle states `gross_margin` as `unavailable` with
   `required_input_unavailable`. The old pinning test is removed, because this is its flip.
3. Every availability-allowlisted headline refusal gets a row. `revenue_by_product` and its three
   siblings are outside the view's metric allowlist, so they get none.
4. A source without `refusals` is refused as an unrecognized shape, not projected.
5. `read_limits` over the real projector reports `gross_margin` unavailable with its reason.
6. `CrossVersionBundle.refusals == ()`. Neither document has a `refusals` key, and
   `BUNDLE_VERSION` is unchanged.

**Mutants to kill:** drop the argument in `ReportBundle.of`; drop the headline reader in the
projection; remove `refusals` from `_REQUIRED_MEMBERS`.

## Gates

`uv run khepri-gov validate`, `uv run ruff check .`, the full `uv run pytest` (read the counts
line), and CodeScene on `bundle.py`, which is at its function budget, so no new function goes
there.
