# #564 item 1 — a detail surface marks its parent destination current

**Authority:** `RCA-010` §Scope ("shell presentation markup and ARIA state") and `RCA-010 FR-194`
("`aria-current="page"` on exactly one entry"). The owner decided the reading on `#564`
(2026-09-24, recorded on the issue in substance): detail routes keep exactly one active navigation
entry, and Insights is the current parent destination. The handoff maps Insights onto `analyses`, with `analysis.html.j2`
and `decision.html.j2` under it (`IMPLEMENTATION_PROMPT.md:116-119`; `INTERACTIONS.md:23`,
"Insights + Report → *Insights*"). No route, destination, copy, CSS or runtime change.

## Why

`shell.html.j2` marks an entry current only when `tail == surface_path`. So analysis detail
(`/{org}/analyses/{run}`), compare (`/{org}/analyses/compare/{a}/{b}`) and decision
(`/{org}/decisions/{run}?…`) mark nothing. `test_at_most_one_entry_claims_to_be_the_current_page`
pinned `<= 1` on the reading the owner has now reversed.

## Change

- In the nav loop, an entry is current when its tail equals the surface path, or is a prefix of it
  followed by `/`. A decision surface (its query string is ignored by the prefix match)
  additionally counts as Analyses. The destinations stay `shell_frame.py`'s, which this scope
  cannot edit. The template therefore restates the `/analyses` and `/decisions/` segments. A
  frame-supplied parent tail would remove that duplication, and it is an RCA-005/RCA-008 change.

## Open readings for the owner (not decided here)

- **Compare counts as a detail route under Insights.** Its path is `/analyses/compare/…`, but the
  handoff table does not list it.
- **A deployment offering decisions or comparisons without Analyses** (`offers_decisions` /
  `offers_comparisons` without `offers_analyses`) marks zero entries current. The shipped image
  (`wiring.py`) wires them together, so the image is unaffected. No fallback entry is inferred.
- The test becomes `test_exactly_one_entry_is_the_current_page_on_every_navigating_surface`. It
  asserts `== 1` on every navigating surface in both languages, and asserts which destination is
  current: the surface itself, or `analyses` for the three detail surfaces.

**Mutants:** drop the prefix rule, which must fail on analysis and compare; drop the decisions
mapping, which must fail on decision.
