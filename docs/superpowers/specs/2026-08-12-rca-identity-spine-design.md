# RCA-001 Slice 1 — Commercial Identity Spine and Isolation Bridge

> ## ⚠️ AMENDED AFTER IMPLEMENTATION
>
> Implemented in PR #148. Three amendments were made during review; **the shipped code is
> the authority where it disagrees with this document.**
>
> 1. **Account disablement is NOT in this slice.** The data flow below shows
>    `Account(..., disabled=False)` and the testing section references a disabled account.
>    Disablement was implemented, reviewed, and removed (`9507580`): it requires
>    `KHEPRI-DEC-015`'s 24-month retention horizon and opaque tombstone, `FR-008`'s session
>    revocation, and `FR-013`'s final-owner guard, none of which this slice scopes. Tracked
>    in issue #149. FR-004 uniformity is therefore asserted across the missing-account and
>    wrong-credential paths, not the disabled path.
> 2. **Email canonicalization was missing.** `RCA-001` A-1 requires one identity per address,
>    but a case-sensitive unique constraint admitted `owner@example.test` beside
>    `owner@EXAMPLE.TEST`. Both storage and lookup now canonicalize.
> 3. **FR-004 uniformity is asserted by call shape.** Every authentication path issues
>    exactly one `DEFAULT_KDF` scrypt call. Wall-clock assertions proved flaky on shared CI
>    runners, and summing nominal `n*r*p` cannot detect that scrypt is memory-hard.
>
> **Date:** 2026-08-12
**Specification:** `RCA-001` (active in `governance/registry.yaml`)
**Requirements covered:** FR-001, FR-002, FR-004, FR-009, FR-010, FR-014, FR-031, FR-032,
FR-033, FR-035, FR-037, FR-039, FR-040
**Scenarios covered:** 1 (account creation), 5 (organization creation), 12 (multi-organization
membership — scope non-merging), plus the negative invariants behind 3 and 14

---

## Why this slice

`RCA-001` carries 40 functional requirements and 20 scenarios. That is several slices of work.
This slice is chosen to settle the one architectural question every later slice inherits: **how an
organization maps to a stable opaque isolation scope without any commercial identifier being
derivable from it.**

`governance/families/RCA.md` excludes "product implementation outside a small, verifiable slice
linked to an active `RCA` specification and satisfying that specification's preconditions." This
document defines that slice. RCA-001's four implementation preconditions were verified met on
2026-08-12 (spec active, `KHEPRI-DEC-008` active, `KHEPRI-DEC-015` active, and this bounded slice).

## The problem in the existing code

`src/khepri/rra/sessions.py:126` mints the isolation key inline when an invitation is redeemed:

```python
session = BetaSession(
    owner_id=f"own_{secrets.token_urlsafe(18)}",
    session_id=f"ses_{secrets.token_urlsafe(18)}",
    ...
)
```

`SessionScope(owner_id, session_id)` is the isolation boundary key, and object storage is keyed
`owners/{owner_id}/sessions/{session_id}/`.

This trivially satisfies FR-032 and FR-033 — nothing is derivable from a random token — but it
**cannot** satisfy FR-035, which requires one organization to resolve to a *stable* scope across
sessions, across active-organization switches, and across membership changes. There is no durable
record tying anything to an `owner_id`.

## Design decision: allocate-and-store, never derive

The scope is a **random opaque token allocated once per organization and stored**, never computed
from organization data.

```
Organization  ──1:1──>  IsolationScope(owner_id)   # allocated at org creation, immutable
```

- **FR-032 / FR-033** hold by construction. There is no function from email, organization name,
  slug, account identifier, or human-readable identifier to `owner_id`, because `owner_id` is
  drawn from `secrets.token_urlsafe`. Nothing to leak and nothing to reverse.
- **FR-035** holds because the mapping is persisted and immutable once written. Distinct
  organizations get independently drawn tokens; one organization keeps its token for life.

The rejected alternative was deriving the scope as `HMAC(key, organization_id)`. It is stable and
looks elegant, but it makes the scope a *function of* a commercial identifier. FR-032 forbids the
identifier being "used as any component of" the key, and a keyed derivation is exactly that. It
also fails closed badly: leak the key and every scope becomes linkable to its organization. The
allocate-and-store approach costs one indexed lookup and is unconditionally safe.

Reusing the existing `own_` prefix and `token_urlsafe(18)` width keeps RCA-minted scopes
indistinguishable from beta-minted ones, so no downstream code can branch on origin.

## Scope resolution returns `owner_id` only — not a `SessionScope`

This is forced by the existing schema, and the constraint is worth recording because the FR-031
wording ("map to the governed opaque isolation scope") reads as though returning a full
`SessionScope` were the natural shape.

`src/khepri/rra/persistence.py:102` and `:142` (and the equivalents in `job_persistence.py` and
`delivery_persistence.py`) declare composite foreign keys:

```python
ForeignKeyConstraint(
    ["owner_id", "session_id"],
    ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
    ondelete="RESTRICT",
)
```

Every RRA content row therefore requires a **real `rra_beta_sessions` row**. An RCA path that
minted its own `session_id` would have to insert into RRA's own table to satisfy those FKs, which
would couple the packages in exactly the direction FR-039 forbids.

**Decision:** `resolve_scope(account_id, organization_id) -> str` returns the durable `owner_id`
and nothing else. It does not construct a `SessionScope`, and this slice creates no sessions.
Binding an organization's `owner_id` to an authenticated session is FR-027's "at most one active
organization at a time" and belongs to the session slice, which is also where the beta-session
lifetime question (7-day content expiry vs. RCA-001's persistent workspaces) gets settled.

## FR-039: RRA stays independently testable

`redeem()` keeps minting its own random `owner_id` for invite-bound beta sessions. This slice adds
a **second, parallel** producer of a durable `owner_id`. Consequences:

- `SessionScope` is **not modified**. No new field, no new type.
- `src/khepri/rra/*` is **not modified** in this slice.
- No RCA code writes to any `rra_*` table.
- Existing RRA tests pass unmodified with no account, organization, or membership present.

**Import direction is RCA → RRA only, never the reverse.** No module under `src/khepri/rra/` may
import from `src/khepri/rca/`. A later slice reversing this breaks FR-039's independent
testability, so it is stated here as a review trip-wire and asserted by a test.

The two paths converge on the same `owner_id` shape, which is what lets RRA remain oblivious.

## Components

New package `src/khepri/rca/`, following the `rra` layout (`Protocol` stores, frozen dataclasses,
a separate SQLAlchemy persistence module).

| Module | Purpose | Est. lines |
|---|---|---|
| `accounts.py` | `Account` dataclass; create, authenticate, disable. scrypt credential hashing. | ~180 |
| `organizations.py` | `Organization`, `Membership` (with FR-014 attribution); create-with-owner atomically. | ~200 |
| `isolation.py` | `IsolationScope`; allocate-once, resolve-by-organization. The bridge. | ~120 |
| `stores.py` | `Protocol` definitions for the three stores above. | ~90 |
| `persistence.py` | SQLAlchemy rows + store implementations for local Postgres. | ~320 |
| `errors.py` | Uniform, content-free refusal exceptions and their single message constants. | ~50 |

All well inside the 400-line preference and the 800-line ceiling.

### Credential handling (FR-002)

Reuse the **idiom** at `sessions.py:100-113` — `hashlib.scrypt` with a per-record salt, verified
with `hmac.compare_digest`. Introducing a second hashing library would be gratuitous.

**But raise the work factor deliberately, do not inherit it.** That call site uses `n=2**14`,
calibrated for a 32-byte `secrets.token_urlsafe` invitation secret — an input with ~192 bits of
entropy, where the hash exists to protect a stored digest rather than to resist guessing. FR-002
credentials are human-chosen and have a different threat model: offline brute force against a
low-entropy secret. This slice uses **`n=2**15, r=8, p=1, dklen=32`** with a 16-byte salt, the
higher cost being justified because a human credential is guessable and an invitation token is not.

Recording the parameters in the design is deliberate: a work factor chosen by copy-paste is a
decision made by omission. Store `n`, `r`, `p` alongside each digest so the factor can be raised
later without invalidating existing records.

**`maxmem` must be passed explicitly at this work factor.** scrypt requires `128 * n * r` bytes —
64 MiB at `n=2**15, r=8` — which exceeds OpenSSL's 32 MiB default, so `hashlib.scrypt` raises
`ValueError("[digital envelope routines] memory limit exceeded")` without it. Measured on this
machine: ~121 ms per hash at `n=2**15` versus ~65 ms at `n=2**14`. The existing invitation call
site very likely uses `n=2**14` because it sits under the default limit. Every authentication pays
the 121 ms, which is acceptable for a login path and is the point of the cost.

Credentials are stored as salt + digest only — no reversible form, never logged, never returned.

### Uniform refusals (FR-004, FR-034, FR-040)

Follow the `_INVITATION_FAILURE` single-constant pattern. One module-level message per refusal
class, raised identically regardless of which check failed:

```python
_AUTHENTICATION_FAILURE = "Credentials are invalid or unavailable."
```

Authentication failure must not disclose whether the account exists, is disabled, or had a wrong
credential. Cross-scope access raises the existing content-free `PermissionError` shape. Log lines
carry identifiers only — never an email, organization name, or credential material (FR-040).

## Data flow

```
create_account(email, credential)
    -> Account(account_id, email, salt, digest, kdf_params, disabled=False)

create_organization(name, creator_account_id)
    -> atomically: Organization(organization_id, name)
                 + Membership(organization_id, account_id, role="owner",
                              changed_by=creator_account_id, changed_at=now)
                 + IsolationScope(organization_id, owner_id="own_<random>")

resolve_scope(account_id, organization_id) -> str
    -> verify membership exists, else content-free refusal
    -> return the stored owner_id
```

`resolve_scope` is the only function that returns an `owner_id`, making it the single auditable
choke point for the FR-031 mapping and the natural attachment point for the later FR-026
authorization checkpoint.

### FR-014 attribution is included, not deferred

FR-014 requires every membership or role change to record which authenticated account made it.
FR-010 creates a membership, so the requirement applies to this slice. `Membership` therefore
carries `changed_by` and `changed_at` from the start — at creation, `changed_by` is the creator's
own account id (self-attributed).

This is included rather than deferred because adding an attribution column now is a field, while
retrofitting it after rows exist is a migration.

## Out of scope for this slice

Deferred, each to its own slice:

- **Invitations** (FR-016–020).
- **The `member` role and role changes** (FR-015). FR-014's attribution mechanism ships here; the
  role *transitions* it attributes ship with the membership slice.
- **Membership revocation and the FR-013 final-owner guard.** Creation cannot produce a
  zero-owner organization, so there is nothing for the guard to protect until revocation exists.
  It is *not* claimed as partially covered here.
- **Authenticated sessions, active-organization switching, and the authorization checkpoint**
  (FR-021–030) — including binding an `owner_id` to a session and settling the beta 7-day content
  expiry against RCA-001's persistent workspaces.
- **Recovery** (FR-005–007), pricing and entitlements, and the FR-036 fact-package consumption path.

## Testing

Test-driven, per `superpowers:test-driven-development`. Tests precede implementation.

**Invariant tests (the ones that matter):**

1. **FR-032/FR-033 negative test** — for a set of organizations built with adversarial names,
   slugs, and emails, assert no commercial identifier appears as a substring of the resolved
   `owner_id`, and that `owner_id` is not reproducible from any of them.
2. **FR-035 stability** — one organization resolves to the same `owner_id` across repeated
   resolutions and across membership additions.
3. **FR-035 distinctness** — two organizations, including two with *identical names*, resolve to
   different `owner_id`s. Scopes do not merge for an account holding both memberships (scenario 12).
4. **FR-039 regression** — the existing RRA suite runs green with no RCA tables populated.
5. **FR-039 import direction** — assert no module under `src/khepri/rra/` imports from
   `khepri.rca`, so the dependency can only ever point one way.
6. **FR-004 uniformity** — authentication failure for a nonexistent account, a disabled account,
   and a wrong credential produce byte-identical error messages.
7. **FR-002** — the stored record contains neither the plaintext credential nor any reversible
   form, and the recorded `kdf_params` match the chosen work factor.
8. **FR-010 atomicity** — a failure midway through organization creation leaves no organization,
   no membership, and no scope.
9. **FR-014 attribution** — the membership created by FR-010 records `changed_by` and `changed_at`.

Stores are exercised twice: against an in-memory implementation for unit tests and against local
Postgres for integration, matching how RRA tests its persistence.

## Verification gate

```
./.venv/Scripts/python.exe -m khepri_gov.cli validate
./.venv/Scripts/python.exe -m pytest -q      # 1561 passed, 9 skipped baseline
./.venv/Scripts/python.exe -m ruff check src/ tests/
```

Do **not** run `ruff format` — CI has no format gate and the local ruff is version-skewed.
CodeScene pre-flight with `analyze_change_set` against a freshly fetched `origin/main`; every file
here is new, so all of them will be scored.

## Constraints acknowledged

- **AWS is frozen on cost.** Local Postgres only. Nothing in this slice provisions or assumes cloud
  infrastructure.
- **No weakening of RRA controls (FR-037).** Opaque identifiers, isolation, and deletion behaviour
  are untouched; this slice only adds a durable producer of an already-existing key shape.
- **RCA performs no retail calculation (FR-036).** Nothing here computes a retail fact.
