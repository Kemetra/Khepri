"""Bind the upload a dataset profile names to the profile's own scope (#600).

`20260926_0033` (#599) keyed `rra_dataset_profiles.upload_id` onto `rra_uploads.upload_id`. That
proves the upload exists, not that it is in the profile's `(owner_id, session_id)`, so a profile in
scope A could name scope B's upload and satisfy both keys. `20260925_0031` closed the same shape for
packages with a composite key, and this revision does the same here.

**`ON DELETE SET NULL (upload_id)`.** Retention deletes a raw upload and keeps its profile (the
#593 decision). A composite key with a plain `SET NULL` would also null `owner_id` and `session_id`,
which are `NOT NULL`. The column-list form nulls only `upload_id`. It is PostgreSQL 15+, and every
target runs 17.

**PostgreSQL only.** SQLite cannot express the column-list form, so on SQLite this revision changes
nothing and the ORM model's single-column key stands. Production and every deployed database run
PostgreSQL. The key is proved at `tests/test_i600_profile_upload_scope.py`.

**It replaces `fk_profile_upload` instead of sitting beside it.** The composite key implies the
single-column one. `uq_upload_scope` exists only as the reference target, because `upload_id` is
already the primary key.

**The upgrade repairs before it keys.** PostgreSQL validates existing rows when a key is added. A
profile naming an upload outside its own scope has no claim to that upload, so its `upload_id` is
set to NULL, the state #593 already admits, rather than failing the upgrade.

Constraint names are spelled literally rather than imported from the model, so a later edit to the
model cannot rewrite what this revision did.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0034"
down_revision: str | None = "20260926_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROFILES = "rra_dataset_profiles"
_UPLOADS = "rra_uploads"
_SCOPE = ["owner_id", "session_id", "upload_id"]
_TARGET = "uq_upload_scope"
_COMPOSITE = "fk_profile_upload_scope"
_LEGACY = "fk_profile_upload"

_CLEAR_CROSS_SCOPE = sa.text(
    "UPDATE rra_dataset_profiles AS profile SET upload_id = NULL "
    "WHERE profile.upload_id IS NOT NULL AND NOT EXISTS ("
    "SELECT 1 FROM rra_uploads AS upload WHERE upload.upload_id = profile.upload_id "
    "AND upload.owner_id = profile.owner_id AND upload.session_id = profile.session_id)"
)
_ADD_COMPOSITE = sa.text(
    "ALTER TABLE rra_dataset_profiles ADD CONSTRAINT fk_profile_upload_scope "
    "FOREIGN KEY (owner_id, session_id, upload_id) "
    "REFERENCES rra_uploads (owner_id, session_id, upload_id) "
    "ON DELETE SET NULL (upload_id)"
)


def _on_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _on_postgres():
        return
    op.execute(_CLEAR_CROSS_SCOPE)
    op.create_unique_constraint(_TARGET, _UPLOADS, _SCOPE)
    op.drop_constraint(_LEGACY, _PROFILES, type_="foreignkey")
    op.execute(_ADD_COMPOSITE)


def downgrade() -> None:
    if not _on_postgres():
        return
    op.drop_constraint(_COMPOSITE, _PROFILES, type_="foreignkey")
    op.drop_constraint(_TARGET, _UPLOADS, type_="unique")
    op.create_foreign_key(
        _LEGACY, _PROFILES, _UPLOADS, ["upload_id"], ["upload_id"], ondelete="SET NULL"
    )
