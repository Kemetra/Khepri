# Provider evaluation — Clerk against `KHEPRI-DEC-018` §5

> **Evidence record, not a decision.** This document records what was verified against Clerk's
> official sources on 2026-08-14, and the owner policy decisions recorded on the same date. It
> **admits no provider**, authorizes no code, and changes no governed artifact. It exists so that a
> future provider-selection decision rests on recorded evidence rather than recollection.

**Status:** advisory planning material under `docs/`, carrying no authority.
**Measured against:** `KHEPRI-DEC-018`, merged to `main` as `dcb63da` (#177) and therefore
governing. The gates below are the active ones.
**Revised 2026-08-14** after owner review: two policy decisions recorded, the gate classification
scheme replaced, and one identity-model error corrected — an earlier draft treated Clerk's
`external_id` as the authenticated provider subject. It is not; the verified JWT `sub` is. See
finding 2.

## Result

Three states, and collapsing them is the mistake this section exists to prevent:

```
Intended provider:          Clerk
Formal DEC-018 admission:   PENDING vendor evidence
Implemented in R3:          no
```

**Technical direction: Clerk is suitable for Khepri's intended hybrid identity architecture.**
Nothing in the evidence below is a requirement Clerk demonstrably fails. The `§4` boundary —
*Clerk proves identity, Khepri owns authority* — holds against every finding, and the two findings
that looked architectural on first reading are neutralised by it rather than by anything Clerk does.

**Formal admission remains fail-closed, and this note does not admit Clerk.** `§5`: "If any gate is
absent, revoked, or unverifiable, no external identity provider is admitted, and the `FR-002`
credential path Khepri already implements remains the only authentication path." Four gates need
material that is not obtainable from public documentation. Until a later decision records it,
`FR-002` remains the only authentication path. "Intended" is a design input; it is not admission.

### Gate disposition

An earlier revision of this note classified nine gates as "Partial" or "Concern" and concluded
`NOT ADMISSIBLE`. That framing merged three different things — evidence nobody retrieved, choices
only the owner can make, and constraints Khepri enforces itself — into one bucket that read as
vendor failure. Reclassified:

| Classification | Gates | Who resolves |
|---|---|---|
| **SATISFIED** | 2, 5\*, 8, 11, 12\*, 13, 15†, 16 | recorded here |
| **OWNER POLICY DECISION** | 5\*, 12\* | **settled — see below** |
| **VENDOR/CONTRACT EVIDENCE** | 3, 4, 6, 9, 7‡ — plus 10, non-blocking | Clerk / portal |
| **IMPLEMENTATION REQUIREMENT** | 1, 7‡, 14 | Khepri, in `R3` |
| **MATERIAL BLOCKER** | **none** | — |

**16 distinct gates.** Three are listed under two classifications, which is why the rows total more
than sixteen: \* gates **5** and **12** are owner decisions that *resolve to* SATISFIED; ‡ gate **7**
needs both a vendor answer and a Khepri-side condition. † Gate 15 is satisfied for identity
continuity; the exported hash *format* is undocumented, which affects password portability only. See
replaceability.

**Four gates block formal admission — 3, 4, 6, 9 — plus gate 7's written answer.** Everything else is
settled, non-blocking, or Khepri's own implementation work.

### Owner decisions recorded (2026-08-14)

**1. Data residency — no region-specific requirement at the current product stage.**

Gate 5 is conditional: "**Where residency obligations apply**, the processing and storage regions
are recorded and verified." No Khepri artifact imposes such an obligation. `KHEPRI-DEC-008` puts
this beyond inference — it defers provider, region, and residency to a future target-selection
artifact and calls leaving residency open "a refusal to record a commitment no approved artifact
supports." Clerk's DPA permits storage "anywhere Clerk or its Sub-processors maintain facilities,"
which does not engage a gate that is not triggered.

Consequence for Clerk: **gate 5 is satisfied by recorded acceptance.** Future customer, regulatory,
deployment, or contractual requirements reopen it — for the identity provider and the runtime
target together, since `KHEPRI-DEC-008` will settle residency for both.

**2. Breach notification — "without undue delay" accepted for the current stage.**

Gate 12 requires notification timelines and channels be *recorded*, not that they meet a numeric
threshold. Clerk's DPA commits to notification "in writing without undue delay after becoming aware
of any Security Incident," which is a recorded obligation and the standard processor formulation.
No Khepri artifact requires a fixed deadline.

Consequence for Clerk: **gate 12 is satisfied.** A fixed contractual deadline remains a legitimate
future negotiation preference and is not an admission blocker.

**Neither decision weakens `KHEPRI-DEC-018`.** Gate 5 was read against its own conditional wording;
gate 12 against its own "recorded" standard. No gate text is amended, and no unverified gate is
treated as verified.

## Sourcing discipline

Only `clerk.com/docs`, `clerk.com/legal`, `clerk.com/changelog`, and Clerk's official GitHub were
treated as evidence. `clerk.com/articles/*` and `clerk.com/blog/*` were **excluded** despite the
domain: marketing and blog content is not a specification.

Two Clerk pages that would normally carry gate evidence were unreachable to automated access:
`trust.clerk.com` returned **403** and `clerk.com/security` returned **404**.

**This is a retrieval failure by an automated agent, not an absence of documentation**, and the
distinction decides how gates 3 and 4 are classified. The material behind those pages may well
satisfy both; nobody has looked. A human with portal access should retrieve it — which is why gates
3 and 4 are `VENDOR/CONTRACT EVIDENCE` (get the document) rather than material blockers (the
guarantee does not exist). Gate 5 no longer depends on it: residency is settled by owner decision
above, not by anything behind the portal.

## The two findings that matter architecturally

### 1. Revoked sessions are invisible to both SDK verifiers (gate 8)

`verifyToken()` is documented as verifying "a Clerk-generated token signature," networkless when
`jwtKey` is supplied. Neither it nor `authenticateRequest()` documents any session-status or
revocation check. **They detect expiry, not revocation.**

Detecting a revoked session server-side requires an explicit Backend API session lookup. Clerk's
OpenAPI specification enumerates seven session statuses — `abandoned`, `active`, `ended`,
`expired`, `removed`, `replaced`, `revoked` — and any check must treat both `revoked` **and**
`replaced` as not-authenticated. The `sts` claim inside the token reflects status at issuance, not
live state.

**Two kinds of staleness, and only one of them exists here.**

*Authentication staleness — real, bounded, non-zero.* A Clerk token whose session was revoked
remains cryptographically valid until it expires, and networkless verification will accept it.
Clerk documents the default: "Clerk's model mitigates this issue by setting an extremely short
session token lifetime of **60 seconds**," with refresh running "on a 50-second interval (allowing
10 seconds for network latency)." That 60 seconds is the **dashboard-configurable default** of the
JWT template *Token lifetime* setting, not an immutable platform guarantee — so an admission record
must **pin it**, or the window becomes whatever a later configuration change makes it.

*Authorization staleness — effectively zero.* `§4` forbids deriving authority from a token and
fixes the resolution order; `FR-008` requires disablement to take effect without waiting for expiry.
Every protected action re-reads Khepri state:

```
verified Clerk identity -> account lookup -> assert_account_active LIVE
    -> membership LIVE -> role LIVE -> resource scope LIVE -> ALLOW / DENY
```

A disabled account, a revoked membership, an `owner`→`member` demotion, and an organization-access
change all take effect on the **next request**, regardless of what any token says or when it was
minted.

**Stated precisely, avoiding both overclaims:**

- A short-lived provider token **does not** preserve revoked *Khepri authority*. It cannot; authority
  is never read from it.
- Provider *identity* revocation is **not instantaneous**. A user whose Clerk session is revoked, but
  whose Khepri account and memberships are untouched, may remain **identified** for up to the
  configured token lifetime — 60 seconds by default. What they may *do* in that window is exactly
  what live Khepri state permits.

**Therefore: no per-request Clerk Backend API lookup.** It would improve no Khepri requirement.
`FR-008` is discharged by `assert_account_active` on every protected action, not by provider-side
revocation. A per-request lookup converts a ≤60-second *identity* staleness window into per-request
latency plus a new external dependency on the authentication path — trading a bounded, understood
window for an unbounded failure mode. If a future requirement ever demands faster *identity*
revocation specifically, the options are shortening the token lifetime or a targeted lookup on
sensitive operations, not a blanket per-request call.

This is the clearest vindication of the boundary. Had Khepri planned to authorize from token
claims, this finding would be disqualifying. Because authority is live, it is a bounded identity
staleness question instead.

### 2. No published immutability guarantee for the user ID (gate 7)

`KHEPRI-DEC-018` §7 requires "an identifier that is stable for the life of the identity, unique
within the instance, and never reused."

Clerk documents `id` only as "The unique identifier for the user." Account-linking pages describe
*attaching* an identity to an existing account — social linking "links the OAuth account to the
existing account," enterprise SSO "automatically links the Enterprise SSO account to the existing
account" — with no merge-or-replace language. But **no Clerk page states that the user ID is
immutable or never reused.**

No evidence of instability was found either. This is the absence of a guarantee, not evidence of a
problem — and §5's standard is verification, so absence is what matters. **The missing guarantee is
classified as `VENDOR/CONTRACT EVIDENCE`: undocumented, not contradicted.**

**Why the absence is an admission condition rather than a Clerk defect.** Take what Khepri controls
and what the token carries, together:

| Property | Owned by | Status |
|---|---|---|
| Verified `sub` in the token | Clerk, signature-verified by Khepri | present |
| Immutable `account_id` | **Khepri** | R2, merged — never provider-derived |
| Unique `(provider, provider_subject)` link | **Khepri** | `§7` requires it; R3 implements |
| No silent link re-pointing | **Khepri** | `§7`: "Re-pointing a link is account takeover" |
| Optional `external_id` reconciliation anchor | **Khepri** | available today |

The failure a stability guarantee protects against is *a `sub` that changes or is reused, silently
re-pointing an existing link to a different person*. Khepri's link table forecloses the dangerous
half by construction: `§7` requires duplicate links to fail closed and forbids silent re-pointing,
so a re-used `sub` colliding with an existing link is **refused**, not silently accepted. A changed
`sub` degrades to "this account cannot authenticate until relinked" — which `§7` already describes
as the expected, non-destructive outcome: "The account, its memberships, its audit events, and the
final-owner invariant survive."

So the residual risk of the undocumented guarantee is **loss of authentication continuity, not loss
of authority or account takeover**. That is an admission condition worth a written answer (see the
checklist), not a material defect. It would be a material defect only if Khepri authenticated by
email or let a provider identifier move a link — and `§7` forbids both.

**Do not record Clerk user-ID immutability as verified.** No authoritative source establishes it.

**The two-anchor model, and why `external_id` is not the subject.** An earlier draft of this note
suggested Khepri could carry "its own subject" in Clerk's `external_id` and treat that as the
durable identity key. **That was wrong, and the correction matters architecturally.**

`external_id` is a *field on the Clerk user object*, not a claim in the verified token. Treating it
as the per-request authentication subject would mean a Clerk Backend API lookup on every protected
request just to learn who is calling — the exact per-request provider dependency `§4`'s live-state
chain is designed to avoid, and a new external failure mode on the authentication path.

The correct model has two anchors with different jobs:

```
Clerk JWT
    sub          = Clerk's authenticated user subject   <- the identity assertion

Clerk user
    external_id  = optional Khepri-controlled anchor    <- migration / reconciliation

Khepri external identity link
    provider         = "clerk"
    provider_subject = Clerk JWT `sub`
    account_id       = Khepri account_id
```

Resolution is therefore local and networkless:

```
Clerk sub  ->  (provider="clerk", provider_subject=sub)  ->  Khepri account_id
```

- **`sub` is the primary authenticated subject.** It arrives inside the token whose signature has
  already been verified, so `(provider, provider_subject)` resolves against Khepri's own link table
  with no provider call.
- **`external_id` is secondary defence and portability metadata.** It may carry a Khepri-controlled
  identifier, and it is genuinely useful for migration, account reconciliation, recovery, and
  provider exit — because it lets Khepri seed a *successor* provider with identifiers it already
  knows. It is not the per-request subject.
- **Email is outside durable identity matching entirely**, per `§7`: "Email is not the durable
  identity key."

Both anchors should be recorded in the admission record rather than left to implementation.

## Gate-by-gate record

Classifications use the five categories in the disposition table above. "Partial" is deliberately
not used: it merged unretrieved evidence, owner choices, and Khepri-side work into one label that
read as vendor failure. The **evidence column is unchanged** — only the classification of what that
evidence means was wrong.

| # | Gate | Classification | Evidence |
|---|---|---|---|
| 1 | Approved personal-data classes | IMPLEMENTATION | Name/username nullable; OAuth access tokens retained. Per-field disablement not documented. **Khepri enumerates what it discloses — not a Clerk question** |
| 2 | Processor relationship | **SATISFIED** | Public DPA: "Clerk acts as 'processor' or 'sub-processor'". No plan gate |
| 3 | Security controls | **VENDOR EVIDENCE** | "SOC 2 Type 2, and HIPAA certified". Encryption described only as "strong" — no algorithms. ISO 27001 covers hosting providers, not Clerk. `trust.clerk.com` 403 to automated access |
| 4 | Subprocessors | **VENDOR EVIDENCE** | 15-day change notice **verified**; the list itself defers to the trust portal (403) |
| 5 | Data residency | **SATISFIED** by owner decision | Gate applies only "where residency obligations apply"; none does — `KHEPRI-DEC-008` defers residency to target selection. Clerk permits storage "anywhere Clerk or its Sub-processors maintain facilities" |
| 6 | Retention and deletion | **VENDOR EVIDENCE** | 90-day post-termination deletion verified; per-user deletion documented only as "Deletes the given User." — what survives is unstated |
| 7 | Stable subject semantics | **VENDOR EVIDENCE** + IMPLEMENTATION | No published immutability or non-reuse guarantee. Bounded by Khepri's link table; `external_id` is the reconciliation anchor. See above |
| 8 | Session and token semantics | **SATISFIED**, bounded | 60-second default token lifetime quoted from official docs; verifiers detect expiry, not revocation. Authorization staleness is zero; identity staleness ≤ configured lifetime. **Pin the lifetime** |
| 9 | Credential handling | **VENDOR EVIDENCE** | bcrypt references concern the **import** path; the at-rest algorithm is undocumented |
| 10 | MFA | **VENDOR EVIDENCE**, non-blocking | SMS / TOTP / backup codes **verified**; backup-code count, single-use, and regeneration not documented. Parameters, not capability — **not a blocker**. Clerk's implementation, not Khepri's: gate 10 requires "enrollment and recovery behavior" be recorded, and Khepri cannot record what only Clerk can state |
| 11 | Enterprise SSO | **SATISFIED** | SAML + OIDC + SCIM 2.0. "Production instances require the Pro or Business plan" |
| 12 | Incident and breach obligations | **SATISFIED** by owner decision | DPA commits to "without undue delay". Gate requires timelines be *recorded*, not that they meet a threshold |
| 13 | Logging and telemetry | **SATISFIED** | `CLERK_TELEMETRY_DISABLED=1`; development instances only; "we do not collect any information from your users" |
| 14 | Environment separation | IMPLEMENTATION | "user data can not be transferred between instances". Dev and production are separate instances with distinct issuers and keys — **pinning the production issuer/key closes this by construction** |
| 15 | Exit and exportability | **SATISFIED** for identity | CSV export including hashed passwords, plus `GetUserList`. Sub-gap: the exported hash **format is undocumented** — affects password portability only |
| 16 | SDK and version compatibility | **SATISFIED** | Official `clerk-backend-api`, MIT, "in GA", v7.0.0 published 2026-08-11. `requires-python >=3.10` — nothing bars 3.13. Exposes `jwt_key`, `audience`, `authorized_parties`, `clock_skew_in_ms` |

**Event stream.** `KHEPRI-DEC-018` §5 requires that no provider event stream be a correctness
dependency. Clerk's own documentation confirms this is the right posture: deliveries are "not
guaranteed to be delivered immediately or at all," and consumers "should be prepared to handle
retries and error scenarios." Retry scheduling is delegated to Svix's documentation, which is not
an official Clerk source, so concrete retry timing is **not verifiable**. Ordering and duplicate
semantics are undocumented.

### Clerk Organizations — recorded initial posture

**Preferred posture: leave Clerk Organizations, roles, and permissions disabled and unused.**

Clerk nests organization claims under `o` (`id`, `slg`, `rol`, `per`, `fpm`) when an organization is
active; the flat `org_id`/`org_role` form is v1 and was deprecated 2025-04-14. Organizations are
enabled explicitly per instance, so leaving them off means **claims Khepri must refuse are never
minted** — which reduces the `§4` prohibition from a discipline Khepri must maintain to a
configuration it simply does not enable. Defence by absence beats defence by vigilance.

**Khepri remains authoritative for all of this, and none of it moves to any provider:**

```
Organization          Membership            Role
Authorization         Tenant isolation      Final-owner invariant
Audit events          Active organization
```

`§4` is unconditional and does not depend on the configuration above: **provider organization, role,
permission, and membership claims must never participate in authorization**, whether or not they are
emitted. If a concrete *authentication-only* reason to enable Clerk Organizations ever appears, it
must be recorded with an explicit statement that no claim they mint is read for authority.

## Remaining vendor evidence — procurement checklist

Everything the owner could settle is settled. What remains is four items requiring material that is
not obtainable from public documentation, plus one written answer. **These are the only outstanding
blockers to formal `§5` admission.**

---

**Gate 3 — Security controls**

```
Evidence needed:  Clerk's security-controls documentation, including encryption algorithms in
                  transit and at rest, from trust.clerk.com (403 to automated access).
Why it matters:   Gate 3 requires controls "documented and verified". Public material says
                  "SOC 2 Type 2, and HIPAA certified" and describes encryption only as "strong",
                  which is an adjective, not a control.
Satisfies:        Named algorithms (e.g. AES-256 at rest, TLS 1.2+ in transit) plus a current
                  SOC 2 Type 2 report or its control summary.
Fails:            Only marketing-level assurances, or a report Khepri cannot obtain under NDA.
```

**Gate 4 — Subprocessors**

```
Evidence needed:  The current subprocessor list (the change-notification obligation is already
                  verified: "at least fifteen (15) days' notice", 10 days to object).
Why it matters:   Gate 4 requires the list "enumerated". Every subprocessor is a further
                  disclosure of the personal-data classes gate 1 enumerates.
Satisfies:        A dated list naming each subprocessor and its processing purpose.
Fails:            A list that cannot be obtained, or one with open-ended categories rather than
                  named entities.
```

**Gate 9 — Credential handling**

```
Evidence needed:  The algorithm and parameters protecting credentials at rest.
Why it matters:   Gate 9 requires a standard "no weaker than the FR-002 obligation they replace" --
                  and where Clerk holds the credential, FR-002 is discharged by this gate rather
                  than by Khepri's own hashing. The bcrypt/argon2/scrypt values in Clerk's docs are
                  `password_hasher` options on the *import* path, not a statement about storage.
Satisfies:        A named modern KDF with parameters (bcrypt cost, or argon2id memory/time/
                  parallelism) at or above FR-002's standard.
Fails:            An unnamed or reversible scheme, or refusal to state it.
```

**Gate 6 — Per-user deletion and backup retention**

```
Evidence needed:  What a per-user deletion erases, what it retains, and for how long -- including
                  backups, logs, and audit records.
Why it matters:   Gate 6 requires recording "what survives account deletion and for how long".
                  The API documents deletion only as "Deletes the given User." The 90-day
                  post-termination deletion commitment is already verified; per-user is not.
Satisfies:        A stated erasure scope and a bounded backup-retention window.
Fails:            Indefinite retention in backups with no stated horizon.
```

**Gate 7 — Stable subject (written answer, not a document)**

```
Evidence needed:  Written confirmation that the Clerk User `id` is immutable for the life of the
                  user and never reused, including across social linking, enterprise SSO linking,
                  identity merge, and identity replacement.
Why it matters:   Gate 7 requires the provider to *document* stability. Nothing authoritative does.
                  Khepri's link table bounds the consequence -- a re-used `sub` is refused, not
                  silently re-pointed -- so the residual risk is authentication continuity, not
                  authority. A written answer converts an assumption into evidence.
Satisfies:        Confirmation of immutability and non-reuse, or documentation stating it.
Fails:            Confirmation that `id` *can* change or be reused with no notification path. That
                  would be a real defect, and would make `external_id` reconciliation mandatory
                  rather than optional.
```

---

**Gate 10 (MFA backup codes)** and **gate 15 (exported hash format)** are worth asking in the same
exchange but are **not admission blockers**: gate 10's core capability (SMS, TOTP, backup codes) is
verified and the unknowns are parameters; gate 15 is satisfied for identity continuity, with the
hash format affecting password portability only.

**Khepri-side, needing no vendor input** — record in the admission decision, implement in `R3`:
enumerate the disclosed personal-data classes (gate 1); pin the production issuer and signing key so
a development identity cannot authenticate against production (gate 14); pin the token lifetime
(gate 8); set `external_id` at user creation as the reconciliation anchor (gate 7); leave Clerk
Organizations disabled.

## Replaceability

```
Identity continuity:   LOW difficulty
Password portability:  MODERATE, pending a verified export hash format
```

Splitting these is the honest answer. Averaging them to one rating would hide that the part carrying
Khepri's business value is the easy part.

**Unchanged by a move to ZITADEL, Keycloak, or any other IdP:**

```
Khepri Account / account_id       Organizations          Memberships
Roles                             Authorization rules    Tenant isolation
Final-owner invariant             Membership audit history
Business-data retention           RRA/RCA ownership relationships
```

None of it is provider-derived. `account_id` is Khepri-allocated; `R2` owns organizations,
memberships, roles, the `FR-013` invariant and `FR-014` events outright; isolation keys derive from
the organization alone under `FR-032`/`FR-033`; and `KHEPRI-DEC-015` §7 states the retention horizons
"do not move because a provider identity changed or vanished."

**The actual migration surface:**

```
ClerkIdentityProvider  ->  NewIdentityProvider     (one adapter behind the §6 seam)
(provider, provider_subject) link migration        (re-point to the new provider's subjects)
provider configuration                             (issuer, keys, audience)
authentication UI / configuration
credential migration or user re-auth/reset strategy
```

This is real work, not zero cost. What makes it *moderate rather than severe* is that `external_id`
lets Khepri seed a successor provider with identifiers it already controls, so the link migration is
a mapping Khepri can compute rather than a reconciliation it must discover.

**The password caveat.** Clerk's CSV export includes hashed passwords — the changelog notes that
"previously, accessing hashed passwords required support team intervention" — but the **format is
undocumented**. If it proves unverifiable or unsupported by the successor, moving passwords requires
either a trickle re-hash on next sign-in or a password-reset flow for all users. That is a UX cost,
not an identity-continuity risk: no account, membership, role, or audit event is at stake.

**Not vendor lock-in.** Khepri retains its entire business identity model, and every identifier a
migration needs is exportable. Calling ordinary adapter-and-link migration "lock-in" would misprice
the risk in the other direction.

## Recommendation

**Clerk is the intended provider for the current product stage. Formal admission stays fail-closed
on the four vendor-evidence items above.** Seven gates are satisfied, two owner decisions are
recorded, four are Khepri's own implementation work, and **no gate is a material blocker**. The two
findings that read as architectural on first contact — invisible session revocation and the
undocumented ID guarantee — are both contained by boundaries `KHEPRI-DEC-018` had already drawn,
which is the strongest evidence available that the boundary was drawn correctly.

The remaining work is a procurement exchange and portal access, not further research. This note
should not be re-opened for another evidence pass unless Clerk's answers contradict something
recorded here.

### Sequencing note — this document authorizes no code

`KHEPRI-DEC-018` §11 states that "no `IdentityProvider`, no adapter, no authentication, no session
handling, no `R3-02` or later slice is authorized by this decision." That is a statement about what
*that decision* authorizes, not a prohibition on `R3` proceeding under its own roadmap authority —
and the same decision's Consequences say "`R3-02` and later slices inherit it," which presumes they
proceed. **No governing clause forbids provider-neutral `R3` work before provider evidence
completes.**

One caveat for whoever sequences `R3`: `R3-01` was designed and merged **before** `KHEPRI-DEC-018`,
so its `R3-02` is Khepri's own session domain vocabulary (`session_id`, `account_id`,
`active_organization_id`, expiry, revocation) and contains **no** `IdentityProvider` seam. The seam
`§6` requires is additional scope that no existing task ID covers. Assigning it to `R3-02` silently
would repurpose a merged task's meaning; it needs a recorded roadmap disposition first.
