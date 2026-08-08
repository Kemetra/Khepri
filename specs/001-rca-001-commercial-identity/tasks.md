# RCA-001 — Task breakdown

Dependency-ordered vertical slices. **None of these may be executed**: implementation is blocked
by three governance preconditions recorded in `analyze.md` §5. This is the plan for work, not the
work.

Commit, push, and pull-request steps are deliberately **not** tasks — they are not implementation,
and this run is forbidden from performing them.

Every task states an expected RED test first. Negative and security tests are marked **[SEC]**.

---

## T-001 — Account domain and credential hashing

- **Objective**: An account can be created with a hash-only credential, and a credential can be
  verified. No storage, no HTTP.
- **Files**: `src/khepri/rca/accounts.py`, `tests/test_rca001_accounts.py`
- **Dependencies**: none
- **Expected RED**: `test_credential_is_never_stored_in_recoverable_form` — module does not exist
- **Minimal implementation**: `Account` frozen dataclass; `scrypt` digest reusing
  `rra.sessions.InvitationService._digest` parameters; `hmac.compare_digest` verification
- **Expected GREEN**: credential round-trips; the stored record contains no plaintext
- **Validation**: `uv run pytest tests/test_rca001_accounts.py`
- **Stop condition**: any need to touch `src/khepri/rra/`
- **Requirements**: `FR-001`, `FR-002`

## T-002 [SEC] — Uniform authentication refusal

- **Objective**: Failed authentication does not disclose which check failed.
- **Files**: `src/khepri/rca/accounts.py`, `tests/test_rca001_accounts.py`
- **Dependencies**: T-001
- **Expected RED**: `test_unknown_account_and_wrong_credential_and_disabled_are_indistinguishable`
- **Minimal implementation**: one refusal constant; one exception type; one condition covering
  nonexistent, wrong-credential, and disabled
- **Expected GREEN**: all three paths raise the identical message
- **Validation**: assert message equality across all three, not merely that each raises
- **Stop condition**: any branch that varies the message
- **Requirements**: `FR-004`, `FR-008` (partial)

## T-003 — Organization and atomic first ownership

- **Objective**: Creating an organization creates its owner membership in the same operation.
- **Files**: `src/khepri/rca/organizations.py`, `tests/test_rca001_organizations.py`
- **Dependencies**: T-001
- **Expected RED**: `test_organization_never_exists_without_an_owner`
- **Minimal implementation**: `Organization`, `Membership`, `Role`; creation returns both
- **Expected GREEN**: no observable instant with zero owners
- **Validation**: `uv run pytest tests/test_rca001_organizations.py`
- **Stop condition**: creation that returns an organization before a membership exists
- **Requirements**: `FR-009`, `FR-010`, `FR-015`

## T-004 [SEC] — Final-owner protection across all three routes

- **Objective**: Remove, downgrade, and disable each fail closed on the final owner.
- **Files**: `src/khepri/rca/organizations.py`, `tests/test_rca001_organizations.py`
- **Dependencies**: T-003
- **Expected RED**: three tests — `test_cannot_remove_final_owner`,
  `test_cannot_downgrade_final_owner`, `test_cannot_disable_account_holding_final_ownership`
- **Minimal implementation**: one guard invoked by all three operations
- **Expected GREEN**: all three refuse; the organization retains an owner
- **Validation**: assert the post-state owner count, not only that an exception was raised
- **Stop condition**: guarding only removal
- **Requirements**: `FR-013`

## T-005 — Membership isolation

- **Objective**: Revoking one membership affects nothing else.
- **Files**: `src/khepri/rca/organizations.py`, `tests/test_rca001_organizations.py`
- **Dependencies**: T-003
- **Expected RED**: `test_revoking_one_membership_leaves_others_intact`
- **Minimal implementation**: revocation targets one membership row
- **Expected GREEN**: the account's other memberships and the org's other members are unchanged
- **Validation**: assert both directions of non-interference
- **Requirements**: `FR-011`, `FR-012`

## T-006 — Attributable role and membership changes

- **Objective**: Every change records actor, target, prior role, next role, and time.
- **Files**: `src/khepri/rca/audit.py`, `tests/test_rca001_audit.py`
- **Dependencies**: T-003
- **Expected RED**: `test_role_change_records_actor_and_prior_and_next_role`
- **Minimal implementation**: append-only audit record emitted by the mutating operations
- **Expected GREEN**: record present with all five fields
- **Validation**: also assert **no** credential, secret, or retail content appears in the record
- **Requirements**: `FR-014`, `FR-040`

## T-007 — Invitation issuance and acceptance

- **Objective**: An invitation names one org and role, is hash-only, and creates one membership.
- **Files**: `src/khepri/rca/invitations.py`, `tests/test_rca001_invitations.py`
- **Dependencies**: T-003
- **Expected RED**: `test_accepting_invitation_creates_one_membership_at_named_role`
- **Minimal implementation**: shape mirroring `rra.sessions.Invitation`
- **Expected GREEN**: exactly one membership at the named role
- **Requirements**: `FR-016`, `FR-018`

## T-008 [SEC] — Invitation replay, expiry, and revocation

- **Objective**: Every invalid invitation path fails closed and uniformly.
- **Files**: `src/khepri/rca/invitations.py`, `tests/test_rca001_invitations.py`
- **Dependencies**: T-007
- **Expected RED**: `test_expired_replayed_revoked_and_malformed_are_indistinguishable`
- **Minimal implementation**: one condition covering all four, one message
- **Expected GREEN**: second acceptance creates no membership; message identical across causes
- **Validation**: assert membership count unchanged after replay, not only that it raised
- **Requirements**: `FR-017`, `FR-020`

## T-009 — Invitation before account exists

- **Objective**: A person with no account can be invited; acceptance requires an account.
- **Files**: `src/khepri/rca/invitations.py`, `tests/test_rca001_invitations.py`
- **Dependencies**: T-007
- **Expected RED**: `test_invitation_may_be_issued_before_account_exists`
- **Expected GREEN**: issuance succeeds; acceptance without an authenticated account is denied
- **Requirements**: `FR-019`

## T-010 — Persistence and migration

- **Objective**: Five `rca_*` tables with a separate declarative `Base`.
- **Files**: `src/khepri/rca/persistence.py`,
  `migrations/versions/2026____0010_rca_commercial_identity.py`,
  `tests/test_rca001_persistence.py`
- **Dependencies**: T-001, T-003, T-007
- **Expected RED**: `test_migration_creates_rca_tables_and_reverses_cleanly`
- **Minimal implementation**: one migration, `down_revision = "20260730_0009"`
- **Expected GREEN**: upgrade and downgrade both clean
- **Validation**: assert **no** `rra_*` table is altered by the migration
- **Stop condition**: any diff to an existing migration
- **Requirements**: `FR-037`, `FR-039`

## T-011 [SEC] — Uniqueness and final-owner under concurrency

- **Objective**: Races cannot defeat email uniqueness or final-owner protection.
- **Files**: `src/khepri/rca/persistence.py`, `tests/test_rca001_persistence.py`
- **Dependencies**: T-010
- **Expected RED**: `test_concurrent_final_owner_removal_leaves_one_owner`
- **Minimal implementation**: unique index on email; partial unique index on active membership;
  transactional re-count guarding owner removal
- **Expected GREEN**: one of two concurrent removals fails; an owner remains
- **Requirements**: `FR-013`, `A-1`

## T-012 — Authenticated session lifecycle

- **Objective**: Opaque server-side session with expiry and revocation.
- **Files**: `src/khepri/rca/auth_sessions.py`, `tests/test_rca001_sessions.py`
- **Dependencies**: T-001, T-010
- **Expected RED**: `test_expired_and_revoked_sessions_establish_no_actor`
- **Minimal implementation**: opaque id; `expires_at`, `revoked_at` checked at resolve
- **Expected GREEN**: neither expired nor revoked resolves an actor
- **Requirements**: `FR-003`, `FR-022` (Scenario 19)

## T-013 — Account recovery

- **Objective**: Single-use expiring recovery that invalidates all sessions.
- **Files**: `src/khepri/rca/recovery.py`, `tests/test_rca001_recovery.py`
- **Dependencies**: T-012
- **Expected RED**: `test_recovery_invalidates_every_pre_existing_session`
- **Minimal implementation**: hashed single-use secret; bulk session revocation on success
- **Expected GREEN**: prior sessions stop authorizing; the secret is not reusable
- **Validation [SEC]**: initiating recovery for an unknown address is indistinguishable
- **Requirements**: `FR-005`, `FR-006`, `FR-007`

## T-014 — The canonical authorization resolver

- **Objective**: One checkpoint producing `AuthorizationContext`; unconstructable elsewhere.
- **Files**: `src/khepri/rca/authorization.py`, `tests/test_rca001_authorization.py`
- **Dependencies**: T-005, T-012
- **Expected RED**: `test_context_cannot_be_constructed_outside_the_resolver`
- **Minimal implementation**: resolver performing the six steps of `plan.md` §5 in order
- **Expected GREEN**: every step denies on failure; a permitted call yields a context
- **Validation**: a static check that no module outside `authorization.py` constructs a context
- **Stop condition**: any handler taking an organization id as a trusted parameter
- **Requirements**: `FR-021`, `FR-022`, `FR-026`

## T-015 [SEC] — Authorization matrix

- **Objective**: Every actor kind × every protected action is asserted.
- **Files**: `tests/test_rca001_authorization.py`
- **Dependencies**: T-014
- **Expected RED**: parametrized matrix over `{owner, member, non-member, unauthenticated}`
- **Expected GREEN**: every cell matches its specified permit or fail-closed denial
- **Validation**: the matrix is exhaustive by construction — adding an action without a row fails
- **Requirements**: `FR-015`, `FR-022`, `FR-024`

## T-016 [SEC] — Cross-organization isolation

- **Objective**: Cross-org read and mutation both denied, indistinguishably from nonexistence.
- **Files**: `tests/test_rca001_isolation.py`
- **Dependencies**: T-014
- **Expected RED**: `test_cross_org_read_is_indistinguishable_from_nonexistent_object`
- **Expected GREEN**: identical refusal for "not yours" and "does not exist"; mutation changes no
  state in either organization
- **Validation**: assert message equality **and** post-state equality
- **Requirements**: `FR-023`, `FR-024`, `FR-025`

## T-017 [SEC] — Live membership: revocation, downgrade, disablement mid-session

- **Objective**: Changes bite on the next action without the session ending.
- **Files**: `tests/test_rca001_authorization.py`
- **Dependencies**: T-014
- **Expected RED**: `test_revoked_membership_stops_authorizing_within_the_same_session`
- **Expected GREEN**: revocation, downgrade, and disablement each take effect immediately
- **Stop condition**: any design caching role into the session record
- **Requirements**: `FR-008`, `FR-030` (Scenarios 16, 20)

## T-018 — Active organization and switching

- **Objective**: At most one active org; switching only into a current membership.
- **Files**: `src/khepri/rca/authorization.py`, `tests/test_rca001_authorization.py`
- **Dependencies**: T-014
- **Expected RED**: `test_switch_into_organization_without_membership_is_denied`
- **Expected GREEN**: switch succeeds only with membership; an account with none authenticates but
  is denied every org-scoped action
- **Requirements**: `FR-027`, `FR-028`, `FR-029` (Scenarios 13, 18)

## T-019 [SEC] — The RRA bridge

- **Objective**: `(account, active org) → SessionScope`, with no commercial identifier inside.
- **Files**: `src/khepri/rca/bridge.py`, `tests/test_rca001_bridge.py`
- **Dependencies**: T-014
- **Expected RED**: `test_two_organizations_resolve_to_distinct_isolation_scopes`
- **Minimal implementation**: organization's opaque `owner_scope_id` → `SessionScope`
- **Expected GREEN**: distinct scopes per org; stable across sessions and switches
- **Validation [SEC]**: assert no email, org name, org slug, account id, or human-readable id
  appears in or is derivable from a resolved scope; assert `src/khepri/rra/sessions.py` is
  **byte-identical** to its state at `3da504c`
- **Stop condition**: any modification to `src/khepri/rra/`
- **Requirements**: `FR-031`..`FR-036`

## T-020 — RRA regression and independence

- **Objective**: RRA passes unmodified with no account or organization present.
- **Files**: none modified; `tests/` existing RRA suites
- **Dependencies**: T-019
- **Expected RED**: n/a — this is a regression gate
- **Expected GREEN**: full existing RRA suites pass with no `rca_*` row present
- **Validation**: `uv run pytest`; plus `git diff --stat src/khepri/rra/ tests/test_rra*` empty
- **Requirements**: `FR-037`, `FR-038`, `FR-039`

## T-021 [SEC] — Direct endpoint access

- **Objective**: The API surface cannot be bypassed by calling endpoints directly.
- **Files**: `src/khepri/rca/api.py`, `tests/test_rca001_api.py`
- **Dependencies**: T-014, T-018
- **Expected RED**: `test_direct_endpoint_call_without_resolver_is_denied`
- **Expected GREEN**: missing scope, conflicting actor/scope, and guessed object id all denied
- **Validation**: exercise the HTTP surface directly, not the service layer
- **Requirements**: `FR-021`, `FR-023`, `FR-024`, `FR-026`

---

## Ordering

```
T-001 ─┬─ T-002
       ├─ T-003 ─┬─ T-004
       │         ├─ T-005 ─────────────┐
       │         └─ T-007 ─┬─ T-008    │
       │                   └─ T-009    │
       └─ T-010 ─┬─ T-011              │
                 └─ T-012 ─┬─ T-013    │
                           └───────────┴─ T-014 ─┬─ T-015
                                                 ├─ T-016
                                                 ├─ T-017
                                                 ├─ T-018 ─┐
                                                 └─ T-019 ─┼─ T-021
                                                           └─ T-020
```

21 tasks, 11 of them security tests. No task exceeds one vertical slice, and none is of the
"implement authentication" shape.
