# Provider evaluation — Clerk against `KHEPRI-DEC-018` §5

> **Evidence record, not a decision.** This document records what was verified against Clerk's
> official sources on 2026-08-14. It admits no provider, authorizes no code, and changes no
> governed artifact. It exists so that a future provider-selection decision — or the choice not to
> make one — rests on recorded evidence rather than recollection.

**Status:** advisory planning material under `docs/`, carrying no authority.
**Measured against:** `KHEPRI-DEC-018`, merged to `main` as `dcb63da` (#177) and therefore
governing. The gates below are the active ones.

## Result

**Clerk is NOT ADMISSIBLE today under `KHEPRI-DEC-018` §5.**

That is a statement about evidence, not about product quality. §5 requires every gate to be
verified, and says: "If any gate is absent, revoked, or unverifiable, no external identity provider
is admitted." Five gates are unmet or unverifiable from official sources, two of them materially.

| Verdict | Count | Gates |
|---|---|---|
| **Verified** | 6 | 2, 11, 12*, 13, 15*, 16 |
| **Partial** | 8 | 1, 3, 4, 6, 7, 8, 9, 10, 14 |
| **Concern** | 1 | 5 (data residency) |

\* Gate 12 is *verified as a fact* but the fact itself is weak — see below. Gate 15 is verified with
one sub-gap.

**Nothing here blocks `KHEPRI-DEC-018` itself.** The gates worked exactly as intended: they turned
a vendor question into a list of things to confirm, and five of them came back unconfirmed. A gate
list whose gates all passed on first contact would not have been doing any work.

## Sourcing discipline

Only `clerk.com/docs`, `clerk.com/legal`, `clerk.com/changelog`, and Clerk's official GitHub were
treated as evidence. `clerk.com/articles/*` and `clerk.com/blog/*` were **excluded** despite the
domain: marketing and blog content is not a specification.

Two Clerk pages that would normally carry gate evidence were unreachable to automated access:
`trust.clerk.com` returned **403** and `clerk.com/security` returned **404**. That is recorded as a
finding — the material behind them may well satisfy several gates, and a human with portal access
should re-check gates 3, 4, and 5 before any of this is treated as settled.

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

**Why this does not damage the architecture.** `KHEPRI-DEC-018` §4 already forbids deriving
authority from a token, and `FR-008` already requires disablement to take effect without waiting
for expiry. Khepri re-reads account status and membership live on every protected action, so a
revoked *Clerk* session cannot extend a disabled *Khepri* account's authority by even one request.
The exposure is narrower: a user whose Clerk session is revoked but whose Khepri account is
untouched may continue to be *identified* until the token expires. With default settings that
window is bounded by the 60-second token lifetime — **an inference from the documented TTL, not a
Clerk commitment**.

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
problem — and §5's standard is verification, so absence is what matters.

**Documented mitigation.** Clerk supports `external_id`, "The ID of the user as used in your
external systems. Must be unique across your instance," and Clerk's own migration guidance
recommends preferring it over the native ID. Khepri could therefore carry *its own* subject and
depend on Clerk's ID semantics only as a fallback — which is a stronger position than the gate
requires, because it makes the durable key one Khepri controls.

Either route works; both should be recorded explicitly rather than left to implementation.

## Gate-by-gate record

| # | Gate | Verdict | Evidence |
|---|---|---|---|
| 1 | Approved personal-data classes | Partial | Name/username nullable; OAuth access tokens retained. Per-field disablement not documented |
| 2 | Processor relationship | **Verified** | Public DPA: "Clerk acts as 'processor' or 'sub-processor'". No plan gate |
| 3 | Security controls | Partial | "SOC 2 Type 2, and HIPAA certified". Encryption described only as "strong" — no algorithms. ISO 27001 covers hosting providers, not Clerk |
| 4 | Subprocessors | Partial | 15-day change notice **verified**; the list itself defers to the trust portal (403) |
| 5 | Data residency | **Concern** | Privacy policy permits data "transferred, processed, and stored anywhere in the world". No region pinning documented |
| 6 | Retention and deletion | Partial | 90-day post-termination deletion verified; per-user deletion documented only as "Deletes the given User." — what survives is unstated |
| 7 | Stable subject semantics | **Partial** | See above |
| 8 | Session and token semantics | **Partial** | See above |
| 9 | Credential handling | Partial | bcrypt references concern the **import** path; the at-rest algorithm is undocumented |
| 10 | MFA | Partial | SMS / TOTP / backup codes verified; backup-code count, single-use, and regeneration not documented |
| 11 | Enterprise SSO | **Verified** | SAML + OIDC + SCIM 2.0. "Production instances require the Pro or Business plan" |
| 12 | Incident and breach obligations | **Verified** (weak) | DPA commits to "without undue delay" — **no 72-hour deadline** |
| 13 | Logging and telemetry | **Verified** | `CLERK_TELEMETRY_DISABLED=1`; development instances only; "we do not collect any information from your users" |
| 14 | Environment separation | Partial | "user data can not be transferred between instances". Whether a dev user can authenticate against production is not stated directly |
| 15 | Exit and exportability | **Verified** | CSV export including hashed passwords, plus `GetUserList`. Sub-gap: the exported hash **format is undocumented**, which is what a migration would need |
| 16 | SDK and version compatibility | **Verified** | Official `clerk-backend-api`, MIT, "in GA", v7.0.0 published 2026-08-11. `requires-python >=3.10` — nothing bars 3.13. Exposes `jwt_key`, `audience`, `authorized_parties`, `clock_skew_in_ms` |

**Event stream.** `KHEPRI-DEC-018` §5 requires that no provider event stream be a correctness
dependency. Clerk's own documentation confirms this is the right posture: deliveries are "not
guaranteed to be delivered immediately or at all," and consumers "should be prepared to handle
retries and error scenarios." Retry scheduling is delegated to Svix's documentation, which is not
an official Clerk source, so concrete retry timing is **not verifiable**. Ordering and duplicate
semantics are undocumented.

**Organizations are opt-in and can stay off.** Clerk nests organization claims under `o` (`id`,
`slg`, `rol`, `per`, `fpm`) when an organization is active; the flat `org_id`/`org_role` form is v1
and was deprecated 2025-04-14. Organizations are enabled explicitly per instance, so Khepri can
simply leave them disabled — which reduces the risk in `KHEPRI-DEC-018` §4 from *discipline* to
*configuration*, since claims Khepri must refuse would never be minted.

## What would make Clerk admissible

Ordered by who can resolve them. None require code.

**Owner action — contractual or portal access (gates 3, 4, 5, 12):**
1. Retrieve the subprocessor list and security documentation from `trust.clerk.com`.
2. Resolve **data residency** (gate 5). This is the one gate that may be structurally unmeetable if
   Khepri has a residency obligation — the published privacy policy affirmatively permits worldwide
   storage. Determine whether Khepri *has* such an obligation before treating it as a blocker.
3. Decide whether "without undue delay" is acceptable in place of a fixed breach deadline.

**Vendor confirmation in writing (gates 7, 9, 10, 15):**
4. Is the user ID immutable and never reused, including across account linking?
5. What algorithm protects credentials at rest, and what format do exported hashes use?
6. Backup-code count, single-use behavior, and regeneration.

**Khepri-side design decisions, recordable now (gates 1, 8, 14):**
7. Enumerate exactly which personal-data classes are disclosed — and confirm organizations stay
   disabled.
8. Decide whether Khepri needs revocation detection faster than token expiry. Given live authority
   resolution, the answer is plausibly no, and saying so explicitly is cheaper than an extra API
   call on every request.
9. Confirm a development identity cannot authenticate against production.

## Recommendation

**Do not select a provider yet, and do not treat this as a rejection of Clerk.** Six gates verified
cleanly, including the two that most often disqualify a vendor for a Python shop: a GA Python SDK
with real verification parity, and a documented export path. The open items are concentrated in
procurement, where a short vendor exchange and portal access would likely close most of them.

Two decisions are worth making before that exchange, because they change what to ask for:

- **Is Khepri subject to a data-residency obligation?** If yes, gate 5 is decisive and no amount of
  vendor correspondence fixes it. If no, it drops to a recorded acceptance.
- **Does Khepri want its own durable subject via `external_id`?** If yes, gate 7 stops being a
  blocker and becomes an implementation note.

Both are owner judgments, and both are cheaper to settle now than after a provider is chosen.
