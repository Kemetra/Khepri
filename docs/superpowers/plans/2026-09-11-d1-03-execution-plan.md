# `D1-03` — The metric card, the first decision surface, and one absence

> **Execution plan** (the `W1-09` tier). Parent: the allocation plan at
> `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`.
> **Authority:** active `RCA-008` — `FR-161`, `FR-162`, `FR-164`, `FR-170`, `FR-171`.

**Deliverable:** `decision/card.py` (the `FR-162` card contract and its four-status selection),
`runtime/shell_decisions.py` + `shell_templates/decision.html.j2` (the first decision surface),
and `offers_decisions`, the `FR-046` predicate its route will need.

> **Amended during GREEN, and the amendment is the record.** This plan first said the slice ships
> the route and a `decisions` field on `ShellServices`. Neither shipped: a decision route needs the
> session and membership resolution `shell_comparison.py` reaches through `_RouteCall`, and driving
> it needs the `W1-04b` journey harness. An HTTP surface no test drives would be worse than a
> deferred one, and question 4 below leaves it unreachable in a deployment regardless. `D1-04`
> ships it, driven. The `FR-164` step below is likewise corrected: the wording is
> `ViewRefusal.wording`, not `refusal_message` — see §The refusal catalog.

---

## Four scope questions, answered from precedent rather than assumed

**1. May a new `shell_*.py` module be created, when §Scope names only `shell_api.py`?**
Yes. `RCA-005` §Scope uses the identical wording — "`src/khepri/runtime/shell_api.py` and
`shell_templates/`" — and under it the repository created `shell_comparison.py`,
`shell_deletion.py` and `shell_pins.py`. That phrase reads as the shell surface layer, and
`shell_api.py` is already 946 lines: adding a surface inline would risk the hotspot decline
§Verification forbids. `_declare_route_modules`' own docstring anticipates this — "a fifth
surface should not have to pay to be added".

**2. Where does the card's metric *label* come from?** The surface, not the read model.
`khepri.rca` may not import `khepri.rra`, but `khepri.runtime` may, and `landing_api.py` already
names metrics through `metric_business_name(metric, language)` so "a catalog rename reaches this
page instead of drifting from it". `FR-159` admits exactly this: "Structure and navigation may
come from `RCA-005` records and the `RRA-011` catalog; figures may not." So `card.py` carries
governed metric *codes* and the surface names them.

**3. Where do the availability literals live?** In `card.py`, as `D1-02` put the view versions in
`seam.py`, for the same reason and with the same cost. `definitions.AVAILABLE`/`PARTIAL`/
`UNAVAILABLE` are `khepri.rra`'s and unimportable here; the literals are therefore pinned and
**asserted against `khepri.rra.definitions` in test**, so drift fails visibly.

**4. Does this slice wire the surface into a running deployment?** **No, and that is the one thing
this plan cannot deliver.** `ShellServices` is constructed in `src/khepri/runtime/wiring.py`,
which `RCA-008` §Scope does not name and whose neighbourhood §Exclusions guards ("no change to
the query orchestration or the composition root"). No active specification claims `wiring.py`,
so whether it is D1's to edit is **an owner question, raised and not decided**.

The consequence is bounded and has precedent: `decisions` joins `ShellServices` as an optional
collaborator beside `comparisons`, `pins` and `deletion`, each of which documents that "a
deployment without it declares no route, so the address is unknown rather than refused
differently (`FR-046`)". The surface is therefore complete, driven and tested — and reachable in
any deployment that passes `decisions`, which today is the tests.

---

## Files

```text
src/khepri/rca/workspace/decision/card.py    NEW  the FR-162 contract, status selection
src/khepri/runtime/shell_decisions.py        NEW  view assembly, render, offers_decisions
src/khepri/runtime/shell_templates/decision.html.j2   NEW
tests/test_d103_metric_card.py               NEW
tests/test_r807_shell_quality.py             EDIT _UNROUTED_TEMPLATES, removed by D1-04
```

## The refusal catalog

`FR-164` means **`RRA-014`'s** governed bilingual wording, which travels on `ViewRefusal.wording`
— which is why `D1-02` kept the refusal whole instead of flattening it to a message. It is *not*
`refusal_message`: that catalog serves the `section` and `result` tiers and knows nothing of a
view's causes, so reaching for it raises `KeyError` on a cause like `unsupported_filter`. Caveats
take the parallel path through `caveat_message`, for the same reason a code in front of a customer
qualifies nothing.

---

## Steps

### RED

- [ ] `tests/test_d103_metric_card.py`, failing because the modules do not exist:
  - **`FR-162` lines.** A card exposes label-bearing code, value, population, versions, status,
    availability, reason, caveats, comparison and evidence — every line named, including the two
    whose source is not yet reachable.
  - **Four-status selection, exhaustively.** Over `{admitted, refused, unavailable}` ×
    `{available, partial, unavailable, absent}` × `{caveats, none}`: refused wins; then
    unavailable from either the outcome or the availability; then caveated from either a caveat
    or `partial`; then verified. **Nothing counts or scores** — asserted against the AST as
    `D1-02` does.
  - **The availability literals match `khepri.rra.definitions`.** The pin's cost, paid in test.
  - **`FR-170` — the Period Comparison absence is asserted.** Every card's `comparison` is
    `None`, the reading reports the surface unreachable, and **a test fails if
    `PeriodComparisonView` ever becomes reachable** without that assertion being removed
    deliberately: the shape predicate still refuses a single-population bundle for it.
  - **`FR-164` — a refusal renders governed bilingual wording**, from `ViewRefusal.wording`, never
    an invented string, in both languages. Caveats likewise, through `caveat_message`.
  - **`FR-171` — parity.** Every card present in English is present in Arabic, with a governed
    label in each, and the same status.
  - **`FR-161`** — availability and caveats are on the surface carrying the figure.
  - **`FR-165`** — S-6 unavailable degrades the qualification only; the S-1 figures still render.
  - **`FR-046`** — a shell without `decisions` declares no decision route.
  - **The dispatch rule carried from `D1-02`** — a refused outcome carrying a projection is still
    refused, on this read model too.

### GREEN

- [ ] `card.py`, `shell_decisions.py`, `decision.html.j2`. No `shell_api.py` edit — see the
      amendment above.

### Gates

- [ ] `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
- [ ] Every new file 10.00 in CodeScene; **`test_r807_shell_quality.py` must not decline** — the
      edit is one named constant and one term in an existing assertion.

---

## Not in this slice

- **No `wiring.py` edit** — question 4 above.
- **No evidence drawer.** `D1-05`. The card names the line and leaves it absent.
- **No breakdowns and no S-6 surface.** `D1-04`.
- **No filters.** `D1-07`; this surface reads one run and sends no filter.
