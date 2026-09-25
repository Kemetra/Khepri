"""Give `rca_sessions.active_organization_id` its foreign key (#432, `RCA-001` `FR-027`).

The column names the one organization a session acts in (`FR-027`), and it had no constraint at all.
The switcher checks membership before it writes, but the row itself would hold any string, so a
mis-wired path or raw SQL could point a session at an organization that does not exist.

**Existence only, not membership.** `fk_rca_session_active_organization` references
`rca_organizations.organization_id`. A composite key onto `rca_memberships` would be stronger on its
face, but revoking a membership deletes its row while `FR-030` keeps the session alive, so a
`RESTRICT` key there would block revocation. Membership therefore stays a live check at resolution
time, where `FR-030` already puts it.

**The column stays nullable.** NULL still means "no active organization": `FR-028` lets an account
with no membership authenticate, and `FR-030` clears the column on revocation.

**`RESTRICT`, matching `fk_rca_session_account`.** Organization rows are never deleted, so the key
cannot block an existing path. A future deletion would have to decide what happens to the sessions
first, and this key makes that decision unavoidable.

**RCA-only, so it replays.** It touches no `rra_` table, so `tests/test_rca001_migration.py` can
drive it against the RCA-only SQLite schema, which it cannot do for its parent `20260925_0031`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260925_0032"
down_revision: str | None = "20260925_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "rca_sessions"
_KEY = "fk_rca_session_active_organization"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as sessions:
        sessions.create_foreign_key(
            _KEY,
            "rca_organizations",
            ["active_organization_id"],
            ["organization_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as sessions:
        sessions.drop_constraint(_KEY, type_="foreignkey")
