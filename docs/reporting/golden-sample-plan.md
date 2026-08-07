# Golden-sample plan (Phase 1)

**Planning-only. Approves nothing. Docs only.** Base commit `c7d78b2`.

Roadmap §18 asks for "the Phase 1 golden-report design-package plan." This is that plan, and
its first finding is that **the design package already exists**. This document plans the gap
between what is drafted and what Phase 1's acceptance criteria require.

Read `README.md` in this directory first — it is the package this plan closes out.

---

## A. Phase 1 deliverables against what exists

| # | Roadmap §10 Phase 1 deliverable | State | Where |
|---|---|---|---|
| 1 | Presentation visibility matrix (Business / Audit / Internal) | **Drafted** | `presentation-visibility-matrix.md` |
| 2 | Business report information architecture | **Drafted** | `business-report-information-architecture.md` |
| 3 | Refusal and limitation presentation contract | **Drafted** | `refusal-presentation.md` — five-part contract, 11 distinct codes in 13 contexts |
| 4 | One fictional but realistic retail dataset | **Drafted, with one gap** | "Al Rahma Trading Co.", Jan–Jul 2026 — no transaction identifiers, see §B.1 |
| 5 | Golden HTML mock | **Drafted** | `golden-sample/khepri-sales-review-sample.html` |
| 6 | Golden PDF mock | **Drafted** | `golden-sample/khepri-sales-review-sample.pdf` — 8 pages, appendix on a fresh page |
| 7 | Golden Excel mock | **Drafted** | `golden-sample/khepri-sales-review-sample.xlsx` — 12 sheets |
| 8 | Arabic and English copy review | **Not done** | See §C |

## B. The dataset against §10's required coverage

| Required | Present |
|---|---|
| Multiple months | Yes — seven, January to July 2026 |
| Products and categories | Yes |
| Multiple branches or locations | Yes — per-branch revenue, units, margin, change |
| Units, revenue, discounts, returns, cost | Yes — all **thirteen** governed metrics: the ten in `facts.py:69-78` plus the three in `growth.GOVERNED_METRICS` (`analysis/growth.py:71-74`) |
| Transaction identifiers | **No — not met.** The sample file carries no receipt or invoice number, so basket analysis is *refused*, not produced. See §B.1 |
| A clear growth-driver story | Yes — growth decomposition into price and volume effects, alongside the total change |
| At least one analysis that succeeds | Yes |
| At least one unavailable for a valid reason | Yes |
| At least one data-quality caveat | Yes |

### B.1 One coverage requirement is not met, and it is not a wording problem

Roadmap §10 requires the fictional dataset to carry **transaction identifiers**. The sample file
does not. Its own Basket Analysis section says so to the reader:

> Your file has no receipt or invoice number, so there is no way to tell which rows belong to
> the same sale. Counting rows instead would overstate basket size wherever one sale spans
> several lines.

So basket analysis appears in the sample as a **refusal**, not as a produced analysis. An earlier
version of this table recorded transaction identifiers as present because basket analysis was
listed in the report — reading a section heading as evidence of the data behind it.

**Two roadmap §10 requirements are in tension here, and the sample resolves them the wrong way
round.** It must carry transaction identifiers, *and* it must show "at least one analysis that is
unavailable for a valid reason." Today one requirement is satisfied by breaking the other: the
missing identifiers are what produce the refusal.

They are separable. Add receipt numbers so basket analysis computes, and let the year-on-year
comparison — already refused in the sample because the file covers only seven months — carry the
refusal requirement on its own. **That is a change to the fictional dataset, not to this plan**,
and it is the owner's call whether to make it before approving the sample or to approve the sample
with the gap recorded.

Recorded as a **known gap in deliverable 4**, not as a defect in the design.

### B.2 What the coverage constraint does and does not permit

From `README.md`:

> Richness comes from metrics Khepri **already computes**, never from invented analysis. A
> golden sample is a promise about the product; inventing a forecast, a customer segmentation,
> or a basket-affinity matrix would make the sample a specification for work nobody approved.

This is why comparable-store sales is absent from the sample and recorded as a roadmap item
instead. Note that adding receipt numbers per §B.1 does **not** violate this constraint: basket
analysis is already implemented (`analysis/basket.py`), so the sample would be showing a capability
Khepri has rather than promising one it lacks.

## C. What Phase 1 still needs

### C.1 Arabic business copy review — deliverable 8, the only missing one

Phase 1's acceptance criterion is specific: "Arabic is genuinely written for Arabic readers,
not mechanically mirrored English."

**This cannot be produced by the agent that wrote the English.** It is a human review by a
reader who works in Arabic business language. The workbook already carries an Arabic summary
sheet and the `(العربية)` naming convention; `verify_separation.py` asserts 0 Eastern-Arabic
numerals, which is a mechanical check on numeral form, not on whether the prose reads natively.

**Recommended shape:** a named reviewer reads the Arabic surfaces cold, without the English
alongside, and answers three questions — does each section's first sentence state a finding a
retail owner would act on; does any phrase read as a translation; is any term wrong for
Egyptian retail. Record the answers. That record is the deliverable.

### C.2 Owner approval — the stop condition

> Do not implement the new report layer until the owner approves the golden sample.

Approval means the three artifacts, not a description of them. The PDF is the one to open
first: it is the surface a customer forwards, and its eight pages are the fastest test of "a
business reader can understand the report without technical training."

### C.3 Commercial validation — the gate this plan adds

**This plan and the static golden sample proceed immediately. Neither waits on anything.**

But **approval of `[SPEC-REPORT]` and implementation of the report layer should follow four
things, in this order:**

1. the **owner-approved** static golden sample — G4, not merely its existence. The sample exists
   today and is awaiting approval; an unapproved mock is not evidence of anything;
2. **three retail chain or mid-market prospect interviews**;
3. **two agency interviews**;
4. an explicit owner decision recorded as **go / revise / stop**.

**Why the gate belongs here and not later.** `docs/khepri-commercial-roadmap.md` Phase 0C states
the problem exactly: the entire sequencing argument "rests on auditability being what a buyer pays
for, and that is currently an *assumption* — no prospect in either named segment has been spoken
to." The golden sample is precisely the artifact that tests it, and it already exists. Showing it
costs a few conversations. Discovering after implementation that defensibility is a hygiene factor
rather than a purchase driver costs the report's information architecture, because the whole
business/audit separation is built around making defensibility visible.

**What to record.** Not "they liked it." Ask what they would pay for *unprompted, before* showing
the sample; then show it and ask again; then write down **what they reacted to that was not
auditability.** That list is the real input, and it is the part a positive-sounding conversation
loses.

**Override.** If the owner elects to approve `[SPEC-REPORT]` without this evidence, that is a
legitimate call — but it must be recorded as an **explicit override** in the approving package,
naming what was skipped and why. Silence is not an override. This gate exists because its absence
is currently invisible, and bypassing it invisibly would restore exactly that condition.

Tracked as **G5** in
[`../platform/cross-repository-pr-sequence.md`](../platform/cross-repository-pr-sequence.md) §2.

> **WITHDRAWN by owner election, 2026-08-06.** The override paragraph above **has now been
> invoked.** The owner has elected not to conduct the interviews, and that election is recorded in
> that document's §0, which stays the single statement of gate status.
>
> **G5 no longer gates `[SPEC-REPORT]`.** The four items in this section are retained as the record
> of what was set aside — naming what was skipped is the condition the override paragraph attaches
> to the election, not an optional courtesy.
>
> **G4 is unaffected**, and is now the only gate on `[SPEC-REPORT]`. It is a read of the sample in
> this directory, not an interview.

### C.4 Acceptance criteria: evidenced, versus asserted

| §10 Phase 1 criterion | Evidence |
|---|---|
| A business reader understands it without technical training | **Owner judgment.** No mechanical check substitutes. |
| No internal identifier in business-facing sections | **Verified** — `verify_separation.py`: 0 identifiers in 9 business worksheets, 0 in the HTML business region |
| Every important finding supported by visible evidence or a linked audit entry | **Partially verified** — 47 Excel / 46 HTML identifiers present in the audit regions; the *linkage* between a finding and its audit entry is not machine-checked |
| Leads with conclusions, not raw metric tables | **Owner judgment.** The IA orders by decision relevance; whether it reads that way is a reader's call. |
| Arabic genuinely written for Arabic readers | **Not evidenced** — §C.1 |
| Owner approves before implementation | **Outstanding** — G4, now the only gate, §C.3 |
| Fictional dataset carries transaction identifiers | **Not met** — §B.1 |
| Commercial validation (G5) before `[SPEC-REPORT]` approval | ~~Required~~ — **WITHDRAWN by owner election 2026-08-06**, §C.3. Never started; the premise stays untested |

Two criteria are owner judgment by construction. That is correct — a mechanical proxy for
"reads like a business report" is the failure mode the package exists to escape.

## D. From approved sample to implementation slice

Not authorized by this plan. Recorded so the approval decision is made with its cost visible.

### D.1 Governance route

The design package records "no governance dependency is known." That is right for the *design*.
The *implementation* changes RRA-006's rendered output and needs a specification.

**Recommended route: a new specification under the existing RRA family.** This is a
recommendation, not a decision. **No approval package, registry entry, or approval reference
records a choice of route**, and none may be inferred from this document. `AGENTS.md` is explicit
that human approval is not claimed or recorded without explicit traceable evidence, so the route
is settled when a governed artifact settles it — not here.

The argument for it: the change is presentational; `docs/reporting/` establishes that `reconcile`
validates the `SurfaceContent` claim and never parses the document, so relocation is
claim-neutral. `[SPEC-REPORT]` needs no commercial capability, so this route does **not** put it
behind the commercial-family charter — which matters, because the report is the only phase a buyer
can see and the charter is the slower gate. That gap has since widened: `RRA.md` is digest-pinned
by `APP-002`, so the charter package requires a renewal rather than a plain edit.

The alternative — placing it under the commercial family — is cleaner if the report is understood
as a commercial deliverable rather than a beta capability, and costs the charter dependency. Both
are live until an approved artifact chooses.

**One thing to check when drafting `[SPEC-REPORT]`.** `APP-002` pins `RRA-006` by
`document_sha256`. `[SPEC-REPORT]` is a *new* specification depending on RRA-006, not an edit to it, so
no renewal is needed — but if drafting reveals that RRA-006's text must change, that becomes a
renewal package and the slice grows. Confirm the dependency is additive before scoping the work.

### D.2 The largest work item is test migration, and it is not mechanical

From `README.md`: **19 test files carry ~170 references** to the structure this design
relocates (`figure_id`, `citation_id`, `data-reason`, `unit_kind`, `<code>`), concentrated in
`test_rra006_bundle_sections.py` (45), `test_rra006_bundle.py` (19),
`test_rra006_bundle_section_reconcile.py` (18), `test_rra006_excel_charts.py` (17),
`test_rra006_charts.py` (17).

`test_rra006_excel_charts.py` addresses the chart-data worksheet **by name** in eleven places,
so the sheet's name and visibility are both test-pinned.

> the tests currently *pin the ledger structure as correct*, so migrating them is an act of
> deciding what the new contract is, not mechanical find-and-replace.

**This is the sentence that should govern how the slice is scoped.** It is likely larger than
the wording tables, and it is where a rushed slice would quietly weaken RRA-006.

### D.3 Two exit criteria the slice must carry

1. **`verify_separation.py` as a required check.** It is currently a verification script for the
   sample that imports nothing from `khepri`. Promoting it to a test makes the separation rule
   decidable in CI.
2. **A coverage test.** The business and audit regions *together* must still cover every
   `bundle.figures`, `bundle.caveats`, and section. Reconcile will not catch a relocation that
   loses content: both surfaces claim `sections=bundle.section_ids` unconditionally
   (`html.py:284`, `excel.py:764`), so `_reconcile_sections_against_bundle` compares an
   asserted claim against its own source. **Deletion is not relocation**, and only this second
   test catches the difference.

### D.4 Two constraints that will bite

- **The metric-name table must be complete at import.** `worded()` (`wording.py:149-151`) raises
  on a missing code by design — "a fallback would ship it quietly" — and a `KeyError` in a
  renderer is caught as `REASON_SURFACE_FAILED` (`bundle.py:1213-1219`). An incomplete table
  means **no report**, not an ugly label. Guard with an import-time key-set assertion.
- **Caveat wording is all-or-nothing.** `bundle.py:1324-1325` requires the claimed and bundle
  caveat sets to be *equal*. An unworded caveat is a reconcile failure. All 12 codes are worded
  in `refusal-presentation.md` §D.4; none may be deferred.

## E. Interaction with the Seshat boundary

**None, for Phase 1.** The report layer consumes Khepri's own `FactPackage` today. Roadmap
Phase 5's `BusinessFinding` → `ReportPlan` → `BusinessReportModel` chain is where a second
evidence source arrives.

Sequencing Phase 1 behind the Seshat integration would delay the only phase a buyer can see
behind the phase with the most unresolved preconditions (distribution, the headless facade,
Seshat's one-spec-at-a-time constraint). The target architecture explicitly places stage 4
outside the stage 1–3 dependency chain for this reason.

## F. Two prior findings this plan carries forward unchanged

Both are corrections the package already made against itself, and both are the kind that
reappear if not restated.

1. **The customer-facing catalog is 11 distinct codes in 13 contexts — not 32, and not 13.**


> **Superseded 2026-08-07:** the shipped catalogue is **15 messages over 13 distinct codes**
> (8 section + 7 result); `dimension_absent` and `negative_base` were added in `#121`. See
> `refusal-presentation.md` §D.1's dated note. `RRA-009.md` still states 13/11 and is
> digest-pinned by `APP-016`, so correcting it needs a renewal package.
   8 section reasons plus 5 result reasons, with `required_input_unavailable` and
   `incomplete_transaction_identifiers` appearing in both, so the distinct union is 11 and each
   of those two needs two messages. The 20 `GOVERNED_REASONS` are bundle-integrity codes: when
   one fires **no report is published**, so a customer cannot encounter one. Earlier sessions
   summed all three vocabularies to 32; an earlier draft corrected it to 13 and reproduced the
   same double-counting.
2. **The audit layer is generated always and delivered on request.** `REQUIRED_SURFACES` is
   compared for exact equality in seven places; a bundle producing fewer than three surfaces is
   an *incomplete bundle* and no report at all (`bundle.py:1222`).
   **Do not implement optionality by skipping generation.** "Optional" is a render variant of
   each surface, decided before the surface is stored — never a delivery-time filter, because
   `delivery_persistence.py:346-350` raises `DeliveryCorrupted` on a delivery that does not name
   every required surface.
