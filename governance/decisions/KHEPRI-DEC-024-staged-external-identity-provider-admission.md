# KHEPRI-DEC-024: Staged external identity provider admission

> Active. **Supersedes `KHEPRI-DEC-018`**, which is retired by this record. Stands beside
> `KHEPRI-DEC-008`, `KHEPRI-DEC-014`, `KHEPRI-DEC-015`, and `KHEPRI-DEC-017`.
>
> A branch is a proposal until the owner merges it (`AGENTS.md`). This record is written in the
> form it will hold on `main`; it is not governing and admits no provider before that merge.

## Context

`KHEPRI-DEC-018` drew the correct boundary: an external provider may prove identity, while Khepri
alone owns accounts, organizations, memberships, roles, authorization, active-organization context,
isolation, audit, and access to RRA. It also made one admission level serve every lifecycle stage.
If any of sixteen evidence gates was absent or unverifiable, no provider was admitted.

The Clerk evaluation in
`docs/superpowers/specs/2026-08-14-r3-provider-evaluation-clerk.md` found Clerk technically suitable
for that boundary but left five evidence items open: gates 3, 4, 6, 9, and the written portion of
gate 7. The gaps are evidence gaps, not demonstrated control failures. They nevertheless prevent
admission under `KHEPRI-DEC-018` as written.

Khepri is still pre-commercial. The present owner direction is to use approximately one year of
educational Clerk access for development and a bounded, non-paying private beta, so product effort
does not reproduce password storage, verification, recovery, and MFA infrastructure already
provided by an identity service. That convenience must not silently become commercial approval or
move business authority into Clerk.

The repository also already contains a provider-neutral `IdentityProvider` seam and a local
`(provider, provider_subject) -> account_id` link table. It does not yet contain a Clerk adapter or
a complete external-only account path. In particular, `Account.create` requires a local credential
and the effective-owner SQL predicate currently requires `credential_digest IS NOT NULL`. This
record authorizes neither an implementation nor an assumption that the existing schema is
sufficient.

Because supersession is whole-document under `KHEPRI-DEC-017`, a standing addendum could conflict
with `KHEPRI-DEC-018`'s fail-closed clause. This successor carries its boundary forward, adds an
explicit provisional admission level, and preserves the stronger commercial gate without editing
the historical record.

## Decision

### 1. Governing principle

> **An external provider may prove identity. Khepri owns authority.**

The provider proves who is present. Khepri decides what that actor may do. The separation applies
at every admission level and cannot be waived as a private-beta convenience.

### 2. What an admitted provider may own

Within its admitted stage, an external provider may own authentication mechanics in full:

- sign-up, sign-in, and sign-out;
- password handling, hashing, storage, and verification;
- forgot-password and reset-password mechanics;
- authentication-session or token issuance, refresh, expiry, and provider-side revocation;
- email-address verification for authentication;
- credential-compromise controls;
- MFA when separately enabled within the admitted data and evidence boundary; and
- enterprise SSO primitives only after the applicable admission gate is satisfied.

Khepri does not implement those mechanics for an account authenticated through that provider.
`FR-002` continues to govern any credential Khepri stores itself. When a provider holds the
credential, the applicable admission record carries the assurance obligation instead.

### 3. What Khepri remains authoritative for

Khepri is the sole source of truth for:

- the durable `Account` and its Khepri-allocated `account_id`;
- account enabled, disabled, and purged state;
- `Organization`, `Membership`, and the `owner` and `member` roles;
- membership revocation, the final-owner invariant, and membership audit events;
- the active organization;
- every authorization decision;
- tenant isolation and the opaque RRA owner scope;
- resource and RRA access;
- Khepri security and authorization audit events; and
- business-data and Khepri identity retention.

No Khepri identifier is derived from a Clerk identifier. Email remains mutable addressing data,
never the durable identity key.

### 4. Provider claims Khepri must refuse

Khepri MUST NOT use provider organization, membership, role, permission, plan, feature, metadata,
`can_act`, or resource-ownership claims for authorization. The prohibition applies even when the
provider emits such claims and even when their values happen to match Khepri state.

Every protected action keeps this order:

```text
provider proves identity, or Khepri verifies its own credential
        |
stable provider subject, where applicable
        |
local (provider, provider_subject) -> Khepri account_id mapping
        |
Khepri session resolution
        |
live Khepri account-state check
        |
live Khepri membership and role lookup
        |
resource-to-organization check
        |
ALLOW / DENY
```

Provider identity never delays account disablement, membership revocation, role change, or an
active-organization switch. Those are resolved from live Khepri state.

### 5. Two admission levels

External identity admission has two levels and no implied promotion between them.

#### 5.1 Provisional non-paying private-beta admission

This record provisionally admits **Clerk only** for development and an invite-only, non-paying
private beta. This is a time- and lifecycle-bounded risk acceptance, not a finding that every
commercial gate is satisfied.

The provisional admission permits authentication for named testers and non-paying design partners.
It does not permit public self-service availability, a paying customer, a commercial production
launch, or reliance beyond the current educational-access period.

Private-beta Khepri accounts and their external identity links are pre-provisioned for invited
testers. A verified but unlinked Clerk subject fails closed and cannot create or claim a Khepri
account at authentication time. Public or post-authentication self-service bootstrap requires a
later governing decision and is not admitted here.

Before any provisional adapter is enabled, its implementation and configuration must prove:

1. the `IdentityProvider` seam remains exactly provider plus provider subject, with no authority
   claims or vendor types crossing it;
2. the verified Clerk token `sub` is the request-time subject;
3. lookup from that subject to `account_id` is local and duplicate or re-pointed links fail closed;
4. the issuer, signing key, audience where used, authorized parties, accepted algorithm, and token
   lifetime are pinned for the intended instance;
5. development, test, and private-beta identities and keys are separated;
6. Clerk Organizations, roles, permissions, plans, features, and custom authorization metadata are
   disabled or ignored and are never read for Khepri authority;
7. no provider event stream is a correctness dependency;
8. Khepri checks account state, membership, role, and scope live on every protected action; and
9. an exit and hard-stop procedure can disable Clerk authentication and revoke affected Khepri
   sessions without deleting Khepri accounts or business state.

#### 5.2 Commercial admission

Commercial admission requires a later owner-merged decision recording evidence against **every**
gate in §8. Provisional operation, elapsed time, a successful private beta, or the absence of an
incident satisfies none of those gates by implication.

### 6. Private-beta personal-data boundary

The provisional Clerk use is limited to these data classes:

- the primary email address used for authentication and recovery;
- password credential material submitted directly to Clerk and the verifier material Clerk owns;
- Clerk-generated user, session, and token identifiers and their authentication timestamps and
  status;
- recovery codes or links delivered to the same authentication address; and
- IP address, user-agent string, device identifier, authentication timestamp, sign-in outcome, and
  risk or lock status produced by the authentication service.

The provisional admission does not authorize names, photographs, phone numbers, organization data,
memberships, roles, permissions, billing data, retail content, RRA identifiers, business metadata,
marketing data, or analytics data in Clerk. MFA data is not admitted by this list; enabling MFA
requires a later record enumerating the chosen factors and their recovery data.

Khepri may retain its own copy of the email address for invitations and its account record under
`RCA-001` and `KHEPRI-DEC-015`. Clerk's copy is limited to authentication and recovery. Neither copy
is authority.

### 7. Accepted provisional evidence gaps and residual risks

The owner explicitly accepts the following only for the scope and lifetime in §5.1. `Accepted`
means the uncertainty is permitted temporarily; it does not mean the missing evidence exists.

| Gate or boundary | Accepted gap or residual | Containment |
| --- | --- | --- |
| Gate 3 — security controls | Named encryption algorithms and the current control report were not obtained from the trust portal. | Data minimization, separate environments, short-lived signed tokens, and the hard stop. |
| Gate 4 — subprocessors | The notification obligation is recorded, but the current enumerated subprocessor list was not obtained. | Private-beta data classes are fixed by §6; the full list remains mandatory commercially. |
| Gate 6 — deletion | Per-user deletion scope and backup/log survival horizons are not documented. | No business or retail data enters Clerk; commercial use remains blocked. |
| Gate 7 — stable subject | Clerk user-ID immutability and non-reuse are not confirmed in writing. | Composite local links never move silently; collision refuses; Khepri state survives loss of authentication continuity. |
| Gate 9 — credential handling | Clerk's at-rest password KDF and parameters are not documented. | Explicit, time-bounded owner risk acceptance for non-paying beta only; this gap alone blocks commercial password use. |
| Provider-session revocation | Networkless token verification can accept a token until its short expiry after provider-side revocation. | Pin the shortest evaluated lifetime; Khepri authority remains live and independent. |
| Recovery completion | Clerk credential replacement and Khepri session revocation cannot share one database transaction. | Reframe `R5-05` as an idempotent Khepri consequence; never mint a new Khepri session before that consequence succeeds. The residual window remains commercially unresolved. |
| Provider availability and educational access | A provider outage or loss of educational entitlement can prevent new authentication. | Existing Khepri domain state remains intact; §9 forces a cutover or fail-closed stop. |

The following are not accepted risks at either level: authority from provider claims, identity by
email, silent link re-pointing, cross-environment authentication, disclosure of retail data, or a
provider event stream required for correctness.

### 8. Full commercial admission gates

A later commercial-admission decision must record verified evidence for every gate below. These are
carried forward unchanged in strength from `KHEPRI-DEC-018`.

1. **Approved personal-data classes.** The exact classes disclosed to the provider are enumerated
   and approved. Any class not enumerated is not disclosed.
2. **Processor relationship.** An executed data-processing agreement names the provider as a
   processor acting only on documented instructions.
3. **Security controls.** Authentication, storage, and transport controls are documented and
   verified.
4. **Subprocessors.** The subprocessor list is enumerated and a change-notification obligation
   exists.
5. **Data residency.** Where residency obligations apply, processing and storage regions are
   recorded and verified.
6. **Retention and deletion.** Provider-side retention periods and deletion behavior are recorded,
   including what survives account deletion and for how long.
7. **Stable subject semantics.** The provider documents a subject stable for the identity's life,
   unique within the instance, and never reused, including behavior across email change, linking,
   merge, and replacement.
8. **Session and token semantics.** Token lifetime, refresh, recovery, and revocation behavior are
   documented, including whether verification detects revocation or only expiry.
9. **Credential handling.** Credential storage and verification are documented at a standard no
   weaker than the `FR-002` obligation they replace.
10. **Multi-factor authentication.** MFA capability, enrollment, recovery, and backup-factor
    behavior are recorded.
11. **Enterprise SSO.** SSO capability is recorded where the commercial phase depends on it.
12. **Incident and breach obligations.** Notification timelines and channels are recorded.
13. **Logging and telemetry exposure.** Provider logging, SDK transmission, and Khepri disclosures
    are recorded; forbidden Khepri data cannot be retained by writing it to a provider.
14. **Environment separation.** Development, test, and production identities are separated so a
    non-production identity cannot authenticate against production.
15. **Exit and exportability.** The identity set is exportable and a tested path preserves Khepri
    account continuity when leaving the provider.
16. **SDK and version compatibility.** The adapter and SDK are pinned and their compatibility
    expectations are recorded.

If any commercial gate is absent, revoked, or unverifiable, commercial admission fails closed. A
commercial decision may reject Clerk and select another provider; this record creates no preference
that overrides the gates.

### 9. Hard-stop conditions

The provisional admission becomes inoperative immediately before the earliest of:

1. accepting money or other consideration from any customer;
2. opening a commercial production service, even if the first customer has not yet paid; or
3. expiration, withdrawal, suspension, or loss of the current educational Clerk access.

Before a hard stop, the owner must merge exactly one of:

- a commercial Clerk admission satisfying §8;
- an admission for another hosted or self-hosted provider plus an approved cutover; or
- a decision deliberately returning credential ownership to Khepri with the required recovery and
  security work.

If no successor path is governing when a stop occurs, Clerk-backed authentication fails closed.
No new Clerk-backed Khepri session may be created, and affected Khepri sessions must be revoked.
Accounts, organizations, memberships, roles, audit history, isolation scopes, and RRA data remain
untouched.

### 10. Integration and identity-link boundary

The existing `IdentityProvider` is vendor containment, not a plugin framework. It exposes only
whether a credential represents a verified identity and the pair `(provider, provider_subject)`.
Vendor SDK types and errors remain behind the adapter.

The durable mapping is:

```text
(provider, provider_subject) -> exactly one Khepri account_id
```

The provider subject is opaque and is not a Khepri account ID. Email is not used to resolve the
mapping. Duplicate links fail closed and an existing link never moves between accounts through an
ordinary path.

For Clerk, a Khepri-controlled `account_id` may be stored in Clerk's `external_id` field solely as
an exit and reconciliation anchor. It is not the request-time subject, is not read for authority,
and is not a substitute for the local link table. No new Khepri reconciliation column is authorized
by this record.

Deleting or losing a provider identity does not delete Khepri business state. The account becomes
unauthenticatable through that link until a governed relink or replacement-provider link exists.

### 11. Session and recovery boundary

Clerk owns its authentication session and token. After Clerk verifies the actor, Khepri may mint its
existing server-side session. The Khepri session represents the accepted local actor, its revocable
Khepri security state, and at most one active organization. It contains no provider authority
claim, role, membership, `owner_id`, or retail content.

The two layers have one responsibility each:

- Clerk decides whether its credential and provider session authenticate the human.
- Khepri decides whether the mapped account and current organization state authorize the request.

Password recovery follows credential ownership, so Clerk owns recovery initiation, secret or code,
expiry, one-use enforcement, delivery, and password replacement. Khepri continues to own account
state revalidation, Khepri-session revocation, content-free security evidence, identity-link
integrity, and disabled or purged-account refusal.

On suspected compromise, both layers must be revoked: Clerk authentication sessions at Clerk and
all Khepri sessions for the mapped account in Khepri. A provider revocation does not substitute for
the Khepri operation.

### 12. Event streams and fresh state

No webhook, callback, or provider event stream may be the sole mechanism enforcing a Khepri
invariant. Events may accelerate reconciliation or retry an idempotent consequence. Correctness
must still hold if no event is delivered.

Khepri continues to consult account state and authority live. Provider token claims about Khepri
state are stale by definition and are ignored.

### 13. Exit paths

All provider transitions preserve Khepri `account_id` values and every organization, membership,
role, authorization rule, isolation mapping, audit event, RRA ownership relation, and historical
analytical record.

- **Paid Clerk:** satisfy §8 and change commercial entitlement and configuration, not Khepri
  identity or authority.
- **Another hosted provider:** add one contained adapter, establish new external links using the
  Khepri reconciliation anchor, revoke old sessions at cutover, and require reset or reauthentication
  where credential hashes are not portable.
- **Self-hosted provider:** the same identity-link cutover, plus explicit operational, backup,
  patching, incident, and credential-control ownership.
- **Khepri-owned credentials:** deliberately restore local credential creation, verification, and
  the deferred credential-recovery slices; provider links may be retired without rebuilding domain
  state.

### 14. What this decision does not authorize

- No Clerk SDK, dependency, secret, environment variable, adapter, route, middleware, UI, schema,
  migration, or production code.
- No public or paying use of Clerk.
- No MFA configuration under the provisional data boundary.
- No Clerk Organizations, memberships, roles, permissions, plans, or features as Khepri authority.
- No provider-backed account creation or linking implementation.
- No conclusion that the existing persistence model needs no migration.
- No `RRA-001`, `RRA-002`, or `RCA-001` amendment.
- No weakening of `KHEPRI-DEC-015` retention or logging rules.
- No provider-switching framework beyond the existing containment seam.
- No edit to `KHEPRI-DEC-018`; it remains historical after retirement.

## Consequences

- Clerk is provisionally admitted only when this record is merged and only within §§5.1, 6, 7,
  and 9.
- Clerk remains commercially unadmitted until a later decision satisfies every §8 gate.
- `R3-11`'s governance dependency can be satisfied provisionally, but implementation must not begin
  before the provider-backed account capability and persistence questions in the companion design
  are resolved.
- `R5-02`, `R5-03`, and `R5-04` are deferred while Clerk owns credentials. `R5-05` and `R5-06` are
  reframed around Khepri-owned consequences and identity-link integrity.
- `KHEPRI-DEC-015` continues to govern Khepri-held identity, sessions, recovery evidence, and audit
  data. Provider-side retention remains an admission matter.
- The private-beta acceptance is deliberately reversible: losing Clerk authentication must not
  destroy or renumber any Khepri business identity or analytical state.
- `KHEPRI-DEC-018` remains in place as history and must not be edited to match this successor.

---

Identity, state, document, dependencies, and supersession are authoritative in
`governance/registry.yaml`.
