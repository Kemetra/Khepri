# M4 acceptance — the exit gate, measured on the deployed image

> ## STATUS: `M4` is ACCEPTED — 2026-09-16, on `main` at `5c4c522`
>
> **Accepted by the owner on the evidence below: all seven `M4` exit-gate clauses PASS.**
>
> This document records four stages and keeps them distinct. Read them in order; do not read the
> first as the outcome:
>
> 1. **Original measurement** (`#471`), `main` at `44d54a7` — **5 of 7 PASS**, clauses 3 and 4
>    failing on one shared blocker. **That result is preserved exactly as run and is not revised.**
> 2. **Blocker remediation** (`#472`, `D1-12`), merged at `5c4c522` — one governed entry point to
>    the decision surface, the single unblocker the measurement named.
> 3. **Re-measurement after remediation** — see §Addendum — **7 of 7 PASS**, driven by navigation
>    on the rebuilt image.
> 4. **Owner acceptance** — recorded here and in the roadmap's `M4` exit gate. See §M4 acceptance.
>
> **Acceptance is scoped to the `M4` gate sentence and nothing else.** It resolves no deferred or
> open work; the caveats in §What this run does not establish and §Caveats stand unchanged, and
> `M4` remains non-paying as already governed.

Roadmap §7's `M4` exit gate is one sentence:

> A design partner can return to a workspace, compare governed periods, view an executive decision
> page, drill through supported breakdowns, inspect evidence and limitations for every material
> claim, and download reconciled bilingual reports.

**This document measures that sentence and nothing else.** It creates no acceptance conditions of
its own and amends no authority. As with `M3`, no governance artifact decomposes `M4`, so §7's own
clauses are the condition source, cited directly. Where a clause admits more than one reading this
document says which it measured rather than choosing silently.

**Run on:** `main` at `44d54a7`, 2026-09-16.

**Result of THIS run, at `44d54a7`: `M4` was NOT YET ACCEPTED.** *(Preserved as run. The blocker
this paragraph names was cleared by `#472` and the gate was re-measured at 7/7; see the STATUS
banner above and §Addendum. Nothing below this line is revised.)* **Five of the seven clauses pass**
against the deployed
image and **two fail** — clauses 3 and 4. The two failures share **one** blocker: **the executive
decision page has no entry point from any shipped surface.** That shared cause reduces the work to
a single unblocker; it does not make either clause pass. Everything both clauses need is built,
correct and bilingual; a design partner has no way to reach it. §The one blocker states the
minimum unblocker.

---

## Method

`M3`'s method (`2026-09-06-m3-acceptance-evidence.md`), used again so the runs stay comparable:
driven inside `khepri-staging-web` through the real HTTP surface against the merged
`docker-compose.staging.yml` stack.

**The stack was rebuilt before measuring.** The running image predated `#470`, so a journey driven
against it would have described a tree that is not `main`. After
`docker compose -f docker-compose.staging.yml up -d --build`, every module this gate depends on was
digest-compared container-against-worktree:

| Module | Digest | Worktree |
|---|---|---|
| `runtime/semantic_view_adapter.py` | `b56a7d49f1f033959135cf7abe390642` | identical |
| `runtime/comparison_operands.py` | `541e96affef99d68e2408ebc58bac0fc` | identical |
| `runtime/comparison_assembly.py` | `1cab7fe50a14230c0e17e24f27ad3fc5` | identical |
| `runtime/shell_comparison.py` | `3e78179f2e88b2902de6898a166c5a32` | identical |
| `runtime/wiring.py` | `2d9132b6ea3bc27bb4f6c5d2ef8c7561` | identical |
| `runtime/shell_controls.py` | `84323675426ea1fbfc963e13b6dfa638` | identical |
| `rca/workspace/decision/seam.py` | `2c317e9191ce4ad263e2d33008a59cbd` | identical |
| `rca/workspace/decision/card.py` | `89bfa8939124e71d906915f2a24ec15f` | identical |
| `rca/workspace/comparisons.py` | `6af99ed822a89b97fb954222682d25f0` | identical |
| `rra/analysis/dataset_period.py` | `2c6dd4f54768bc22b119dc93e4733258` | identical |

Ten of ten identical. **The route table was enumerated from `khepri.runtime.web:app`** — the
literal object the compose file's uvicorn command serves — rather than from a factory called in a
test process. **46 paths / 48 path-and-method pairs**, including both comparison routes and
`GET /app/{language}/{organization}/decisions/{source}`. This is the check `#382`'s review
introduced after a route passed every test while being absent from the image.

**Two deployment-only failure modes were excluded before any response was interpreted**, because
both collapse into the uniform unavailable outcome and would be indistinguishable from a governed
refusal on the surface:

- `/tmp/khepri-comparisons` exists and is writable in the container (`_scratch_under` returns
  `None` on `OSError`, which the action converts into the uniform unavailable page).
- Chromium is present at `/ms-playwright/chromium-1228/chrome-linux64/chrome` (`KHEPRI-DEC-007`
  bakes it in; a Playwright fault also collapses into unavailable).

**Setup used production verbs only:** `AccountService.create_account`,
`OrganizationService.create_organization`, `SessionService.create`, `OrganizationSwitcher.switch`.
No workspace row was written directly.

> **`OrganizationSwitcher.switch` is not optional, and omitting it is how this run first went
> wrong.** A session with no active organization agrees with no address, so
> `_names_the_active_organization` denies every scoped surface and all six clause-1 reads returned
> the governed 404 (`FR-042`, `FR-048` scenario 4). That is the surface behaving correctly; it is
> recorded here so a later run does not read it as a defect.

**The analyses were entered the way a customer enters them:** `POST /app/{lang}/{org}/analyses`,
which resolves the session, compares the address's organization against it, opens the commercial
session and hands the browser to the journey with the beta cookie. Both entries returned `303` to
`/beta/en/upload` with the cookie set.

**Two fixed extracts with genuinely different periods**, the same pair `M3` used, because the gate
says *periods*: `GOLDEN` (4 rows, 2026-01-05..07) and `OTHER` (3 rows, 2026-02-02..04). Both drove
the full pipeline: `consent 204`, `upload 201`, `profile 201`, `facts 201`, `report 201`, and the
worker settled both runs to `completed`.

---

## The seven §7 clauses

| # | §7 clause | Measured on | Result |
|---|---|---|---|
| 1 | return to a workspace | Overview, Data, Analyses — `200` in both languages | **PASS** |
| 2 | compare governed periods | `/analyses/compare/{subject}/{baseline}`, admitted `CrossVersionBundle`, 20 cited figures | **PASS** |
| 3 | view an executive decision page | `/decisions/{source}` renders fully — **but is linked from no shipped surface** | **FAIL** |
| 4 | drill through supported breakdowns | Filters work and materially change the page — on the unreachable surface only | **FAIL** (inherits 3) |
| 5 | inspect evidence and limitations | Analysis Passport, linked from Analyses, carrying digests, coverage, version triple | **PASS** |
| 6 | download reconciled bilingual reports | All four artifact kinds × both languages — 8/8 `303` with a scoped cookie | **PASS** |
| 7 | fail-closed, scope/isolation, Arabic/English | Cross-org `404`, no-session `404`, unknown run → governed empty, RTL parity | **PASS** |

**Clauses 3 and 4 are one failure, not two.** Clause 4's breakdowns live on the decision page, so
they inherit its reachability exactly. Clause 5 does **not** inherit it: the Passport has an
independent satisfier reached from Analyses, which is why it passes on its own evidence.

---

### 1 — return to an existing workspace — PASS

| Surface | `en` | `ar` |
|---|---|---|
| Overview | `200`, 2,588 B | `200`, 2,863 B |
| Data | `200`, 2,026 B | `200`, 2,161 B |
| Analyses | `200`, 2,018 B | `200`, 2,172 B |

A returning member's session resolves, the address is compared against it, and all three workspace
destinations render in both languages.

### 2 — compare governed periods — PASS

**This is the clause the roadmap called the M4 gap, and it is met — by the `C1` surface.**

The governed outcome, taken from the composition root's own action rather than inferred from a
rendered page:

| Property | Value |
|---|---|
| `ComparisonOutcome.kind` | **`admitted`** |
| `refusal` | `None` |
| bundle | `CrossVersionBundle`, section `crossversion` |
| surfaces | 2 HTML documents, 2 PDF documents, 14,532-byte workbook (8 sheets, 198 strings) |

**It is the non-null case.** Twenty `CitedFigure` rows across five metrics, each carrying a
`citation_id` and `fact_id`, each rendered in both languages:

| Metric | Subject (Jan) | Baseline (Feb) | Difference | % difference |
|---|---|---|---|---|
| Revenue | 500.00 | 61.00 | 439.00 | 719.67% |
| Units sold | 11 | 6 | 5 | 83.33% |
| Average sale value | 166.67 | 20.33 | 146.34 | 719.82% |
| Average selling price | 45.45 | 10.17 | — | — |

Arabic renderings are present on every figure (`'٥٠٠٫٠٠'`, `'٧١٩٫٦٧٪'`), not a fallback to Latin
digits.

**Provenance survives the comparison.** `CrossVersionIdentity` pins both packages' digests, both
profile digests, both coverage-manifest identities and coverage signatures, plus
`rra003.mapping.v3`, `rra004.package.v3`, `rra004.formula.v2`.

**It is reachable by a design partner, not only by URL.** The Analyses surface renders the Compare
form itself — `action="/app/{lang}/{org}/analyses/compare"`, `<select name="subject">` and
`<select name="baseline">`, both versions offered — **in English and Arabic**. Driving it:

| Path | Status | Bytes |
|---|---|---|
| `GET …/analyses/compare/{subject}/{baseline}` `en` | `200` | 658,336 |
| `GET …/analyses/compare/{subject}/{baseline}` `ar` | `200` | 841,614 (`dir="rtl"`) |
| `POST …/analyses/compare` (the form) | `200` | 658,336 |

**The reading this clause measured, stated rather than assumed.** "Compare governed periods" is
read as satisfied by the `C1` two-dataset-version comparison, because that comparison *is* a period
comparison by its own governing contract: `rra/analysis/dataset_period.py` states "February against
March is the ordinary case of this family", and `periods_comparable` refuses only on granularity,
retail-day boundary and incomplete coverage — never because two periods differ. `G4-01`
§Comparison scope says the same: "`C1`'s comparison is **two dataset versions**." The extracts used
here are January against February, and the run was admitted.

**The competing reading is addressed rather than left open.** `RCA-009` says "M4 remains unmet
until a later implementation slice makes the source reachable and removes `FR-170`'s asserted
absence." **Both halves of that sentence are now true at `44d54a7`:** `#470` shipped the
composition branch, and the `FR-170` absence assertions are gone from `src/` (the only remaining
matches are stale `.pyc` files and historical prose). So that sentence does not contradict this
clause's PASS on either reading.

### 3 — view an executive decision page — FAIL

**The page is built, correct, bilingual, and unreachable.**

What renders when the address is supplied directly:

| Property | `en` | `ar` |
|---|---|---|
| Status / bytes | `200`, 56,954 B | `200`, 60,832 B |
| Direction | — | `dir="rtl"` |
| Sections present | `section-branches`, `section-products`, `section-basket`, `section-concentration` | same |
| Refusal or unavailable wording | none | none |

**What fails.** A design partner cannot arrive there. Measured on four shipped surfaces, each
checked for any `href` containing `decisions`:

| Surface | Links to `/decisions/` |
|---|---|
| Overview | **none** |
| Data | **none** |
| Analyses | **none** |
| Analysis Passport (`/analyses/{run_id}`) | **none** |

The shell's destination set is the four-item `Overview · Data · Analyses · Team`
(`shell_copy.py:75`). The decision page's address also requires a `run_id` the partner has no
surface to obtain. **This is the same test this ledger applied to `#470`** — present in the runtime
but named by no reachable path — and it produces the same answer: capability exists, capability is
not reachable by a design partner. The gate's subject is "A design partner can…", so implementation
presence does not settle it.

### 4 — drill through supported breakdowns — FAIL (inherits clause 3)

**The mechanism is real and correctly fed**, which is worth recording because it is not the reason
this clause fails. The decision page offers one form with three text filters — `store`, `product`,
`category` — and each materially changes the page rather than echoing a label:

| Request | Bytes | Differs from base |
|---|---|---|
| base (no filter) | 56,939 | — |
| `store=Cairo` | 51,452 | yes |
| `store=Giza` | 51,445 | yes |
| `category=Beverages` | 39,295 | yes |
| `product=Snacks` | 39,256 | yes |
| `store=Cairo&category=Beverages` | 33,664 | yes |
| `store=Nowhere` | 45,836 | yes — governed empty state |
| `colour=blue` | 57,381 | yes — the unroutable-parameter refusal path |

Cairo and Giza differing from each other by seven bytes is the tell that real figures moved rather
than a filter label being echoed; the combined filter narrows further; an unroutable parameter
earns a governed refusal (`FR-137`) rather than being ignored.

**It fails only because it is reachable only through clause 3's surface.** Fixing clause 3 makes
this clause executable with no further work, which is why the two are one blocker.

### 5 — inspect evidence and limitations — PASS

**This clause has an independent satisfier and does not inherit clause 3's failure.**

The Analysis Passport at `/app/{lang}/{org}/analyses/{run_id}` is reached from Analyses:

| Property | Value |
|---|---|
| Status / bytes | `200`, 6,497 B |
| Package digest present | yes |
| Coverage present | yes |
| Governed versions | `rra003.mapping`, `rra004.package`, `rra004.formula` — all three |

The decision page additionally carries 37 `evidence` / 32 `Evidence` references, 25 `caveat`
references and 34 `cit_` citation identifiers, which is strong evidence for `FR-161`'s distributed
limits — but it is recorded as supporting detail only, because that surface is the one clause 3
reports unreachable.

### 6 — download reconciled bilingual reports — PASS

Every artifact kind, in both languages — eight requests, eight handoffs:

| Kind | `en` | `ar` |
|---|---|---|
| `web` | `303` → `…/surfaces/web/en`, cookie set | `303` → `…/surfaces/web/ar`, cookie set |
| `evidence` | `303` → `…/surfaces/evidence/en`, cookie set | `303` → `…/surfaces/evidence/ar`, cookie set |
| `pdf` | `303` → `…/surfaces/pdf/en`, cookie set | `303` → `…/surfaces/pdf/ar`, cookie set |
| `excel` | `303` → `…/surfaces/excel`, cookie set | `303` → `…/surfaces/excel`, cookie set |

`excel` carries no language segment by its own route shape, exactly as `M3` recorded.

**The reading this clause measured.** "Download reconciled bilingual reports" is read as the
artifact-reopen path above, which is what `M3` measured and what ships. The **decision page's own
export** is a separate, undecided question: `D1-08` §Exclusions leaves whether "no
cross-organization access, sharing, or export" reaches "export" to the owner — print shipped,
export did not. That open question is a caveat on this ledger and **not** the reason any clause
fails. The comparison's own reconciled workbook (clause 2, 14,532 B, 8 sheets) is a second
satisfier reached from Analyses.

### 7 — fail-closed, scope/isolation, Arabic/English — PASS

| Probe | Result |
|---|---|
| Decision page addressed with **another organization's** identifier | `404`, 1,306 B — the uniform unavailable surface |
| Overview addressed with another organization's identifier | `404`, 1,306 B — byte-identical |
| Decision page with **no session** | `404`, 1,306 B — byte-identical |
| Decision page for a **non-existent run** | `200`, 5,744 B — governed empty |
| Arabic parity | `en` 56,946 B / `ar` 55,036 B, `dir="rtl"` present |

**The non-existent run is the interesting one, and it is correct.** The page frame renders while
every section reads *"Part of this view is unavailable."* — zero `cit_` citation references, no
figures. The `run_` identifiers and the two numbers visible on that page are the **source picker
listing this organization's own completed runs**, which is `source_options` for the same scope, not
leaked content. A cross-organization address and an absent session produce byte-identical `404`s,
so neither distinguishes "does not exist" from "not yours".

---

## The one blocker

**Failed clause:** 3 (view an executive decision page), and 4 with it.

**The single reason:** the decision surface is reachable only by an address a design partner cannot
construct. No shipped surface links to `/app/{language}/{organization}/decisions/{source}`, and its
`{source}` segment requires a `run_id` no surface exposes for this purpose.

**The minimum unblocker:** one entry point to the decision surface from a shipped surface — a
destination alongside `Overview · Data · Analyses · Team`, or a per-run link from Analyses or the
Passport that supplies the `{source}` segment. Nothing else about clauses 3 or 4 needs to change;
both pass on their own content the moment the surface is reachable.

**The authority, and the exact ambiguity.** This needs an owner reading before a slice proceeds,
and the two halves genuinely point in different directions:

- **For:** `RCA-008` §Scope already names `src/khepri/runtime/shell_api.py` and `shell_templates/`
  — the files one entry point lives in — and positions the decision surfaces "beside `RCA-005`'s
  Overview, Data and Analyses **destinations**". A surface fixed in scope beside the destination set
  is hard to read as one the destination set may not reach.
- **Against:** `RCA-008` §Exclusions bars "no chart grammar, **navigation**, accessibility-evidence,
  or visual-regression **programme** beyond the tests its Verification names, which remain `U1-03`,
  `U1-05`, `U1-06` and `U1-07`'s and need their own authority", and implementation precondition 3
  repeats that `U1`'s navigation tasks "are not preconditions and are not authorized here".

The word doing the work is **programme**. One link is not a navigation programme, and
`khepri-ui-authority-is-the-spec-not-the-program` records that `U1` being blocked is a false
blocker when an ACTIVE spec's scope names the files — which `RCA-008`'s does. But the exclusion's
wording is broad enough that a slice could read it either way, and a slice may not settle that for
itself.

**The smallest reviewable slice, once the reading is given:** a single `RCA-008` slice adding one
governed entry point in `shell_api.py`/`shell_templates/`, with its bilingual copy, plus a test
asserting that a reader arriving at a workspace can reach the decision surface without composing an
address. It adds no view, route, read model, calculation, persistence, telemetry or stylesheet
programme.

---

## What this run does not establish

- **It is a local-stack run.** As with `M2` and `M3`, it authorizes no external participant; the
  hosted environment (`OPS1-02`…`OPS1-03`) remains deferred by `KHEPRI-DEC-031` §4.
- **It measures §7's sentence, not a decomposed condition set.** If the owner would rather `M4`
  acceptance rest on numbered conditions in a governed decision — as `M2`'s did — this ledger should
  be re-read against them once they exist.
- **`D1-11` repeat-use telemetry stays excluded** by `RCA-008` §Retention, which declines to amend
  `KHEPRI-DEC-015` §3.
- **The `D1-08` export reading stays open** and is a caveat, not a blocker (clause 6).

## Caveats that do not invalidate any clause

1. **`#470` is reachable through the composition root and consumed by no route.** `PeriodComparisonView`
   answers through `SemanticQueryActions`, but `shell_controls.SURFACE_VIEWS` is "seven and not
   eight" by explicit design and `MetricCard.comparison` stays `None` "because no read model fills
   it, not because its source is unreachable" (`card.py`). Whether the decision surface should
   consume it is an `RCA-008` reading. **It is not an M4 blocker:** clause 2 is satisfied by the
   `C1` surface, which is route-reachable, discoverable and admitted.
2. **The roadmap's D1 row and §17 item 26 are factually stale at `44d54a7`**, saying "Compare is
   not implemented" and "item 26 is still not implemented". `#470` implemented it. Corrected
   separately; the correction is a statement of fact and does not itself move any gate.

## Commands run

```
docker compose -f docker-compose.staging.yml up -d --build
./.venv/Scripts/python.exe -m pytest tests/test_c107_compare_flow.py \
  tests/test_c106_comparison_orchestration.py tests/test_c101_dataset_period.py \
  tests/test_rca009_period_comparison_composition.py -q
# 66 passed in 27.44s
```

The journey itself was driven inside `khepri-staging-web` against `khepri.runtime.web:app`.

---

# Addendum — 2026-09-16: the blocker is cleared, and all seven clauses pass

**The measurement above stands as run.** It recorded `main` at `44d54a7`, and every finding was
true of that tree. This addendum records a later tree; it does not revise the earlier one.

**The owner's reading.** Asked whether `RCA-008` authorizes one decision-surface entry point or
whether that is reserved to `U1`'s navigation programme, the owner ruled that it is authorized.
`D1-12` implements it under `RCA-008` §Scope, which already names `shell_api.py` and
`shell_templates/`.

**What shipped.** One entry point on the Analysis Passport — not a fifth frame destination, because
the settled `Overview · Data · Analyses · Team` set is `U1`'s and a test now asserts the entry point
never leaks into it. The link is offered per run, because the route is addressed per run, and is
guarded twice: on `offers_decisions`, so a deployment without the seam offers no dangling address
(`FR-049`), and on a *completed* run, because an unsettled run has no projections for the surface
to show.

**Re-measured by navigation, on a rebuilt image whose four changed modules digest-match the
worktree.** The reader arrives at Analyses, follows a rendered link to the Passport, and follows a
rendered link to the decision surface. **No address in this run was composed by the harness** —
each was read out of the page before it.

| Step | `en` | `ar` |
|---|---|---|
| 1. Analyses → Passport links | 2 | 2 |
| 2. Passport → decision links | 1 | 1 |
| 3. Decision surface | `200`, 56,947 B, 34 citations, all four sections | `200`, 60,825 B, `dir="rtl"`, 34 citations, all four sections |
| 4. Filters offered by the page | `store`, `product`, `category` | same |

Clause 4 drilled from the page's own form: `store=Cairo` 51,452 B, `category=Beverages` 39,295 B,
`store=Cairo&category=Beverages` 33,664 B — each materially different from the 56,947 B baseline.

| # | §7 clause | Result |
|---|---|---|
| 1 | return to a workspace | **PASS** |
| 2 | compare governed periods | **PASS** |
| 3 | view an executive decision page | **PASS** — was FAIL at `44d54a7` |
| 4 | drill through supported breakdowns | **PASS** — was FAIL at `44d54a7` |
| 5 | inspect evidence and limitations | **PASS** |
| 6 | download reconciled bilingual reports | **PASS** |
| 7 | fail-closed, scope/isolation, Arabic/English | **PASS** |

**Seven of seven clauses pass.** On the measured evidence the `M4` exit gate is met.

**The caveats above stand unchanged** — the local-stack limitation, the `D1-08` export reading,
`D1-11`'s telemetry exclusion, and `PeriodComparisonView` being reachable through the composition
root while consumed by no route. None of them blocks the gate; see §M4 acceptance below for what
acceptance does and does not settle.

**Guards proven by mutation, because a guard with no failing test is not a guard.** Dropping the
completeness check left all 39 detail tests passing until
`test_an_unsettled_run_offers_no_entry_point` was added; dropping `offers_decisions` fails the
unwired test; and a mutant returning `"mut_" + run_id` survived a containment assertion, so the
`{source}` segment is now compared exactly.

## Commands run for this addendum

**The suite count below is 5,577 and §M4 acceptance reports 5,578; both are right, and the
difference is one test.** This addendum's run predates review on `#472`, which found that a failed
run is settled but not decision-ready (`fail_run` writes `completed_at`) and added
`test_a_failed_run_offers_no_entry_point`. That test is the 5,578th and is present in the accepted
tree. Two trees, two counts, neither revised.

```
docker compose -f docker-compose.staging.yml up -d --build   # 4/4 modules digest-match
./.venv/Scripts/python.exe -m pytest -q                       # 5577 passed, 77 skipped, 1 xfailed
                                                              # (pre-review-fix tree; see note above)
uv run ruff check .                                           # All checks passed!
uv run khepri-gov validate                                    # Governance validation passed.
codescene analyze_change_set --base origin/main               # quality_gates passed
```

---

# M4 acceptance

**`M4` is ACCEPTED.**

| | |
|---|---|
| **Milestone** | `M4` — Sellable decision workspace |
| **Accepted on** | 2026-09-16 |
| **Accepted against** | `main` at `5c4c522` (`feat(d1-12): reach the decision surface from the Analysis Passport (#472)`) |
| **Basis** | All **7 of 7** `M4` exit-gate clauses PASS, measured on the deployed image |
| **Original measurement** | `#471` — `main` at `44d54a7`, 5/7 PASS, one shared blocker on clauses 3 and 4 |
| **Unblocker** | `#472` (`D1-12`) — one governed entry point to the decision surface |
| **Re-measurement** | §Addendum — 7/7 PASS, driven by navigation on the rebuilt image |
| **Accepted by** | The owner, explicitly, on the evidence in this document |

**The four stages are distinct, and the record keeps them so.** The 5/7 result at `44d54a7` was
true of that tree and is preserved unrevised; `#472` cleared the single blocker it named; the
re-measurement then found 7/7; and acceptance is the owner's judgment on that evidence. This
document is not rewritten as though the first run had passed.

**Validation carried by the accepted tree** (from `#472`, the merge that produced `5c4c522`):
full suite 5,578 passed / 77 skipped / 1 xfailed; `ruff check .` clean; `khepri-gov validate`
passing; the CodeScene change-set gate passing; and all CI checks green on the merged PR.

## What acceptance does NOT settle

Acceptance is scoped to the `M4` exit-gate sentence. It closes, schedules, reinterprets and
authorizes nothing else. Each of the following remains exactly as it stood before:

- **`M4` remains non-paying**, as `KHEPRI-DEC-025` §5 governs. Taking consideration is `M5` and
  waits on the successor commercial identity authority under `G6`.
- **`D1-08`'s export reading** — whether "no cross-organization access, sharing, or export"
  reaches "export" — is still the owner's, still undecided. Print shipped; export did not.
- **`D1-11`** content-free decision-use telemetry stays **unauthorized**, not merely unscheduled:
  `RCA-008` §Retention declines to amend `KHEPRI-DEC-015` §3.
- **`PeriodComparisonView` is consumed by no route.** It is reachable through the semantic-query
  composition root (`RCA-009`, `#470`), but `shell_controls.SURFACE_VIEWS` names seven views and
  not eight, and `MetricCard.comparison` stays `None` because no read model fills it. Whether the
  decision surface should consume it is an `RCA-008` reading, still open. Clause 2 is satisfied by
  the `C1` comparison surface and does not depend on it.
- **`U1`'s navigation, chart-grammar, accessibility-evidence and visual-regression programme**
  remains `U1-03`/`U1-05`/`U1-06`/`U1-07`'s and still needs its own authority; `U1` is blocked on
  the owner's `RRA-010` journey-adoption reading. `D1-12` added one entry point under `RCA-008`
  §Scope and changed no destination set.
- **`S1-05` / `#152`** is untouched by this acceptance.
- **This is a local-stack run.** It authorizes no external participant; the hosted environment
  (`OPS1-02`…`OPS1-03`) stays deferred by `KHEPRI-DEC-031` §4, and hosted-production admission is
  not granted here.
