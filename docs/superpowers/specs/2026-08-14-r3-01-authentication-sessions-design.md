# R3-01 — Commercial authentication sessions

**Task:** `R3-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Stated output: "Session
design".

**Status:** Design note. **No code is authorized by this document.** `R3-02` onward each need the
owner's approval of that task ID.

**Baseline:** `main` @ `ab1f2e3`, 2026-08-14. Migration head `20260813_0012`, single head.

**Governed by:** `RCA-001.md` FR-003, FR-004, FR-008, FR-022, FR-027, FR-028, FR-029, FR-030,
FR-035, FR-039, FR-040; `KHEPRI-DEC-015` §4, §5, §7.

**Companion:** `2026-08-14-r2-01-membership-lifecycle-design.md`. R2 and R3 may be designed and
implemented in parallel **except** for their migrations — see §8.

---

## 1. The absence being removed

Every `session` token in `src/khepri/rca/` today is a docstring or SQLAlchemy's `sessionmaker`.
There is no session concept, which blocks FR-003's second clause, FR-007, FR-008's second clause
generally, FR-027, FR-029, FR-030, and the session halves of FR-022 and FR-035.

The chokepoint already exists and is waiting: `LifecycleService.assert_account_active`
(`lifecycle.py`) ships with no production caller, and its docstring states the requirement R3 must
honour — an implementation that copies an `enabled` flag into the session record at login
"satisfies the type checker and fails the requirement", because the copy goes stale the instant the
account is disabled.

## 2. RCA sessions and RRA beta sessions are structurally incompatible

`rca/isolation.py:14-17` records that it deliberately does not mint a `SessionScope` because RRA's
content tables carry composite FKs onto `rra_beta_sessions(owner_id, session_id)`. That is correct,
and the constraint is **stronger than that docstring claims**:

`rra/persistence.py:74` declares `owner_id: Mapped[str] = mapped_column(String, nullable=False,
unique=True)`. With `session_id` as the primary key and `owner_id` independently unique, RRA's
`owner_id ↔ session_id` relationship is strictly **1:1** — one RRA owner key can never span two
sessions.

RCA's `owner_id` is the opposite: an **organization-level, durable** key that FR-035 requires to
stay stable across sessions and active-organization switches, and which therefore must outlive any
single session.

So the two models are not merely separated by policy. Even if FR-039 permitted writing into
`rra_beta_sessions`, the unique constraint would physically refuse a second commercial session under
the same isolation key. **R3 must not attempt the bridge**; the commercial session resolves an
`owner_id` through `IsolationService`, and RRA's own session machinery is untouched.

### 2.1 A live collision risk in the identifier format

`rra/sessions.py:126` mints `f"own_{secrets.token_urlsafe(18)}"`. `rca/organizations.py:95,104`
mints `_OWNER_ID_PREFIX = "own_"` plus `token_urlsafe(18)`. **The formats are byte-identical**, and
the values are distinguishable only by which table holds them.

Two consequences R3 must respect:

- **Nothing may infer provenance from an `owner_id` string.** A validator that accepted "looks like
  an owner id" would accept either kind.
- **RCA session identifiers must use a distinct prefix.** RRA uses `ses_`; R3 should not, or the
  same ambiguity appears one layer up. Something like `cse_` (commercial session) keeps the two
  legible in evidence.

## 3. The session record

Provisional shape, deliberately minimal:

| Field | Why |
|---|---|
| `session_id` | opaque primary key, `cse_` + CSPRNG. The lookup handle |
| `account_id` | the one authenticated actor (FR-003) |
| `active_organization_id` | nullable — FR-028 requires an account with no membership to authenticate |
| `created_at`, `expires_at` | the horizon |
| `revoked_at` | nullable; set by logout, recovery (FR-007), and revocation |

**What must not be in it, and this is the load-bearing part:**

- **no role**, **no membership**, **no `owner_id`**, **no `can_act` flag**. FR-030 requires a
  membership or role change to take effect for decisions made *after* it, without the session
  ending, and FR-008 requires disablement to stop authorization without waiting for expiry. Any of
  those values cached in the row goes stale exactly when it matters.
- **no retail content** (FR-003 states this directly).

FR-027 is satisfied structurally: one nullable `active_organization_id` column cannot hold two
organizations.

### 3.1 The bearer question

`KHEPRI-DEC-015` §5 calls session identifiers bearer material, subject to "no purpose, no
retention".

RRA stores the raw `session_id` as its primary key and puts the same value in the cookie, unsigned.
That is a coherent choice for a 7-day pseudonymous beta. **R3 should store a hash instead** and keep
the raw token only in the cookie, following the pattern RCA already uses for every other secret —
credentials (FR-002) and invitations (FR-016) are both hash-only, and `credentials.py` exists to
enforce exactly this.

The cost is one hash per authorization instead of a primary-key lookup; the benefit is that a
database disclosure does not hand over live sessions. Given `RCA-001` is the commercial identity
spine and DEC-015 §5's rule is stated generally, matching the surrounding discipline is the right
default. **This is worth the owner's explicit confirmation** — see §9.

## 4. Resolution: one chokepoint, everything live

The resolution path per protected action:

1. read the cookie; absent → uniform refusal;
2. look up the session; missing, expired, or revoked → uniform refusal;
3. `assert_account_active(account_id)` → the FR-008 chokepoint, consulted **every time**;
4. if the action is organization-scoped, resolve membership and role **live** from the store;
5. only then act.

Steps 3 and 4 are what make FR-008 and FR-030 hold. Neither result may be memoized into the session
row.

**RRA is the counter-example to avoid.** Its expiry predicate is repeated at each call site
(`sessions.py:146-151`, `:161-165`, `packages.py:255-258`, `deletion.py:191-193`), and
`get_session` does not filter on expiry — so expiry is a caller obligation, which is why it is
duplicated. R3 has the chokepoint RRA lacks and should route through it rather than replicate the
scattered predicate. This is `R3-05`, and it is why the roadmap calls R3 cheaper than its task count
suggests.

## 5. The cookie boundary

Follow `rra/session_cookie.py`'s shape — one module owning the name and the refusal message, so no
second definition of a security-relevant cookie name can drift — but **with different values**:

| | RRA | RCA |
|---|---|---|
| Name | `khepri_beta_session` | must differ |
| Path | `/api/v1/beta` | the commercial surface |
| Flags | `HttpOnly`, `Secure`, `SameSite=Strict`, `Max-Age` mirroring the horizon | same discipline |

**The name must differ regardless of path.** A browser sends cookies by name and path, and a name
collision on an overlapping path is silent — any route under a shared prefix would read an RCA
cookie as a beta `session_id`.

**The cookie carries the lookup handle and nothing else.** RRA's `owner_id` never crosses the wire;
an RCA cookie carrying an organization or isolation key would be a weaker posture than the beta
system beside it.

**Refusals are uniform (FR-004, FR-022).** Absent cookie, unknown session, expired session, revoked
session, and disabled account must be indistinguishable. `report_api.py:367-368` already maps two
distinct causes to one response and is the pattern to copy. Whether to reuse RRA's
`SESSION_UNAVAILABLE` literal or define an RCA one is a small decision; **define a separate one** —
sharing it would couple two refusal vocabularies that are allowed to diverge later.

## 6. Revocation, and what must revoke

| Trigger | Effect | Requirement |
|---|---|---|
| Logout | that session | — |
| Account disabled | every session for the account | FR-008 |
| Recovery completed | every pre-existing session | FR-007 (`R5-05`) |
| Membership revoked | not the session — the *authorization*, live | FR-030 |

The last row is the subtle one. FR-030 does not require the session to end when a membership is
revoked; it requires the session to stop authorizing *in that organization*. Because step 4 of §4
resolves membership live, that falls out with no revocation write at all — and an implementation
that revoked the session instead would over-apply, logging the user out of an organization they may
still legitimately belong to.

`assert_account_active` covers the disablement row without R3 adding a second mechanism, which is
the point of it having shipped early.

## 7. Retention and the sweeper

DEC-015's matrix: an authentication session is retained "until expiry or revocation… record may
persist only until purged; it authorizes nothing from the trigger instant," and **retention never
delays revocation**.

So the sweeper purges *records*; it is never what makes a session stop authorizing. That is §4's
read path, which refuses an expired or revoked row on sight.

`R3-07` should follow the established shape exactly: one pass when called, no scheduler, a frozen
report of counts with no identifier echoed (FR-040), and — importantly — **plug into `LocalSweeper`
as an optional injected dependency**, the way `AccountRetentionSweeper` already does, rather than
standing up a parallel loop. `local/sweeper.py` records the reasoning: a retention rule whose only
caller does not exist is indefinite retention with a policy comment on top.

**Do not copy RRA's 7 days.** That is an `RRA-002` content-retention rule, not an auth-session
horizon. The session horizon is R3's to propose, and it is not governed by DEC-015 beyond "until
expiry or revocation".

## 8. Coordination with R2

**Design and domain work overlap freely. Migrations do not.** `R2-02` adds
`rca_membership_events` and `R3-03` adds the session table; head is `20260813_0012` and neither may
merge alongside the other. The later to merge re-points its `down_revision`.

Recommended order: **`R2-02` first.** R2's backfill reads columns that `R2-03` then drops, so its
window is the tighter of the two; R3's table is new and depends on nothing R2 touches.

One shared dependency worth naming: `R6` needs both — live membership resolution (R2's role model)
and a resolved actor (R3's session). Neither alone unblocks it.

## 9. Open questions for the owner

**1. Hash the session identifier at rest, or store it raw like RRA?** §3.1. Recommendation: hash
it, matching the hash-only discipline RCA already applies to credentials and invitations. RRA's raw
storage is defensible for a pseudonymous beta and less so for the commercial spine.

**2. What is the session horizon?** Not governed. A commercial product usually wants idle timeout
plus absolute lifetime; the simplest defensible starting point is a single absolute expiry with no
sliding renewal, since renewal makes "when does this session end" a moving target that FR-008's
"no dependence on session expiry" already discourages relying on.

Neither question blocks `R3-02`'s domain types. Both must be settled before `R3-03` writes schema.
