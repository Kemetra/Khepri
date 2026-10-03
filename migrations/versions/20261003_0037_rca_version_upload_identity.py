"""Give each dataset version its upload's stable identity (`RCA-005` `FR-262`, #535).

`RRA-002`'s encryption is randomised, so re-sealing an upload changes
`rra_uploads.ciphertext_sha256_hex`. Three joins matched a version to its upload on that digest.
This revision gives `rca_workspace_dataset_versions` the upload's primary key, `upload_id`, and the
code at this revision joins on it instead. In order:

1. on PostgreSQL, refuse to run while an application process is connected, then take an
   `EXCLUSIVE` lock on `rra_uploads` and the version table, so no old writer inserts a version
   without the column;
2. add `upload_id`, nullable;
3. abort if any version's digest matches more than one upload row in its scope;
4. set each version's `upload_id` from the one upload row in its scope whose ciphertext digest
   equals the version's recorded digest, leaving it null where none does;
5. on PostgreSQL, add the reference index `uq_rra_upload_owner_identity` on
   `rra_uploads (owner_id, upload_id)` and the foreign key `fk_rca_workspace_version_upload`, with
   `ON DELETE SET NULL (upload_id)`, following `20260926_0034`;
6. create `uq_rca_workspace_version_upload_id` and drop `uq_rca_workspace_version_upload`;
7. on PostgreSQL, move the sweep role's column grant from `upload_ciphertext_digest` to
   `upload_id`. `RRA-017` `FR-271` grants it "the columns `_due` reads", and `_due` now reads
   `owner_id`, `upload_id` and `sealed_at`.

**Stop every application process first.** Code from before this revision would insert a version
with a null `upload_id` while its upload still exists, and that upload would then be neither purged
nor found by a deletion until `khepri.runtime.upload_identity_repair` ran. So on PostgreSQL the
revision refuses to start while any runtime role (`khepri_app`, `khepri_worker`, `khepri_sweep`,
`RRA-017` `FR-270`) holds a connection to the database. That check is what keeps old code out, and
it sees only those three roles: a process connected as the migration owner or another role is not
detected, so stopping the app is still the operator's step. The `EXCLUSIVE` locks on
`rra_uploads` and the version table, taken together and first, then hold off any writer that
connects afterwards until this commits, in one order, so such a writer queues rather than
deadlocks against the index and key this adds on `rra_uploads`. The order, in every environment:
stop web, worker and sweep; run this upgrade; start the new code.

**The digest match is valid only because no upload has been re-sealed yet.** That is why
`FR-263` opens the re-seal slice only once this revision is at head.

**The runner must cross row security.** `rra_uploads` is under `FORCE ROW LEVEL SECURITY`
(`20261002_0036`), and its policies name only the runtime roles. A runner without `BYPASSRLS` would
see no upload row, leave every `upload_id` null, and let the downgrade's re-seal check pass on
nothing. `RRA-017` `FR-270` gives the migration owner that attribute; this revision refuses to run
without it rather than complete against an empty read.

**The downgrade fails closed.** It aborts if any version's `upload_id` names an upload whose digest
differs from the version's: that upload has been re-sealed, and the digest joins it restores would
miss it.

**It replays on the RCA-only chain.** `tests/test_rca001_migration.py` drives the RCA revisions on
a SQLite schema that has no `rra_uploads`. There, no version can name an upload, so the reads that
need one (the ambiguity check, the backfill, the downgrade's re-seal check) are skipped and every
`upload_id` stays null, which is what the backfill would have produced. In a deployed database
`rra_uploads` always exists, and the reads run.

Migration `20260915_0030` already ran; its one-time digest join is left as it is. Every name is
spelled literally, so a later edit to the model cannot rewrite what this revision did.

The migration head is pinned in three places and this revision moves all of them:
`tests/test_rca001_migration.py` `RCA_UNREPLAYED`,
`tests/test_rca001_session_persistence.py`'s `alembic heads` assertion, and
`specs/001-rca-001-commercial-identity/STATUS.md`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0037"
down_revision: str | None = "20261002_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VERSIONS = "rca_workspace_dataset_versions"
_UPLOADS = "rra_uploads"
_IDENTITY = ["owner_id", "upload_id"]
_IDENTITY_INDEX = "uq_rca_workspace_version_upload_id"
_DIGEST_INDEX = "uq_rca_workspace_version_upload"
_TARGET = "uq_rra_upload_owner_identity"
_KEY = "fk_rca_workspace_version_upload"
_SWEEP = "khepri_sweep"

_MATCHES = (
    "SELECT count(*) FROM rra_uploads AS u WHERE u.owner_id = v.owner_id "
    "AND u.ciphertext_sha256_hex = v.upload_ciphertext_digest"
)
_AMBIGUOUS = f"SELECT count(*) FROM rca_workspace_dataset_versions AS v WHERE ({_MATCHES}) > 1"
_BACKFILL = (
    "UPDATE rca_workspace_dataset_versions SET upload_id = ("
    "SELECT u.upload_id FROM rra_uploads AS u "
    "WHERE u.owner_id = rca_workspace_dataset_versions.owner_id "
    "AND u.ciphertext_sha256_hex = rca_workspace_dataset_versions.upload_ciphertext_digest"
    ") WHERE upload_id IS NULL"
)
_RESEALED = (
    "SELECT count(*) FROM rca_workspace_dataset_versions AS v JOIN rra_uploads AS u "
    "ON u.owner_id = v.owner_id AND u.upload_id = v.upload_id "
    "WHERE u.ciphertext_sha256_hex <> v.upload_ciphertext_digest"
)
_BLIND = (
    "SELECT c.relrowsecurity AND NOT (r.rolsuper OR r.rolbypassrls) "
    "FROM pg_class AS c JOIN pg_roles AS r ON r.rolname = current_user "
    "WHERE c.oid = 'public.rra_uploads'::regclass"
)
_LOCK = "LOCK TABLE public.rra_uploads, public.rca_workspace_dataset_versions IN EXCLUSIVE MODE"
_RUNNING = (
    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
    "AND pid <> pg_backend_pid() AND usename IN ('khepri_app', 'khepri_worker', 'khepri_sweep')"
)
_ADD_KEY = (
    "ALTER TABLE public.rca_workspace_dataset_versions ADD CONSTRAINT "
    "fk_rca_workspace_version_upload FOREIGN KEY (owner_id, upload_id) "
    "REFERENCES public.rra_uploads (owner_id, upload_id) ON DELETE SET NULL (upload_id)"
)
_GRANT = "GRANT SELECT ({column}) ON public.rca_workspace_dataset_versions TO khepri_sweep"
_REVOKE = "REVOKE SELECT ({column}) ON public.rca_workspace_dataset_versions FROM khepri_sweep"

AMBIGUOUS_FAILURE = "a dataset version's ciphertext digest matches more than one upload row"
RESEALED_FAILURE = "an upload has been re-sealed; the digest joins cannot be restored"
BLIND_FAILURE = "the migration runner is subject to row security on rra_uploads (RRA-017 FR-270)"
RUNNING_FAILURE = (
    "an application process is connected; stop web, worker and sweep before this revision runs"
)


def _on_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _count(statement: str) -> int:
    return op.get_bind().execute(sa.text(statement)).scalar_one()


def _hold_off_writers() -> None:
    """Refuse a runner that cannot see every upload, or an application still running, then lock."""
    if op.get_bind().execute(sa.text(_BLIND)).scalar_one():
        raise RuntimeError(BLIND_FAILURE)
    if _count(_RUNNING):
        raise RuntimeError(RUNNING_FAILURE)
    op.execute(_LOCK)


def _uploads_exist() -> bool:
    return sa.inspect(op.get_bind()).has_table(_UPLOADS)


def _backfill() -> None:
    if not _uploads_exist():
        return
    if _count(_AMBIGUOUS):
        raise RuntimeError(AMBIGUOUS_FAILURE)
    op.execute(_BACKFILL)


def _key_and_grant() -> None:
    op.create_index(_TARGET, _UPLOADS, _IDENTITY, unique=True)
    op.execute(_ADD_KEY)
    op.execute(_GRANT.format(column="upload_id"))
    op.execute(_REVOKE.format(column="upload_ciphertext_digest"))


def _unkey_and_ungrant() -> None:
    op.execute(_REVOKE.format(column="upload_id"))
    op.execute(_GRANT.format(column="upload_ciphertext_digest"))
    op.drop_constraint(_KEY, _VERSIONS, type_="foreignkey")
    op.drop_index(_TARGET, table_name=_UPLOADS)


def upgrade() -> None:
    postgres = _on_postgres()
    if postgres:
        _hold_off_writers()
    op.add_column(_VERSIONS, sa.Column("upload_id", sa.String(), nullable=True))
    _backfill()
    if postgres:
        _key_and_grant()
    op.create_index(_IDENTITY_INDEX, _VERSIONS, _IDENTITY, unique=True)
    op.drop_index(_DIGEST_INDEX, table_name=_VERSIONS)


def downgrade() -> None:
    postgres = _on_postgres()
    if postgres:
        _hold_off_writers()
    if _uploads_exist() and _count(_RESEALED):
        raise RuntimeError(RESEALED_FAILURE)
    if postgres:
        _unkey_and_ungrant()
    op.create_index(_DIGEST_INDEX, _VERSIONS, ["owner_id", "upload_ciphertext_digest"], unique=True)
    op.drop_index(_IDENTITY_INDEX, table_name=_VERSIONS)
    op.execute("ALTER TABLE rca_workspace_dataset_versions DROP COLUMN upload_id")
