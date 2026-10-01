# SCRUM-26 slice: commentary figures take the tables' form in each language (A9(b))

> Plan and RED evidence for one slice. The reading is the owner's, recorded as the `RRA-005`
> amendment in `#637` (`99eaf5f`). A9(a) is `#635`.

## Authority

`RRA-005` §Requirements and §Verification as amended by `#637` (registry `state: active` at
`62f15e3`). Prose states each figure in the display form the report's own tables give it in that
language. The request supplies that form, and the provider quotes it and never converts.
Grounding normalizes digits, separators and the percent sign, a changed significant digit is
still refused, and the two languages' figures are compared after the same normalization. The
form is consumed from `RRA-006` by analogy, not by a dependency edge.

## Change

1. **One implementation of the form.** The grouping, percentage and Arabic-digit rendering
   moves unchanged from `bundle` into `rra/presentation.py`. `bundle` imports `narrative`, so the
   request could not reach the tables' form without a second copy, and a second copy is how
   "byte-identical" drifts. `bundle._renderings` is now a thin wrapper, and `bundle` re-exports
   `PERCENTAGE_METRICS` and `RATE_METRICS`. This lands as its own commit (`52e303a`), and the
   formatting suites pass unchanged on it.
2. **The request supplies the form.** Each fact carries `display` (`{"en": …, "ar": …}`), and
   each series point and comparison bucket carries `display` for its value and `rows_display`
   for its count, all built by `presentation.forms`. `value_percent` stays, because grounding
   reads it. `NARRATIVE_VERSION` does not move: the request gained a field, as it did when
   `value_percent` was added.
3. **The narrator quotes it.** `deterministic_narrative._fact_figures` chooses each language's
   supplied form, and `PERCENTAGE_METRICS` is no longer read there. A fact with no form quotes no
   figure. `ADAPTER_VERSION` moves to `rra005.deterministic.v4`.
4. **No grounding change.** `_normalize_digits` already maps Arabic-Indic digits, `٫`, `٬` and
   `٪`, and `_parse_number` drops group separators. A probe on the SCRUM-21 file validated the
   display forms before any code changed.

## Tests (RED at `9f3254c`)

`tests/test_rra005_display_forms.py`, on the SCRUM-21 file shape through the real pipeline:

- every fact's `display` equals the bundle figure's `renderings` for that citation, which is what
  the tables print;
- every point and bucket carries `display` and `rows_display`;
- the commentary contains the table's form byte for byte in each language, and the Arabic
  commentary contains no Latin digit;
- the forms ground, and a changed last significant digit is refused in each language;
- the adapter version is `rra005.deterministic.v4`.

Mutants: the Arabic sentence quoting the English form turns 3 tests red, and a request supplying
the bare value as the form turns 6 red.

`test_rra005_narrative_units.py` now asserts the v4 contract, the table's own string, and keeps
its rate-against-proportion guard over `RATE_METRICS` and `PERCENTAGE_METRICS`.
