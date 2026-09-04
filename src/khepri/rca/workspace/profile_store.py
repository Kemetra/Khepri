"""The source profile store (`W1-04`; `RCA-005` `FR-114`, `FR-115`).

`W1-02` wrote `SourceProfileRow` and no operation touched it: nothing remembered a profile and
nothing offered one. This is the store for both. It is separate from `SqlWorkspaceRecordStore`
because a profile is not a record the domain acts on -- `contracts.py` keeps `SourceProfile`
unsealed for exactly that reason -- so the store takes and returns the plain dataclass, and
`assert_sealed` has nothing to check.

**A profile is offered only while its version is live.** `KHEPRI-DEC-033` §1: derived content never
outlives its input's right to exist. Both reads join the version and require `active`, so a profile
of a version the customer deleted is not proposed for reuse. Purging the row itself is the cascade
`W1-07` writes; until then the row remains and is unreadable, which is the tombstone posture one
level down.

The two list columns are JSON text, as `W1-02` declared them: a caller-shaped list whose length is
not knowable at migration time, never read as authority -- `RRA-003` admits the new submission.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.persistence import _utc
from khepri.rca.workspace.contracts import SourceProfile
from khepri.rca.workspace.schema import RETENTION_ACTIVE, DatasetVersionRow, SourceProfileRow
from khepri.rca.workspace.unit_of_work import reading, writing


def _profile_from_row(row: SourceProfileRow) -> SourceProfile:
    return SourceProfile(
        profile_id=row.profile_id,
        owner_id=row.owner_id,
        source_version_id=row.source_version_id,
        column_labels=tuple(json.loads(row.column_labels)),
        proposed_mapping=tuple(
            (str(semantic), str(label)) for semantic, label in json.loads(row.proposed_mapping)
        ),
        created_at=_utc(row.created_at),
    )


def _live_profiles(owner_id: str):
    """Profiles in one scope whose source version is still live."""
    return (
        select(SourceProfileRow)
        .join(
            DatasetVersionRow,
            (DatasetVersionRow.owner_id == SourceProfileRow.owner_id)
            & (DatasetVersionRow.version_id == SourceProfileRow.source_version_id),
        )
        .where(SourceProfileRow.owner_id == owner_id)
        .where(DatasetVersionRow.retention_state == RETENTION_ACTIVE)
    )


class SqlSourceProfileStore:
    """Rows for `SourceProfile`. Nothing here authorizes; see `SqlWorkspaceRecordStore`."""

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def add(self, profile: SourceProfile) -> SourceProfile:
        """Store one profile under a version that exists in its scope, or refuse."""
        with writing(self._factory) as database:
            database.add(
                SourceProfileRow(
                    profile_id=profile.profile_id,
                    owner_id=profile.owner_id,
                    source_version_id=profile.source_version_id,
                    column_labels=json.dumps(list(profile.column_labels)),
                    proposed_mapping=json.dumps([list(pair) for pair in profile.proposed_mapping]),
                    created_at=profile.created_at,
                )
            )
        return profile

    def get(self, profile_id: str, owner_id: str) -> SourceProfile | None:
        with reading(self._factory) as database:
            row = database.scalars(
                _live_profiles(owner_id).where(SourceProfileRow.profile_id == profile_id)
            ).one_or_none()
            return None if row is None else _profile_from_row(row)

    def for_scope(self, owner_id: str) -> tuple[SourceProfile, ...]:
        """Newest first, within one scope, over live versions only."""
        with reading(self._factory) as database:
            rows = database.scalars(
                _live_profiles(owner_id).order_by(
                    SourceProfileRow.created_at.desc(), SourceProfileRow.profile_id.desc()
                )
            )
            return tuple(_profile_from_row(row) for row in rows)
