# Feature roadmap — brainstorm and sequencing

Date: 2026-08-02

Authority: none. This document proposes; it approves nothing and changes no registry. Every
candidate below would need its own specification or family artifact and its own approval.

## Why this document exists

Two chains are currently blocked, and both blockages are governance rather than engineering:
`RRA-008` waits on approval evidence for `APP-006`, and `KHEPRI-DEC-008` cannot be materialized at
all. Meanwhile the useful question is what comes *after* those, and in what order, so that work is
queued rather than invented under time pressure.

Seven candidates are assessed. One is recommended to go first, and the reasoning is that it is the
only one that unblocks something else.

## The deadlock worth naming first

`KHEPRI-DEC-008` supersedes `KHEPRI-DEC-005` and `KHEPRI-DEC-007`. Its approval package cannot
express that. `INITIAL_TRANSITIONS["decisions"]` in `src/khepri_gov/approval_packages.py` admits
only `("proposed", "accepted")`, and the only other branch requires `from_state == to_state`, so an
`accepted -> superseded` entry is rejected as an unsupported transition.

`KHEPRI-DEC-008` records fixing this as one of its own follow-on obligations — which is circular.
The obligation cannot be discharged under the authority of a decision that cannot be approved until
the obligation is discharged.

The way out is that this is not a runtime concern at all. `FND` already owns "stable artifact
identifiers and lifecycle vocabularies" and "fail-closed validation and its evidence". Supersession
is a lifecycle transition, so it belongs to the foundation family and can carry its own authority,
independent of anything about AWS or DigitalOcean. That is candidate A, and it is the recommendation.

## Candidates

### A. FND-002 — Governed lifecycle transitions · **recommended first**

Teach approval packages and the validator the transitions the registries already define but no
package can perform: `accepted -> superseded` for decisions, `approved -> retired` for
specifications, `active -> retired` for families. Add `superseded_by` to the decisions registry and
validate the linkage rather than leaving it in prose.

Small, entirely inside `src/khepri_gov/`, no product surface, and the only candidate here that
unblocks another. Without it the whole runtime pivot stays parked no matter how carefully
`KHEPRI-DEC-008` is reviewed.

The risk to respect: this is the governance kernel. A permissive transition table would let a future
package quietly retire something. The specification should enumerate a closed set of legal
transitions and require every non-initial one to cite the approval it supersedes, which the package
schema already supports per artifact.

### B. RRA-009 — Multi-dimension breakdowns

Deferred out of `RRA-008` deliberately. Crossing category with store answers real questions — which
categories underperform in which stores — that no single-dimension comparison can.

The reason it was deferred is a genuine design problem, not squeamishness. `RRA-004` caps
comparisons at 20 buckets with an `other` aggregate; a naive crossing produces up to 400 cells, and
truncating a crossed set is far more misleading than truncating a flat one, because the reader
cannot see which axis was cut. It needs a governed rule for which cells survive and how the
remainder is disclosed, and that rule deserves its own design pass.

Medium size. Depends on `RRA-008` being approved and implemented, since it reuses the concentration
machinery.

### C. RRA-010 — Data quality disclosure

`RRA-003` already computes profile and quality findings — null rates, distinctness, parse-quality,
date coverage — and `RRA-002` already governs what may not be exposed. What no approved
specification settles is whether those findings reach the report surface, and in what form.

The value is trust rather than analysis: a retailer who sees "8% of rows had no store attributed,
and those rows are excluded from the store comparison" believes the store comparison more, not less.
It also closes a gap where a caveat exists in the fact package but has nowhere to be seen.

Small to medium. Needs a check first: confirm what the bundle surfaces today before specifying, so
the specification records a change rather than restating existing behaviour.

### D. New family — governed connectors

Ingest beyond an uploaded CSV or XLSX: point-of-sale exports, e-commerce platforms, accounting
systems. A connector's output would be exactly the governed upload `RRA-002` already accepts, so the
whole downstream chain is untouched.

The cleanest boundary of any candidate here, and the largest genuine product expansion. It is also
the one that most changes the privacy surface: a connector holds credentials to a live system, which
is a different trust conversation from a file a client chose to upload. That belongs in a family
document, not smuggled into a specification.

Large. Independent of everything else.

### E. New family — scheduled and delivered reports

Recurring runs and delivery to email or messaging. `RRA` excludes scheduling explicitly.

Interacts awkwardly with the retention model, and that interaction is the whole design: a scheduled
report implies keeping something for the next run, while `RRA-002` promises seven-day expiry and
immediate deletion on request. Either the schedule regenerates from nothing each time, or the
retention promise changes. Worth doing only after that is decided.

Medium. Depends on nothing technically, on a retention decision entirely.

### F. New family — commercial tenancy

Authentication, organizations, workspaces, membership, billing, public signup. `KHEPRI-DEC-003` and
`KHEPRI-DEC-005` exclude all of it from the private beta.

This is what the commercial phase actually requires, and it is the largest and most cross-cutting
item on the list. It touches session ownership, which `RRA-001` currently defines as invite-bound
and pseudonymous, so it cannot be added without amending an approved specification.

Large. Should follow beta evidence rather than precede it: designing multi-tenancy before a single
tenant has run a report is how the wrong abstractions get approved.

### G. Benchmark descriptors and the certify rework

Not a new feature — the remaining obligation `KHEPRI-DEC-006` records. The population and row
generators exist; what is missing is the two descriptors and the repair of the digest comparison,
which `KHEPRI-DEC-006` itself documents as currently incompatible with the approved population.

Blocked on the target-selection artifact, because the environment descriptor cannot be written
before a provider and region exist. The workload half could proceed sooner.

## Recommended sequence

```
A. FND-002 lifecycle transitions        <- unblocks KHEPRI-DEC-008
   └─ KHEPRI-DEC-008 materialization
      └─ target-selection artifact
         └─ G. descriptors + certify rework
            └─ benchmark run
               └─ beta authorization

RRA-008 implementation                  <- parallel, needs only APP-006 approval
   └─ C. RRA-010 quality disclosure
   └─ B. RRA-009 multi-dimension breakdowns

D. connectors family                    <- independent, start whenever
E. scheduling family                    <- after a retention decision
F. commercial tenancy                   <- after beta evidence
```

The left column is the launch path and the right column is product value, and they do not block each
other. That separation is the point: no product work should ever be waiting on the provider
question, and none of it currently is.

## What was considered and not proposed

**Forecasting and customer-defined metrics.** Both would require amending `RRA-004`'s explicit
prohibition and the `RRA` family's `Excludes` list before any code. Customer formulas additionally
contradict the one-source-of-numbers model, since a customer formula produces a numerical claim the
fact package did not compute and cannot reconcile. Neither is ruled out forever; both need a
decision, not a specification.

**Cohort and repeat-purchase analysis.** Permanently out, and `RRA-008` already records it as such.
The governed mapping carries no customer identifier because `RRA-003` requires likely personal-data
columns to be detected and excluded. This is a consequence of the privacy model rather than a gap.

**A dashboard or interactive exploration surface.** `KHEPRI-DEC-005` rejected a second runtime and
an SPA for the private beta, and nothing observed since changes that reasoning.
