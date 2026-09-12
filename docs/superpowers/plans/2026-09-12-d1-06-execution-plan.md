# `D1-06` — The navigable report workspace, and the return paths that carry no figure

> **Execution plan.** Parent: the allocation plan at
> `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`, refined at
> `docs/superpowers/plans/2026-09-12-d1-06-10-planning-refinement.md`.
> **Authority:** active `RCA-008` — `FR-159`, `FR-161`, `FR-165`.

**Deliverable:** S-7 (Recent Analyses and Comparisons) as a new read model under
`rca/workspace/decision/`, and S-8 (the navigable report workspace) as a **refactor of the existing
analysis surface**. Neither surface derives a figure, and neither performs a semantic-view read.

---

## What `D1-05` handed forward, and the scope this slice inherits

`D1-05` was expected to defer S-3, S-4 and S-5 to this slice. The implementation that shipped
(`#451`, `b28b97e`) built them, on the reading that a slice allocated to *attach* a drawer to a
surface may build the surface. **This plan is written against the reduced scope** — S-7 and S-8,
which the allocation plan always assigned here.

> **The reading is the owner's and is still unsettled.** `RCA-008` §Scope names
> `src/khepri/rca/workspace/decision/` and the decision templates, which covers the breakdown
> sections either way, so nothing merged is outside authority. What is unsettled is whether one
> slice may build a surface it was allocated only to attach to. Recorded here, as the refinement
> document records it, so this slice proceeds on the scope rather than on an assumption about the
> ruling. **If the owner rules the other way, this plan does not change** — S-3/S-4/S-5 would
> already be built, and this slice's own deliverable is untouched either way.

---

## The thing this plan found before writing a line

**Every prior D1 slice added a semantic-view read. This one must add none.**

`D1-01`'s surface table marks both S-7 and S-8 **"No"** in its SV1-read column, and says S-7
*cannot* be an SV1 read **at any view version**: no published projection ranges over runs, and
`ScopedSourceReader.get_analysis_run` reads one run by id. A view is a projection over a bundle,
never over a workspace.

So `FR-159` is satisfied here **by carrying no figures at all**, not by reading a view correctly.
Its own text is what admits this: structure and navigation *may* come from `RCA-005` records and
the `RRA-011` catalog; only figures may not. S-7 and S-8 are return paths.

**The failure mode this creates.** A plan that reaches for a view read has misread the slice, and
the resulting code would be a `FR-159` violation dressed as compliance — a figure derived on a
surface whose whole purpose is navigation. The acceptance below asserts the *absence* of a view
read by module, not merely the correctness of one.

---

## What already exists, verified rather than assumed

`memberships_for_organization` is absent and each shell slice finds a missing list read
(`[[khepri-rca-store-has-no-list-reads]]`). **This slice is the exception, and it was checked:**

| Need | Exists today | Where |
|---|---|---|
| Pinned objects for a scope | **Yes** — `pins_for_scope(owner_id)` | `rca/workspace/pins.py:211` |
| Recency for a scope | **Yes** — `recent_activity(owner_id, *, limit=5)` | `rca/workspace/pins.py:233` |
| The presented shape | **Yes** — `RecentItem`, `WorkspacePin` | `rca/workspace/pins.py:62`, `:44` |
| The S-8 surface | **Yes** — `analysis.html.j2`, rendered from `shell_api.py:609` | `runtime/` |

**No new store method is required, and none may be added:** `pins.py` and `store.py` are `RCA-005`
source paths, which §Exclusions bars this slice from editing.

**`RecentItem` carries no count and no rank**, by its own docstring — recency is an ordering over
records that exist, and frequency would need a record of each visit, which `KHEPRI-DEC-034` §2
refuses. A read model that sorts by frequency, scores recency, or synthesizes a "most used" is
inventing the access record that decision declined, and would additionally be an `FR-159`
derivation. S-7 orders by the `occurred_at` the record already carries, and does nothing else.

---

## The `RCA-005` boundary is the risk in this slice

`RCA-008` says this **twice, in two clauses**, and both were read rather than assumed. §Scope
permits new modules under `src/khepri/rca/workspace/` and adds "`RCA-005`'s existing files are
**untouched**". §Exclusions (line 152) bars "edits to `RCA-001`, `RCA-002`, `RCA-005`, `RCA-006`,
`RCA-007`, `RRA-011`, `RRA-012` or `RRA-014` source paths". §Scope's *Not in scope* names
"workspace persistence and the comparison request/result routes (`RCA-005`)".

**A refactor that needs to change `persistence.py`, `pins.py` or `store.py` is mis-sliced and needs
the owner, not a workaround.** If S-8's refactor reaches one of those files, stop and file the
question rather than widening the diff — this is the shape
`[[khepri-a-spec-can-assign-work-to-the-wrong-slice]]` records.

The acceptance asserts this **by path**, so the constraint is checked mechanically rather than by
the author's care.

---

## S-8 is refactored, not built

`analysis.html.j2` exists and is rendered at `shell_api.py:609`. **A slice that builds a second
report surface has created the two-definitions problem the repository fails closed on.**

The refactor makes the existing surface navigable. It does not introduce a parallel report page,
and it does not move the address: `shell_api.py:606` already sets
`surface_path = f"/{context.organization_id}/analyses/{run_id}"` with a comment recording that
`FR-054` keeps the language control on this analysis. That comment is a constraint, not
decoration — a refactor that changes the address breaks the language control's return path.

---

## `FR-165` — the two reads are independent, and this is testable

S-8 reads **two authorities**: the `RRA-006` report bundle and `RCA-005` analysis detail.
`FR-165` makes each independently authorized and independently able to answer unavailable, so the
surface renders partial success rather than failing whole. The unavailable outcome is
**content-free** — the surface may say a part is unavailable and may never say why.

**Both directions need their own case.** One outcome test passes with either read degrading
(`[[khepri-redundant-guards-need-separate-evidence]]`): bundle-unavailable-detail-available, and
detail-unavailable-bundle-available, are two tests, and a single "partial renders" test is not
evidence for either.

**Watch the access path, not just the values.**
`[[khepri-a-batching-fix-regresses-the-single-item-caller]]`: `#378` fixed a spine and made detail
read the whole scope, and value assertions could not see it. A test here asserts *what was read*,
not only what rendered.

---

## `FR-161` — reachability, not a terminal page

A claim is presented only where the reader can also reach whether it is allowed to be made.
Availability, caveats and refusals are reachable **from the surface carrying the figure they
qualify**, and are not deferred to a terminal page.

S-7 and S-8 carry no figures, so this requirement binds them as a **navigation** constraint: a
return path that leads to a figure must not strand the reader from that figure's limits. The
`D1-05` precedent is the one to follow — S-6 renders distributed, in each section's own row,
rather than as a consolidated limits page.

---

## Execution

Plan-then-RED-then-GREEN in one PR, per `[[khepri-one-pr-per-slice]]`.

1. **Plan commit** — this document.
2. **RED** — the tests below, failing because the read model and the refactor do not exist.
   Check each RED test's surface and exception type against the tier matrix before making it
   green (`[[khepri-red-tests-can-contradict-the-tier-matrix]]`).
3. **GREEN** — `decision/recent.py` (S-7's read model) and the S-8 refactor.

**Verification before any completion claim** — evidence, not assertion:

```
uv run khepri-gov validate
uv run ruff check .
uv run pytest                      # the FULL suite, not the targeted file
```

The full suite is not optional here: S-8 is a refactor of a surface other suites already exercise,
and `[[khepri-run-the-full-suite-before-believing-a-targeted-one]]` records that changing an
existing surface breaks suites you never opened while the targeted file stays green.

Pre-flight CodeScene against a **fetched** `origin/main`
(`[[khepri-fetch-before-codescene-preflight]]`), and note that extracting helpers *raises* the
module mean rather than lowering it (`[[khepri-codescene-measures-complexity-not-length]]`).

---

## Acceptance

1. **The workspace reads records and bundles for structure and derives no figure.** Asserted as the
   *absence* of a semantic-view read in the S-7/S-8 modules — by import and by call, not by
   inspecting output values. A scan asserting absence carries its own emptiness assertion
   (`[[khepri-guards-that-cannot-see-the-new-surface]]`).
2. **A record read that is unavailable degrades that region only**, in both directions, as two
   separate cases, with the unavailable outcome content-free per `FR-165`.
3. **No file under `RCA-005`'s paths is modified, asserted by path.**
4. **No second report surface exists** — the S-8 address is the one that exists today, asserted
   against the app's route table rather than against the template
   (`[[khepri-a-hand-wired-fixture-hides-an-unwired-deployment]]`).
5. S-7 orders by the `occurred_at` its records already carry, with no count, rank, score or
   frequency anywhere on the path.

---

## Exclusions

- **`RCA-005` source paths** — `persistence.py`, `pins.py`, `store.py`, and workspace persistence
  generally. A need to edit them is a mis-slice, not a workaround.
- **The comparison request/result routes** — `RCA-008` §Not-in-scope names them.
- **The navigation, accessibility-evidence and visual-regression *programme*.** §Exclusions bars
  it "beyond the tests its Verification names", and reserves it to `U1-03`, `U1-05`, `U1-06` and
  `U1-07`, which need their own authority. Making one surface navigable is this slice's; a
  navigation or accessibility programme is not, and the boundary is the Verification section's
  named tests.
- **`D1-07`'s controls** — the source selector and the three real view filters are that slice's,
  and it is parallel-safe with this one (blocked by `D1-04`, not by `D1-06`).
- **The `ports.py:113` annotation defect** — `evidence_absences` is annotated `tuple[str, ...]`
  and carries `tuple[tuple[str, str], ...]`. Live on `main`, recorded on `#450`'s closing comment,
  and it needs `RCA-006`'s authority or a one-line amendment. Not this slice's to fix.
- **`limits.py`'s dead read** — `D1-05` left it called by nothing, its single read duplicating one
  `read_cards` already performs. It is a cleanup candidate, and folding it in here would mix a
  `D1-05` correction into a `D1-06` diff.

---

## Parallel-slice collision notes

- **Alembic sibling migration status:** no migration; this slice adds no persistence schema change,
  stored column or retention record.
- **Stacked-branch rebase status:** branched from `b28b97e` (`main`), no stack beneath it.
  `[[khepri-stacked-prs-auto-close-on-base-delete]]` — every slice branches off `main`.
- **Same-slice collision:** `D1-05` was implemented twice in parallel
  (`[[khepri-two-branches-can-implement-one-slice]]`). Before starting GREEN, check that no other
  branch is implementing `D1-06`.
