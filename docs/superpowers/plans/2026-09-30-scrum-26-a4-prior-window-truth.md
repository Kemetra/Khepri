# SCRUM-26 slice: `prior_window_absent` states only what it knows (A4, in-key half)

> Plan and RED evidence for one slice. The SCRUM-26 mapping is in
> `2026-09-30-scrum-26-report-follow-ups.md` (PR #633). A4 was recorded in
> `2026-09-29-scrum-21-u1-acceptance-evidence.md`.

## Authority

`RRA-009` §Refusals (registry `state: active` at `10a9bb8`). The second part states "why the
supplied data could not support it", the actual cause. `wording.py`'s `REFUSAL_WORDING` is the
catalogue that section names.

## A4 has two halves

1. **A false claim, fixed here.** `prior_window_absent` is emitted per comparison mode
   (`comparison._absent_reason`) and by growth (`growth._derive`, through the accepted
   period-over-period window). A file with several periods, whose period-over-period comparison
   is answered, still refuses year-over-year with it. The sentence said "Your file covers a
   single period". The SCRUM-21 fixture is exactly that case.
2. **The basis is not named. Not fixed here.** The caveat code carries its mode
   (`revenue_delta_absolute.year_over_year:prior_window_absent`), but the prose is keyed by
   reason alone. Naming the basis needs messages keyed by mode, which moves the catalogue counts
   in `RRA-009` §Refusals. That is an amendment for the owner.

## Change

The same key and the same five parts, in English and Arabic:

- **Part 2** says the file does not include the earlier period this comparison needs, which is
  true in every context the code fires in: comparison for either mode, growth, and the landing
  specimen (`landing_api._SPECIMEN_REASON`, a single-period example).
- **Part 5** names one example, the same months a year earlier, instead of offering "the months
  immediately before". On the SCRUM-21 page, that alternative is the basis the neighbouring
  `coverage_structurally_incompatible` refusal had just refused.
- **Arabic:** "وهو يوصف" becomes "وهو يصف".
- `docs/reporting/refusal-presentation.md` mirrors the prose and follows it.

No reason code, count, template, renderer or governed artifact changes. `stated_once` still
collapses the two per-metric codes into one printed sentence, because both still map to one
prose string.

## Tests (RED at `10a9bb8`)

`tests/test_rra009_prior_window_truth.py`:

- the fixture answers period-over-period and refuses year-over-year with `prior_window_absent`,
  so the case is present;
- the printed web report carries the sentence in both languages, and the sentence makes no
  single-period claim.
