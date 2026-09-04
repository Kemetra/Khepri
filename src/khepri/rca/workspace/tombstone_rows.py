"""The tombstone table's row mapping, in both directions (`W1-03`).

`rca_workspace_tombstones` holds both subjects in one nullable union (`schema.py`), and each row
belongs to one allowlist by `subject_kind`. This module is the only place a `VersionTombstone` or
`RunTombstone` becomes a row or is rebuilt from one, so the two directions can be read side by side
and a column mapped in one and forgotten in the other is visible on the page.

**Every column is named.** The row constructors below spell out each allowlisted column rather than
spreading the tombstone's fields, for the same reason the projections in `tombstones.py` name each
field: the allowlist is stated where it is used, and a reviewer can check it against
`KHEPRI-DEC-033` §3 without following an indirection. The `CHECK` constraints `W1-02` wrote refuse
a row that fills the other subject's side, so a mapping error here fails at the insert rather than
reaching a reader.

Split from `store.py` so the store stays the operations and their locks; this is a translation.
"""

from __future__ import annotations

from khepri.rca.persistence import _utc
from khepri.rca.workspace.contracts import (
    AdmittedSource,
    RunSubject,
    VersionLifecycle,
    _identifier,
)
from khepri.rca.workspace.schema import (
    TOMBSTONE_RUN,
    TOMBSTONE_SECTIONS,
    TOMBSTONE_VERSION,
    WorkspaceTombstoneRow,
)
from khepri.rca.workspace.tombstones import (
    RunTombstone,
    RunTrace,
    VersionSubject,
    VersionTombstone,
)


def tombstone_row(tombstone: VersionTombstone | RunTombstone) -> WorkspaceTombstoneRow:
    """A new row for a tombstone, on the side of the allowlist its subject belongs to."""
    if isinstance(tombstone, VersionTombstone):
        return _version_row(tombstone)
    return _run_row(tombstone)


def tombstone_from_row(row: WorkspaceTombstoneRow) -> VersionTombstone | RunTombstone:
    """The tombstone a row holds, rebuilt through its reconstruction door."""
    if row.subject_kind == TOMBSTONE_VERSION:
        return _version_from_row(row)
    return _run_from_row(row)


def _version_row(tombstone: VersionTombstone) -> WorkspaceTombstoneRow:
    # `version_id` restates `subject_id` on a version's row: §3 keeps "the opaque version id" and
    # the identity `CHECK` requires the two to agree.
    return WorkspaceTombstoneRow(
        tombstone_id=_identifier("tmb"),
        subject_kind=TOMBSTONE_VERSION,
        subject_id=tombstone.version_id,
        owner_id=tombstone.owner_id,
        deleted_at=tombstone.deleted_at,
        version_id=tombstone.version_id,
        created_at=tombstone.created_at,
        sealed_at=tombstone.sealed_at,
        upload_plaintext_digest=tombstone.upload_plaintext_digest,
        upload_ciphertext_digest=tombstone.upload_ciphertext_digest,
        upload_size_bytes=tombstone.upload_size_bytes,
        upload_media_type=tombstone.upload_media_type,
        manifest_digest=tombstone.manifest_digest,
        mapping_version=tombstone.mapping_version,
        admission_outcome=tombstone.admission_outcome,
    )


def _run_row(tombstone: RunTombstone) -> WorkspaceTombstoneRow:
    # `version_id` on a run's row is the dataset the run derived from -- the one column §3 puts on
    # both allowlists, and the provenance a run tombstone would lose without it.
    return WorkspaceTombstoneRow(
        tombstone_id=_identifier("tmb"),
        subject_kind=TOMBSTONE_RUN,
        subject_id=tombstone.run_id,
        owner_id=tombstone.owner_id,
        deleted_at=tombstone.deleted_at,
        version_id=tombstone.version_id,
        started_at=tombstone.started_at,
        completed_at=tombstone.completed_at,
        package_digest=tombstone.package_digest,
        package_version=tombstone.package_version,
        formula_version=tombstone.formula_version,
        section_overview=tombstone.section_overview,
        section_comparison=tombstone.section_comparison,
        section_concentration=tombstone.section_concentration,
        section_growth=tombstone.section_growth,
        section_basket=tombstone.section_basket,
    )


def _version_from_row(row: WorkspaceTombstoneRow) -> VersionTombstone:
    return VersionTombstone._from_storage(
        subject=VersionSubject(version_id=row.subject_id, owner_id=row.owner_id),
        source=AdmittedSource(
            plaintext_digest=row.upload_plaintext_digest,
            ciphertext_digest=row.upload_ciphertext_digest,
            size_bytes=row.upload_size_bytes,
            media_type=row.upload_media_type,
            manifest_digest=row.manifest_digest,
            mapping_version=row.mapping_version,
            admission_outcome=row.admission_outcome,
        ),
        lifecycle=VersionLifecycle(created_at=_utc(row.created_at), sealed_at=_utc(row.sealed_at)),
        deleted_at=_utc(row.deleted_at),
    )


def _run_from_row(row: WorkspaceTombstoneRow) -> RunTombstone:
    return RunTombstone._from_storage(
        subject=RunSubject(run_id=row.subject_id, owner_id=row.owner_id, version_id=row.version_id),
        trace=RunTrace(
            started_at=_utc(row.started_at),
            completed_at=_utc(row.completed_at),
            package_digest=row.package_digest,
            package_version=row.package_version,
            formula_version=row.formula_version,
            sections={
                section: getattr(row, f"section_{section}") for section in TOMBSTONE_SECTIONS
            },
        ),
        deleted_at=_utc(row.deleted_at),
    )
