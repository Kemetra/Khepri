# R3-09 — How external identity composes with R3's session model

**Status:** Design note. **No code is authorized by this document.** `R3-10` and `R3-03` each need
their own approval.

**Task:** `R3-09` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`, added by the task disposition
in `8e55834` (#181).

**Measured against:** `RCA-001`, `KHEPRI-DEC-018` (`dcb63da`), `KHEPRI-DEC-015`, and the merged
`R3-01` design note. Where this note and any of those disagree, they win and this note is the
defect.

---

## 1. The question

`KHEPRI-DEC-018` §2 permits an admitted provider to own "session or token issuance, refresh, and
expiry" and states that "Khepri implements none of these for accounts authenticated through an
admitted provider." Read alone, that suggests Khepri holds no session of its own.

But `R3-01` was designed and merged *before* `KHEPRI-DEC-018`, and describes Khepri minting an
opaque server-side session. Both are governing. `R3-03` cannot write schema until it is settled
which one describes the deployed shape, which is why the disposition made `R3-03` depend on this
note.

## 2. The answer, and why it is not a trade-off

**Khepri keeps its own server-side session, even when an admitted provider authenticates the
actor.**

This is not one option among several. The alternatives fail governed requirements rather than
trading off against them:

| Candidate | Fails |
|---|---|
| Provider token only, no Khepri session | `FR-007` — "Completing recovery MUST invalidate **every** pre-existing authentication session for that account." Khepri cannot enumerate, let alone invalidate, sessions it does not hold. |
| Provider token only | `FR-008` — every pre-existing session must "cease to authorize any action, with **no dependence on session expiry**". A provider token Khepri cannot revoke expires on the provider's schedule. |
| Active organization in the provider's session | `KHEPRI-DEC-018` §3 — the active organization (`FR-027`) is Khepri-authoritative, and "no provider assertion may substitute for Khepri state". |
| Active organization in a client-held claim | `FR-029` — a switch must "take effect for every subsequent authorization decision", which a client-controlled value cannot guarantee. |

`FR-007` is the decisive one. It is unsatisfiable without a server-side record Khepri can enumerate
by `account_id` and revoke, and no configuration of a provider-issued bearer token supplies that.

**§2 and this conclusion do not conflict.** §2 assigns *authentication mechanics* to the provider —
proving who the actor is, and the credential machinery behind that proof. A Khepri session is not an
authentication mechanic; it is the server-side handle for an actor Khepri has already accepted, and
it carries state (`active_organization_id`) that §3 makes Khepri-authoritative. Khepri does not
verify credentials, refresh provider tokens, or manage provider sign-in. It does hold its own
session, for reasons `FR-007` and `FR-008` state directly.

### 2.1 The composed request path

```
provider verifies identity            <- R3-11 adapter, behind the seam
        |
stable provider subject               <- R3-10 seam: (provider, subject) only
        |
(provider, provider_subject) -> account_id     <- local lookup, no provider call
        |
Khepri mints its own session          <- R3-04, cse_ cookie
        |
        v
   [R3-01 §4 steps 2-5, unchanged]
        |
session lookup -> assert_account_active LIVE -> membership LIVE -> role LIVE -> ALLOW / DENY
```

**The seam is additive, and no existing `R3` task changes shape.** `R3-02` (merged), `R3-03`,
`R3-04`, and `R3-06` all stand as designed. Everything external identity adds happens *before*
`R3-01` §4 step 1; from the cookie onward the path is identical whether the actor authenticated
through `FR-002` credentials or through an admitted provider. `R3-06`'s cookie boundary is Khepri's
own `cse_` cookie in both cases.

An earlier framing of mine said four tasks were shape-affected. That was wrong and is retracted
here.

## 3. Where the provider link lives

This is the question that remains genuinely open. Three placements:

**A. A dedicated `rca_external_identities` table.** Keyed `(provider, provider_subject)`, carrying
`account_id`. **Recommended.**

**B. Columns on `rca_accounts`.** A `provider` / `provider_subject` pair on the account row.

**C. On the session row.** The provider subject recorded per session.

**Why A.** `KHEPRI-DEC-018` §7 requires that "duplicate links fail closed" and that "an existing
link MUST NOT silently move between accounts". Both are uniqueness properties, and both are
enforceable by the database in A: a unique constraint on `(provider, provider_subject)` makes a
duplicate link a write failure rather than an application check that can be forgotten, and
re-pointing requires an explicit `UPDATE` that no ordinary path issues.

B expresses one link per account, which is adequate today and wrong soon: an account that later adds
enterprise SSO alongside a password provider needs two links to one account, and B would require a
migration to express what A expresses from the start. B also puts a mutable provider identifier on
the row `KHEPRI-DEC-015` §2b minimizes to a tombstone, mixing two lifecycles on one row.

C is unsound. A link is durable identity; a session is ephemeral. Recording the subject per session
means the mapping vanishes when sessions expire, so the *same* human returning tomorrow cannot be
recognized — and `FR-001`'s durable account would depend on session lifetime.

### 3.1 The foreign key, and why this case differs from `rca_membership_events`

`rca_membership_events` deliberately carries **no** foreign key, because a `RESTRICT` FK would make
the account purge fail while any event referenced it — inverting the horizon relationship where the
24-month tombstone must outlast the 12-month audit event.

**That reasoning does not apply here, and the difference is verifiable rather than assumed.**
`purge_if_still_eligible` nulls the identity columns (`email`, `credential_salt`,
`credential_digest`, the KDF parameters) and **keeps the row**; `KHEPRI-DEC-015` §2b calls the
result "an opaque tombstone" holding "an opaque account identifier and the disablement timestamp".
Nothing in `src/khepri/rca/` deletes an `AccountRow`. So `account_id` survives every horizon, and a
`RESTRICT` foreign key onto `rca_accounts.account_id` can never block a purge — there is no delete
to block.

`rca_external_identities` should therefore carry the FK, matching `fk_rca_membership_account`.

### 3.2 What the link table holds, and what it must not

| Column | Why |
|---|---|
| `provider` | which provider issued the subject. Opaque to Khepri |
| `provider_subject` | the verified token's `sub`. Opaque; carries no meaning beyond identity |
| `account_id` | FK onto `rca_accounts`, `RESTRICT` |
| `linked_at` | when the link was established |

**Not held:** email (`§7`: "Email is not the durable identity key"), any provider organization,
role, or permission claim (`§4`), and no provider access or refresh token — `§5` gate 1 admits only
enumerated personal-data classes, and a stored provider token would be both a new class and a
credential Khepri has no reason to hold.

`provider_external_id` — the provider-side field carrying a Khepri-controlled anchor, per the merged
Clerk evaluation — is **not** a column here. It is Khepri's identifier written *into the provider*,
useful at exit; Khepri already knows it, because it is `account_id`.

### 3.3 Consequence for `R3-03`

**`R3-03` carries two tables, not one:** the session table and `rca_external_identities`. One
migration, one head. Stated here so `R3-03` does not discover it mid-slice.

Whether the link table ships in `R3-03` or waits for `R3-11` is `R3-03`'s call. Shipping it early
costs an unused table; shipping it late costs a second migration and re-opens the single-head
window. The first is cheaper.

## 4. Session lifetime is Khepri's, independent of any provider token

**Rule:** the Khepri session's `expires_at` is set by Khepri policy and has no relationship to a
provider token's lifetime. Stated provider-neutrally, because `R3-09` must not depend on any
particular vendor's behaviour.

Two consequences worth naming, because they look like defects and are not:

- **A Khepri session may outlive a provider token.** Provider tokens are typically short and
  auto-refreshed. Khepri does not observe refresh and must not depend on it — `KHEPRI-DEC-018` §5
  forbids any provider event stream from being a correctness dependency.
- **A revoked provider session does not immediately end a Khepri session.** Khepri learns of
  provider revocation only if it asks, and per the merged Clerk evaluation it should not ask on
  every request: a per-request provider lookup improves no Khepri requirement while adding latency
  and an external dependency on the authentication path.

**What that exposure is, stated precisely.** *Authorization* staleness is zero:
`assert_account_active`, membership, and role are read live on every protected action, so a disabled
account or revoked membership stops authorizing on the next request regardless of any token.
*Identity* staleness is non-zero and bounded by Khepri's own session lifetime — an actor whose
provider session was revoked, but whose Khepri account and memberships are untouched, remains
identified until their Khepri session expires or is revoked.

If a future requirement demands faster identity revocation, the levers are a shorter Khepri session
lifetime or a targeted provider check on sensitive operations — not a blanket per-request call. No
such requirement exists in `RCA-001` today.

## 5. Unlinking, and what survives it

`KHEPRI-DEC-018` §7: "Deleting an external identity does not delete Khepri business state. The
account, its memberships, its audit events, and the final-owner invariant survive. The account
becomes unauthenticatable until relinked; it does not become ownerless."

So removing a link row:

- leaves `rca_accounts`, `rca_memberships`, `rca_membership_events`, and isolation scopes untouched;
- does **not** trigger `FR-013` — the account is not disabled, and `count_owners` reads account
  state through `can_act`, which unlinking does not change;
- should revoke that account's live sessions, by the same reasoning as `FR-007`: an actor who can no
  longer authenticate should not continue to act on a session minted earlier. `R3-04` owns that.

This last point is a **recommendation, not a governed requirement** — no `RCA-001` clause names
unlinking. It is recorded so `R3-04` decides deliberately rather than by omission.

## 6. What this note does not settle

- **The seam's concrete signature.** `R3-10`. `KHEPRI-DEC-018` §6 fixes what it may expose; the
  types are implementation.
- **Any provider's admission.** `KHEPRI-DEC-018` §5 gates that, and the Clerk evaluation records
  four outstanding vendor-evidence gates.
- **Column types, indexes, and the migration.** `R3-03`.
- **Linking and unlinking operations.** `R3-04`. This note fixes what the state must satisfy.
- **The cookie.** `R3-06`, unchanged by this note.

## 7. Open question for the owner

**One, and it is small.** Should `R3-03` ship `rca_external_identities` alongside the session table,
or should it wait for `R3-11`?

Recommendation: **ship both in `R3-03`.** The cost is one unused table until a provider is admitted;
the alternative costs a second migration and re-opens the single-head coordination window that `R2`
and `R3` have had to serialize around twice already.

Nothing else here needs an owner decision. The two `R3-01` §9 questions — hashing the session
identifier and the session horizon — were settled before `R3-02`, and `R3-02` implements them.
