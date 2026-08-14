# KHEPRI-DEC-018: External identity provider boundary

> Active. Stands beside `KHEPRI-DEC-008`; supersedes nothing.

## Context

`RCA-001` is active and requires durable commercial identity: accounts, authentication, sessions,
recovery, organizations, memberships, and the authorization records over them. Its assumption
`A-4` leaves one question deliberately open:

> "Authentication is by a credential the account holder supplies. No external identity provider is
> assumed, and none is excluded; that is a plan-level decision constrained by `FR-002`, not a
> product requirement."

`governance/families/RCA.md` excludes "Runtime, provider, and deployment selection outside an
active architecture decision," and `RCA-001`'s implementation precondition 2 requires an active
architecture decision to settle provider selection. So the plan-level choice `A-4` describes cannot
be made inside an implementation slice. Constitution IV says the same thing from the other
direction: a slice "does not widen its specification, privacy boundary, runtime boundary, or data
use," and "material boundary changes require the owner to merge an updated or new artifact first."
Admitting an external identity provider would widen the privacy boundary and data use, because
personal data would reach a third party.

This decision settles the boundary. It does not select a provider.

### What already constrains the answer

The `R3-01` authentication-session design is merged and establishes the rule that any external
provider must not disturb. A session record carries "**no role**, **no membership**, **no
`owner_id`**, **no `can_act` flag** … Any of those values cached in the row goes stale exactly when
it matters," and every protected action consults account liveness "**every time**" and resolves
membership and role "**live** from the store," with neither result memoized.

That rule is not stylistic. `FR-008` requires a disabled account's sessions to "cease to authorize
any action, with no dependence on session expiry to take effect," and `FR-030` requires a
membership or role change to take effect "without requiring the session to end." A design that
authorizes from a provider's token claims cannot satisfy either requirement, because a token
already issued cannot be made to reflect a change that happened after it was issued.

### Why this is not a specification question

`A-4` already permits this choice at plan level, so `RCA-001` needs no amendment and none is made
here. What `A-4` cannot do is authorize the widening itself, because a specification cannot widen
the privacy boundary its family excludes. This decision supplies the missing authority and nothing
more.

## Decision

### 1. The governing principle

> **An external provider may prove identity. Khepri owns authority.**

Identity is the claim that a particular human is present. Authority is the determination of what
that human may do. This decision permits the first to be delegated. It forbids the second.

### 2. What an external identity provider may own

A provider admitted under §5 may own authentication mechanics in full:

- sign-in and sign-out
- credential handling, storage, and verification
- session or token issuance, refresh, and expiry
- identity verification
- email address verification
- credential recovery
- multi-factor authentication
- enterprise single sign-on primitives

Khepri implements none of these for accounts authenticated through an admitted provider.

### 3. What Khepri remains authoritative for

Khepri is the sole source of truth for every item below. No provider assertion may substitute for
Khepri state in any of them:

- the `Account` and its identifier
- account enabled and disabled state
- the `Organization`
- `Membership`
- the `owner` and `member` roles
- membership revocation
- the final-owner invariant (`FR-013`)
- membership audit events (`FR-014`)
- the active organization (`FR-027`)
- every authorization decision (`FR-021` through `FR-026`)
- tenant isolation and the opaque isolation scope (`FR-031` through `FR-035`)
- resource ownership
- business-data retention

### 4. The claims Khepri must refuse

A provider token or session may assert facts that resemble Khepri's authority model. Providers
commonly emit organization, role, and permission claims. **Khepri MUST NOT read them for any
authorization purpose.** This applies to at least:

```
organization        role            permissions
membership          can_act         resource ownership
```

Reading any of these would make the provider's directory authoritative over Khepri's, which §3
forbids. The prohibition is on *use for authority*; a provider is not required to stop emitting
them.

**The governed request model.** Every protected action resolves in this order, and no step may be
skipped, cached, or reordered:

```
provider verifies identity
        ↓
stable external subject
        ↓
Khepri Account mapping
        ↓
live account-status check
        ↓
live membership lookup
        ↓
live role lookup
        ↓
resource-organization check
        ↓
ALLOW / DENY
```

A valid provider session or token MUST NOT delay the effect of account disablement, membership
revocation, an `owner` to `member` demotion, or any change to organization access. Authorization
is decided from live Khepri state at the moment of the request, never from a claim minted earlier.

This restates for external identity exactly what `R3-01` already established for internal sessions.
It is not a new rule and it weakens nothing in `R2`.

### 5. Admission gates

No external identity provider is admitted by this decision. A provider becomes admissible only
through a later decision that records evidence against every gate below.

Each gate is an obligation to verify, not an assumption. A provider's marketing or documentation
claim is not evidence; verified configuration is.

1. **Approved personal-data classes.** The exact personal-data classes disclosed to the provider
   are enumerated and approved. Any class not enumerated is not disclosed.
2. **Processor relationship.** An executed data-processing agreement names the provider as a
   processor acting only on documented instructions.
3. **Security controls.** The provider's authentication, storage, and transport controls are
   documented and verified.
4. **Subprocessors.** The subprocessor list is enumerated, and a change notification obligation
   exists.
5. **Data residency.** Where residency obligations apply, the processing and storage regions are
   recorded and verified.
6. **Retention and deletion.** Provider-side retention periods and deletion behavior are recorded,
   including what survives account deletion and for how long.
7. **Stable subject semantics.** The provider documents an identifier that is stable for the life
   of the identity, unique within the instance, and never reused. Its behavior across email change,
   identity merge, and identity replacement is recorded.
8. **Session and token semantics.** Token lifetime, refresh behavior, and revocation semantics are
   documented, including whether verification detects a revoked session or only an expired one.
9. **Credential handling.** Credential storage and verification meet a standard no weaker than the
   `FR-002` obligation they replace.
10. **Multi-factor authentication.** MFA capability and its enrollment and recovery behavior are
    recorded.
11. **Enterprise SSO.** SSO capability is recorded where the commercial phase depends on it.
12. **Incident and breach obligations.** Notification timelines and channels are recorded.
13. **Logging and telemetry exposure.** What the provider logs, what its SDK transmits, and what
    Khepri would expose to it are recorded. Nothing `FR-040` or `KHEPRI-DEC-015` §7 forbids
    retaining may be disclosed by writing it to a provider instead.
14. **Environment separation.** Development, test, and production identities are separated so that
    a non-production identity cannot authenticate against production.
15. **Exit and exportability.** The identity set is exportable, and a documented path exists to
    migrate away without destroying Khepri account continuity.
16. **SDK and version compatibility.** The adapter and its provider SDK are pinned, and the
    compatibility expectation is recorded.

**No provider event stream may be a correctness dependency.** Webhooks, callbacks, and asynchronous
notifications may be used for convenience only. Every invariant in §3 MUST hold when no such event
is ever delivered.

**Fail closed.** If any gate is absent, revoked, or unverifiable, no external identity provider is
admitted, and the `FR-002` credential path Khepri already implements remains the only authentication
path. This mirrors the pattern `KHEPRI-DEC-008` uses for its narrative provider, where an
unverifiable gate leaves the adapter disabled rather than trusted.

### 6. The integration boundary

Provider concepts MUST NOT spread into Khepri's domain, authorization, organization, membership, or
isolation logic. A narrow internal seam — an `IdentityProvider` — contains them.

The seam exists for vendor containment, not to build a provider-switching framework. It exposes
only what Khepri needs to identify an authenticated actor:

- whether the request carries a verified identity
- the stable provider subject, and the provider that issued it

It exposes nothing else. Khepri business authority is not expressible through it, so a provider
cannot assert authority even in error. `KHEPRI-DEC-008` established this shape when it replaced a
named cloud provider with a capability contract and confined the vendor SDK behind a `Protocol`;
this decision applies the same pattern to identity.

Vendor SDK types, request and response shapes, and error types stay behind the adapter. No module
outside it may import them. Concrete interface design belongs to `R3` implementation and is not
settled here.

### 7. External identity linking

```
provider + provider_subject  →  exactly one Khepri Account
```

- The **stable provider subject** is the durable external identifier. It is opaque to Khepri and
  carries no meaning beyond identity.
- **Email is not the durable identity key.** It remains a mutable `Account` attribute. An identity
  whose email address changes is the same identity.
- **Duplicate links fail closed.** A second attempt to link an already-linked external identity is
  refused, and the refusal is uniform per `FR-004`.
- **An existing link MUST NOT silently move between accounts.** Re-pointing a link is account
  takeover and requires an explicit, audited operation if it is ever specified.
- **Deleting an external identity does not delete Khepri business state.** The account, its
  memberships, its audit events, and the final-owner invariant survive. The account becomes
  unauthenticatable until relinked; it does not become ownerless, and no organization loses its
  owner as a side effect.
- **Khepri lifecycle and retention remain independently governed.** `KHEPRI-DEC-015`'s horizons are
  anchored to Khepri's own disablement lifecycle and do not move because a provider identity
  changed or vanished.

Concrete schema, columns, constraints, and migrations belong to `R3` implementation. This decision
settles the principles they must satisfy and nothing more.

### 8. Email authority and purpose

Khepri retains an email address because `RCA-001` requires it: `FR-016` through `FR-020` issue
invitations to an address before an account exists. An admitted provider may also process an email
address for authentication and verification. Both may hold it; only one governs its use.

- **Khepri's copy is authoritative for Khepri purposes** — invitation delivery and the account
  identity record — under the retention and purpose limits `KHEPRI-DEC-015` §3 already sets.
- **The provider's copy is limited to authentication mechanics** and the purposes named in its
  admission record.
- **Email is never authority.** It is not the identity key, it does not imply membership, and a
  verified address confers no organization access. `FR-032` continues to forbid it from appearing
  in, or being derivable from, any analytical isolation key.
- Disclosing an address to a provider is disclosure to a processor, governed by the §5 gates, and
  authorizes no new purpose.

### 9. Relationship to `KHEPRI-DEC-015`

`KHEPRI-DEC-015` §1 governs "the retention of commercial identity and authorization data required
by `RCA-001`, and nothing else" — data classes Khepri holds, each anchored to a named requirement.

**It remains compatible unchanged, and this decision does not amend it.** Under a hybrid model
Khepri holds *fewer* credential classes and the same email class. Holding less is not a widening,
and every horizon in the matrix stays anchored to Khepri's own lifecycle.

What is genuinely new is disclosure to a processor, which §5 gate 6 captures as an admission
obligation rather than a retention change. If a specific provider's retention or deletion behavior
turns out to conflict with a matrix row, the conflict is a **provider-selection** finding, and the
selecting decision must record it. Because supersession is whole-document, amending the matrix would
require restating it in full; nothing found here requires that today.

### 10. Relationship to `KHEPRI-DEC-008`

**This decision stands beside `KHEPRI-DEC-008` and supersedes nothing.** Three reasons, and the
third is the one a reader is most likely to challenge.

1. `KHEPRI-DEC-008` permits "a new **or** superseding architecture decision." A new one is
   sufficient.
2. Its "changing providers or materially changing provider data handling" clause sits inside the
   narrative-provider section and governs the narrative adapter and its model snapshot. Identity is
   a different capability, not a change to that provider.
3. Its clause that "no separate SPA, Node.js runtime, Redis, data warehouse, notebook runtime, or
   microservice boundary is introduced for the private beta" enumerates **deployed runtime
   components** and is scoped to the private beta. A hosted identity provider introduces no runtime
   component into Khepri's deployment: the adapter is a library inside the existing web process, and
   the provider is reached by an outbound call. `KHEPRI-DEC-008` already precedents exactly that
   shape for its narrative provider. Commercial identity is an `RCA` concern, and `RCA` did not
   exist when that clause was written.

Superseding would also be destructive. Supersession is whole-document, so retiring
`KHEPRI-DEC-008` would retire the entire portable runtime architecture — the capability contract,
claim-and-redrive, envelope encryption, observability — and require restating all of it to change
nothing. That is a larger artifact for no governance gain, and Constitution IV asks for the
smallest change that authorizes the boundary.

### 11. What this decision does not authorize

- **No provider is selected.** Admitting a named provider requires a later decision recording
  evidence against every §5 gate.
- **No product code.** No `IdentityProvider`, no adapter, no authentication, no session handling,
  no `R3-02` or later slice is authorized by this decision.
- **No dependency change.** No SDK is added.
- **No schema or migration.**
- **No `RCA-001` amendment.** `A-4` already permits this choice at plan level.
- **No `KHEPRI-DEC-015` change.** See §9.
- **No deployment, provisioning, or spend.** The target-selection artifact `KHEPRI-DEC-008`
  requires remains outstanding and is unaffected.
- **No relocation of authority.** Organizations, memberships, roles, and authorization do not move
  to any provider, in whole or in part.
- **No weakening of any `RRA-001`, `RRA-002`, or `RRA-006` control**, and no change to `R2`'s
  merged membership lifecycle, final-owner invariant, or audit events.

## Consequences

- The `R3` implementation gate that required an architecture decision on provider selection is
  satisfied for the *boundary*. Selecting a named provider remains gated on §5.
- `R3-01`'s live-authority rule is reaffirmed and extended to external identity. `R3-02` and later
  slices inherit it.
- `assert_account_active` remains the `FR-008` chokepoint and must be consulted on every protected
  action regardless of who authenticated the actor.
- `FR-002` continues to govern any credential Khepri itself stores. Where an admitted provider
  holds the credential, Khepri stores none, and the obligation is discharged by gate 9 rather than
  by Khepri's own hashing.
- `KHEPRI-DEC-008`, `KHEPRI-DEC-014`, `KHEPRI-DEC-015`, and `RCA-001` are unaffected and not
  superseded.
- The commercial thesis behind the phase ordering remains an untested assumption, as
  `KHEPRI-DEC-014` records. This decision does not change that.

---

Identity, state, document, dependencies, and supersession are authoritative in
`governance/registry.yaml`.
