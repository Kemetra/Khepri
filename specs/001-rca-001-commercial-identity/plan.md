# RCA-001 — Technical plan

Plan for `governance/specifications/RCA-001.md`. This plan is **not** an authorization to
implement; see "Governance readiness" below and `analyze.md` §5.

Architecture was inspected before deciding anything. Every decision below names the existing code
or governance it is constrained by.

---

## 1. Governance readiness (Phase D)

Four states are kept distinct. Repository rules place this plan at state 2.

| State | Reached? | Evidence |
|---|---|---|
| Spec written | **yes** | `governance/specifications/RCA-001.md` |
| Spec reviewed | **yes** | `checklist.md`, 5 defects found and resolved |
| Spec approved | **no** | Registry entry is `draft`; no `approved_by`/`approved_at`/`approval_ref` |
| Implementation authorized | **no** | Three independent blockers — §5 below |

**Is planning permitted before approval?** Yes. `AGENTS.md:14-15` forbids adding *product
application code* ahead of an approved specification; it does not restrict planning. Khepri's own
history confirms the pattern: `docs/superpowers/plans/` holds plans written before their artifacts
were accepted. Planning documents carry no authority and change no registry.

**What approval evidence would be required?** Per Constitution II and VIII, either the named human
authority `AHMED-SHAABAN` approving directly, or a named delegate acting under a **recorded,
unexpired** delegation naming this artifact. `governance/delegations/DEL-001..005` are all
session-scoped with `expires_at` on or before `2026-08-06`; today is `2026-08-08`; none names
`RCA-001`. **No delegated authority exists for this work.**

---

## 2. Domain model

Framework-free, mirroring `src/khepri/rra/sessions.py`'s style: frozen slotted dataclasses, a
`Protocol` store, and a service holding the rules. Proposed home: `src/khepri/rca/`, a sibling of
`rra/` — `FR-039` requires RRA to remain independently testable, and a sibling package keeps the
import direction one-way (`rca → rra`, never the reverse).

| Entity | Fields (product-level) | Notes |
|---|---|---|
| `Account` | `account_id`, `email`, `credential_salt`, `credential_digest`, `disabled_at` | `FR-002`: digest only. `account_id` opaque |
| `Organization` | `organization_id`, `display_name`, `owner_scope_id` | `owner_scope_id` is the bridge — §5 |
| `Membership` | `membership_id`, `account_id`, `organization_id`, `role`, `revoked_at` | Unique on `(account_id, organization_id)` where not revoked |
| `Invitation` | `invitation_id`, `organization_id`, `email`, `role`, `secret_salt`, `secret_digest`, `expires_at`, `accepted_at`, `revoked_at` | Shape copied from `rra.sessions.Invitation` |
| `Role` | enum: `owner`, `member` | `FR-015`; exactly two |
| `AuthSession` | `auth_session_id`, `account_id`, `active_organization_id`, `created_at`, `expires_at`, `revoked_at` | Server-side; §4 |
| `AuthorizationContext` | `account_id`, `organization_id`, `role` | Resolved per action, never stored; §4 |

`AuthorizationContext` is deliberately **not** persisted. It is recomputed from current membership
on every protected action, which is what makes `FR-030` (revocation bites immediately) true by
construction rather than by discipline.

---

## 3. Persistence

Smallest change compatible with the existing architecture. `src/khepri/rra/persistence.py` uses
SQLAlchemy 2.0 declarative `Mapped[...]` rows against Alembic migrations under
`migrations/versions/`, latest `20260730_0009_rra_report_deliveries.py`.

- **One new Alembic migration** adding five tables: `rca_accounts`, `rca_organizations`,
  `rca_memberships`, `rca_invitations`, `rca_auth_sessions`.
- **A separate `rca` declarative `Base`**, not RRA's. Sharing a `Base` would couple the two
  families' metadata and let an `rca` model break an `rra` test — `FR-039`.
- **No change to any existing table, row class, or migration.** `FR-037` requires the RRA controls
  be preserved with their tests unmodified; touching RRA's schema would put that in doubt.
- **Uniqueness at the database, not in application code**: unique index on `rca_accounts.email`
  (`A-1` is a product rule, so it is enforced where races cannot defeat it) and a partial unique
  index on `(account_id, organization_id)` for non-revoked memberships.
- **Final-owner protection is a database constraint plus a service check**, not a service check
  alone. Two concurrent "remove the other owner" requests both pass an application-level count.
  A conditional delete guarded by a re-count in the same transaction is the minimum;
  `T-011` tests it concurrently.

**Migration collision warning, per `AGENTS.md:24-28`.** This migration's `down_revision` is
`20260730_0009`. If any other slice lands a migration first, this one re-points rather than
merges. Stated here before it happens, as required.

---

## 4. Authentication

**Existing behaviour was evaluated first.** `src/khepri/rra/session_cookie.py` establishes that
Khepri already carries an **opaque server-side session identifier in a cookie**, with the domain
(`sessions.py`) kept free of any web framework and the transport isolated in its own module. Its
docstring states the reasoning: "RRA-001 governs what a session is; how one is transported is a
separate decision."

**Direction: extend that pattern. Opaque server-side sessions, no self-contained token.**

Justification against repository constraints, not preference:

1. `FR-030` and `FR-008` require revocation and disablement to take effect **without waiting for
   expiry**. A self-contained signed token asserting role and organization is authoritative until
   it expires; honouring revocation would require a server-side revocation list checked on every
   request — which is the opaque-session design, reached by a longer route.
2. `FR-002` requires hash-only credential storage. `rra.sessions.InvitationService._digest`
   already implements `scrypt` at `n=2**14, r=8, p=1, dklen=32`. Reusing that shape adds no new
   cryptographic decision.
3. Constitution VII (least data) favours an opaque identifier that reveals nothing over a token
   carrying account and organization claims to the client.

**No external identity provider is proposed.** `RCA-001` `A-4` leaves this open at the product
level. Adopting one would introduce a vendor dependency, a data-processor relationship engaging
Constitution VII, and a deployment dependency while `KHEPRI-DEC-008` is still `proposed`. If one is
later wanted, `FR-002`..`FR-007` are written so that it is substitutable without a spec change.

---

## 5. Authorization — one canonical path

`FR-026` requires a single checkpoint. The architecture must make cross-organization bypass
difficult *by construction*, not by reviewer vigilance.

```
request
  → resolve auth session          (opaque id → AuthSession; invalid ⇒ deny)
  → resolve account               (disabled ⇒ deny)
  → resolve active organization   (absent where required ⇒ deny)
  → resolve current membership    (none/revoked ⇒ deny)          ← reads live state
  → AuthorizationContext(account_id, organization_id, role)
  → require_role(context, needed)                                 ← the only permit
  → resolve isolation scope       (§6)
  → RRA capability
```

Design rules that carry the guarantee:

- **`AuthorizationContext` is unconstructable outside the resolver.** No handler builds one from a
  request parameter. This is what stops "pass the org id from the query string" bypasses.
- **The `RRA` capability layer is reached only with an isolation scope**, never with an
  organization id. A handler that skips the resolver has nothing to call `RRA` with — `FR-026`'s
  "unreachable rather than permitted."
- **Membership is read live at step 4**, never cached into the session — `FR-030`.
- **One refusal for every denial cause.** `session_cookie.SESSION_UNAVAILABLE` is the existing
  precedent ("One sentence for every cause… because RRA-001 refuses without revealing which check
  failed"). `RCA` adds one equivalent constant and no second wording — `FR-004`, `FR-025`.

---

## 6. RRA bridge

The highest-risk element. Designed against the **actual** contract, read at
`src/khepri/rra/sessions.py:38-42` and `src/khepri/rra/deletion.py:149`.

```
authenticated account + active organization
        ↓  (resolver, §5)
AuthorizationContext
        ↓  organization.owner_scope_id
SessionScope(owner_id=<organization's opaque owner id>, session_id=<upload session>)
        ↓  unchanged
existing RRA capabilities
```

**The organization maps to `owner_id`, not the account.** `clarify.md` C-11 records the evidence:
storage keys are `owners/{owner_id}/sessions/{session_id}/`, and `assert_same_scope` compares the
whole frozen `SessionScope` by equality. Mapping an account would place colleagues under different
`owners/` prefixes and make shared organizational content unreachable without modifying isolation
code `FR-037` forbids touching.

Consequences that make this safe:

- **`sessions.py` is not modified.** `assert_same_scope`, `SessionScope`, and every existing
  isolation test keep working unchanged — which is precisely `KHEPRI-DEC-014` §2's survival
  obligation and `FR-037`.
- **`owner_scope_id` is generated opaquely** with the existing `own_{token_urlsafe(18)}` shape and
  is **never derived from** organization name, slug, or email — `FR-032`, `FR-033`. A derivation
  would make a commercial identifier an analytical key by the back door.
- **One organization ⇒ one stable `owner_scope_id`** for its lifetime, so scope survives switching
  and membership change — `FR-035`.
- **Commercial identity is not analytical authority**: `RRA` receives a `SessionScope` and learns
  nothing about accounts, roles, or organizations — `FR-036`.

---

## 7. Security

| Concern | Approach | Requirement |
|---|---|---|
| Credential handling | `scrypt` salted digest, reusing `rra.sessions` parameters | `FR-002` |
| Session creation | Opaque high-entropy id, server-side record | `FR-003` |
| Session expiry | Absolute expiry stored on the record, checked at resolve | `FR-003`, `FR-022` (Scenario 19) |
| Session revocation | `revoked_at` checked at resolve; set by disable and recovery | `FR-007`, `FR-008` |
| Account recovery | Single-use hashed expiring secret; invalidates all sessions | `FR-005`..`FR-007` |
| Invitation lifecycle | Hashed secret, expiry, single acceptance, uniform refusal | `FR-016`, `FR-017` |
| Privilege change | Live membership read per action; no cached role | `FR-030` |
| Final-owner protection | Transactional re-count guarding remove, downgrade, disable | `FR-013` |
| Object-level authz | Scope resolved from membership, never from a supplied id | `FR-023` |
| Organization switching | Validated against current membership before taking effect | `FR-029` |
| Replay | Single-use invitation and recovery secrets, hash-compared | `FR-017` |
| Audit logging | Content-free: opaque ids, timestamps, prior/next role only | `FR-014`, `FR-040` |
| Enumeration | One refusal wording per surface | `FR-004`, `FR-006`, `FR-025` |

Timing note: credential and secret comparison uses `hmac.compare_digest`, as
`rra.sessions.verify_secret` already does.

---

## 8. Compatibility

- No existing RRA behaviour changes. The beta invitation path continues to work as specified by
  `RRA-001`, and this plan adds no branch to it.
- No existing table, migration, row class, or test is modified.
- The private beta remains a governed product boundary — `KHEPRI-DEC-014` §Consequences: "`RRA`
  remains `active` with every specification under it unchanged."
- New API surfaces are additive and carry their own cookie name; the existing
  `khepri_beta_session` cookie is untouched.

---

## 9. Testing

| Layer | Coverage |
|---|---|
| Unit | Each domain rule in isolation: hashing, expiry, single-use, role powers, final-owner |
| Authorization matrix | `{owner, member, non-member, unauthenticated}` × every protected action; every cell asserts permit or fail-closed |
| Cross-org isolation | Read and mutate attempts across organizations; refusal indistinguishable from nonexistence |
| Session/revocation | Disablement and revocation take effect on the next action without session end |
| Invitation | Expiry, replay, revocation, acceptance before account exists |
| Persistence | Uniqueness under concurrency; final-owner race; migration up/down |
| API | Direct endpoint access bypassing any UI; missing and conflicting scope |
| Bridge | Two orgs ⇒ two distinct scopes; scope stability; no commercial identifier in a scope |
| RRA regression | Full existing RRA suites pass unmodified, with no account or organization present |

---

## 10. What this plan does not do

No billing, workspace, retention, multi-dataset, Seshat, AI, forecasting, agency, scheduling,
public-signup, or deployment work. No organization or account deletion. No RRA refactoring. No
role beyond `owner` and `member`.
