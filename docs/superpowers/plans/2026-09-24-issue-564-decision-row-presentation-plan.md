# #564 item 4 — the decision surface prints no machine token

**Authority:** `RCA-008` (the D1 decision surfaces: `shell_decisions.py` and its partials).
`FR-162` requires population on a card, and `FR-164` requires governed wording, never a bare code.
`FR-167` qualifies a breakdown figure by its own projection's population. `RRA-014` `FR-140` says
an absence stays an absence. `RCA-010 FR-199` requires `dir="auto"` on customer-controlled values,
and Product principle 5 keeps machine vocabulary from customers. Owner decision on `#564`
(2026-09-24): "If the raw tokens reach real runtime UI, fix them under the appropriate `RCA-008`
authority."

## Finding (real, not fixture-only)

Driven over the real projector (`ReportBundle.of(package())` through `project()`), in both
languages:

- Every breakdown row printed its metric code (`revenue_by_store`, `revenue_by_category`), and
  every product/category row printed its dimension code (`category`).
- Every row and every card printed the population absence as the literal text `None`.
- `versions` (Basket/Concentration rows) would print as a Python tuple of pairs.

The stub (`revenue 700.00 complete ()`) hid all of this.

## Change (presentation only, existing words only)

- `_row` presents cells through `_presented`. `store`, `member` and `value` print as they stand.
  `dimension` prints the controls' own label (`CONTROL_COPY`: Store / Product / Category, both
  languages). An absent `population` prints the governed `not_stated`. `metric` is withheld,
  because the row's label already names it. `versions` moves into the drawer via
  `_stated_versions`, as on the cards. A population code, or any unknown field, is withheld rather
  than printed; no view projects a population code today.
- A card's population uses the same `_population`.
- The `store` and `member` spans carry `dir="auto"`.

The read path is untouched: `BreakdownRow.cells` and `FR-167` are unchanged.

## Not exercised here

The golden fixture renders Basket and Concentration empty, so the drawer's `versions` line
has no row to render in this test.

## Open, not fixed here (filed separately)

A series fact's `rows`-kind figure is projected under `value` with no kind, so "Revenue · Cairo ·
2" reads a row count as revenue (4 of 8 branch rows on the golden package). The row carries no
`kind`, so no presentation fix exists. It is an `RRA-014` view-contract question for the owner.
