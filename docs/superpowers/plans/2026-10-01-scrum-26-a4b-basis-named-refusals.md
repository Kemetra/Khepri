# SCRUM-26 slice: comparison refusals name their basis (A4(b))

> Plan and RED evidence for one slice. The reading is the owner's, recorded as the `RRA-009`
> amendment in `#637` (`99eaf5f`). The A4 in-key half is
> `2026-09-30-scrum-26-a4-prior-window-truth.md` (`#634`).

## Authority

`RRA-009` §Refusals and §Verification as amended by `#637` (registry `state: active` at
`62f15e3`). A refusal whose cause belongs to one basis names it in the first part, in both
languages, at both tiers. The wording comes from the governed basis labels
(`label.period_over_period`, `label.year_over_year`) composed into the existing message. That
adds no reason code and no message, so the catalogue counts do not move.

## Decisions made in this slice

1. **Composition: the label leads the sentence.** The output is "Against the previous period:
   Revenue change is not shown — …", and the same in Arabic. The label is used verbatim. No
   message gains a placeholder, because the raw messages are also read unformatted: the landing
   specimen, `definitions.explain_reason`, and the workbook's governed-text set. A placeholder
   would have printed `{basis}` on those.
2. **Result tier.** The basis is the comparison mode in the refused result's own scope
   (`wording.basis_of`). A result with no mode names none.
3. **Section tier.**
   - Period comparison reads each basis's cause from the section's own scoped refusal records,
     which are the records the family summary was chosen from. Bases refused for different
     causes are each named with their own cause, in governed mode order.
   - When every basis is refused for the same cause, the cause belongs to neither basis alone.
     It is stated once with no basis.
   - Growth records no per-basis refusal. It names the previous period only for the two causes
     it takes from that window (`window_refusal`).
4. **No bundle change.** The prose is composed at render time from codes the bundle already
   carries. `BUNDLE_VERSION` and the identity document do not move.
5. **The panel prose is per bundle.** `html` used to hand the template a static
   `chrome.refusal_prose[section][reason]` table. Each section view now carries its own
   `refusal`, resolved by `refusal_basis.section_refusal_prose`, which the workbook writes too.

## Not in this slice

`report_api`'s analysis-quality `SectionStatement.wording` explains a section reason code from
the catalogue (`definitions.explain_reason`). It is a code explanation, not the section's
refusal sentence, and it is left as it is. Its `CaveatStatement` and `ResultStatement` read
`caveat_prose`, so they name the basis.

## Tests (RED at `533183a`)

`tests/test_rra009_refusal_basis.py`, over real CSV bytes through `ReportBundle.of`:

- `split` (four days, no manifest): previous period refused for coverage and the same period
  last year for `prior_window_absent`. The comparison panel names each basis with its own cause.
  Growth names the previous period. The workbook states both.
- `single` (one day): both bases refused alike. The panel states the cause once with no basis,
  and the two result sentences, which differ only in basis, are both printed.
- A result refusal names the basis it was computed against, and a non-comparison result is
  unchanged.

Nine cases were RED before the change. Five control cases passed at RED (an unnamed headline and
an unchanged non-comparison result), which is what they assert.
