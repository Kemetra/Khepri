# `D1-06` — S-7, the return path that carries no figure (S-8 is owner-blocked)

> **Execution plan.** Parent: the allocation plan at
> `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`, refined at
> `docs/superpowers/plans/2026-09-12-d1-06-10-planning-refinement.md`.
> **Authority:** active `RCA-008` — `FR-159`, `FR-161`, `FR-165`.

**Deliverable:** S-7 (Recent Analyses and Comparisons) as a new read model under
`rca/workspace/decision/`. It derives no figure and performs no semantic-view read.

> **S-8 is not in this deliverable, and the reason is a specification conflict this slice cannot
> settle.** See §S-8 is owner-blocked below. `D1-06` ships S-7; the S-8 half is filed for the
> owner rather than worked around.

---

## What `D1-05` handed forward, and the scope this slice inherits

`D1-05` was expected to defer S-3, S-4 and S-5 to this slice. The implementation that shipped
(`#451`, `b28b97e`) built them, on the reading that a slice allocated to *attach* a drawer to a
surface may build the surface. **This plan was written against the reduced scope** — S-7 and S-8,
which the allocation plan always assigned here. **It ships only S-7**: writing it surfaced a
specification conflict that blocks S-8, recorded below and filed for the owner.

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
(`[[khepri-rca-store-has-no-list-reads]]`). **S-7 is the exception; S-8 is not.** Each row below
was read in source rather than inferred from a name:

| Need | Exists today | Where |
|---|---|---|
| S-7: pinned objects for a scope | **Yes** — `pins_for_scope(owner_id)` | `rca/workspace/pins.py:211` |
| S-7: recency for a scope | **Yes** — `recent_activity(owner_id, *, limit=5)` | `rca/workspace/pins.py:233` |
| S-7: the presented shape | **Yes** — `RecentItem`, `WorkspacePin` | `rca/workspace/pins.py:62`, `:44` |
| S-8: the surface | Exists, but is **`RCA-005`'s** — see §S-8 is owner-blocked | `shell_api.py:609` |
| S-8: the `RRA-006` bundle read | **No** — `SqlRunReportStore` exposes link-table reads only | `rca/workspace/run_reports.py:89`–`:153` |

**The last row is the recurring defect, and it was nearly missed.** An earlier draft of this plan
listed only S-7's three reads, checked `run_reports.py` for `class` definitions rather than for
read methods, and on that basis called the whole slice "the exception". `SqlRunReportStore` has
`link`, `run_id_for_job`, `job_id_for_run`, `links_for_scope` and `links_of_started_runs` — every
one a read of the run↔report *link table*, and none returning a report bundle. Checking a class
list is not checking a read.

**No new store method is required for S-7, and none may be added:** `pins.py` and `store.py` are
`RCA-005` source paths, which §Exclusions bars this slice from editing.

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

## S-8 is owner-blocked: two active specifications claim the same surface

**The allocation plan says "S-8 is a surface `D1-06` refactors rather than builds". That
instruction cannot be executed without violating `RCA-008`, and the conflict is in the authorities
rather than in the plan's wording.**

`D1-01` and the allocation plan identify S-8 as the existing analysis surface — `analysis.html.j2`,
rendered at `shell_api.py:609` through `_workspace_reads(services, context, surface="analyses")`.
That surface is **`RCA-005`'s**, and `RCA-005` says so in its own §Scope:

> `RCA-005`:33 — "`src/khepri/runtime/shell_api.py` and `shell_templates/` — the Overview, Data and
> **Analyses** surfaces"

`RCA-008` claims the same two files, and resolves the overlap with one word:

> `RCA-008` §Scope — "the decision surfaces, under `RCA-002`'s frame and **beside** `RCA-005`'s
> Overview, Data and Analyses destinations"

**"Beside" is positional.** It admits *adding* decision surfaces to those files; it does not admit
*editing* `RCA-005`'s destinations in them. §Exclusions then says it flatly: "no edits to …
`RCA-005` … source paths".

**So both available moves are barred, and this is why it needs the owner rather than a decision
here:**

| Move | Barred by |
|---|---|
| Refactor `analysis.html.j2` / its handler | `RCA-008` §Exclusions — no edits to `RCA-005` source paths |
| Build a second report surface | `RCA-005` `FR-118` — "There is no reports index and **no second list of the same objects**" |

`FR-117` reinforces it: the Analyses surface is "the single history spine", and `FR-118` puts
artifacts reachable "only from Analysis detail". A navigable report workspace built alongside is
the second list `FR-118` refuses by name.

**This is the shape `[[khepri-a-spec-can-assign-work-to-the-wrong-slice]]` records**, and the plan's
own §The `RCA-005` boundary prescribed the response before the conflict was found: *stop and file
the question rather than widening the diff*. That is what this does.

**What the owner is being asked.** Either amend `RCA-008` to admit the specific `RCA-005` surface
edit S-8 needs, or reassign S-8 to a slice under `RCA-005`'s authority, or rule that S-8 is a
`U1`-style surface needing its own artifact. **Not** a question this slice may answer by choosing
the reading that lets it proceed —
`[[khepri-never-delete-the-clause-that-gates-your-change]]`.

**The second finding, recorded because it outlives this block.** S-8 reads two authorities, and the
`RRA-006` report bundle half has **no reachable read**. `SqlRunReportStore` exposes `link`,
`run_id_for_job`, `job_id_for_run`, `links_for_scope` and `links_of_started_runs` — all link-table
reads, none returning a report bundle. This is
`[[khepri-rca-store-has-no-list-reads]]` landing on this slice exactly as it has on every prior
shell slice, and it means the `FR-165` two-direction tests had no second authority to degrade even
if the surface question resolved. Whoever picks S-8 up inherits both problems, not one.

---

## `FR-165` — deferred with S-8, and what it will require

**This section describes S-8's obligation and is not executed by this slice.** S-8 reads
**two authorities**: the `RRA-006` report bundle and `RCA-005` analysis detail.
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

**For S-7, which this slice ships:**

1. **S-7 reads records for structure and derives no figure.** Asserted as the *absence* of a
   semantic-view read in the S-7 module — by import and by call, not by inspecting output values.
   A scan asserting absence carries its own emptiness assertion
   (`[[khepri-guards-that-cannot-see-the-new-surface]]`).
2. **A record read that is unavailable degrades that region only**, with the unavailable outcome
   content-free per `FR-165`. S-7's two reads are `pins_for_scope` and `recent_activity`, so this
   is two cases — pins-unavailable and recency-unavailable — not one
   (`[[khepri-redundant-guards-need-separate-evidence]]`).
3. **No file under `RCA-005`'s paths is modified, asserted by path.** This is the acceptance the
   S-8 finding was caught by, and it stays even though S-8 is deferred: S-7 reads `pins.py` and
   must not edit it.
4. **S-7 orders by the `occurred_at` its records already carry**, with no count, rank, score or
   frequency anywhere on the path — `FR-129` MUST-retain-nothing, and `KHEPRI-DEC-034` §2.
5. **S-7 writes nothing.** `FR-129`: "A view that writes a row to answer 'what was recent' is
   product telemetry and is excluded by this specification, whatever it is named." Asserted as no
   write on the path, not as the absence of a named table
   (`[[khepri-guards-that-cannot-see-the-new-surface]]`).

**For S-8, which it does not:**

6. **No second report surface is created** — asserted by the route table
   (`[[khepri-a-hand-wired-fixture-hides-an-unwired-deployment]]`). This holds as a *negative*:
   this slice adds no report address, and `FR-118` bars one until the owner rules.

---

## Exclusions

- **S-8, the navigable report workspace** — owner-blocked on the `RCA-005`/`RCA-008` surface
  conflict recorded above, and additionally missing its `RRA-006` bundle read. Deferred whole, not
  partially attempted.
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
