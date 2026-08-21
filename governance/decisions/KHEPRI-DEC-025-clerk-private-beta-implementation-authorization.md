# KHEPRI-DEC-025: Authorization for the merged Clerk private-beta implementation

> Active. **Supersedes `KHEPRI-DEC-024`**, which is retired by this record and which itself retired
> `KHEPRI-DEC-018`. Both remain historical and must not be edited to match this successor.
>
> `active` is the only non-retired state the registry admits (`validator.py:15`), and a branch is a
> proposal until the owner merges it (`AGENTS.md`). This record is therefore written in its merged
> form and is **not governing until that merge** — the header states the state it will hold, not a
> claim that it already holds it.

## Context

`KHEPRI-DEC-024` (`f5afc00`) provisionally admitted Clerk for development and an invite-only,
non-paying private beta. It was a **risk-acceptance** record: it settled which provider is tolerated,
for which population, over which data classes, with which accepted evidence gaps, and under which
hard stops. It deliberately authorized no code.

`#240` then merged the implementation (`15a8175`). A post-merge audit of fresh `main` found the
implementation **conformant to every boundary `-024` drew** and found no functional or security
defect across eleven capabilities and five absence checks. It also found that `-024` does not
authorize it, and says so twice in terms that are refusals rather than silence:

> **`-024` Context, line 32:** "This record authorizes neither an implementation nor an assumption
> that the existing schema is sufficient."

> **`-024` §14:** "No Clerk SDK, dependency, secret, environment variable, adapter, route,
> middleware, UI, schema, migration, or production code." … "No provider-backed account creation or
> linking implementation." … "No conclusion that the existing persistence model needs no migration."

> **`-024` Consequences:** "`R3-11`'s governance dependency can be satisfied provisionally, but
> implementation **must not begin** before the provider-backed account capability and persistence
> questions in the companion design are resolved."

Every category the first bullet names is present on `main`: the dependency `clerk-backend-api>=7,<8`
(`pyproject.toml`), six environment variables (`runtime/config.py:30`–`:35`), the adapter
(`runtime/clerk_identity.py`), the route (`runtime/external_auth_api.py:70`), migration
`20260821_0019`, and the provider-backed account-and-link path (`rca/persistence.py:621`).

**This record closes the authorization gap rather than reopening the engineering question.** The two
preconditions `-024`'s Consequences named are answered by merged code, so the condition it attached
to `R3-11` is satisfied in fact:

1. **The provider-backed account capability exists.** `Account._for_external_identity`
   (`rca/accounts.py:140`) builds an account with no local verifier, and
   `add_account_with_external_identity` (`rca/persistence.py:621`) commits the account row and its
   `(provider, provider_subject)` link in **one** transaction, returning `False` on `IntegrityError`
   so a duplicate link leaves no orphan.
2. **The effective-owner predicate no longer requires a local credential.**
   `_effective_owner_conditions` (`rca/persistence.py:797`) reads
   `or_(credential_digest IS NOT NULL, external_identity_exists)`, where the second term is a
   correlated `EXISTS` against the live link table. It is defined once and used at all three
   owner-counting sites, so `FR-013` counts an owner who can act through an external identity.
3. **The persistence probe's finding is now recorded as a decision rather than assumed.** `-024`
   §14 forbade concluding that no migration was needed. The probe found the existing nullable
   verifier columns and `rca_external_identities` sufficient for the account-and-link model, and
   §2.4 below adopts that finding explicitly. Migration `20260821_0019` adds only the recovery
   security-evidence table.

**Why supersession rather than an addendum.** `KHEPRI-DEC-017` makes supersession whole-document, so
a standing addendum would leave §14's prohibition and this record's grant both live and in conflict.
`-024`'s own §14 forbids editing `-018`; the same rule protects `-024` here. This is the sixth use of
the instrument, following `-019`→`-020`→`-021`→`-022`→`-023`.

## Decision

### 1. Everything `KHEPRI-DEC-024` decided is carried forward unchanged

Its §1 governing principle, §2 provider-owned mechanics, §3 Khepri-authoritative list, §4 refused
provider claims and mandatory check order, §5 two admission levels including all nine §5.1
pre-enablement obligations, §6 private-beta personal-data boundary, §7 accepted evidence gaps and
residual risks, §8 sixteen commercial gates, §9 hard-stop conditions, §10 identity-link boundary,
§11 session and recovery boundary, §12 event-stream prohibition, and §13 exit paths all stand as
written and are not weakened, narrowed, or reinterpreted by this record.

In particular: **an external provider may prove identity; Khepri owns authority.** No Clerk
organization, membership, role, permission, plan, feature, or metadata claim may be read for Khepri
authority, even when its value happens to match Khepri state. Clerk remains commercially unadmitted.

### 2. What this record additionally authorizes

The implementation merged at `15a8175` is authorized for the scope and lifetime of §5.1's provisional
admission, bounded to the four decisions below. This replaces `-024` §14's first and fifth bullets
and the refusal at its Context line 32; every other §14 exclusion is carried forward in §3.

- **The contained Clerk adapter and its configuration.** `clerk-backend-api>=7,<8`, the six
  `KHEPRI_CLERK_*` environment variables, and `runtime/clerk_identity.py` are authorized. The
  adapter returns only `VerifiedIdentity(provider, provider_subject)` — two `str` fields
  (`rca/identity.py:71`) — so no vendor type, error, or authority claim crosses the
  `IdentityProvider` seam. Issuer, signing key, key id, algorithm, authorized parties, audience,
  and a maximum token lifetime are pinned for the configured instance, and verification is
  networkless. `runtime/config.py` admits only `development`, `test`, and `private_beta` and raises
  `RuntimeConfigurationError` on any other mode, so a `commercial` mode cannot be configured.

- **One external-authentication route.** `POST` at `EXTERNAL_SESSION_PATH`
  (`runtime/external_auth_api.py:70`) is authorized. It follows §4's order exactly: verify the
  credential, resolve `(provider, provider_subject)` to `account_id` through the **local** link
  table, assert the account is live, mint the Khepri server-side session, then switch to the
  requested organization — refusing at every step with one empty-body `404`. Email is never used to
  resolve the mapping. A verified but unlinked subject fails closed and creates nothing, satisfying
  §5.1's pre-provisioning requirement.

- **The provider-neutral account-and-link path.** `Account._for_external_identity`,
  `preprovision_external_account`, `add_account_with_external_identity`, and the widened
  `_effective_owner_conditions` are authorized. The path is provider-neutral: nothing in
  `khepri.rca` names Clerk. Account and link commit together, a duplicate or re-pointed link fails
  closed, and an existing link never moves between accounts through an ordinary path.

- **No new schema for the account-and-link model.** The existing nullable verifier columns and
  `rca_external_identities` express it. Migration `20260821_0019` is authorized for the recovery
  security-evidence table only. This adopts the probe's finding as a decision; it is not a standing
  conclusion that future external-identity work needs no migration.

### 3. The Khepri-owned recovery consequence

`-024` Consequences reframed `R5-05` and `R5-06` around Khepri-owned consequences, and deferred
`R5-02`, `R5-03`, and `R5-04` while Clerk owns credentials. That disposition stands.
`rca/recovery_security.py` and `rca/recovery_security_persistence.py` are authorized as the reframed
consequence: verified-link resolution, live account revalidation, revocation of every Khepri session,
a re-check after revocation, content-free evidence keyed by digest, idempotency with cross-account
fail-closed, disabled and purged refusal, and identity-link integrity.

**Khepri implements no credential replacement and no password recovery for a Clerk-backed account.**
The only two doors that set a non-`None` verifier are account creation and load-from-storage; the
disable, enable, and purge paths can only clear it. Clerk owns recovery initiation, delivery, expiry,
one-use enforcement, and password replacement, per §11 carried forward.

### 4. Composition is authorized, and is not yet done

The audit found that `RecoverySecurityService`, its sweeper, and `SqlRecoverySecurityEventStore` have
**no production caller** — `wiring.py` never constructs them — and that `clerk_hard_stop.main()` has
**no registered entry point**, since `[project.scripts]` declares only `khepri-gov`. Both ship as
complete, tested libraries that a deployed system cannot reach.

**Wiring them is authorized under this record**, in a separately reviewed slice, and is required
before the private beta admits a tester. The hard stop matters most: §9 makes it the control that
fires when educational access lapses or a paying customer appears, and an unreachable emergency
procedure is not one. Authorizing the wiring here is what keeps that slice from needing a seventh
supersession to do the obvious thing.

Recording this rather than treating it as an implementation detail follows `-024`'s own practice of
naming what a record does not settle.

### 5. What this record still does not authorize

Every remaining `KHEPRI-DEC-024` §14 exclusion is carried forward intact, and its §§5.2, 8 and 9
continue to govern:

- **No public or paying use of Clerk.** §9's hard stop is unchanged: the provisional admission
  becomes inoperative immediately before accepting consideration from any customer, opening a
  commercial production service, or losing the current educational access.
- **No commercial admission.** Every §8 gate remains unrecorded, and §7's accepted gaps — gates 3,
  4, 6, 7, 9, provider-session revocation, the recovery window, and provider availability — remain
  accepted **only** for §5.1's scope and lifetime. Elapsed time, a successful beta, and the absence
  of an incident satisfy none of them.
- **No public or post-authentication self-service bootstrap.** Accounts and links stay
  pre-provisioned for invited testers.
- **No MFA configuration** under §6's data boundary.
- **No Clerk Organizations, memberships, roles, permissions, plans, or features as Khepri
  authority**, and no provider event stream as a correctness dependency.
- **No `RRA-001`, `RRA-002`, or `RCA-001` amendment**, and no weakening of `KHEPRI-DEC-015`
  retention or logging rules.
- **No provider-switching framework** beyond the existing containment seam.
- **No live secrets in the repository**, and no production Clerk instance provisioned by this
  record.
- **No UI.** `R8` owns templates. This authorizes an endpoint and its supporting domain path.
- **No edit to `KHEPRI-DEC-018` or `KHEPRI-DEC-024`.** Both remain historical after retirement.

### 6. Code-health findings are not authorized as an exception

`AGENTS.md` requires every new file to score 10.00 in CodeScene Code Health Review, a required
server-side gate. `#240` merged with that gate red: `clerk_identity.py`'s `_verified_subject`
(Complex Method) and `external_auth_api.py`'s `_bearer` (Complex Conditional) each scored 9.69
against the "Bare Minimum" profile.

Both are dense boolean validation rather than defective logic, and the audit classified neither as
functional or security-critical. **This record does not waive the gate and does not suppress the
findings.** They are recorded here so the exception is visible rather than absorbed, and clearing
them belongs to the composition slice §4 authorizes.

## Consequences

- **The merged implementation is authorized** for §5.1's scope and lifetime once this record is
  merged. Nothing in `#240` needs reverting or re-landing.
- **`R3-11` is satisfiable.** Its governance dependency and both engineering preconditions are met,
  so the roadmap may record it merged at `15a8175` — subject to §15's rule that `MERGED` requires a
  `main` SHA, which it now has.
- **`R5-02`, `R5-03`, and `R5-04` remain deferred.** The reframed `R5-05`/`R5-06` consequence is
  authorized and implemented, and is not composed.
- **One slice is owed before a tester is admitted:** compose the recovery consequence in `wiring.py`,
  register the hard-stop entry point, and clear the two code-health findings. §4 authorizes it; it
  remains separately reviewed.
- **The private beta remains reversible by construction.** Losing Clerk authentication must not
  destroy or renumber any Khepri account, organization, membership, role, audit event, isolation
  scope, or RRA record. `revoke_all_for_provider` touches sessions only.
- **`KHEPRI-DEC-024` and `KHEPRI-DEC-018` remain in place as history and must not be edited to
  match this record.** `KHEPRI-DEC-017`'s rule applies to both.
- **This gap is the reason a risk-acceptance record and an implementation authorization are
  different instruments.** `-024` answered "is this vendor tolerable, for whom, with which gaps" and
  answered it well; it was read afterwards as though it had also answered "may this code land". A
  record that admits a provider provisionally is not a mandate to implement, and the audit that
  caught the difference is the control that worked.

---

Identity, state, document, dependencies, and supersession are authoritative in
`governance/registry.yaml`.
