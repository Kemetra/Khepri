"""`W1-07a` -- the workspace revocation ledger (`RCA-005` `FR-126`; `KHEPRI-DEC-015` §8).

`FR-126` says a restore from backup MUST NOT make a deleted object readable. Live deletion takes
effect immediately, but a backup taken before it still holds the row, so a restore puts it back --
the ledger is what refuses it afterwards.

`KHEPRI-DEC-015` §8 item 6 bounds what the ledger may hold, and the bound is the point: enforcing
the guarantee requires knowing what was revoked, which is itself retained data, so the mechanism
could quietly become a second identity store. It holds **opaque identifiers, revocation timestamps
and status only**. The extent assertion below is what keeps that true.
"""

from __future__ import annotations

from datetime import UTC, datetime

from khepri.rca.workspace.audit import OBJECT_RUN, OBJECT_VERSION
from khepri.rca.workspace.revocation import RevokedObject, SqlRevocationLedger
from tests.w104_support import member
from tests.w104b_support import journey

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_a_revoked_object_is_known_revoked_and_an_unrevoked_one_is_not() -> None:
    """The ledger's whole answer: this identifier ended, that one did not."""
    j = journey()
    who = member(j.w)
    ledger = SqlRevocationLedger(j.w.factory)

    ledger.revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION, object_id="dsv-1", owner_id=who.owner_id, revoked_at=NOW
        )
    )

    assert ledger.is_revoked(OBJECT_VERSION, "dsv-1", who.owner_id) is True
    assert ledger.is_revoked(OBJECT_VERSION, "dsv-2", who.owner_id) is False


def test_another_scopes_revocation_is_not_this_scopes() -> None:
    """Scoped like every other workspace read. A ledger answering across scopes would let one
    organization learn that another's identifier ended."""
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    ledger = SqlRevocationLedger(j.w.factory)

    ledger.revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION, object_id="dsv-1", owner_id=other.owner_id, revoked_at=NOW
        )
    )

    assert ledger.is_revoked(OBJECT_VERSION, "dsv-1", other.owner_id) is True
    assert ledger.is_revoked(OBJECT_VERSION, "dsv-1", who.owner_id) is False


def test_the_same_kind_of_identifier_under_two_kinds_is_two_entries() -> None:
    """`object_kind` is part of the key, not decoration: a run and a version could carry the same
    opaque identifier without one revoking the other."""
    j = journey()
    who = member(j.w)
    ledger = SqlRevocationLedger(j.w.factory)

    ledger.revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION, object_id="x-1", owner_id=who.owner_id, revoked_at=NOW
        )
    )

    assert ledger.is_revoked(OBJECT_VERSION, "x-1", who.owner_id) is True
    assert ledger.is_revoked(OBJECT_RUN, "x-1", who.owner_id) is False


def test_revoking_twice_does_not_move_the_instant() -> None:
    """A repeat is `FR-123`'s idempotent retry reaching the ledger. `KHEPRI-DEC-033` bounds the
    ledger by the backup horizon measured from `revoked_at`, so overwriting it on every repeat
    would let repeated requests push that deadline outward -- the defect `store.py:631` records
    for `retention_changed_at`, arriving here through the same door."""
    j = journey()
    who = member(j.w)
    ledger = SqlRevocationLedger(j.w.factory)
    first = RevokedObject(
        object_kind=OBJECT_VERSION, object_id="dsv-1", owner_id=who.owner_id, revoked_at=NOW
    )

    ledger.revoke(first)
    ledger.revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION, object_id="dsv-1", owner_id=who.owner_id, revoked_at=LATER
        )
    )

    assert ledger.revoked_at(OBJECT_VERSION, "dsv-1", who.owner_id) == NOW


def test_the_ledger_holds_nothing_but_identifiers_and_the_instant() -> None:
    """`KHEPRI-DEC-015` §8 item 6: minimal and purpose-bound. An extent assertion, so a column
    added later fails here rather than quietly turning the ledger into a second content store."""
    from khepri.rca.workspace.schema import WorkspaceRevocationRow

    assert {column.name for column in WorkspaceRevocationRow.__table__.columns} == {
        "object_kind",
        "object_id",
        "owner_id",
        "revoked_at",
    }
