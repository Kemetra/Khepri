"""A source profile is refused under a deleted version (`#526` D-02; `RCA-005` `FR-114`).

`add_analysis_run` and `add_artifact_binding` lock their parent and refuse one the customer
deleted (`_refuse_tombstoned_parent`). The profile store inserted with neither, so a profile could
be written under a tombstoned version -- a derivative of an input whose right to exist had ended
(`KHEPRI-DEC-033` §1). The reads already hide such a row; this is about not writing it.

Deterministic on SQLite: the foreign key is satisfied by a real, tombstoned version row, so the
only thing that can refuse the insert is the store's own liveness check.
"""

from __future__ import annotations

import pytest

from khepri.rca.workspace.contracts import SourceProfile
from khepri.rca.workspace.schema import PARENT_TOMBSTONED_FAILURE
from khepri.runtime.workspace import WorkspaceRefused
from tests.w104_support import LATER, NOW, admitted_session, member, world


def _profile_for(owner_id: str, version_id: str) -> SourceProfile:
    return SourceProfile(
        profile_id="spf_526",
        owner_id=owner_id,
        source_version_id=version_id,
        column_labels=("day", "net_sales"),
        proposed_mapping=(("business_day", "day"),),
        created_at=LATER,
    )


def test_a_profile_is_refused_under_a_tombstoned_version() -> None:
    w = world()
    who = member(w)
    session_id = admitted_session(w, who.owner_id)
    version = w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)
    w.store.tombstone_dataset_version(version.version_id, now=LATER, owner_id=who.owner_id)

    with pytest.raises(ValueError, match=PARENT_TOMBSTONED_FAILURE):
        w.profiles.add_source_profile(_profile_for(who.owner_id, version.version_id))

    with w.factory() as database:
        from sqlalchemy import func, select

        from khepri.rca.workspace.schema import SourceProfileRow

        stored = database.scalar(select(func.count()).select_from(SourceProfileRow))
    assert stored == 0, "a profile was written under a deleted version"


def test_a_profile_under_a_live_version_is_still_stored() -> None:
    """The refusal must be the tombstone's, not every insert's."""
    w = world()
    who = member(w)
    session_id = admitted_session(w, who.owner_id)
    version = w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)

    profile = w.profiles.add_source_profile(_profile_for(who.owner_id, version.version_id))

    assert w.profiles.get(profile.profile_id, who.owner_id) == profile


def test_a_version_deleted_mid_remember_is_a_workspace_refusal() -> None:
    """`remember_profile` reads the version live and then inserts. A deletion landing between the
    two reaches the store's refusal, which the service must turn into its content-free
    `WorkspaceRefused` -- the translation `start_run` already makes for `add_analysis_run`.

    The deletion is injected immediately before the insert, not after the service's read: the
    admission read between the two runs `RRA` sessions over the fixture's one shared `StaticPool`
    connection, and their rollback would silently discard a tombstone written earlier in the unit.
    """
    w = world()
    who = member(w)
    session_id = admitted_session(w, who.owner_id)
    version = w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)
    real_add = w.profiles.add_source_profile

    def deleted_first(profile: SourceProfile) -> SourceProfile:
        w.store.tombstone_dataset_version(
            profile.source_version_id, now=LATER, owner_id=profile.owner_id
        )
        return real_add(profile)

    w.profiles.add_source_profile = deleted_first  # type: ignore[method-assign]
    with pytest.raises(WorkspaceRefused):
        w.services.remember_source_profile(
            who.caller, version_id=version.version_id, session_id=session_id, now=LATER
        )
