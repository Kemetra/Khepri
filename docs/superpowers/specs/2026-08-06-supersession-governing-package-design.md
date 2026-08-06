# Making supersession possible: the governing-package model — design

Date: 2026-08-06

Authority: none. This designs a change to `src/khepri_gov`, the governance tooling. It proposes no
governed artifact, amends no specification, and grants no approval. The behaviour it describes is
already asserted by a strict `xfail` merged in #108, so this design is a route to an existing test
rather than a new requirement.

## Outcome

`khepri-gov validate` accepts a repository in which an artifact has been superseded after a prior
approval was renewed. The strict `xfail` marker on
`tests/test_approval_packages.py::test_approved_renewal_survives_a_later_supersession` is removed,
not relaxed, and no currently-valid repository becomes invalid.

## The defect, precisely

`validate_approval_packages` (`approval_packages.py:379-383`) iterates
`sorted(approval_dir.glob("APP-*.yaml"))` and validates **every** package against the **current**
registry on every run. Nothing in the code distinguishes *this package governs the artifact now*
from *this package is history*.

Four checks each read the live registry, and each therefore treats every approved package as though
it were the current one:

| Error | Source |
|---|---|
| `<APP>: <ID> approved_at does not match package` | `_approval_field_errors`, `approval_transition_validation.py:311-330` |
| `<APP>: <ID> approval_ref must be <this package>` | `_approval_ref_errors`, `approval_transition_validation.py:213-218` |
| `<APP>: renewal must preserve state '<current>'` | `_preserves_state`, `approval_renewals.py:148-155` |
| `<APP>: <ID> does not currently use the superseded approval` | `_current_evidence_errors`, `approval_renewals.py:178-187` |

**Checks 2 and 4 cannot both be satisfied.** Check 2 requires the registry to still name the older
package; check 4 requires it to name the newer one. Supersession is exactly the situation where two
approved packages name one artifact, so no arrangement of correct files passes. That is what makes
this structural rather than a matter of authoring a package correctly.

This is not hypothetical. `KHEPRI-DEC-005` was renewed by `APP-013`, so `KHEPRI-DEC-008` cannot be
accepted while it supersedes DEC-005. The one edit that would clear it is rewriting `APP-013`, and
Constitution VI forbids that: supersession is explicit and never rewrites prior authority.

## The invariant this design states

> An approved package is an immutable historical record. The registry is the present. Exactly one
> approved package governs each artifact now.

A package **governs** an artifact when the registry entry for that artifact carries an
`approval_ref` equal to that package's own reference. Everything else follows from separating the
two questions the current code conflates: *is this package internally sound and lifecycle-legal*
(asked of every package, forever) versus *does the registry agree with this package* (asked only of
the governing one).

## What is already half-built

`_approval_is_carried_over` (`approval_transition_validation.py:202-210`) already asks
`ApprovedPackageIndex.has_successor(..., replaces_approval=True)`. The concept of a later package
taking over an artifact exists.

It fails here for one reason. `_replacement_matches` (`:96-104`) computes
`replaces = not ends_authority(ref.registry, str(entry.get("to_state")))`. A superseding package
moves the artifact to `superseded`, which **does** end authority, so `replaces` is `False`, the
successor is refused as a replacement, and check 2 fires. The fix extends this existing index; it
does not introduce a new mechanism.

## The design

### 1. A single governing predicate

Add one predicate to `ApprovedPackageIndex` (or beside it): given the registry artifact and a
package reference, does that reference equal the artifact's recorded `approval_ref`. Checks that
compare a package to the live registry consult it first.

### 2. Registry-agreement checks become governing-only

`_approval_field_errors` (check 1) and `_approval_ref_errors` (check 2) run only when the package
governs the artifact. For a historical package they are skipped, because the registry has
legitimately moved on and the package is a record of what was true, not a claim about now.

### 3. Renewal state preservation splits by role

`_preserves_state` (check 3) currently compares the package's `from_state` against
`artifact.get("state")` — the live value. Split it:

- **Governing package:** keep today's behaviour unchanged.
- **Historical package:** check lifecycle *legality* rather than agreement. A declared transition
  where `from_state != to_state` must be an edge in `LIFECYCLE_TRANSITIONS[registry]`, which the
  code already checks. A renewal, where `from_state == to_state`, must name a state in that
  registry's vocabulary. Nothing is compared to the present.

### 4. The prior-reference check loses its live read

`_requires_prior_ref` (`approval_renewals.py:189-193`) returns `True` when the package is
`proposed` **or** when its `to_state` ends authority. The second branch is what fires for an
approved superseding package, and it is the half that contradicts check 2.

Keep the `proposed` branch — a package that has not yet been recorded *should* find the registry
still pointing at the approval it supersedes, because the flip has not happened. Drop the
`ends_authority` branch. `_prior_package_errors` already verifies the substantive part: that
`supersedes_approval_ref` names an approved package containing the artifact. That check reads
packages, not the registry, and stays exactly as it is.

### 5. The positive check that replaces what was relaxed

**This is the part that must not be omitted.** Relaxing four checks would otherwise open a hole in
which an artifact's registry row agrees with no package at all.

Add one invariant, asserted per artifact rather than per package: for every artifact carrying an
`approval_ref`, **exactly one** approved package must name that reference, contain that artifact,
and record a `to_state` equal to the artifact's registry `state`.

This is strictly stronger than the current code for the governing package: today nothing verifies
that the governing package's recorded `to_state` matches the registry state, because each package
only checks itself. Four scattered per-package assumptions become one stated per-artifact rule.

## Out of scope

**Full chain reachability.** A stronger design would reconstruct each artifact's state path across
the `supersedes_approval_ref` chain and require it to reach the registry's current state. Packages
carry links but no ordering, so reconstructing the path is its own slice with its own failure modes.
Recorded here so the omission is deliberate rather than overlooked.

**The six accepted decisions carrying a false closing sentence.** Unrelated to this defect, already
recorded, and each needs its own renewal package.

**Any registry or artifact transition.** This slice changes validation logic and tests only. It
performs no transition and unblocks G-a rather than executing it.

## Verification

The merged `xfail` is the acceptance test. Beyond it:

- The marker is **removed**, not weakened. An `xfail` that merely stops being `strict` is a failed
  fix, and the suite must move from `1 xfailed` to `0 xfailed` with the pass count up by one.
- A negative test per relaxed check, proving the relaxation did not become permissive: an artifact
  whose `approval_ref` names no package; one whose governing package omits it; one whose governing
  package records a `to_state` disagreeing with the registry; and two approved packages both
  claiming to govern the same artifact.
- A historical package declaring an illegal lifecycle edge still fails.
- The existing suite passes unchanged otherwise, which is what proves no valid repository became
  invalid. Baseline: 1604 passed, 9 skipped, 1 xfailed.

## Risks

- **Permissiveness.** The whole slice moves checks from many-and-narrow to one-and-central. If the
  per-artifact invariant in §5 is wrong or incomplete, the relaxations in §2–4 have no backstop. It
  is written first and tested adversarially before the relaxations land.
- **CodeScene.** `approval_transition_validation.py` and `approval_renewals.py` are both touched,
  and every new file must score 10.00 with no tracked hotspot declining. Keep helpers small and
  constructors to two or three arguments; CI is the only authority on the threshold.
- **Scope creep into G-a.** Fixing the validator makes G-a possible; it does not make G-a correct.
  The DEC-003 condition-3 caveat still has to be carried explicitly in that supersession, and it
  belongs to that slice.
