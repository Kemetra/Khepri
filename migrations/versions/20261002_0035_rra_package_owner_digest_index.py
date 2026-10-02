"""Index `rra_fact_packages (owner_id, package_digest)` for the owned-package read (#555 D-01).

`SqlFactPackageRepository.get_owned_package` filters on `package_digest = $1 AND owner_id = $2`.
Nothing at `20260926_0034` leads with either column: the indexes are the primary key
(`package_id`), `uq_package_profile_versions` (`profile_id, ...`) and `ix_package_session`
(`session_id`). Every call was therefore a sequential scan of the table.

**Why this index and not the others #555 listed.** The owner ruled that an index lands only on
`EXPLAIN ANALYZE` evidence against realistic data. On PostgreSQL 18.4 at 200,000 packages (2,000
owners, 100 each, about 8 KB documents) the production statement fell from a 32.9 ms median
parallel sequential scan to a 0.05 ms index scan. `rca_memberships (account_id)` and
`rra_deletion_evidence (attempted_at)` stayed under the thresholds fixed beforehand and were
rejected. The plan, thresholds and plans are in
`docs/superpowers/plans/2026-10-02-555-d01-index-review.md` and `-index-evidence.md`.

**Equality on both columns, `owner_id` first.** Both predicates are equalities, so the order does
not change the lookup. `owner_id` leads so the same index also serves any later owner-scoped read.
It is not unique: two profiles with identical facts can publish the same digest under one owner.

**Online.** `CREATE INDEX CONCURRENTLY` cannot run inside a transaction, so on PostgreSQL both
directions run in `autocommit_block()`. Other dialects (the SQLite test chain) create it plainly.
An interrupted `CREATE INDEX CONCURRENTLY` leaves an INVALID index of the same name behind, which
the planner never uses. `IF NOT EXISTS` alone would skip it silently on a retry, so the upgrade
first looks the index up in `pg_index`: an invalid one is dropped concurrently and rebuilt, a
valid one is left alone.

The index name is spelled literally rather than imported from the model, so a later edit to the
model cannot rewrite what this revision did.

The migration head is pinned in three places and this revision moves all of them:
`tests/test_rca001_migration.py` `RCA_UNREPLAYED`,
`tests/test_rca001_session_persistence.py`'s `alembic heads` assertion, and
`specs/001-rca-001-commercial-identity/STATUS.md`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0035"
down_revision: str | None = "20260926_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "rra_fact_packages"
_INDEX = "ix_package_owner_digest"
_COLUMNS = ["owner_id", "package_digest"]


def _on_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


_INVALID = sa.text(
    "SELECT 1 FROM pg_index AS i JOIN pg_class AS c ON c.oid = i.indexrelid "
    "WHERE c.relname = :name AND NOT i.indisvalid"
)


def upgrade() -> None:
    if not _on_postgres():
        op.create_index(_INDEX, _TABLE, _COLUMNS, if_not_exists=True)
        return
    with op.get_context().autocommit_block():
        if op.get_bind().execute(_INVALID, {"name": _INDEX}).first() is not None:
            op.drop_index(_INDEX, table_name=_TABLE, postgresql_concurrently=True, if_exists=True)
        op.create_index(_INDEX, _TABLE, _COLUMNS, postgresql_concurrently=True, if_not_exists=True)


def downgrade() -> None:
    if not _on_postgres():
        op.drop_index(_INDEX, table_name=_TABLE, if_exists=True)
        return
    with op.get_context().autocommit_block():
        op.drop_index(_INDEX, table_name=_TABLE, postgresql_concurrently=True, if_exists=True)
