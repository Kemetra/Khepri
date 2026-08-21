# Clerk-first identity and `R5` disposition

> **Design and roadmap output only.** This note implements no provider, account, session, recovery,
> or UI behavior. `KHEPRI-DEC-024` is a proposal on this branch and becomes governing only if the
> owner merges it.

**Repository baseline:** `origin/main` at `7cb535e` on 2026-08-21.

**Measured against:** `RCA-001`, `KHEPRI-DEC-015`, proposed `KHEPRI-DEC-024`, the merged `R3-01`
and `R3-09` designs, the Clerk evaluation, and the merged `R5-01` design. If this note conflicts
with a governing artifact, the governing artifact wins.

## 1. Current truth

### `R3`

`R3-01` through `R3-10` are merged. Khepri has hash-at-rest commercial sessions, revocation by
account, an active-organization pointer, live account and authorization resolution, a local
external-identity link table, and the provider-neutral `IdentityProvider` seam. `R3-11`, the named
provider adapter, is not implemented.

The current Khepri session is not a provider credential cache. It is Khepri's server-side bearer
record for one accepted local actor, Khepri revocation state, expiry, and at most one active
organization. It carries no role, membership, provider organization, or RRA owner identifier.

### `R5`

`R5-01` merged at `1c51249`. It designs Khepri-owned credential recovery because no provider was
admitted when it was written. `R5-02` through `R5-06` have no production implementation or recovery
migration.

Its organizing principle remains correct:

> **Recovery ownership follows credential ownership.**

What changes is which side owns the credential during the provisional Clerk phase.

### Clerk

The merged evaluation found Clerk technically suitable for the contained identity boundary but
commercially unadmitted because gates 3, 4, 6, 9, and part of 7 lack vendor evidence. Proposed
`KHEPRI-DEC-024` accepts those gaps only for an invite-only, non-paying private beta and retains a
hard commercial stop.

## 2. Recommended ownership model

### Clerk

- sign-up and sign-in;
- password storage, hashing, and verification;
- forgot-password and reset-password mechanics;
- authentication sessions and short-lived tokens;
- provider-side session revocation;
- authentication-email verification; and
- MFA only after its data and evidence boundary is separately admitted.

### Khepri

- durable, Khepri-allocated `account_id` values;
- account enabled, disabled, and purged state;
- organizations, memberships, roles, and the final-owner invariant;
- active-organization context;
- every authorization and isolation decision;
- Khepri authentication-session revocation and security evidence;
- identity-link integrity;
- RRA access and ownership; and
- every retail and analytical record.

Clerk proves who is present. Khepri decides what that local account may do. Clerk organization,
membership, role, permission, plan, feature, and metadata claims never enter the Khepri authority
model.

## 3. Session boundary

The existing two-layer composition remains the smallest compatible design:

```text
Clerk verifies credential and provider session
        |
IdentityProvider.verify -> (provider="clerk", provider_subject=sub)
        |
local external-identity lookup -> Khepri account_id
        |
Khepri mints or resumes its server-side session
        |
live account -> live membership -> live role -> live scope -> decision
```

Clerk's layer owns authentication mechanics. Khepri's layer owns a revocable local actor handle and
the active organization. Khepri does not refresh Clerk tokens, copy Clerk authorization claims, or
call Clerk to resolve an already-established local session on every protected request.

This duplication has a concrete reason rather than being permanent machinery by default:

- `FR-027` and `FR-029` require Khepri-owned active-organization state;
- `FR-008` requires immediate local account disablement regardless of provider-token expiry; and
- `FR-007` requires Khepri to revoke every Khepri session after recovery or compromise.

### Recovery and compromise

Clerk recovery must request provider-side revocation of other Clerk sessions. That does not revoke
the Khepri cookie. After the provider verifies successful recovery, an idempotent Khepri operation
must:

1. resolve the verified subject through the existing local link;
2. re-read and refuse a disabled or purged account;
3. revoke every Khepri session for the account;
4. append one content-free Khepri security event; and
5. permit a new Khepri session only after steps 1-4 succeed.

Clerk credential replacement and Khepri revocation cannot be one database transaction. The
non-paying private beta explicitly accepts the residual window between those systems. A webhook may
retry or accelerate the Khepri operation, but it cannot be the sole correctness mechanism.

Commercial admission must close or explicitly govern that residual with evidence and a bounded
failure policy. A successful private beta does not settle it.

Suspected compromise requires revocation at both layers: Clerk sessions at Clerk and Khepri
sessions in Khepri. Revoking only one leaves the other bearer valid within its own boundary.

## 4. `R5` disposition

The original task rows stay as history. Their effective disposition while Clerk owns credentials is:

| Task | Disposition | Rationale |
| --- | --- | --- |
| `R5-02` | **DEFER** | A Khepri recovery secret, verifier table, and migration are credential infrastructure Clerk owns during this stage. Preserve the design for a future return to Khepri credentials. |
| `R5-03` | **DEFER** | Clerk owns recovery initiation, delivery, and anti-enumeration behavior for its credential. Khepri must not build a parallel password-recovery endpoint. |
| `R5-04` | **DEFER** | One-use credential replacement and its concurrency guard belong to Clerk while Clerk owns the password. |
| `R5-05` | **REFRAME** | Replace the impossible cross-provider transaction with the idempotent Khepri consequence in §3: live account revalidation, all-local-session revocation, and content-free evidence before a new Khepri session. |
| `R5-06` | **REFRAME** | Prove Khepri consequences and identity-link integrity rather than Clerk's internal replay, expiry, KDF, or recovery-code implementation. |

### `R5-06` evidence boundary

The reframed evidence covers only behavior Khepri owns:

- a verified subject resolves through one local `(provider, provider_subject)` link;
- a duplicate subject or attempted link re-point fails closed;
- disabled and purged accounts cannot complete the Khepri consequence or receive a new session;
- all pre-existing Khepri sessions are revoked before a new one is created;
- repeating the Khepri consequence is safe and cannot restore authority;
- an absent, stale, or foreign identity link grants no account;
- the security event contains no email, password, provider token, recovery code, session bearer, or
  retail content; and
- provider organization, role, permission, plan, feature, and metadata claims cannot affect the
  result.

It does not attempt to mutation-test or reproduce Clerk's password KDF, recovery-secret expiry,
one-use code, delivery, or provider-session store. Those are provider evidence and adapter-contract
questions, not Khepri implementation.

The `R5-01` owner questions about a Khepri recovery-secret horizon and delivery vendor are dormant,
not answered. They return only if Khepri deliberately owns credentials again.

## 5. Identity-link and replaceability boundary

The request-time mapping remains sufficient:

```text
(provider, provider_subject) -> Khepri account_id
```

It is local, networkless, opaque, and independent of email. The composite key prevents a subject
from silently moving between accounts. No generic provider framework is needed.

For migration, Clerk's `external_id` may carry the already-allocated Khepri `account_id` as a
secondary reconciliation anchor. It is never the token subject and is never authority. Khepri does
not need another durable identity ID merely because the provider changes.

### Exit paths

- **Clerk to paid Clerk:** commercial evidence and entitlement change; Khepri IDs and domain state
  do not.
- **Clerk to another hosted provider:** add one contained adapter, provision successor identities,
  create new links to the same Khepri accounts, revoke sessions at cutover, and require password
  reset where credential hashes are not portable.
- **Clerk to a self-hosted provider:** the same link cutover, plus explicit operational ownership of
  patching, keys, backups, recovery, and incident response.
- **Clerk to Khepri credentials:** restore local credential enrollment and the deferred
  `R5-02`-`R5-04` path, then cut over links and sessions. Organizations, memberships, authority,
  isolation, and analytical history remain unchanged.

## 6. Future external-identity account slice: implementation readiness

Do not begin with the Clerk adapter. The provider-neutral account path has four verified gaps:

1. `Account.create(email, credential)` cannot create an external-only account without deriving a
   local verifier.
2. `Account.can_authenticate` equates authentication capability with a local verifier.
3. the SQL effective-owner predicate requires `credential_digest IS NOT NULL`, so an external-only
   final owner would be treated as unable to authenticate;
4. account creation and external-identity linking currently open through different stores and do
   not provide one atomic creation-and-link operation.

The future bounded slice should create a provider-neutral, sealed account-and-link operation that
allocates the Khepri `account_id`, records the already-verified provider subject without a Khepri
credential, and makes effective-owner eligibility recognize either a local verifier or an eligible
external identity link. It must preserve the final-owner transaction and must not import Clerk.

**Persistence remains an open proof obligation.** The existing `rca_external_identities` table and
`revoke_all_for_account` operation are useful evidence, but they do not prove the slice needs no
migration. Before implementation, the slice must probe:

- whether current constraints express every required account/link invariant;
- whether an external link's existence is sufficient to represent authentication capability;
- how the final-owner query evaluates that capability without a stale runtime-provider flag;
- whether account and link creation can be atomic with the current store boundaries; and
- whether any schema change is necessary for a safe hard-stop or provider cutover.

No migration may be proposed or rejected before that probe.

For the admitted private beta, provisioning is settled: an operator-controlled path must create the
Khepri account and external identity link before the invited tester authenticates. An unknown or
unlinked verified subject fails closed; it does not trigger runtime account creation. This settles
the initial workflow, not the persistence proof obligations above, and does not authorize public
self-service signup.

The slice's minimum evidence should cover external-only owner creation, duplicate-link refusal,
atomic rollback, disabled and purged accounts, final-owner protection, and coexistence with a local
credential. It should add no provider SDK, route, UI, recovery behavior, MFA, or authorization
claim.

## 7. Downstream impact

`R7` remains structurally unchanged. Its commercial routes start from the Khepri session and pass
through the canonical live resolver, so provider identity does not reach RRA.

`R8-03` must not build Khepri password or recovery forms for Clerk-backed accounts. Its Clerk-stage
scope becomes the authentication handoff, uniform unavailable state, and return to the Khepri shell
after the local session and recovery consequence succeed. Organization selection and every later
surface continue to use Khepri state.

## 8. Owner decisions still open

1. **Commercial recovery consistency:** before commercial admission, whether the accepted
   cross-system recovery window is closed by a stronger synchronous protocol, bounded and retained
   as an explicit residual, or avoided by revisiting the session model.

The provisional evidence-gap acceptance, the three deferred `R5` tasks, and the two reframed tasks
are settled by proposed `KHEPRI-DEC-024`; they are not repeated as open decisions here.

## 9. Non-goals

- No Clerk implementation, dependency, configuration, secret, route, middleware, or UI.
- No account, session, identity-link, recovery, or audit production code.
- No schema or migration decision.
- No change to Khepri authority or RRA boundaries.
- No generic authentication-provider framework.
