# `R5-01` — Account recovery design

> **Design output only.** This note specifies `R5-02`…`R5-06`; it implements nothing. `R5` stays
> `READY_FOR_PLAN` until the owner merges it — a branch is a proposal (`AGENTS.md`).

**Governing requirements:** `FR-005` (single-use, expiring, hash-only recovery secret, invalidated
on first successful use), `FR-006` (initiation for an unknown address is externally
indistinguishable from initiation for a known one), `FR-007` (completing recovery invalidates every
pre-existing authentication session), plus `FR-002` (credential stored only as a strong salted
hash), `FR-004` (uniform authentication failure), `FR-040` (content-free logging).

**Governing decisions:** `KHEPRI-DEC-015` §2 and its retention table — whose **Recovery request**
row settles more of this design than any other single artifact — and `KHEPRI-DEC-018`, which draws
the boundary this design must survive if an external identity provider is ever admitted.

**Measured against code at `a45b2d1`.** Every claim about an existing surface below was read from
the file named, not recalled.

---

## 1. The organizing principle: recovery ownership follows credential ownership

Recovery is not one capability. It is two, and conflating them is the mistake this section exists to
prevent.

```
(A) CREDENTIAL RECOVERY            (B) KHEPRI SECURITY CONSEQUENCES
    prove recovery authority           revoke every pre-existing session
    replace the credential             validate account state
                                       audit, content-free
    ^ belongs to whoever owns          one-use / replay protection
      the credential                   destroy the verifier
                                       ^ ALWAYS Khepri's, under every provider
```

**Today Khepri owns `FR-002` credentials, so Khepri owns (A).** `FR-002` is discharged by
`Verifier.derive` in `accounts.py`, and `KHEPRI-DEC-018` §5 admits no external provider, so the
`FR-002` path is the only authentication path. `R5` implements both halves.

**If a provider is ever admitted, (A) moves and (B) does not.** `KHEPRI-DEC-018` §2 lets an admitted
provider own "session or token issuance, refresh, and expiry", and credential recovery is an
authentication mechanic of the same kind. But `FR-007` is a statement about *Khepri's* sessions, and
no provider can make it true — a provider that resets its own password knows nothing about the rows
in `rca_sessions`.

### What this design deliberately does not build

**No `RecoveryProvider` port, no strategy interface, no plugin seam.** `KHEPRI-DEC-018` §5 admits no
provider and its §6 states the `IdentityProvider` seam "exists for vendor containment, not to build
a provider-switching framework". A second speculative seam for a provider that may never be admitted
is the premature abstraction that decision already refused once.

The boundary is preserved by **separating the two concerns in the design**, so that (B) is reachable
without (A):

> **`R5-04` implements credential replacement and `R5-05` implements the consequences as separate
> operations composed in one transaction — not as one procedure that happens to do both.**

That is the entire provision for the future. If a provider is admitted, (A)'s implementation is
replaced and (B)'s is called by the new (A). Nothing else changes, and nothing was built early.

---

## 2. The eighteen questions this note settles

### 2.1 Initiation

A caller supplies an email address. Nothing else — no account identifier, since supplying one would
be an enumeration oracle by itself.

The service canonicalizes the address (`canonical_email`, the same function `Account.create` and
`SqlAccountStore` use), looks for an enabled account, and **always returns the same response**.

### 2.2 Enumeration-resistant response (`FR-006`)

**One response shape, one status, and no timing tell.**

| Case | Externally |
|---|---|
| Enabled account exists | identical |
| No account for that address | identical |
| Account exists but is disabled | identical |
| Account exists but is a purged tombstone | identical |

`FR-006` names only the first two. The third and fourth are included because `FR-004` already
requires a failed authentication not to reveal "whether it is disabled", and an initiation endpoint
that distinguished them would reintroduce through recovery exactly what `FR-004` closes at login.

**Work must be done on the negative path.** A branch that returns immediately when no account exists
is distinguishable by response time from one that derives a verifier and writes a row. `R5-03` must
perform equivalent work in both branches — deriving a throwaway verifier at the same parameters. The
test for this asserts the negative path *does* the work, not merely that the status codes match; a
timing-blind test would pass against the defect.

### 2.3 Recovery secret creation

A cryptographically random secret, generated server-side by `secrets.token_urlsafe`. Never derived
from the address, the account identifier, or a clock — those are guessable, and `FR-005`'s
"single-use, expiring" says nothing about unpredictability, which is why it is stated here.

**Token form:** `krc1.<request_id>.<secret>`, following the two existing precedents — `kci1.` for
RCA invitations and `kiv1.` for RRA beta invitations. The prefix is a version marker, the identifier
selects the row, and the secret is verified against that row's verifier.

### 2.4 Verifier and storage model (`FR-005`, `FR-002`)

**Only a strong salted hash is stored.** `R5-02` follows `Invitation`'s shape in `invitations.py`
exactly: scrypt at RRA's parameters, a per-request salt, the digest, and no column that could hold
the secret.

**The verifier is sealed, and one door is its only source.** Project memory records the reason
directly: *shape checks cannot establish provenance* — checking a KDF's parameters is defeated by
supplying the right parameters with an arbitrary digest. `RecoverySecret` gets a single
`issue_secret`-style door, mirroring `InvitationSecret`, so a caller-supplied digest cannot be
written down rather than being validated and rejected.

**The stored row carries no plaintext address.** It references `account_id`. `FR-040` forbids the
recovery secret in logs; storing the address on the request row would also outlive the address's own
purge horizon under `KHEPRI-DEC-015` §2b.

### 2.5 Expiry

**⚠️ OWNER DECISION REQUIRED — the numeric horizon.**

`KHEPRI-DEC-015`'s table says a recovery request is retained "until first use or expiry" but sets no
number. `FR-005` requires "expiring" without saying how fast. No artifact in the repository fixes
this, and inventing one here would be recording a commitment no approved artifact supports —
the failure mode `KHEPRI-DEC-008` names when it leaves residency open.

What the design *does* fix, so the decision is narrow:

- Expiry is an absolute `expires_at` written at issuance, never a relative window evaluated at
  redemption. A relative window is unauditable after the fact.
- A `CHECK (expires_at > requested_at)` constraint, mirroring
  `ck_rca_invitation_expiry_after_issuance`.
- The boundary is expressed **once**, as `is_open_at(now)` on the domain object, following
  `Invitation.is_expired_at`. Two expressions of one boundary is how `<` and `<=` diverge.

Recommendation for the owner: **1 hour**, materially shorter than an invitation's, because a
recovery secret grants credential replacement rather than an invited role, and it is delivered to an
address rather than handed to an authenticated actor.

### 2.6 One-use semantics (`FR-005`)

**The verifier is destroyed, not flagged.** `KHEPRI-DEC-015`'s table is explicit: *"Verifier
**destroyed**; a content-free event record may remain as security evidence"*, and the trigger list
is *"Use; expiry; replacement by a newer request"*.

Destruction rather than a `used_at` flag is the stronger form, and the design commits to it: a row
whose verifier is gone cannot be replayed even if a later bug misreads its state. The event record
that remains carries no secret and no address.

**Enforced by a conditional statement, never by a read-then-write.** `R4-04` established this in
this codebase: reading a row and then writing it is a stale-snapshot defect. Redemption is a single
`UPDATE … WHERE request_id = :id AND verifier IS NOT NULL AND expires_at > :now` whose `rowcount`
decides the outcome. Whoever gets `rowcount == 1` proceeds; everyone else is refused.

`R5-06`'s evidence must isolate this: a service-level pre-check that also refuses would *shadow* the
statement, and every mutant of the `WHERE` clause would survive. That exact defect was found and
fixed in `R4-05`.

### 2.7 Credential replacement

The new credential is taken as plaintext, and only `Verifier.derive` may turn it into a stored
verifier — `Account`'s existing door. `R5-04` adds no second derivation site.

**No "current credential" check.** A recovery flow exists precisely because the actor cannot produce
the old credential.

**The new credential replaces the old atomically, in the same transaction as §2.8.**

### 2.8 Transaction boundary — the design's central claim

**One transaction contains, in this order:**

```
1. conditional UPDATE destroying the verifier      (rowcount == 1 or refuse)
2. re-read the account row FOR UPDATE              (state as of NOW, not as of initiation)
3. refuse unless account.can_act                   (FR-008)
4. write the new credential verifier
5. revoke every pre-existing session               (FR-007)
6. append one content-free recovery event          (FR-040)
```

Either all of it happens or none of it does. The ordering is load-bearing at three points:

- **Step 1 first.** Destroying the verifier before doing any work is what makes two concurrent
  redeemers resolve to exactly one winner.
- **Step 2 re-reads.** The account may have been disabled between initiation and redemption. This is
  the defect `R4-05` hit: `actor.session` was a pre-revocation snapshot, and the fix was to re-read
  inside the transaction. Recovery has the same shape and must not repeat it.
- **Step 5 inside, not after.** `FR-007` is not satisfied by a best-effort revocation that a crash
  can skip. `revoke_all_for_account` already exists (`session_persistence.py:94`) and
  `SessionService.revoke_all` wraps it (`session_service.py:130`), so `R5-05` composes an existing
  operation rather than writing a new one — it must accept the caller's transaction rather than
  opening its own.

**A credential changed without its sessions revoked is the failure this boundary exists to prevent.**
An attacker holding a stolen session cookie would survive the victim's recovery, which is precisely
what `FR-007` forbids.

### 2.9 Session revocation (`FR-007`)

Every session for the account, with no exception for the one initiating recovery. `FR-007` says
"every pre-existing", and an unauthenticated recovery flow has no session to preserve anyway.

`KHEPRI-DEC-015` §5 adds that **retention never delays revocation**: the sessions authorize nothing
from the transaction's commit, whether or not their rows are purged later.

### 2.10 Replay behaviour

A second presentation of a used token is refused, uniformly with every other refusal. The verifier is
gone, so `verifier IS NOT NULL` fails and `rowcount` is 0.

**The refusal for a used token, an expired token, a malformed token, a token for a disabled account,
and a token that never existed are one message.** `FR-004`/`FR-006`'s uniformity applies to
completion as well as initiation: a caller who can distinguish "already used" from "never existed"
learns that an account exists at that address.

### 2.11 Concurrent redemption

Two redeemers presenting the same valid token. **MUST PREVENT** — exactly one succeeds.

The conditional `UPDATE` decides it: PostgreSQL serializes the two writes on the row, the second
sees `verifier IS NULL` and gets `rowcount == 0`. No advisory lock is needed because both contend
for one identified row.

`R5-06` owes a real two-connection PostgreSQL test, `concurrency`-marked. `require_concurrency_tests.py`
fails CI if such a test skips, so the marker cannot silently disarm. **A SQLite run proves nothing
here** and the test file must say so — `R4-06`'s advisory-lock note is the precedent.

### 2.12 Disabled and purged accounts

| State | Initiation | Completion |
|---|---|---|
| Enabled | issues a request | may complete |
| Disabled | **uniform response, no request issued** | refused at step 3 |
| Purged tombstone | uniform response, no request issued | unreachable — the address is gone |

Disabled is checked at **both** ends, and both checks are needed rather than one being redundant:
initiation must not mint a usable secret for an account that cannot act, and completion must re-check
because disablement can happen in between. `FR-008` requires disablement to take effect "with no
dependence on session expiry", which applies equally to a recovery secret minted earlier.

`Account.can_act` is the single definition of "can act" — project memory records that counting rows
instead of consulting it stranded an organization. `R5` uses it and does not re-derive it.

### 2.13 Credential-change race

The account's credential changes by another path (a normal password change) while a recovery secret
is outstanding.

**Outcome: the recovery secret still works, and that is correct.** It is single-use and expiring, it
was issued to the address on the account, and using it revokes every session — including any the
other change created. Invalidating outstanding secrets on every credential change would be a
defensible alternative but requires a mechanism no requirement asks for.

**Classified: ACCEPTABLE RESIDUAL — but stated as a consequence, not a discovery.** The residual is
the *window*, not the outcome: an attacker who obtained the recovery secret can override a legitimate
password change made within the expiry window. §2.5's short horizon is what bounds it, which is a
further reason the number matters.

### 2.14 Audit and retention (`FR-040`, `KHEPRI-DEC-015`)

One append-only event per lifecycle transition, content-free.

**Never recorded:** the secret, the verifier, the old or new credential, the email address.
`KHEPRI-DEC-015` §7's never-logged list names credentials, verifiers, recovery secrets, invitation
secrets, and the login identity.

**Recorded:** the account identifier, the event kind, the timestamp, and — for a completion — the
count of sessions revoked, which is security evidence carrying no content.

Retention follows the **Recovery request** row: the verifier is destroyed at the trigger; the
content-free event may remain. Anchor the event horizon to `MembershipEvent`'s existing twelve-month
horizon rather than a fresh literal — `R4-03` set that precedent.

**⚠️ Carried gap, not this slice's to close:** no scheduler exists, so every governed horizon runs
only from the manual `sweep`. `R4-01` §8.1 assigns that elsewhere. `R5-02`'s sweeper will be wired
the same way and will be equally unenforced until a scheduler exists. Recorded so a reader does not
mistake a written sweeper for an enforced horizon.

### 2.15 Delivery boundary

**A narrow port, and no vendor selected.**

```python
class RecoveryDeliverer(Protocol):
    def deliver(self, *, address: str, token: str) -> None: ...
```

Two parameters, no template, no subject line, no provider concept. The service calls it and ignores
its return.

**Why a port here when §1 refused one for providers:** delivery is *required* for the feature to
function at all and has no implementation in the repository, whereas external identity has a
merged seam already and no admitted provider. A port for something needed now is not speculative.

**Deliberately unselected**, mirroring how `KHEPRI-DEC-008` leaves the runtime target open. A vendor
selection is an owner decision engaging the same personal-data questions `KHEPRI-DEC-018` §5 asks —
the address is disclosed to whoever delivers.

**⚠️ OWNER DECISION REQUIRED: the delivery vendor**, before `R5-03` can run outside a test.

**Failure is not distinguishable to the caller.** If delivery raises, the response is unchanged —
otherwise delivery failure becomes an enumeration oracle. The transaction has already committed;
`R5-03` calls the deliverer *after* commit, since a delivery inside the transaction would be sent
and then rolled back.

**Delayed or duplicate delivery** changes nothing: one-use is enforced at the row, so a token
arriving twice is redeemable once.

### 2.16 Future external-provider behaviour

If a provider is admitted under `KHEPRI-DEC-018` §5 and owns the credential:

- **(A) moves to the provider.** Initiation, secret, expiry, and credential replacement become its
  mechanics. `FR-002` "continues to govern any credential Khepri itself stores" — of which there
  would be none for such accounts.
- **(B) stays with Khepri, entirely.** `FR-007`'s session invalidation, `can_act`, the audit event,
  and the retention rules are Khepri's under every provider. `KHEPRI-DEC-018` §3 requires that a
  provider token "MUST NOT delay the effect of account disablement", and the same logic makes
  post-recovery revocation Khepri's.
- **The seam is not widened.** `IdentityProvider` has one method and `VerifiedIdentity` two fields
  by design. A provider-driven recovery signals Khepri through a Khepri-side operation, not through
  a new method on that Protocol.

**Not designed further here.** No provider is admitted, so anything more concrete would be built for
a vendor that may never be selected.

### 2.17 What Khepri always remains responsible for

Unconditionally, under every provider:

```
Session invalidation on recovery (FR-007)      Account activation state (can_act)
The account identity itself                    Organization membership and roles
Authorization                                  Tenant isolation
Audit events                                   Retention and destruction horizons
```

A provider may prove who someone is. It never decides what they may do.

### 2.18 `R8` recovery-UI contract

Two surfaces, and one hard rule.

| Surface | Shows |
|---|---|
| Request recovery | address field; on submit, **one** confirmation regardless of outcome |
| Complete recovery | new-credential field; on failure, **one** message for every cause |

**The rule: the UI may not distinguish outcomes the service refuses to distinguish.** `R8-01`
already records this hazard for the shell — expired, deleted, and session-unavailable collapse into
one surface because distinguishing them is the disclosure `FR-025` forbids. Recovery is the sharper
case: a "no account with that address" message is the enumeration oracle `FR-006` exists to prevent,
and it is the single most natural thing for a helpful error page to say.

The confirmation copy must not assert that mail was sent — "if an account exists, a message is on
its way" — since asserting delivery for an address with no account is a lie the UI would be telling
on every negative path.

---

## 3. Concurrency and adversarial classification

Every case, classified. No residual is invented: each one below is either derivable from a
requirement or explicitly flagged as needing the owner.

| # | Case | Classification | Basis |
|---|---|---|---|
| 1 | Nonexistent identity at initiation | **MUST PREVENT** disclosure | `FR-006`; equal work on both paths (§2.2) |
| 2 | Disabled account at initiation | **MUST PREVENT** disclosure and issuance | `FR-004`, `FR-008` |
| 3 | Purged tombstone | **MUST PREVENT** disclosure | `KHEPRI-DEC-015` §2b — address is gone |
| 4 | Expired secret | **MUST PREVENT** use | `FR-005`; `expires_at > :now` in the statement |
| 5 | Reused secret | **MUST PREVENT** | `FR-005`; verifier destroyed (§2.6) |
| 6 | Two concurrent redeemers | **MUST PREVENT** double success | conditional `UPDATE`, `rowcount` (§2.11) |
| 7 | Account disabled between initiation and redemption | **MUST PREVENT** completion | `FR-008`; step 3 re-read (§2.8) |
| 8 | Simultaneous password change | **ACCEPTABLE RESIDUAL** (the window) | §2.13 — bounded by §2.5's horizon |
| 9 | Session created during the recovery transaction | **MUST PREVENT** survival | revocation inside the transaction (§2.8) |
| 10 | Session revoked concurrently by another path | no conflict | `revoke_all_for_account` is idempotent |
| 11 | Delayed or duplicate delivery | no conflict | one-use enforced at the row (§2.15) |
| 12 | Two concurrent initiations for one account | **MUST PREVENT** two live secrets | `KHEPRI-DEC-015`: "replacement by a newer request" is a destruction trigger |
| 13 | Changed email between initiation and redemption | **MUST PREVENT** use of the old secret | the request references `account_id`; a changed address does not re-target it, and §2.12's re-read governs |
| 14 | Future external provider owns the credential | boundary preserved by design | §1, §2.16 |
| 15 | Recovery completes while the account is being purged | **OWNER DECISION REQUIRED** | see below |

**Case 15, stated rather than resolved.** `purge_if_still_eligible` nulls the address of a
long-disabled account. A recovery secret cannot be minted for a disabled account (case 2) and
completion re-checks `can_act` (case 7), so both known orderings refuse — but the *interleaving* of
purge and completion is the same shape as `R4-01` §8.2's accepted issuance-versus-purge residual,
which the owner accepted on 2026-08-18 for invitations. Whether it is equally acceptable here is the
owner's call, not a conclusion this note may reach. **Not classified as a residual**, because
project memory is explicit that an accepted residual is never invented.

---

## 4. Slice sequence

| Slice | Delivers | Notes |
|---|---|---|
| `R5-02` | `RecoveryRequest` domain + sealed verifier + table + migration | Follows `Invitation`/`InvitationSecret`. Migration must land when no other migration is in flight (§2.4, roadmap L1127) |
| `R5-03` | Uniform initiation | Equal work on both branches is the assertion (§2.2) |
| `R5-04` | One-use credential replacement | The conditional `UPDATE` is the guard (§2.6) |
| `R5-05` | Session revocation in the same transaction | Composes `revoke_all_for_account`; must not open its own transaction (§2.8) |
| `R5-06` | Replay, expiry, concurrency, logging evidence | Two-connection PostgreSQL test, `concurrency`-marked (§2.11) |

**Depends on:** `R3` session revocation — merged (`session_persistence.py:94`). Nothing in `R5`
depends on `R7`, and nothing in `R7` depends on `R5`.

## 5. Owner decisions required before `R5-02`

1. **The recovery-secret expiry horizon** (§2.5). Recommendation: 1 hour. No artifact fixes it.
2. **The delivery vendor** (§2.15). Blocks `R5-03` outside tests; the port is designed without it.
3. **Case 15's classification** (§3) — whether the purge-versus-completion interleaving is an
   acceptable residual, by analogy to `R4-01` §8.2.

## 6. What this design refuses to do

- **No `RecoveryProvider` port or strategy seam** (§1) — no provider is admitted.
- **No credential-change invalidation of outstanding secrets** (§2.13) — no requirement asks for it.
- **No distinguishable error states** anywhere (§2.2, §2.10, §2.18).
- **No second verifier-derivation site** (§2.7) — `Verifier.derive` stays the only one.
- **No numeric expiry invented** (§2.5) — the owner's to set.
- **No invented residual** (§3, case 15).
