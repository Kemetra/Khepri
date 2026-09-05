"""`W1-07a` -- the restore guard and `KHEPRI-DEC-033` §5's copy constraint.

`FR-126`: a restore from backup MUST NOT make a deleted or tombstoned object readable. Live
deletion is immediate and independent of any backup (`KHEPRI-DEC-015` §8 item 1), but a backup
taken before it still holds the row -- so the guarantee cannot be a property of the delete. The
ledger is what a read consults afterwards.

**The restore is modelled with raw SQL, deliberately.** `_check_one_way_transitions` refuses to
move a tombstoned row back through the ORM, which is right and is not this guarantee: a restore
replaces rows *beneath* the ORM, so a test that went through it would assert the wrong guard and
pass while `FR-126` was unmet. Measured before this slice: after a raw restore,
`get_dataset_version` answered the version as readable.
"""

from __future__ import annotations

from sqlalchemy import text

from khepri.runtime.shell_copy import SHELL_COPY
from tests.w104_support import member
from tests.w107_support import NOW, deletion_service, journey, sealed_version


def _restore(j, version_id: str) -> None:
    """Put the row back live the way a backup restore does: beneath the ORM's one-way guard."""
    with j.w.factory() as database:
        database.execute(
            text(
                "UPDATE rca_workspace_dataset_versions "
                "SET retention_state='active' WHERE version_id=:v"
            ),
            {"v": version_id},
        )
        database.commit()


def test_a_restored_deleted_version_is_not_readable() -> None:
    """`FR-126`, through the read a surface actually makes."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )

    _restore(j, version.version_id)

    assert j.w.store.get_dataset_version(version.version_id, who.owner_id) is None


def test_a_restored_version_is_absent_from_the_scopes_history() -> None:
    """The listing a surface renders, not only the single read: a restored row that reappeared in
    the history would put a deleted analysis back in front of the customer."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )

    _restore(j, version.version_id)

    history = j.w.store.history_for_scope(who.owner_id)
    assert [v.version_id for v in history.versions] == []
    assert len(history.tombstones) == 1


def test_a_version_that_was_never_deleted_stays_readable() -> None:
    """The guard refuses what the ledger names, and nothing else -- a check that refused every
    version would pass the two tests above while breaking the product."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)

    assert j.w.store.get_dataset_version(version.version_id, who.owner_id) is not None
    assert len(j.w.store.history_for_scope(who.owner_id).versions) == 1


def test_no_surface_says_content_expires_automatically() -> None:
    """`KHEPRI-DEC-033` §5: until `W1-07b` ships a sweep with a caller, no surface may tell a
    customer that content expires by itself.

    **This guard passes over an empty set today** -- no `SHELL_COPY` string contains the word --
    so it was proven by the inverse mutant instead: adding a violating string makes it fail, and
    removing it makes it pass again. Recorded because a guard nobody has watched fail is not
    evidence of anything.
    """
    for language, copy in SHELL_COPY.items():
        for key, text_value in copy.items():
            assert "automatic" not in str(text_value).lower(), f"{language}.{key}"
