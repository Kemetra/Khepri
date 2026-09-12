# `D1-04` — Breakdowns, the limits surface that qualifies them, and the route `D1-03` deferred

> **Execution plan** (the `W1-09` tier). Parent: the allocation plan at
> `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`.
> **Authority:** active `RCA-008` — `FR-159`, `FR-163`, `FR-165`, `FR-167`, plus `FR-046`/`FR-050`
> for the route `D1-03`'s plan deferred here by amendment.

**Deliverable:** `decision/breakdowns.py` (S-3 Branch, S-4 Product/Category, S-5a Basket, S-5b
Concentration), `decision/limits.py` (S-6 — availability, caveats and refusals), and the decision
route: `add_decision_routes` in `shell_decisions.py`, a `decisions` collaborator on
`ShellServices`, and `decision.html.j2` moving from `_UNROUTED_TEMPLATES` into `SHELL_SURFACES`.

---

## What `D1-03` handed forward, verbatim

> "`D1-04` ships it, driven. … when `D1-04` ships the route, `decisions` joins `ShellServices` as
> an optional collaborator beside `comparisons`, `pins` and `deletion`."

and, in `tests/test_r807_shell_quality.py`:

> "**This set is removed by `D1-04`, not amended by it.** The moment the route exists the template
> gains an address, and the equality below then fails until it moves into `SHELL_SURFACES` with
> one."

Both are discharged here. The `wiring.py` question `D1-03` raised is **not** discharged here and
cannot be: see §The two things this slice still cannot reach.

---

## Six decisions, taken from precedent rather than assumed

**1. Where does the fail-closed dispatch rule live now that four modules need it?**
In `seam.py`, as `admitted_projection`. `D1-02` put it in `overview.py` and `D1-03` re-derived it
as `card._admitted_projection` with a docstring saying it was "in one place for both reads". Two
more read models make that claim false, and the rule — *the kind decides, never the payload,
because `ViewOutcome` has no kind-to-payload validation* — is a property of the seam rather than of
any surface. It moves to the module that owns the outcome contract and the two existing callers
import it. This is `RCA-008` §Scope's own `src/khepri/rca/workspace/` and touches nothing else.

**2. Do the breakdown readers pass filters through, when `D1-07` owns the filter surface?**
Yes, verbatim, and that is the requirement rather than an anticipation of `D1-07`. `FR-137` refuses
an unsupported filter *before* projection and `FR-166` says so in as many words — a parameter a
view's `request_filter_allowlist` does not name "does not get it ignored; it gets a refusal". A
reader that filtered the filters would be a second copy of the allowlist and would *drop* exactly
what the requirement says must refuse. `D1-07` owns which controls a surface **offers**; this slice
owns that whatever is asked for is asked for.

**3. What shape is a breakdown row, when the four views publish four different field orders?**
The view's own, as ordered pairs. `BranchPerformanceView` publishes
`("store", "metric", "value", "population")` and `ProductCategoryView` publishes five fields with
different names; a common flattened record would have to invent a name for at least one of them.
Naming each row by its projection's `fields` is `FR-159`'s "group for layout" and nothing more —
**and it is also how `FR-167` holds by construction**: a field the view did not publish cannot
appear, so a four-state availability cannot be attached to a per-store figure even by accident.

**4. Does S-6 re-read the other surfaces to collect their caveats?**
No. `RCA-008`'s source map gives S-6 "`MetricAvailabilityView`, **and each projection's own
caveats**" — *its own*, already fetched. A second fetch would be the pre-aggregation `FR-168` bars
and the second truth `FR-135` bars, and the caveats would be a different run's the moment anything
moved. So `LimitsRequest` carries the outcomes the surfaces already hold, named by surface, and
`limits.py` reads exactly one view of its own.

**5. Where does the route's member gate come from?**
Restated in `shell_decisions.py`, not shared. `shell_comparison._member_or_none` is the identical
gate, and `RCA-008` §Exclusions bars "edits to `RCA-001`, `RCA-002`, `RCA-005` … source paths" —
so this slice may neither lift it into a shared home (`shell_invitations.py` is `RCA-002`'s) nor
edit the module that has it. Importing `RCA-005`'s private name would bind D1's authorization to a
symbol another specification may rename without notice. **The duplication is the cost of the
boundary and is recorded here rather than discovered in review.**

**6. Does the decision surface get a frame link?**
No, and not for want of one. `organization_frame`'s `destinations` are decided in
`shell_frame.py`, which is `RCA-002`'s and which §Exclusions does not admit. The surface is
reachable by address and not by navigation until an authority that owns the frame says otherwise.
`RCA-002` `FR-049`/`FR-121` point the same way meanwhile — a link ships with a complete surface,
and `D1`'s is complete when `D1-06` has finished with it.

---

## Files

```text
src/khepri/rca/workspace/decision/seam.py        EDIT  admitted_projection moves here
src/khepri/rca/workspace/decision/overview.py    EDIT  imports it
src/khepri/rca/workspace/decision/card.py        EDIT  imports it
src/khepri/rca/workspace/decision/breakdowns.py  NEW   S-3, S-4, S-5a, S-5b
src/khepri/rca/workspace/decision/limits.py      NEW   S-6
src/khepri/runtime/shell_decisions.py            EDIT  add_decision_routes
src/khepri/runtime/shell_api.py                  EDIT  ShellServices.decisions, _ROUTE_DECLARATIONS
tests/test_d104_breakdowns_and_limits.py         NEW
tests/test_r807_shell_quality.py                 EDIT  _UNROUTED_TEMPLATES removed
```

---

## Steps

### RED

- [ ] `tests/test_d104_breakdowns_and_limits.py`, failing because the modules do not exist:
  - **`FR-160` — each breakdown reads its own view at its literal version**, and only that one.
    Asserted through a port that records what it was asked for.
  - **`FR-163` — the two empty rules on one page.** S-3 and S-4 report `stated_no_rows`; S-5's two
    views report `stated_absence`. A store filter naming a store with no sales is `stated_no_rows`
    and is **not** a refusal — asserted as both a positive and a negative.
  - **`FR-165` — S-5 is one surface and two independent reads.** Basket admitted while
    Concentration is unavailable renders the basket figures and says the other part is
    unavailable, content-free. The converse too, so neither ordering is privileged.
  - **`FR-167`, negatively and three ways.** No breakdown shape carries an availability field; no
    breakdown row can carry one, because rows are named by the projection's published fields and
    no breakdown view publishes availability; and `breakdowns.py` names neither
    `METRIC_AVAILABILITY` nor any availability literal, asserted against its AST.
  - **`FR-137`/`FR-166` — a filter is passed through verbatim**, never dropped, and an unsupported
    one arrives at the seam rather than being filtered out before it.
  - **S-6 reads exactly one view** and collects caveats and refusals from outcomes already
    fetched, re-reading nothing (`FR-168`, `FR-135`).
  - **The dispatch rule** — a refused outcome carrying a projection is still refused, on all four
    breakdown readers and on the limits read.
  - **The route.** A shell without `decisions` declares no decision address at all (`FR-046`); a
    session whose organization disagrees with the address gets the uniform unavailable surface
    (`FR-042`, `FR-050`); a member gets the decision surface in the page language, with the
    governed cards on it (`FR-171`).

### GREEN

- [ ] `seam.admitted_projection` and its two callers; `breakdowns.py`; `limits.py`;
      `add_decision_routes`; `ShellServices.decisions`; `_ROUTE_DECLARATIONS`.
- [ ] `tests/test_r807_shell_quality.py`: **delete** `_UNROUTED_TEMPLATES` and add
      `"decision": "/org-acme/decisions/run-a"` to `SHELL_SURFACES`, with a stub collaborator. The
      set equality fails until both halves are done, which is what the constant was for.

### Gates

- [ ] `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
- [ ] Every new file 10.00 in CodeScene; no tracked hotspot declines. `shell_api.py` gains one
      optional field and one tuple entry and nothing branching; `shell_decisions.py` gains a route
      whose conditionals are single-operator and whose arguments are grouped in a value object,
      because two logical operators in one conditional and a fifth argument have each cost this
      programme a finding already.

---

## `wiring.py` — the question, and how it was answered in practice

This plan shipped saying the composition root was out of reach: `ShellServices` is constructed in
`src/khepri/runtime/wiring.py`, which `RCA-008` §Scope does not name, so whether it was `D1`'s to
edit was raised as an owner question and left open — on `#447`, in this plan, and in
`shell_decisions.py`'s docstring.

**It was answered in practice, by the fix review forced** (`387c21c`, after review on `#448`):
`_shell_decisions` composes `SemanticQueryActions` from the caller's own `IsolationService` and
record store, and `build_shell_services` passes it as `decisions`. So the decision route is in the
built image, and the surface is reachable by a deployment rather than only by a test.

**Attribution, stated exactly.** The owner merged that fix; the owner did **not** author a scope
ruling. `#448` review found the route absent from the built image, the alternative to editing
`wiring.py` was shipping a capability no customer could reach, and the call was taken in-session on
that basis. **The scope question therefore remains open and owner-authored** — a merge accepts a
change, it does not settle whether `RCA-008` §Scope reaches this file.

**The reading offered in support of it, which the owner has not ratified.** §Scope not naming a file is not
the same as §Exclusions barring it. §Exclusions names `RCA-001`, `RCA-002`, `RCA-005`, `RCA-006`,
`RCA-007`, `RRA-011`, `RRA-012` and `RRA-014` source paths; `wiring.py` is named by neither, and
the alternative to editing it was shipping a capability no customer could reach. Decisions 5 and 6
above are **not** loosened by this: `shell_invitations.py` and `shell_frame.py` are `RCA-002`'s,
named explicitly, and stay out of bounds.

**What the failure actually was, and it is worth naming.** Every `D1-04` test built
`SemanticQueryActions` by hand, so the route table they exercised was the test's and never the
deployment's — a route test can prove a route works *once wired* and cannot prove anything wires
it. Six green checks and the whole suite passed over the gap. `W1-07a` shipped the same defect for
`deletion` (`#382`) and `W1-09` nearly shipped it for `pins`, and both left comments inside
`build_shell_services` one line above where `decisions=` belonged.

The guard that came with the fix is the part that outlives this slice:
`test_the_built_image_wires_every_optional_field` derives its population from
`dataclasses.fields(ShellServices)`, so **the next optional field is covered without anyone
remembering to cover it** — a test naming `decisions` would have guarded `decisions` and left
field #11 open, which is how this recurred three times.

## The one thing this slice still cannot reach

- **The frame link.** Decision 6 above: `organization_frame`'s destinations live in
  `shell_frame.py`, which §Exclusions names as `RCA-002`'s. The decision surface is reachable by
  address and not by navigation until an authority that owns the frame says otherwise.

## Not in this slice

- **No evidence drawer.** `D1-05`. Breakdown rows carry `evidence_absences` as the projection
  published them and present no drawer.
- **No filter controls.** `D1-07`. Filters pass through; nothing offers them yet.
- **No Period Comparison binding.** `RCA-008` §The open question; `FR-170`'s assertion stands.
- **No stylesheet rules.** The surface reuses `RCA-005`'s document card; `D1-08` and `D1-10` own
  the presentation work.
