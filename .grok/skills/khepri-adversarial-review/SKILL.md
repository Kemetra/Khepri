---
name: khepri-adversarial-review
description: Use when the user asks for adversarial review, red-team, independent review, pressure-test, grill, second opinion, or IN_REVIEW on a Khepri slice, PR, program, plan, spec, decision, product claim, the whole project, all of Khepri, or the entire repo; also before merge, before declaring a slice done, when a reading of an active artifact is unsettled, or when the user runs /khepri-adversarial-review. Not a substitute for ordinary code review, CodeScene, pytest, or khepri-gov.
user-invocable: true
argument-hint: "[slice|program|product] [target]"
---

# Khepri Adversarial Review

Independent judge of claims against Khepri governing artifacts. The judge never edits. Green tests, CodeScene, ruff, and `khepri-gov` are evidence the judge may cite; they are not the verdict.

**REQUIRED BACKGROUND:** `external-reviewer` (fresh context, raw artifact, judge-never-edits). This skill adds the Khepri contract. Do not skip it in favor of generic review.

## When not to use

- Lint, types, Code Health, or "does this test pass" — run those gates; do not invoke this.
- The user wants fixes applied — this skill stops at the verdict.
- No claim exists yet — use `socrat` to grill, then return here once there is an artifact.

## Layer (exactly one per run)

| Layer | Question | Inspect |
|---|---|---|
| `slice` | Did this PR/slice stay inside its spec, and is the evidence real? | diff, slice plan, named FRs, tests that claim those FRs, spec §Scope |
| `program` | Do successive slices still agree with the allocation and the active spec? | allocation plan, later slice plans, registry row, contradictions |
| `product` | Does a product/constitution claim hold against shipped artifacts? | `governance/CONSTITUTION.md`, `governance/registry.yaml`, `PRODUCT.md`, active specs named in the claim |

If the user says "the project", "all of Khepri", "the whole repo", or "everything", the layer is `product`. Do not loop every slice. Do not ask slice vs program vs product.

If the user did not name a layer and the target is a named slice or PR, pick `slice`. Mixing layers in one verdict is a defect. A product run is one verdict against the load-bearing product claims, sampled across shipped families — not a concatenation of every slice review.

## Invariants

1. **Fresh context.** Dispatch a general-purpose subagent that did not build the work. The current session authors no verdict if it implemented, planned, or defended the target.
2. **Raw artifact.** Paths, diffs, spec sections, registry rows, rejected alternatives. No flattering summary.
3. **Registry over prose.** `governance/registry.yaml` wins. Markdown cannot grant what the registry does not.
4. **Default fail.** Uncertain → `REVISE` or `REJECT`. `APPROVE` requires evidence for every named claim.
5. **Judge never edits.** Relay the verdict. Stop. Apply nothing until the owner says so.

## Steps

1. Name **layer**, **target**, **base** (the ref the diff is taken against, `n/a` when the target is not code), and **1–3 claims** to stress-test (the author's strongest claims, stated plainly).
2. Resolve governing artifacts from the registry (spec/decision identity + `active`/`retired`). A claim with no active artifact is already a finding.
3. For `slice` only, run deterministic gates as *evidence* (`uv run khepri-gov validate`, `uv run ruff check .`, targeted pytest). Do not treat their passing as `APPROVE`. Ordinary code review (`/review` or CodeRabbit) may run first; it does not replace this skill.
4. Dispatch the judge with [references/judge-prompt.md](references/judge-prompt.md). Fill every bracket. Do not paraphrase the rubric. Isolation is the current worktree (`none`) — the judge must see the real files. Prefer a model that did not author the work.
5. Relay the verdict in full. If you disagree with a finding, say so *beside* it — do not drop it.
6. **Stop.**

Optional second isolated judge, same prompt (santa-method), only for auth, tenancy, retention, metric meaning, or money. Both must pass or the verdict is `REVISE`.

## Rubric

Every claim is `PASS` only if all of these hold. A single miss is a finding.

1. **Grant.** An *active* artifact (spec FR, decision clause, constitution article) grants the behavior. "It seemed implied" is `REJECT`.
2. **Slice bound.** Product code stays inside the named spec's §Scope and the slice's allocation. Widening spec, privacy, runtime, or data use is `REJECT` until the owner merges a new artifact.
3. **Evidence can fail.** A test that cannot fail the claimed way (wrong question, fake that hides the defect, assertion that would also pass the bug) is not evidence. Mutation-green is not meaning-correct.
4. **Fail closed.** Ambiguous identity, org, state, dependency, scope, privacy, or runtime is refused, not inferred. No fallback, partial projection, nearby substitution, or unfiltered widen.
5. **One definition.** Two surfaces, metrics, versions, or stores for one fact is a defect. `Kemetra/Seshat-Platform` is reference; copying its catalogs, specs, or application code is a defect.
6. **Owner items.** An unsettled reading is raised, not decided by the implementer. A surface that computes (sums, rates, ranks, thresholds) is a defect where the spec forbids it.

## Rationalizations

| Excuse | Reality |
|---|---|
| "I'll review it myself, I know the slice" | Builder context is the failure mode. Dispatch. |
| "Tests are green" | Under-refusals and wrong-question guards were green. Inspect whether the test can fail the claim. |
| "CodeScene is 10.00" | Required PR gate, different question. |
| "The plan said this was out of scope" | Inspect the built route/image, not the plan's claim. |
| "Close enough to the spec" | Spec text is the bound. Close is widen. |
| "I'll fix while I review" | Judge never edits. |
| "Summary is easier for the judge" | Summary review is rubber-stamp. |
| "Layer doesn't matter" | Mixed layers hide the miss. Pick one. |

## Red flags — stop and restart the review

- Verdict written by the implementing session
- Judge given a digest instead of paths
- `APPROVE` while any named claim is uninspected
- Fixes applied before the owner answers the verdict
- `governance/` edited inside a product slice "to make the review pass"
