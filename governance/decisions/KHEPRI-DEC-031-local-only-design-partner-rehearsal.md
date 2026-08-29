# KHEPRI-DEC-031: Local-only M2 rehearsal, and the two clauses it leaves unmet

> Active when merged to `main`.

## Context

`CAL1` completed at `#330` (`f320c17`) and `#332` (`f7bf2d3`). The calculation contract is stable,
which satisfies the first of `M2`'s five acceptance clauses and unblocks the `T1` catalog work the
third and fourth depend on.

Two of the remaining clauses cannot be satisfied on the current path, and for entirely different
reasons. This decision records which, why, and what each would take — so that a later reader can tell
a milestone genuinely reached from one whose gaps were quietly waived.

**The owner has decided not to provision the DigitalOcean environment for now.** Work continues on
the merged production-like local stack. `KHEPRI-DEC-030` supplies the authority to provision a
provisional non-production bootstrap; that authority is simply not being exercised. Nothing about it
is wrong, so nothing about it needs superseding — which is why this decision supersedes nothing and
carries every one of `KHEPRI-DEC-030`'s gates forward untouched.

Separately, `R8-08`'s activation telemetry turns out not to be unscoped work awaiting a specification.
It is work that **conflicts with an active decision.** `KHEPRI-DEC-015` forbids using retained
commercial identity data for product analytics, and `R8-08`'s event chain begins at invite and
authentication. Active `RRA-010` excludes "any new data collection, field, telemetry event, or
persistence", and active `RCA-003` excludes "new telemetry, cookies, advertising". The only active
telemetry authority, `RRA-007` under `KHEPRI-DEC-028`, is an eleven-stage operational pipeline
vocabulary that structurally cannot carry an activation event. Authorizing `R8-08` therefore requires
amending an active decision rather than writing a new specification, and that is the owner's to
author.

### Why this is one decision rather than two

The local-only choice and the telemetry conflict are unrelated in subject and identical in
consequence: each leaves one `M2` clause unmet, and each would otherwise be discovered later as a
surprise. A single decision that names both keeps `M2`'s standing readable in one place. Splitting
them would leave a reader checking two artifacts to learn what "M2 complete" currently means.

## Decision

### 1. `M2`'s staging clause splits, and its local half is met

`M2` requires a full journey passing "in production-like local staging **and** an owner-approved
non-production hosted environment before external use". The local half is met: `CAL1-14` proved the
journey end to end against the merged PostgreSQL and MinIO stack — upload, admission, facts, worker,
HTML, PDF, Excel, and evidence in both languages, with restart, retry, and recovery — and that
evidence merged at `#330` (`f320c17`).

The hosted half remains unmet and stays gated on `KHEPRI-DEC-030` §6.

`M2` is therefore reachable in a **local-only form**: an internal rehearsal, on the local stack, with
no external participant. It is not the whole of `M2` as written, and this decision does not pretend
otherwise.

### 2. External alpha is deferred, not cancelled

No design partner, prospective customer, or other external participant may receive access, a report,
an artifact, or a link under this decision. The phrase "before external use" in `M2`'s clause is the
operative bound: local rehearsal is internal by definition, and the moment a participant outside the
project is involved, the hosted half of the clause governs again.

External alpha remains blocked until `KHEPRI-DEC-030` §6's sequence completes and the private-beta
authorization it names is merged.

### 3. `KHEPRI-DEC-030` is unaffected and unexercised

Nothing here narrows, widens, discharges, or reinterprets any gate in `KHEPRI-DEC-030`. Its
provisioning authority remains available and simply is not being used. Its bars on paid resources
beyond the provisional shape, on beta traffic, and on spend commitment remain fully binding.

This decision takes no position on hosted readiness. It records only which `M2` clauses local
evidence satisfies.

### 4. Hosted-dependent tasks are deferred past `M2`

`OPS1-02`, `OPS1-03`, `OPS1-04`, `OPS1-05`, `OPS1-09`, and `R8-11` are deferred. Each remains a
precondition of external alpha under `KHEPRI-DEC-030` and the roadmap's `OPS1` table, and none is
required for the local-only rehearsal this decision defines.

Deferral is not cancellation and not a judgement about their difficulty. `OPS1-01` is done and
`OPS1-02` is unblocked; the work is authorized and simply not scheduled.

### 5. `R8-08` is blocked by active governance, not merely unscoped

`R8-08` may not begin. It requires an owner-authored amendment to `KHEPRI-DEC-015`, or a superseding
decision, before any implementation task for it exists.

The distinction from §4 is deliberate and material. The `OPS1` items are deferred: authorized, simply
not scheduled. `R8-08` is **blocked**: an active decision forbids the data use it needs. Recording
both as "deferred" would hide that one resumes by scheduling it and the other cannot resume at all
until governance changes.

Until that amendment merges, `M2`'s clause "activation telemetry exists" is **unmet by design**, on
the same footing as the hosted-environment clause. No task in any program may close it by building a
new telemetry event, and no specification may authorize an exception to `KHEPRI-DEC-015` without
amending it.

`T1-07`'s trust telemetry is blocked by the same constraint and resumes under the same amendment.

### 6. `T1`'s scope for the local-only `M2` minimum

`RRA-011` is the receiving authority for the metric, population, and reason catalog. Its `M2` minimum
is `T1-01` through `T1-05` and `T1-08`, together with closure of the wording-table completeness gaps
`CAL1-11` filed as finding `F5` under `RRA-009`.

`T1-06` lineage and `T1-07` trust telemetry are excluded from the `M2` minimum. The roadmap already
permits both to complete during early `M3`; `T1-07` additionally waits on §5's amendment.

### 7. When local-only `M2` is complete

The local-only rehearsal is complete when all of the following hold:

1. `RRA-011`'s catalog and evidence surfaces are merged to `main` and pass `T1-08`'s parity,
   fail-closed, and no-duplicate-truth tests.
2. `CAL1` remains complete, with its two carried `P2` findings still non-blocking.
3. The journey and shell entry points render without widening `RRA-010` or `RCA-002`.
4. The full journey passes end to end on the local stack against the merged catalog surfaces, in both
   languages.

No hosted environment and no external participant are required. When those four hold, `M2` is
recorded as reached **in its local-only form**, with its hosted-environment and activation-telemetry
clauses recorded as unmet rather than checked.

## Alternatives not selected

**Superseding `KHEPRI-DEC-030`** was not selected. It is unexercised rather than wrong. Supersession
would imply its hosted-readiness content was defective and would orphan gates that remain binding for
everything past local rehearsal.

**Marking `M2` complete without naming the unmet clauses** was not selected. It would leave a later
reader unable to distinguish a milestone genuinely reached from one where two clauses were waived in
silence — and `M2` gates external customer contact, which is exactly the wrong place for that
ambiguity.

**Recording `R8-08` as deferred alongside the `OPS1` items** was not selected, for the reason §5
states: they are blocked on scheduling, it is blocked on an active prohibition.

**Amending `KHEPRI-DEC-015` here, to unblock `R8-08` in the same decision**, was not selected. That
amendment is a purpose-limitation change on retained identity data — a privacy decision on its own
merits, deserving its own artifact and its own deliberation, not a clause folded into a scheduling
decision.

## Consequences

- `M2` is reachable with no cloud spend and no external participant.
- `M2` carries two explicitly unmet clauses. The roadmap's milestone row must show them rather than
  presenting `M2` as wholly met, or the roadmap contradicts this decision on the day it merges.
- `KHEPRI-DEC-030`'s gates remain binding for anything beyond local rehearsal. Nothing here is a
  shortcut around them.
- `R8-08` and `T1-07` cannot resume until a separate owner-authored decision amends
  `KHEPRI-DEC-015`'s product-analytics prohibition. This decision creates that prerequisite
  explicitly so it is not rediscovered later as a surprise blocker.
- `RRA-011` becomes the governing authority for `T1-01` through `T1-05` and `T1-08`, and the `T1`
  program moves from `PROPOSED` to `READY_FOR_PLAN`.

## Evidence

- `KHEPRI-DEC-015`: active retention and purpose-limitation decision whose product-analytics
  prohibition blocks `R8-08` and `T1-07`.
- `KHEPRI-DEC-028`, `KHEPRI-DEC-029`, `KHEPRI-DEC-030`: active hosted-readiness architecture,
  benchmark authority, and provisional bootstrap authority, unexercised by this decision.
- `RRA-010` Exclusions and `RCA-003` Exclusions: active specifications each excluding new telemetry
  events under their own authority.
- `RRA-007` and `KHEPRI-DEC-028`: the active operational telemetry vocabulary, whose eleven pipeline
  stages structurally cannot carry an activation event.
- `#330` (`f320c17`): `CAL1-12` through `CAL1-15`, including `CAL1-14`'s local staging evidence.
- `#332` (`f7bf2d3`): the `CAL1` roadmap reconciliation.
- `docs/superpowers/plans/2026-08-29-cal1-11-compatibility-sweep-ledger.md`: finding `F5`, filed
  under `RRA-009`.

Identity, lifecycle state, dependencies, and supersession are authoritative in
`governance/registry.yaml`. Git history retains the transition evidence.
