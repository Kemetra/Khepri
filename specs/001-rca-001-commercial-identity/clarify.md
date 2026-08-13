# RCA-001 — Clarification pass

> **SUPERSEDED — historical artifact, written 2026-08-08. Do not follow these instructions.**
> This document predates the current governance model and three merged RCA-001 slices. It reasons
> from a Constitution and an approval framework that no longer exist, and its status claims are
> false: `RCA-001` is `active` and implementation is under way. Read
> [`SUPERSEDED.md`](SUPERSEDED.md) for the delta and [`STATUS.md`](STATUS.md) for what is actually
> implemented. `governance/specifications/RCA-001.md` and `governance/registry.yaml` are
> authoritative; this file is not.

Ambiguity pass over the first draft of `governance/specifications/RCA-001.md`. Every item is
resolved from repository evidence or escalated. No artificial questions were manufactured, and no
item was guessed.

**Result: 11 of 11 items resolved from repository evidence. Zero owner decisions required to
complete the specification.** Two items produce implementation preconditions rather than
specification gaps, and both are recorded in the specification and in the final report.

---

## C-1 — Account creation semantics

**Question.** Does creating an account grant any access on its own?

**Resolved: no.** `governance/families/RCA.md:5-7` separates "durable commercial identity:
accounts, credentials, sessions, and recovery" from "organizations, membership roles, and the
authorization model over them" as distinct owned concerns. Access to content is a property of
membership in an organization, not of having an account. Scenario 18 ("authenticated account with
no organization") only has meaning if account creation grants nothing.

→ `FR-001`, `FR-028`.

---

## C-2 — Is email uniqueness a product rule or an implementation assumption?

**Question.** The task asks this explicitly.

**Resolved: a product rule.** Two requirements in this specification are undefined without it.
`FR-005` recovery must identify *which* account to recover from the address supplied. `FR-019`
allows inviting a person who has no account yet, which requires that the address the invitation
names resolves to at most one account when it is eventually created. A uniqueness constraint that
two requirements depend on for their meaning is a product rule, not a storage detail.

Recorded as **A-1** in the specification rather than buried, because a reviewer may reject it —
and if they do, `FR-005` and `FR-019` must both change.

---

## C-3 — Invitation lifecycle, and may an invitation precede account creation?

**Question.** The task asks the second part explicitly.

**Resolved: yes, invitation may precede account creation.** The alternative — requiring an account
before an invitation may be issued — would mean an organization owner cannot invite anyone who has
not already signed up, and `RCA-001` excludes public self-serve signup. Those two together would
make organizations unreachable by any second person, contradicting the whole purpose of `FR-011`
and Scenario 12.

Acceptance, however, requires an authenticated account to exist at that moment, because `FR-018`
creates a membership and a membership must bind to an account.

Lifecycle resolved as: `issued → (accepted | expired | revoked)`, at most one acceptance, modelled
directly on `RRA-001`'s invitation controls — high-entropy secret, hash-only persistence, expiry,
single use, and refusal that does not disclose which check failed. `src/khepri/rra/sessions.py:114`
(`redeem`) is the existing implementation of exactly this shape, and it checks nonexistence,
prior redemption, expiry, and secret mismatch in one condition raising one message.

→ `FR-016`..`FR-020`.

---

## C-4 — Final-owner behaviour

**Question.** What happens when an operation would remove the last owner?

**Resolved: fail closed.** Constitution V ("Unknown states, owners, dependencies… block progress")
and Constitution II ("Every governed artifact has a known human owner") both point the same way.
An ownerless organization is an unadministrable one: nobody could invite, change roles, or revoke.

Resolved to cover three operations, not just removal — removal, **downgrade** to `member`, and
**disablement of the account holding the final ownership**. Removal alone is the obvious case; the
other two reach the same end state and would otherwise be bypass routes.

→ `FR-013`, Scenario 17.

---

## C-5 — Multi-organization semantics

**Question.** What does membership in several organizations mean for data scope?

**Resolved: scopes never merge.** `KHEPRI-DEC-014` §2 keeps `RRA-001`'s cross-session isolation as
a surviving control, and `governance/families/RCA.md:27-29` forbids "any weakening of the privacy,
isolation… controls that `RRA-001`, `RRA-002`, and `RRA-006` fix."

Confirmed against code: `assert_same_scope`
(`src/khepri/rra/sessions.py:168`) compares the **entire** frozen `SessionScope` by equality, so
there is no partial or union match available even in principle. A merged scope is not expressible
in the existing contract.

→ `FR-011`, `FR-035`.

---

## C-6 — Session behaviour after membership or role changes

**Question.** Must a session end for a revocation to take effect?

**Resolved: no — changes take effect on the next authorization decision.** The opposite reading
means a revoked member keeps access until their session happens to expire, which would make
Scenario 20 untestable and would contradict `FR-022`'s deny-by-default posture.

This makes authorization a decision taken per action against current membership, rather than a set
of permissions captured into the session at authentication. Recorded here because it is the single
most consequential clarification for the plan: it rules out any design that stamps roles into a
bearer token and treats that token as authoritative until expiry.

→ `FR-030`, Scenario 20; carried into `plan.md` as the constraint that forbids self-contained
authorization claims.

---

## C-7 — Disabled-account behaviour

**Question.** Does disabling an account end its existing sessions?

**Resolved: yes, immediately, without relying on expiry.** Same reasoning as C-6, and the task's
Scenario 16 names "disabled account with active session" as an adversarial security test. A
control that takes effect only at expiry is not a control.

→ `FR-008`.

---

## C-8 — Recovery semantics

**Question.** What does recovery do to existing sessions?

**Resolved: recovery invalidates all pre-existing sessions for that account.** Recovery exists for
the case where the credential may be compromised. Leaving an attacker's session alive through a
recovery the legitimate holder performed would defeat the purpose of the operation.

Single-use and expiring, hash-only persistence, and non-disclosure of account existence all follow
`RRA-001`'s established invitation-secret pattern rather than inventing a second one.

→ `FR-005`..`FR-007`.

---

## C-9 — Exact minimum powers of each role

**Question.** The task asks for "the smallest sufficient role model."

**Resolved: two roles, `owner` and `member`.**

| Action | `member` | `owner` |
|---|---|---|
| Read the organization's retail content | yes | yes |
| Upload, generate, and export reports in the organization | yes | yes |
| Delete content per `RRA-002` | yes | yes |
| Invite a person to the organization | no | yes |
| Change another member's role | no | yes |
| Revoke a membership | no | yes |

One role cannot express Scenario 10 (role change) or Scenario 17 (final-owner protection), so one
is too few. Three would require naming a power that neither of these two covers, and no scenario in
the task's list needs one — an administrator distinct from an owner, or a read-only viewer, are
both genuinely useful and both are `RCA-002` or later. `governance/families/RCA.md:32` excludes
"product implementation while this family remains proposed or its specifications remain draft",
and inventing unused roles is exactly the speculative scope Constitution IV forbids.

→ `FR-015`.

---

## C-10 — Does organization deletion belong in this specification?

**Question.** The task asks this explicitly.

**Resolved: no — excluded.** Deleting an organization destroys retail content, which engages
`RRA-002`'s governed deletion lifecycle and Constitution VII's retention rules. `KHEPRI-DEC-014`
§3 states plainly: "No retention change. Durable retention requires its own Constitution VII
decision." Deletion and retention are the same governed question seen from two sides, and this
specification is not permitted to settle it.

`RRA-002`'s immediate idempotent **content** deletion is preserved unchanged by `FR-037`. What is
excluded is deletion of the *commercial* objects — organizations and accounts.

→ Exclusions.

---

## C-11 — Which entity maps to the opaque isolation key?

**Question.** Not asked by the task, but discovered while reading the code, and it is the single
highest-risk decision in the specification.

**Resolved: the organization maps to `owner_id`, not the account.**

Evidence. `src/khepri/rra/deletion.py:149` builds the storage prefix
`owners/{job.owner_id}/sessions/{job.session_id}/`, and `SessionScope`
(`src/khepri/rra/sessions.py:38-42`) is the frozen pair `(owner_id, session_id)` compared by whole
equality.

If an **account** mapped to `owner_id`, two members of one organization would occupy different
`owners/` prefixes, `assert_same_scope` would reject every legitimate colleague access, and
shared organizational content would be unreachable — `FR-011` and Scenario 12 would be
unimplementable without modifying the isolation code that `FR-037` forbids touching.

Mapping the **organization** to `owner_id` puts all of an organization's content under one owner
prefix with per-upload session subtrees, which is the multi-user shape required, and it needs no
change to `sessions.py` at all. This is also what `RRA-001:21-22` anticipated: "Preserve the
opaque owner ID as the only future attachment point for separately approved commercial
authentication."

→ `FR-031`, `FR-035`, **A-3**; carried into `plan.md` as the bridge design.

---

## Items that are preconditions, not gaps

Two matters are settled as to *what the specification says* but remain blockers on implementation.
Neither is an owner decision needed to finish this specification; both are recorded as
implementation preconditions and reported.

- **P-1 — Retention decision (Constitution VII).** Storing an email address durably is new data
  use. `KHEPRI-DEC-014` §2 permits collecting an email owner key while requiring "its own
  retention decision"; §3 confirms this decision "does not pre-approve its content." The
  specification therefore names it as precondition 3 and **does not author it**. Authoring it here
  would be the borrowed-authority failure Constitution III forbids.
- **P-2 — Architecture decision (`KHEPRI-DEC-008`).** `KHEPRI-DEC-014` §2a requires "a separately
  approved architecture decision has settled runtime and provider selection" before any `RCA`
  slice begins. `governance/registries/decisions.yaml:60-64` records `KHEPRI-DEC-008` as
  `proposed`. This gate is closed independently of any approval of `RCA-001` itself.

---

## Outcome

No `NEEDS CLARIFICATION` marker remains in the specification. No `OWNER DECISION REQUIRED` was
raised, because every product question resolved against existing governance or existing code. The
two open matters are governance preconditions on implementation, not unresolved product decisions.
