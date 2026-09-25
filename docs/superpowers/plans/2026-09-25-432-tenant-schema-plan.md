# #432: make a cross-scope fact package and an unknown active organization unrepresentable

**Authority:** `RRA-001` §Requirements ("Bind every upload, fact package, narrative, export, job, and
deletion operation to the opaque owner and session; fail closed on cross-session access") and
`RCA-001` `FR-027`/`FR-034`. No specification, decision, validator, or governance file is edited.
Both changes are constraints the active specifications already require; neither adds a column, a
verb, or a behaviour.

**Vehicle:** one PR. Commit 1 is this plan and the RED tests. Commit 2 adds the implementation and
the two migrations.

## What ships

1. **`rra_fact_packages` → `rra_dataset_profiles` becomes composite.** `fk_package_profile`
   (`profile_id` alone) is replaced by `fk_package_profile_scope`
   `(owner_id, session_id, profile_id)`. Its target is a new `uq_profile_scope` on the profile
   table. Today a package's `(owner_id, session_id)` and its `profile_id` are checked by two
   independent FKs, so a package in scope A can cite scope B's profile. The workspace closed the same
   hole in `20260904_0021`. The FK carries all three columns rather than `(owner_id, profile_id)`
   because `RRA-001` binds a package to its owner *and* its session. `packages.py` builds every
   package from the scope and the profile of the same session, so the stronger form refuses nothing
   the product writes. `ON DELETE RESTRICT` is kept: `deletion_persistence.py` already deletes
   packages before profiles.
2. **`rca_sessions.active_organization_id` → `rca_organizations.organization_id`**, named
   `fk_rca_session_active_organization`, `RESTRICT`. The column is nullable, and NULL still means
   "no active organization" (`FR-028`/`FR-030`). Organization rows are never deleted, so `RESTRICT`
   cannot block an existing path.
3. **Two migrations.** `20260925_0031` covers the RRA change (parent `20260915_0030`).
   `20260925_0032` covers the RCA change (parent `0031`). The RCA-only revision can still be
   replayed in `RCA_REVISIONS`, and the RRA revision is registered but not replayed, the way `0030`
   is. The head pins are updated in `test_rca001_session_persistence.py`, `test_rca001_migration.py`
   and `specs/001-rca-001-commercial-identity/STATUS.md`.

## Deferred, with the reason

- **FK `rra_beta_sessions.owner_id` → `rca_isolation_scopes.owner_id`.** An invitation-redeemed
  session carries a design-partner `own_…` scope that has no row in `rca_isolation_scopes`
  (`runtime/pipeline_recording.py`, "What is not recorded"), and `redeem` mints one per invitation.
  An unconditional FK would therefore refuse every beta redemption, breaking the beta path that
  `KHEPRI-DEC-023` (carrying `-020` §4) says must stay unchanged. Declaring the FK on RRA's metadata
  would also make RRA's schema depend on an RCA table, which breaks `RCA-001` `FR-039`
  (independently testable RRA). A conditional form needs a discriminator. Both kinds of session mint
  the same `own_` shape, so the discriminator would have to be a new column. RRA would then have to
  learn which sessions are commercial, and a forged row could still set that column to NULL. That is
  a decision to take, not a schema fix. The FK also would not stop the attack #432 names: another
  organization's `owner_id` *is* a real scope row.
- **Composite membership FK on `rca_sessions`.** Revoking a membership deletes its row
  (`rca/persistence.py` `revoke`), and `FR-030` keeps the session alive afterwards, so a `RESTRICT`
  FK would block revocation.
- **`rra_dataset_profiles.upload_id` → `rra_uploads`.** `runtime/workspace_retention.py` deletes
  `UploadRow` while the profile survives (`KHEPRI-DEC-033`), so an FK would break the raw-upload
  sweep.
- **Unscoped `session_id` lookups** (`get_session`, `get_upload_for_session`,
  `get_profile_for_session`, `get_package_for_session`). The pipeline reaches these through the
  beta cookie. Narrowing them changes a Protocol that `FR-037` says RRA's existing tests must pass
  unmodified against, and belongs with `#152`'s construction-boundary triage.
- **RLS.** No active specification requires it. #432 itself says the FKs are not RLS.

## RED tests (`tests/test_i432_tenant_scope_foreign_keys.py`)

These drive the production verbs (`open_commercial_session`, `SqlProfileRepository.add_profile`,
`SqlFactPackageRepository.add_package`, `SqlSessionStore.add_session` and
`point_session_at_organization`) on SQLite with `PRAGMA foreign_keys=ON`:

- a package citing another scope's profile raises `IntegrityError`;
- a package citing another session's profile in its own scope raises `IntegrityError`;
- a package citing its own profile is admitted (positive control);
- a session naming, or pointed at, an absent organization raises `IntegrityError`; a real one and
  `None` are admitted.

A PostgreSQL block (`concurrency` marker, so a CI skip fails the build) upgrades to head. It asserts
both named FKs exist, that a cross-scope package is refused there, and that a downgrade to
`20260915_0030` restores `fk_package_profile`.

Mutation checks: dropping the composite FK from the ORM must fail both refusal tests. Narrowing it
to `(owner_id, profile_id)` must fail only the other-session test. Dropping the RCA FK must fail the
organization tests.
