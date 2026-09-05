"""Admit the deletion action and the `already_deleted` outcome (`W1-07a`, `RCA-005` `FR-123`).

`FR-123` requires that a repeated deletion emit one audit event with outcome `already_deleted`, so
an idempotency test and an evidence consumer read the same contract. `20260905_0022` spelled both
vocabularies into `CHECK` constraints, and neither admits a deletion: an event written with the new
values would be refused by the driver even though the domain allows them.

**`already_deleted` is not `already_recorded`.** The existing outcome says a *write* was a
duplicate; this one says the object had already ended and no new evidence was written. Reusing the
first would make `FR-123`'s contract unreadable to the consumer it names, so the vocabulary gains a
value rather than overloading one.

**Both constraints are rebuilt, not altered.** SQLite cannot `ALTER` a `CHECK`, so
`batch_alter_table` recreates the table; the literals here are spelled out as `20260905_0022`
spells them, and `test_migration_columns_match_the_declared_models` compares them against
`audit.py`'s tuples.

**`down_revision` is `20260905_0025`**, `W1-08`'s family versions, the head this slice inherits.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260906_0026"
down_revision: str | None = "20260905_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS_BEFORE = "('version_created', 'run_started', 'run_completed', 'run_failed', 'profile_remembered', 'profile_reused')"  # noqa: E501
_ACTIONS_AFTER = "('version_created', 'run_started', 'run_completed', 'run_failed', 'profile_remembered', 'profile_reused', 'version_deleted')"  # noqa: E501
_OUTCOMES_BEFORE = "('completed', 'refused', 'already_recorded')"
_OUTCOMES_AFTER = "('completed', 'refused', 'already_recorded', 'already_deleted')"


def _rewrite(actions: str, outcomes: str) -> None:
    with op.batch_alter_table("rca_workspace_audit_events") as batch:
        batch.drop_constraint("ck_rca_workspace_audit_action", type_="check")
        batch.drop_constraint("ck_rca_workspace_audit_outcome", type_="check")
        batch.create_check_constraint("ck_rca_workspace_audit_action", f"action IN {actions}")
        batch.create_check_constraint("ck_rca_workspace_audit_outcome", f"outcome IN {outcomes}")


def upgrade() -> None:
    _rewrite(_ACTIONS_AFTER, _OUTCOMES_AFTER)


def downgrade() -> None:
    # A row carrying one of the new values cannot satisfy the narrower constraint; the downgrade
    # refuses rather than deleting a customer's audit history to fit an older shape.
    _rewrite(_ACTIONS_BEFORE, _OUTCOMES_BEFORE)
