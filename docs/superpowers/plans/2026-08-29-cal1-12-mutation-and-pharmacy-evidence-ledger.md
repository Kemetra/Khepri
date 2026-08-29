# CAL1-12 — mutation evidence and pharmacy golden fixtures

**Slice:** `CAL1-12`, the first of the four verification slices that follow the seven publication
commits. **Depends on:** `CAL1-11` (`9e7a886`, `#328`). **Branch:** `cal1-12-mutation-pharmacy-evidence`.

**Acceptance, from the roadmap task table:** *"Named mutants for row-vs-transaction, unequal windows,
unmatched populations, full-set concentration, sign/currency rules, and publication gating are
killed."* Plus pharmacy-focused golden fixtures.

---

## 1. What this slice is

The seven governed successor versions merged at `#308` (`7088749`). This slice adds no product
behaviour and moves no version constant. It establishes **evidence about code that already governs**:
that the guards protecting each named rule are actually tested, and that a realistic pharmacy month
publishes the figures a hand derivation says it should.

That inverts the usual order. The mutant *is* the RED step: apply it to merged source, watch the
suite, revert. A mutant that dies proves the existing guard is tested and needs nothing added — a
near-duplicate test there would be pure CodeScene cohesion cost for no evidence. A mutant that
survives is where a test gets written.

---

## 2. The six named mutants

Each was applied to merged source on `main`, run, and reverted. Every mutant was confirmed to import
cleanly before its run, so a survivor is a real proof gap and not a malformed edit reported as one.

| # | Named mutant | Site | Edit | Result |
|---|---|---|---|---|
| M1 | row-vs-transaction | `facts.py:2036` | canonical composite key → bare mapped column (`_text_values`) | **KILLED** — 4 tests |
| M2 | unequal windows | `comparison.py:537` | drop the coverage-shape term from `_structurally_compatible` | **KILLED** — 1 test |
| M3 | unmatched populations | `facts.py:1038` | `complete_selling = True` — ASP narrows instead of refusing | **KILLED** — 3 tests |
| M4 | full-set concentration | `aggregates.py:416` | delete the `sale_absent` refusal — rank survivors over a partial base | **KILLED** — 1 test |
| M5a | sign rules | `facts.py:1158` | suppress `CAVEAT_NEGATIVE_REVENUE` | **KILLED** — 1 test |
| M5b | currency rules | `facts.py:1152` | suppress `CAVEAT_CURRENCY_NOT_DECLARED` | **SURVIVED** — see F1 |
| M6 | publication gating | `versions.py` | add one admitted row to each table | **SURVIVED** — closed here |

### Killing tests, for the four that died

- **M1** — `test_repeated_invoices_in_two_stores_are_two_transactions_each`,
  `test_the_aov_denominator_uses_canonical_keys`, `test_a_transaction_basis_counts_canonical_keys`,
  `test_a_missing_key_component_refuses_only_what_needs_the_key` (all `test_rra004_facts.py`).
- **M2** — `test_stores_covering_different_days_are_not_one_complete_set`
  (`test_rra008_coverage_compatibility.py`). The mutant published a delta where a ragged window must
  refuse, which is the right failure rather than an incidental one.
- **M3** — `test_selling_price_and_margin_use_the_same_rows_as_their_pair`
  (`test_rra004_facts.py`), `test_a_zero_unit_sale_refuses_asp_rather_than_leaving_the_population`,
  `test_asp_refuses_when_an_eligible_sale_row_is_unmatched`
  (`test_rra004_formula_populations.py`).
- **M4** — `test_an_incomplete_sale_revenue_value_refuses_the_whole_curve`
  (`test_rra004_aggregates.py`).
- **M5a** — `test_negative_revenue_is_kept_and_disclosed` (`test_rra004_facts.py`).

---

## 3. Findings

### F1 — `CAVEAT_CURRENCY_NOT_DECLARED` cannot be raised *(FILED — unreachable branch)*

M5b survived, and the reason is not a missing test. The branch is **unreachable under
`rra003.mapping.v3`**, so no test could kill it.

`facts.py:1143` fires only when `admitted_events.currency is None` **and** at least one published
fact is monetary. Those two conditions are mutually exclusive:

- `source_contract.py:207-211` proves currency exactly once — a contract declaring neither a currency
  column nor a currency code is refused at contract-build time. So `currency is None` cannot arise
  from an absent declaration.
- It can only arise from `admission._currency` returning `(None, True)` — a mapped currency column
  holding mixed or non-ISO values. But that same return sets `monetary_refused`, and
  `admission.py:227-243` then nulls revenue, cost and discount for every row. No monetary fact
  survives to be qualified.

Verified empirically, not only by reading: a two-row extract declaring `currency_column="currency"`
with `EGP` and `USD` produces `package.currency is None` and `package.caveats == ()`.

The caveat is not merely unreachable in code. It carries accepted bilingual prose
(`rendering/wording.py:670` EN, `:741` AR), a registration at `wording.py:148`, and two narrative
branches that read it (`narrative.py:922`, `:1020`). This is the *defined but never attached* shape:
a governed code complete on every customer surface with no path that can raise it.

**Not closed here.** The fix is a decision about which of two things is true — either mixed currency
should publish count-only facts *with* the caveat attached (an `RRA-003` admission change), or the
caveat is dead and its prose, registration and narrative branches should be withdrawn (an `RRA-009`
catalogue change). Both are family changes outside a mutation-evidence slice, and choosing between
them is the specification's call rather than this slice's.

### F2 — the version-pairing tables had no extent guard *(CLOSED here)*

M6 added one row to `ADMITTED_PACKAGE_PAIRS` —
`("rra003.mapping.v2", "rra004.package.v3", "rra004.formula.v2")`, legacy admission paired with the
successor package and formula, precisely the skew `versions.py` exists to forbid — and **the entire
suite stayed green: 3,618 passed, 72 skipped, 1 xfailed.**

Every prior assertion in `test_rra004_version_compatibility.py` tests membership: a named triple is
admitted, or a named triple is refused. An *added* row breaks no inclusion and is not one of the
finitely many exclusions anyone thought to name.

A sentinel cannot catch it either. The existing `.v9` cases refuse because their versions are
**unrecognised**; a widening mutant builds its row from real, recognised strings. Extent is the only
assertion that reaches it.

Closed by two tests asserting the tables' exact contents — three package triples, eight family pairs.
Both were mutation-verified independently: the package mutant fails only the package test, and a
family mutant (`("rra004.formula.v1", "rra008.concentration.v2")` — a successor family over an
unmoved formula) fails only the family test, while
`test_a_moved_family_against_an_unmoved_formula_is_refused` stays green because it names `growth`.
That is the redundancy trap avoided: each guard has its own evidence.

These are deliberately hand-maintained assertions. `versions.py` says a row is exactly that kind of
fact — *"A slice adds its own row when it lands; it never edits a row another slice put here"* — so a
test that must be consciously updated is the guard that rule needs, and the module already uses the
idiom (`test_the_published_predecessor_triple_stays_admitted` hardcodes for the same reason).

---

## 4. The pharmacy golden fixture

`PHARMACY_ROWS` and its five expectation tables were added to `tests/rra_calculation_oracle.py`;
`tests/test_cal1_pharmacy_golden.py` drives them through the production path.

**Pharmacy in its values, not its schema.** `RRA-003` governs which columns exist, and batch, expiry
and payer are not among them — adding one would be a mapping change and a different family's slice.
What makes the case a pharmacy case is what the admitted columns carry: drug codes as products,
therapeutic classes as categories, an insurance co-pay as an additive discount, and a same-day
dispensing reversal as a posted return.

**The design property.** The reversal shares prescription `RX-5005` with the sale it reverses, so the
sale-only and financial populations differ **while the transaction count does not** — five either
way. An implementation ignoring event kind publishes the right transaction count and an AOV of
209.00 → 191.00. Both are exact to the cent; no rounding artifact betrays the substitution. A dataset
where every population differed would not isolate that failure from any other.

**Mutation-verified.** Blanking `facts._sale_only` to `list(values)` — event kind ignored — fails
exactly the two discriminating tests (AOV and ASP) and leaves the five population-independent ones
green. The fixture discriminates what it was built to discriminate.

Every literal is hand-derived with its arithmetic shown, `Decimal` throughout, half-even where
rounding applies (`1045.00 / 13 = 80.384615… → 80.38`). No production aggregation helper is imported
by the oracle.

**Every table is read by a test, and review found the layers where that was not yet true.** Three
tables shipped in the first commit that nothing asserted — the shape this ledger files as F1 against
production, reproduced in its own fixture. Two of them were also wrong, and nothing could have said
so: `returns` carried the row's sign where `RRA-004`:83 governs a positive magnitude, and the
category table assumed the concentration basis where a dimensional comparison is built over
`financial_posted`. Review then found a fourth layer: `curve_for` returns the *retained* curve, so
`top_decile_share` and `top_quartile_share` — the figures a customer actually reads — were still
unasserted. `concentration.derive` is now driven directly, and the test is verified against a
floor-for-ceiling mutant on `_leading`, which no other test in the module catches.

---

## 5. Disposition

| Finding | Kind | Disposition |
|---|---|---|
| M1, M2, M3, M4, M5a | Guard tested | Killed by existing tests; nothing added |
| M5b / F1 | Unreachable governed caveat | **Filed** — needs an `RRA-003` or `RRA-009` ruling |
| M6 / F2 | Proof gap, both version tables | **Closed here**, mutation-verified per table |
| Pharmacy fixture | Golden evidence | **Added**, mutation-verified against `_sale_only` |

**All six named mutants are accounted for.** Five are killed. The sixth (M6) is killed by the tests
this slice adds. M5b is not a mutation-evidence failure but an unreachable-branch finding, filed with
its proof.

**CodeScene pre-flight was not run:** the CodeScene MCP server failed to connect this session. One
new test module (`test_cal1_pharmacy_golden.py`) is added and will be scored; it is deliberately flat
— one package builder, one value reader, eleven plain test functions, no helper pyramid — because
extracting helpers raises a module's complexity mean. The server-side gate remains the authority.
