"""A fixture's upload identity for a hand-built dataset version (#535, `RCA-005` `FR-255`).

`DatasetVersion.create` requires the `rra_uploads` key the version was admitted from, and
`uq_rca_workspace_version_upload_id` allows one version per upload in a scope. Fixtures that build
a version from an `AdmittedSource` rather than through an upload derive the identity from the
source's ciphertext digest. One source then stands for one upload, which is the arbitration those
fixtures were written against when uniqueness sat on the digest itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import sessionmaker

from khepri.rca.workspace.contracts import AdmittedSource
from khepri.rra.persistence import Base as RraBase
from khepri.rra.sessions import SessionScope, object_prefix


def upload_for(source: AdmittedSource) -> str:
    """`upl_` and the source's ciphertext digest, without its algorithm prefix."""
    return "upl_" + source.ciphertext_digest.rsplit(":", 1)[-1]


def seed_upload(factory: sessionmaker, owner_id: str, source: AdmittedSource, now: datetime) -> str:
    """The `rra_uploads` row `upload_for(source)` names, in its own session, for a migrated schema.

    On PostgreSQL `fk_rca_workspace_version_upload` keys a version's `(owner_id, upload_id)` onto
    `rra_uploads` (`FR-256`), so a version built from a bare `AdmittedSource` needs the row there.
    Written as the migration owner, which crosses `RRA-017`'s policies. Returns the identity.
    """
    upload_id = upload_for(source)
    session_id = "ses_" + upload_id
    digest = source.ciphertext_digest.rsplit(":", 1)[-1]
    tables = RraBase.metadata.tables
    with factory.begin() as database:
        database.execute(
            tables["rra_beta_sessions"]
            .insert()
            .values(
                session_id=session_id,
                owner_id=owner_id,
                created_at=now,
                content_expires_at=now + timedelta(days=7),
            )
        )
        database.execute(
            tables["rra_uploads"]
            .insert()
            .values(
                upload_id=upload_id,
                owner_id=owner_id,
                session_id=session_id,
                object_key=object_prefix(SessionScope(owner_id, session_id)) + "upload",
                size_bytes=source.size_bytes,
                sha256_hex=source.plaintext_digest.rsplit(":", 1)[-1],
                media_type=source.media_type,
                created_at=now,
                expires_at=now + timedelta(days=7),
                encryption_algorithm="AES-256-GCM",
                envelope_version=2,
                ciphertext_sha256_hex=digest,
            )
        )
    return upload_id
