"""Add the workspace audit event table (`W1-04`, `RCA-005` `FR-125`).

`FR-125`: every workspace action emits one content-free audit event -- opaque actor, opaque
organization, object identifiers, action, outcome, timestamp -- under `KHEPRI-DEC-015` §7's logging
rule and its twelve-month horizon. This is the table those events are written to.

**No foreign key onto `rca_isolation_scopes`, deliberately.** The other workspace tables carry one;
this one follows `rca_membership_events` instead, and for its reason: the event has its own horizon
and must outlive the organization it describes until then, while a `RESTRICT` key would enforce the
opposite ordering. `owner_id` is indexed because every read is by scope; `occurred_at` because the
sweep `W1-07` writes selects on it.

**`object_kind` and `object_id` are null together.** A refusal that produced no object names none.
The pairing is a `CHECK`, so a kind without an identifier is unrepresentable in a row as it is in
the `AuditSubject` value type.

**Values are spelled literally here and built from the model's tuples in `schema.py`**, the same
split as `20260904_0021`: a migration is a historical record, and importing a module constant would
let a later edit rewrite history. `test_w104_workspace_services.py` asserts the two spellings agree.

**`down_revision` is `20260904_0021`**, `W1-02`'s workspace tables, the head this slice inherits.
The pin in `tests/test_rca001_session_persistence.py` and the head stated in
`specs/001-rca-001-commercial-identity/STATUS.md` move in this same commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0022"
down_revision: str | None = "20260904_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS = "('version_created', 'run_started', 'run_completed', 'run_failed', 'profile_remembered', 'profile_reused')"  # noqa: E501
_OUTCOMES = "('completed', 'refused', 'already_recorded')"
_OBJECTS = "('version', 'run', 'profile')"


def upgrade() -> None:
    op.create_table(
        "rca_workspace_audit_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("actor_account_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("object_kind", sa.String(), nullable=True),
        sa.Column("object_id", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_rca_workspace_audit_events"),
        sa.CheckConstraint(f"action IN {_ACTIONS}", name="ck_rca_workspace_audit_action"),
        sa.CheckConstraint(f"outcome IN {_OUTCOMES}", name="ck_rca_workspace_audit_outcome"),
        sa.CheckConstraint(f"object_kind IN {_OBJECTS}", name="ck_rca_workspace_audit_object"),
        sa.CheckConstraint(
            "(object_kind IS NULL) = (object_id IS NULL)",
            name="ck_rca_workspace_audit_subject_pair",
        ),
    )
    op.create_index(
        "ix_rca_workspace_audit_events_owner_id", "rca_workspace_audit_events", ["owner_id"]
    )
    op.create_index(
        "ix_rca_workspace_audit_events_occurred_at",
        "rca_workspace_audit_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rca_workspace_audit_events_occurred_at", table_name="rca_workspace_audit_events"
    )
    op.drop_index("ix_rca_workspace_audit_events_owner_id", table_name="rca_workspace_audit_events")
    op.drop_table("rca_workspace_audit_events")
