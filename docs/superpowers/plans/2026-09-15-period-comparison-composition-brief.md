# Period Comparison composition: the owner decision brief

**Authority:** none. This document is a brief, not an authority. It records what blocks the Period
Comparison surface, what the shipping code actually does, and which artifact shapes could resolve
it. **It is deliberately not drafted `proposed`** — there is no such registry state, and the
artifact that resolves this is the owner's to author, per `RCA-008`:88 and `§17` item 25.

**Written at** `main` = `d753e41`, 2026-09-15.

**Why a brief rather than the artifact.** `RCA-008` names two branches — author a successor
composition artifact, or accept a D1 milestone without Compare — and the second is a product call.
Recording a recommendation here as settled would author the owner's decision. What this document
can do is make that decision a signature rather than an investigation.

---

## 1. The collision, in one paragraph

`PeriodComparisonView` is published, governed and unreachable. It is unreachable because the only
composition root that feeds the semantic-view port builds single-population bundles, and the view
admits only a two-population one. Binding the two-population source means changing
`semantic_view_adapter.py`. That file is `RCA-007` §Scope. `RCA-008` — which governs the D1
surfaces — declined to claim the binding for exactly that reason, and holds the surface open
instead. So the surface has authority, the source has authority, and **the one line joining them
has none**.

## 2. What the code does, verified at `d753e41`

Each claim below was checked against the tree rather than carried from a note.

| # | Claim | Verified at |
|---|---|---|
| 1 | The adapter returns a single-population bundle and nothing else | `runtime/semantic_view_adapter.py:188` — `return ReportBundle.of(package)` |
| 2 | The view admits only the two-population shape | `rra/semantic_views/registry.py:115` — `accepted_source_shape=SHAPE_TWO_POPULATION` |
| 3 | A shape mismatch is refused, not degraded | `rra/semantic_views/compatibility.py:178` — `definition.accepted_source_shape not in (shape, SHAPE_EITHER_BUNDLE)` |
| 4 | The only `assemble_crossversion` caller in the runtime is not bound to the port | `runtime/comparison_assembly.py:166`; the other callers are `rra/crossversion_bundle.py:353` (internal) |
| 5 | The seam records the absence deliberately | `rca/workspace/decision/seam.py:89-94` — "Published and **not reachable**" |

`SHAPE_EITHER_BUNDLE` does not rescue this: `compatibility.py:168-170` states that "either" means
*either of the two concrete bundles*, and the view names `SHAPE_TWO_POPULATION` specifically.

## 3. The governing clauses, quoted

Three clauses jointly create the gap. A successor must address all three; amending one leaves the
other two standing.

1. **`RCA-008`:80-85** — *"This specification does not claim that binding… the binding is a
   composition-root change in a file `RCA-007` §Scope already governs, and two active
   specifications governing one file is the ambiguity this repository fails closed on."*
2. **`RCA-008` §Implementation preconditions, item 2** — *"A slice may ship the surface with
   `FR-170`'s visible absence; **none may bind the two-population source under this document**."*
3. **`RCA-007` §Scope:36-37** — `semantic_view_adapter.py` is *"the future composition boundary that
   satisfies `RRA-014`'s projection protocol over organization-scoped runs."* Its §Scope also
   states that no route, template, public API, migration, cache or background job is governed.

**The trap this creates.** Any artifact resolving this must amend or supersede clauses 1 and 2. An
artifact that instead *edits* `RCA-008`'s precondition to admit itself is self-authorization — the
failure mode the repository's own integrity rules name. The successor states the new reading; it
does not quietly delete the clause that refused it.

## 4. Stop conditions, tested

The task this brief answers carried stop conditions. Two fired.

- **Does an active artifact already authorize the wiring?** No. `governance/decisions/` contains
  one file mentioning a composition root — `KHEPRI-DEC-021` — and it is `state: retired`
  (`registry.yaml:137`, superseded by `KHEPRI-DEC-023`), and its usage concerns Docker roles for
  the RRA web and worker images, not this binding. No `RCA-009` or `RRA-015` row exists.
- **Are multiple materially different owner product decisions required?** Yes — §5 and §6.

The blocker is therefore real, unresolved, and **not** resolvable by a plan.

## 5. Owner decision one: which artifact shape

Three shapes are admissible. Each is a different reading of the same boundary, and the choice
determines what a future slice may touch. **No recommendation is recorded here.**

| Shape | What it says | What it costs |
|---|---|---|
| **A. Amend `RCA-007`** | Widen its §Scope so the adapter may compose a two-population bundle. | Smallest diff. Grows the file's single authority rather than splitting it — but `RCA-007`'s §Composition flow describes a one-package rebuild, so the amendment must restate that flow, not append to it. |
| **B. A new `RCA-009` successor** | A fresh specification claiming the two-population composition, superseding `RCA-007`'s claim on that one file. | Cleanest boundary, matching what `RCA-008`:84 anticipated ("a successor can state cleanly"). Costs a new registry row, and a specification row must depend on exactly one family — which is itself decision two. |
| **C. A `KHEPRI-DEC-*` re-reading** | A decision that re-reads the construction boundary, leaving both specifications' text intact. | Touches no specification. But a decision that grants file-level implementation authority is a shape this repository has not used for a composition root, and it leaves `RCA-008` precondition 2 to be read against it rather than amended. |

**`D1-01` §9 recommended admitting the cross-version binding under the D1 authority, and `RCA-008`
declined it.** That recommendation is spent; it is not a standing recommendation for shape A.

## 6. Owner decision two: does M4 wait

`RCA-008`:88-90 puts this plainly: *"A successor composition artifact is a precondition for that
surface, and the owner's alternative is to accept a D1 milestone without it."*

M4's requirement is "compare governed periods." D1 alone does not satisfy it. The two branches:

- **Author the successor**, and M4 waits on one more specification plus one implementation slice.
- **Accept M4 without Compare**, and the surface stays held open under `FR-170` indefinitely.

Authoring the artifact silently elects the first. That is why this brief stops here.

## 7. What the future slice would owe

Recorded so the chosen artifact can name verification rather than invent it. This is not a plan and
authorizes nothing.

- **The `FR-170` removal condition, quoted** (`RCA-008`:144-147): the assertion *"is removed by the
  slice that makes its source reachable — not by the slice that ships the surface."* So the slice
  that binds the source is the same slice that removes the assertion, and neither happens alone.
- **The assertions that must flip**, found by sweeping for `FR-170` rather than from a note:
  `tests/test_d103_metric_card.py:216-234`, `tests/test_d104_breakdowns_and_limits.py:647`,
  `tests/d109_support.py:83`, and the comments at `rca/workspace/decision/seam.py:89`,
  `rca/workspace/decision/card.py:13`, `runtime/shell_controls.py:68`,
  `runtime/shell_decisions.py:23`.
- **A reachability test that can fail.** A view that returns `ViewRefusal('incompatible source
  shape')` and a view that returns an empty projection are different outcomes; the test must
  distinguish them, or it reports `NOT EXERCISED` as a pass — the trap `SV1-08` recorded.
- **`shell_controls.py:68`'s "seven and not eight"** becomes eight, and its count is an extent
  assertion that must move with the binding.
- **No new persistence, migration, cache or materialization.** `FR-144` makes any caching,
  pre-aggregation, materialized view or sampling on the acquisition path a governed change.
- **Bilingual parity** (`FR-171`) and the existing isolation tests apply unchanged.

## 8. What this brief does not do

No registry row is added; no specification is edited; no roadmap row is flipped; no product code
changes. A `docs/` brief requires none of those, and adding a registry row would pre-empt decision
two — a specification row must depend on exactly one family, which is the RRA/RCA split the owner
has not made.

---

**The one-sentence version.** `PeriodComparisonView` is published and unreachable because the
composition root that would bind it belongs to `RCA-007` while the surface belongs to `RCA-008`,
and neither may claim the join — so the next move is an owner-authored successor, or an explicit
decision that M4 ships without Compare.
