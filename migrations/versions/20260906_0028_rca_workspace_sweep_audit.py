"""Admit the retention sweep's audit action (`W1-07b`, `RCA-005` `FR-125`).

`FR-125` names `sweep` among the workspace actions that MUST emit one audit event, and
`KHEPRI-DEC-033` §2's audit row states the class's ending is "run by the retention sweep, recorded
as a" content-free record. `20260906_0026` did not admit it -- `W1-07a` left the note in `audit.py`:
"`W1-07b` adds the sweep when it writes it, and the migration literal moves in the same commit."

**Only the action constraint moves.** A sweep's subject is `None`, which
`ck_rca_workspace_audit_subject_pair` already admits and every `WorkspaceAuditEvent` constructor
already takes, so `AUDIT_OBJECTS` needs nothing; the outcome is `completed`, already admitted. An
object kind added for the sweep would be a value no other class uses, and naming an existing kind
would misdescribe a class-level purge as an act on one object.

**Rebuilt, not altered.** SQLite cannot `ALTER` a `CHECK`, so `batch_alter_table` recreates the
table, and `test_migration_columns_match_the_declared_models` compares the literal here against
`audit.py`'s tuple.

**`down_revision` is `20260906_0027`**, `W1-07a`'s revocation ledger, the head this slice inherits.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260906_0028"
down_revision: str | None = "20260906_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS_BEFORE = "('version_created', 'run_started', 'run_completed', 'run_failed', 'profile_remembered', 'profile_reused', 'version_deleted')"  # noqa: E501
_ACTIONS_AFTER = "('version_created', 'run_started', 'run_completed', 'run_failed', 'profile_remembered', 'profile_reused', 'version_deleted', 'retention_swept')"  # noqa: E501


def _rewrite(actions: str) -> None:
    with op.batch_alter_table("rca_workspace_audit_events") as batch:
        batch.drop_constraint("ck_rca_workspace_audit_action", type_="check")
        batch.create_check_constraint("ck_rca_workspace_audit_action", f"action IN {actions}")


def upgrade() -> None:
    _rewrite(_ACTIONS_AFTER)


def downgrade() -> None:
    # A row carrying the new action cannot satisfy the narrower constraint; the downgrade refuses
    # rather than deleting a customer's audit history to fit an older shape.
    _rewrite(_ACTIONS_BEFORE)
