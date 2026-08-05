# Cross-repository platform planning package

**Status: planning-only drafts. Nothing here is a governed artifact.**

This package answers the assignment in §18 of
`kemetra-analytics-platform-master-roadmap.md` (owner-supplied, 2026-08-05). It approves
nothing, records no approval, creates no authority, allocates no identifier, and authorizes
no implementation.

## Base commits reconciled

| Repository | Branch | Commit | Date |
|---|---|---|---|
| `Kemetra/Khepri` | `main` | `c7d78b223e24b655c53309266cfac4688c4d8ce8` | 2026-08-04 |
| `Kemetra/Seshat-BI` | `main` | `157ef43e0449a68d1488db0fc967f55b77e77ad5` | 2026-08-04 |

Both working trees were clean at inspection. Every claim in this package is anchored to a
file path or a registry entry at those two commits.

## Owner direction given in session, 2026-08-05 — not traceable evidence

> **These are planning inputs, not cleared gates.** The owner selected each of these in a working
> session. **That selection is not recorded anywhere in this repository** — there is no issue
> comment, approval package, registry entry, or approval reference behind any row below.
>
> `AGENTS.md` is explicit: *"Do not claim or record human approval unless the named authority
> supplied explicit, traceable evidence."* Constitution II reserves approval to a named authority
> and Constitution V fails closed on ambiguous authority. **A reader must therefore treat every
> row as an unresolved input**, and any artifact that depends on one must obtain its own
> traceable approval rather than citing this table.
>
> Each row states the direction taken so the reasoning in this package is legible. None of them
> approves anything, and none may be cited as evidence that a gate is cleared.

| # | Question | Direction taken | What it shapes |
|---|---|---|---|
| 1 | Seshat integration in the first release? | **Define the boundary now, defer the integration** | `[DEC-BOUNDARY]` and the Seshat boundary decision proceed. Waves 3–6 (contract package, headless facade, adapter, consumer) are **deferred past Milestones A and B**. |
| 2 | Contract distribution | **Committed files; no package** | Five source-of-truth rules replace the package pin — Seshat owns the canonical schemas, Khepri consumes a pinned copy or projection, version and digest recorded, drift tests fail closed, fixtures demonstrate but do not define. See `[DEC-BOUNDARY]` §2a. |
| 3 | Renderer duplication | **Two renderers, two products — closed** | Neither removed, neither imports the other, neither may be ported again. One enforced rule: **neither may acquire arithmetic.** |
| 4 | Report layer home | **`[SPEC-REPORT]` under the existing RRA family** | Not blocked behind the commercial-family charter. The only buyer-visible phase moves on the faster gate. |
| 5 | `KHEPRI-DEC-012` | **Amend now, while `proposed`, then accept** | Reverses roadmap §10 Phase 0's ordering. An edit to a draft, not a supersession. |
| 6 | `AGENTS.md` Seshat ambiguity | **Qualify to Seshat-Platform**, in the `[DEC-BOUNDARY]` package | Leaves no reading under which the 2026-08-03 Seshat port is a standing violation. |
| 7 | Deployment gate | **Phase 0 item 0 — accept `KHEPRI-DEC-008` first** | Accepting costs nothing; it authorizes no provisioning. It gates real-customer data, beta launch, production claims, and external demonstration — **not** documentation, the golden sample, `[SPEC-REPORT]`, or synthetic-fixture implementation. |

**Two further questions were resolved by inspection rather than by direction**, and these *are*
evidenced — each is a fact about the repository that any reader can re-derive:

- **`RRA.md` is digest-pinned** by `APP-002` as `sha256:8a1235a0d6…`, and the file hashes to
  exactly that today. The commercial re-scope of `RRA.md` is therefore a **renewal approval package**, not an edit.
- **The `APP-009` gap is intentional and traced.** Created at `c00c098` for `KHEPRI-DEC-009`,
  withdrawn at `f38ee8f` when DEC-009 was rejected. Nothing to reconcile.

## Read in this order

| # | Document | Answers |
|---|---|---|
| 1 | [`current-state-delta.md`](current-state-delta.md) | What is already built, partial, duplicated, missing, blocked, or contradicted |
| 2 | [`cross-repository-ownership-matrix.md`](cross-repository-ownership-matrix.md) | Which repository owns each capability, and where today's state disagrees |
| 3 | [`khepri-seshat-target-architecture.md`](khepri-seshat-target-architecture.md) | The boundary, the dependency direction, and the seven seams it needs |
| 4 | [`cross-repository-pr-sequence.md`](cross-repository-pr-sequence.md) | PR split (R1a / R1b / R2 / R3), gate scope, the exact transitions each governance package would carry, validation commands, stop conditions |

### Not in this slice — do not follow these as links

The package was split so that reviewing whether an architecture read is *correct* stays separate
from reviewing whether a governance draft is *the right thing to propose*. Three groups of
documents are therefore named but **not present in this tree**, and are written as plain paths
rather than links so nothing here resolves to a 404:

| Arrives in | Path, once it lands | Contents |
|---|---|---|
| **R1b** | `docs/platform/proposed-governance/` | `README.md`, `identifier-survey.md`, `KHEPRI-DEC-012-amendment.md`, `decision-draft-seshat-boundary.md`, `family-charter-draft-commercial.md` — drafts named by placeholder, each with the registry *shape* it would need |
| **R3** | `docs/reporting/golden-sample-plan.md` | Phase 1 plan against the design package that already exists, plus the G5 commercial-validation gate |
| **R2** | `Kemetra/Seshat-BI` · `docs/architecture/` | `headless-analysis-engine.md`, `khepri-consumer-boundary.md`, `analysis-evidence-contracts.md` |

Prose elsewhere in this package refers to those documents by name. Until their PRs land, treat
every such reference as a forward reference, not a navigable link.

## Why no file was written under `governance/`

Constitution I makes the YAML registries authoritative for identity and states that
explanatory documents cannot override them. A Markdown file sitting in
`governance/decisions/` with no registry entry has no governed identity, and
`khepri-gov validate` performs no orphan-document scan (`src/khepri_gov/validator.py` has
no `rglob` over the governance tree), so such a file would pass validation while carrying
the visual authority of a governed record. That is the drift Constitution I exists to stop.

Every governance draft therefore lives under `proposed-governance/` and states its intended
target path plus the exact registry block it would need. Promoting a draft is one move by the
owner, and until that move nothing in `governance/` has changed.

`uv run khepri-gov validate` passes at this commit and is unaffected by this package.

## What this package deliberately does not do

- No product code, in either repository.
- No implementation task breakdown. §18 stops before it, and so does this.
- No registry edit, no approval package, no lifecycle transition, no identifier allocated.
- No approval of `[SPEC-REPORT]`, and no product code.
- No `/speckit.specify` run. §13 places that after the boundary decision is approved.
- No commit, push, branch, or pull request.
