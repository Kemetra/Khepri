# Defect: `alembic downgrade base` cannot run past revision `20260817_0017`

Date: 2026-08-22
Status: recorded, **not fixed**. Found while proving `20260822_0020` against PostgreSQL.
Owner decision needed on whether to repair it.

## What happens

`uv run alembic downgrade base` against a PostgreSQL database at head fails inside
`20260817_0017` (`#205`, "let one commercial scope hold many analysis sessions"):

```
ERROR: cannot drop constraint uq_session_owner_scope on table rra_beta_sessions
  because other objects depend on it
DETAIL:  constraint fk_upload_session_scope on table rra_uploads
         depends on index uq_session_owner_scope
         constraint fk_deletion_session_scope on table rra_deletion_jobs
         depends on index uq_session_owner_scope
HINT:  Use DROP ... CASCADE to drop the dependent objects too.
[SQL: ALTER TABLE rra_beta_sessions DROP CONSTRAINT uq_session_owner_scope]
```

## Why it happens

`20260729_0002` creates `rra_uploads` with `fk_upload_session_scope`, a composite foreign
key onto `(owner_id, session_id)` of `rra_beta_sessions`. PostgreSQL satisfies that
reference using the unique index `uq_session_owner_scope`, so the foreign key depends on
the index rather than merely on the columns.

`20260817_0017`'s `downgrade` restores that unique constraint, and its `upgrade` drops it.
The drop succeeds on a database where the dependent foreign keys do not yet exist, which
is the order the forward chain produces. In reverse the dependents are still present when
the drop is attempted, so PostgreSQL refuses.

Nothing detected this because no test has ever downgraded the chain on PostgreSQL. SQLite
cannot express the failure: it has no `ALTER TABLE ... DROP CONSTRAINT` at all, so the
same revision raises `NotImplementedError` long before dependency order matters.

## Why it was not fixed here

The `KHEPRI-DEC-008` portability slice does not own `20260817_0017`, and repairing another
revision's downgrade is a different change with a different blast radius: it alters the
reverse behaviour of a merged migration, which is exactly the kind of edit that wants its
own review rather than to ride along in a storage slice.

`tests/test_rra_portable_encryption_migration.py` works around it rather than depending on
it. Its fixture drops and recreates the `public` schema instead of downgrading to `base`,
and its downgrade test steps back exactly one revision — to `20260821_0019` — which is
inside the range this slice owns and works correctly.

## Impact

**Not a production risk today.** No deployment definition exists, so no environment exists
(`KHEPRI-DEC-008`), and nothing has ever been downgraded outside a test.

**It is a testing gap.** Any future test that wants a clean PostgreSQL database by
downgrading to `base` will hit this, and the natural workaround — dropping the schema — is
less honest evidence than a working reverse chain would be.

## Possible repairs, none selected

1. **Drop and recreate the dependent foreign keys inside `20260817_0017`'s `downgrade`.**
   Most faithful, and makes the revision genuinely reversible. Touches a merged migration.
2. **Recreate the unique index before restoring the constraint.** Narrower, but the
   ordering problem simply moves rather than disappearing.
3. **Accept it and document that `downgrade base` is unsupported on this chain.** Cheapest,
   and consistent with a private beta that has never deployed — but it makes the next
   person's clean-database fixture their own problem to discover.

## Reproduction

```bash
# any disposable PostgreSQL database
KHEPRI_DATABASE_URL="postgresql+psycopg://<user>:<pw>@127.0.0.1:5432/<db>" uv run alembic upgrade head
KHEPRI_DATABASE_URL="postgresql+psycopg://<user>:<pw>@127.0.0.1:5432/<db>" uv run alembic downgrade base
```

The second command fails. `downgrade 20260821_0019` and `downgrade 20260818_0018` both
succeed, so the defect is specific to `20260817_0017` and everything below it.
