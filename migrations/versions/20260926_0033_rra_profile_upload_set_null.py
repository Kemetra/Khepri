"""A dataset profile outlives its raw upload, and names it only while it exists (#593).

The owner decided on 2026-09-26 (recorded on #593 and in `KHEPRI-DEC-033` §1) that retention
deleting a raw upload keeps its dataset profile. `rra_dataset_profiles.upload_id` had no key at
all, so `RawUploadRetentionSweeper` has been leaving profiles that name an upload row it already
deleted.

**`ON DELETE SET NULL`, over a now-nullable column.** `RESTRICT` would block the retention sweep,
which deletes the upload row while the profile survives. `CASCADE` would delete the profile
retention keeps. Session deletion deletes profiles before uploads (`deletion_persistence.py`), so
the key never fires on that path.

**A single-column key.** Scope is already bound by `fk_profile_session_scope`. A composite
`(owner_id, session_id, upload_id)` key with `SET NULL` would null the two scope columns, which are
not nullable, and the column-list form `SET NULL (upload_id)` is PostgreSQL 15+ only.

**The upgrade repairs before it keys.** PostgreSQL validates existing rows when a key is added,
and swept databases already hold dangling ids. Those rows are exactly what the owner decision
allows, so they are set to NULL first rather than treated as defects.

**The downgrade refuses once a profile has outlived its upload.** `NOT NULL` cannot be restored
over a NULL without inventing an upload id, so a database holding one refuses to downgrade, with
the reason, instead of pretending to reverse.

Constraint names are spelled literally rather than imported from the model, so a later edit to the
model cannot rewrite what this revision did.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0033"
down_revision: str | None = "20260925_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILES = "rra_dataset_profiles"
_UPLOADS = "rra_uploads"
_KEY = "fk_profile_upload"

_CLEAR_DANGLING = sa.text(
    "UPDATE rra_dataset_profiles SET upload_id = NULL "
    "WHERE upload_id IS NOT NULL "
    "AND upload_id NOT IN (SELECT upload_id FROM rra_uploads)"
)
_OUTLIVED = sa.text("SELECT count(*) FROM rra_dataset_profiles WHERE upload_id IS NULL")


def upgrade() -> None:
    with op.batch_alter_table(_PROFILES) as profiles:
        profiles.alter_column("upload_id", existing_type=sa.String(), nullable=True)
    op.execute(_CLEAR_DANGLING)
    with op.batch_alter_table(_PROFILES) as profiles:
        profiles.create_foreign_key(
            _KEY, _UPLOADS, ["upload_id"], ["upload_id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    outlived = op.get_bind().execute(_OUTLIVED).scalar_one()
    if outlived:
        raise RuntimeError(
            f"{outlived} dataset profile(s) have outlived their raw upload; "
            "NOT NULL cannot be restored over them without inventing an upload id."
        )
    with op.batch_alter_table(_PROFILES) as profiles:
        profiles.drop_constraint(_KEY, type_="foreignkey")
        profiles.alter_column("upload_id", existing_type=sa.String(), nullable=False)
