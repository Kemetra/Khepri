# #600: bind a profile's upload to the profile's own scope

Follow-up to #599 in the #432 tenant-schema family (S1 hardening). A database backstop only:
`ProfilingService` already takes the upload from the profile's own session.

## Shape

Migration `20260926_0034`, **PostgreSQL only** (dialect guard):

1. **Repair first.** Set `upload_id = NULL` on every profile whose upload is not in its own
   `(owner_id, session_id)`. Those rows name an upload the profile has no claim to. NULL is the
   state #593 already admits ("a profile names its upload only while it exists"), so the repair
   reuses that meaning instead of inventing one.
2. Add `uq_upload_scope (owner_id, session_id, upload_id)` on `rra_uploads`, as the reference
   target (`upload_id` is already the primary key). This mirrors `uq_profile_scope` in #578.
3. Replace `fk_profile_upload` with `fk_profile_upload_scope`: `(owner_id, session_id, upload_id)`
   references `rra_uploads`, `ON DELETE SET NULL (upload_id)`.

**Why the column-list form.** A plain composite `SET NULL` would null the two scope columns, which
are `NOT NULL`. `SET NULL (upload_id)` nulls only the upload, keeping #593's decision. The form is
PostgreSQL 15+, and CI, local and staging all run 17.

**Why PostgreSQL only.** SQLite cannot express the column-list form, and the ORM-built SQLite
fixtures would fail on it. The ORM model keeps the single-column key and records that PostgreSQL
carries the wider one. Of the options #600 lists, this is the declarative one; a trigger would
put the same rule in procedural code.

The downgrade drops the composite key and `uq_upload_scope`, then restores the single-column key.

## Tests: `tests/test_i600_profile_upload_scope.py` (PostgreSQL, `concurrency` marker)

- Head carries the composite key over the three columns, and not the legacy key.
- A profile in scope A naming scope B's upload is refused. Naming its own upload is admitted.
- Deleting the upload nulls only `upload_id`, so the scope columns survive.
- The upgrade clears a cross-scope `upload_id` written under `0033`.
- The downgrade restores the single-column `SET NULL` key.

Pins to move with a new head: `RCA_UNREPLAYED` in `test_rca001_migration.py`, and the single-head
pin in `test_rca001_session_persistence.py`. `test_i593`'s head assertion moves to `0033`, whose
DDL it describes.
