# SCRUM-26 slice: the commentary states whole-file facts, by their names (A9)

> Plan and RED evidence for one slice. The SCRUM-26 mapping is in
> `2026-09-30-scrum-26-report-follow-ups.md` (PR #633). A9 was recorded in both SCRUM-21
> acceptance runs.

## Authority

`RRA-005` (registry `state: active` at `10a9bb8`). It states its requirements as bullets and
numbers no FRs:

- "Require equal factual and caveat coverage in Arabic and English; wording may differ without
  changing meaning."
- "Validate the response ... and reject unsupported numbers, citations, claims, or unsafe label
  transformations."

`deterministic_narrative.py` is the facts-only narrator that `RRA-005` admits ("A deterministic
facts-only report remains available when approved by the delivery contract").

## What was measured

On the SCRUM-21 file, the narrator wrote eleven sections. Six of them quoted a breakdown's
**last bucket** under the **breakdown's** name:

| Sentence | What the figure is |
|---|---|
| "The recorded revenue by period is 398.21." | 2026-02-28 alone |
| "The recorded revenue by category is 6584.93." | Snacks alone |
| "The recorded revenue by store is 10681.09." | one branch |

A reader takes each one for a total. That is a change of meaning, which is worse than the
formatting A9 first recorded. Also:

- the Arabic named every measure by its English code ("القيمة المسجلة لـ revenue");
- the English read "The recorded units is 836".

## Change

- **Whole-file facts only.** Every breakdown is stated in full in the report's tables. A
  sentence has room for one figure, and a breakdown has one per bucket.
- **Governed names.** Each measure is named by `wording.business_metric_name`, the name the
  report's own tables use, in each language. A metric with no name in either language is left
  out rather than quoted by its code.
- **Name, then figure.** "Units sold: 836, as recorded in the file." / "الوحدات المبيعة: 836،
  وفق ما سُجّل في الملف." No verb has to agree with a plural name.
- **`ADAPTER_VERSION` becomes `rra005.deterministic.v3`.** Every `NarrativeAttempt` records it,
  so a stored run says which prose it was written in. The version is pinned in the source and in
  `tests/test_local_narrator.py`.
- The dead series and comparison branch of `_figure` is removed. Its "never reformatted" rule
  moves to `_fact_figure`, the one path left.

## Not in this slice: owner reading

**Formatted figures ("23,520.06") and Arabic-Indic digits in the Arabic commentary.** The
validator would ground both, since `_COMPLETE_NUMBER` accepts grouping and `_normalize_digits`
maps Arabic-Indic digits. But the module records a rule that it quotes a supplied figure verbatim
and has no mandate to change its digits. Whether the commentary should match the tables' rendering
is the owner's call. The figures here remain the request's, unchanged.

## Tests (RED at `10a9bb8`)

`tests/test_rra005_commentary_states_whole_file_facts.py`, on the SCRUM-21 package:

- the draft passes `narrative.validate`, so no report loses its narrative;
- every cited fact is a whole-file fact, and the fixture does publish breakdowns;
- each section carries its governed name in each language, and the Arabic has no Latin word;
- the English has no "… is …" agreement;
- the adapter version is `v3`.

RED at `7188f9b`: four fail, and validation passes.
