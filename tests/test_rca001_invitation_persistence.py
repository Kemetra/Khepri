"""`R4-03` -- the invitation table, its store, and its retention sweep.

Scope: persistence only. Issuance and revocation services are `R4-04`, the cascades `R4-06`,
redemption and its uniform-failure path `R4-05`.

Three claims here are not about SQL mechanics and are the reason the file is long: that the four
`CHECK` constraints refuse what the domain refuses, that a read destroys an expired verifier, and
that the sweep implements two lifecycle rules rather than one horizon.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.credentials import KdfParams, Verifier
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_retention import (
    INVITATION_HORIZON_IS_UNENFORCED,
    InvitationRetentionSweeper,
)
from khepri.rca.invitations import (
    Invitation,
    InvitationOffer,
    issue_secret,
    verify_secret,
)
from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import InvitationRow, SqlAccountStore, SqlOrganizationStore
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    factory_fixture,
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
ISSUED = NOW - timedelta(days=1)
LATER = NOW + timedelta(days=7)
TARGET = "invitee@example.com"


_ORGANIZATIONS = itertools.count()


def _organization(factory: sessionmaker) -> tuple[str, str]:
    """A real organization row, because the invitation FK is RESTRICT and must be satisfiable.

    The owner's address is unique per call: `create_account` fails closed on a duplicate email
    rather than returning a marker, so a shared constant would make the *second* organization in any
    test raise instead of building a fixture.
    """
    nth = next(_ORGANIZATIONS)
    accounts = SqlAccountStore(factory)
    owner = AccountService(accounts).create_account(
        f"owner{nth}@example.com", "correct horse battery staple"
    )
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        f"Acme {nth}", owner.account_id, now=ISSUED
    )
    return organization.organization_id, owner.account_id


def _offer(organization_id: str, actor_id: str, *, role: str = MEMBER_ROLE, target: str = TARGET):
    return InvitationOffer(
        organization_id=organization_id,
        intended_role=role,
        target_identity=target,
        issued_by=actor_id,
    )


def _invitation(
    factory: sessionmaker,
    *,
    role: str = MEMBER_ROLE,
    expires_at: datetime = LATER,
    target: str = TARGET,
) -> tuple[SqlInvitationStore, Invitation, str]:
    organization_id, actor_id = _organization(factory)
    store = SqlInvitationStore(factory)
    invitation = Invitation.create(
        _offer(organization_id, actor_id, role=role, target=target),
        secret=issue_secret(),
        expires_at=expires_at,
        issued_at=ISSUED,
    )
    assert store.add_invitation(invitation)
    return store, invitation, organization_id



def _stored_verifier_columns(
    factory: sessionmaker, invitation_id: str
) -> tuple[object, object, object, object, object]:
    """The five verifier columns as the database holds them, bypassing every destroying read.

    `get_invitation`, `find_for_redemption` and `invitations_for_organization` all destroy an
    expired verifier, so none can witness whether a *previous* call persisted its destruction. This
    reads the row, which is what `SqlInvitationStore.get_invitation`'s own docstring tells a test to
    do when it needs to observe undestroyed bytes.
    """
    with factory() as database:
        row = database.get(InvitationRow, invitation_id)
        assert row is not None
        return (row.secret_salt, row.secret_digest, row.kdf_n, row.kdf_r, row.kdf_p)


# --- the round trip ---------------------------------------------------------------------------


def test_an_invitation_survives_a_round_trip_through_the_store(factory: sessionmaker) -> None:
    store, invitation, organization_id = _invitation(factory)

    restored = store.get_invitation(invitation.invitation_id, now=NOW)

    assert restored is not None
    assert restored.organization_id == organization_id
    assert restored.intended_role == MEMBER_ROLE
    assert restored.target_identity == TARGET
    assert restored.expires_at == LATER
    assert restored.issued_at == ISSUED
    assert restored.redeemed_at is None
    assert restored.revoked_at is None


def test_the_stored_verifier_still_verifies_the_secret_it_was_derived_from(
    factory: sessionmaker,
) -> None:
    """The five columns round-trip as one whole. A store that dropped the KDF parameters and let
    `_verifier_from_row` default them would fail here rather than silently verifying nothing."""
    organization_id, actor_id = _organization(factory)
    store = SqlInvitationStore(factory)
    secret = issue_secret()
    store.add_invitation(
        Invitation.create(
            _offer(organization_id, actor_id),
            secret=secret,
            expires_at=LATER,
            issued_at=ISSUED,
        )
    )

    restored = store.get_invitation(secret.invitation_id, now=NOW)

    assert restored is not None
    assert verify_secret(secret.secret, restored.verifier)
    assert not verify_secret("not-the-secret", restored.verifier)


def test_timestamps_come_back_timezone_aware(factory: sessionmaker) -> None:
    """SQLite drops `tzinfo`, so a naive `expires_at` would compare wrongly against an aware `now`
    and mis-decide expiry -- the one thing the column exists to decide. `_utc` is why this holds."""
    store, invitation, _ = _invitation(factory)

    restored = store.get_invitation(invitation.invitation_id, now=NOW)

    assert restored is not None
    assert restored.expires_at.tzinfo is not None
    assert restored.issued_at.tzinfo is not None
    assert restored.is_expired_at(LATER)
    assert not restored.is_expired_at(NOW)


def test_a_duplicate_identifier_is_refused_rather_than_raising(factory: sessionmaker) -> None:
    store, invitation, _ = _invitation(factory)

    assert store.add_invitation(invitation) is False


def test_the_target_identity_is_canonicalized_at_rest(factory: sessionmaker) -> None:
    """`R4-01` §4 requires both the migration and `R4-04` apply this, because a store caller that
    bypassed the service would otherwise write a raw address -- and then the addressee check, the
    recipient cascade, and the purge cascade would all fail to match an account at the canonical
    form. Asserted at the store because that is the boundary that cannot be bypassed."""
    store, invitation, _ = _invitation(factory, target="Alice@Example.COM ")

    restored = store.get_invitation(invitation.invitation_id, now=NOW)

    assert restored is not None
    assert restored.target_identity == "alice@example.com"


def test_listing_is_scoped_to_one_organization(factory: sessionmaker) -> None:
    """`R4-01` §4.1 scopes revocation by `(organization_id, invitation_id)`, never by identifier
    alone. A listing that crossed organizations would be the enumeration oracle `FR-023` forbids."""
    store, first, first_org = _invitation(factory)
    second_org, second_actor = _organization(factory)
    other = Invitation.create(
        _offer(second_org, second_actor),
        secret=issue_secret(),
        expires_at=LATER,
        issued_at=ISSUED,
    )
    assert store.add_invitation(other)

    held = store.invitations_for_organization(first_org, now=NOW)

    assert [invitation.invitation_id for invitation in held] == [first.invitation_id]
    listed = store.invitations_for_organization(second_org, now=NOW)
    assert listed[0].invitation_id == other.invitation_id


# --- the four CHECK constraints ---------------------------------------------------------------


def _insert_raw(factory: sessionmaker, organization_id: str, **overrides: object) -> None:
    """Write a row through raw SQL, bypassing the domain doors entirely.

    This is the whole point of the constraints: `Invitation.create` already refuses each of these,
    and the CHECK exists because a store caller can reach the row directly. A test that went through
    the domain would prove the domain guard, not the column.
    """
    values: dict[str, object] = {
        "invitation_id": "inv_raw",
        "organization_id": organization_id,
        "intended_role": MEMBER_ROLE,
        "target_identity": TARGET,
        "secret_salt": None,
        "secret_digest": None,
        "kdf_n": None,
        "kdf_r": None,
        "kdf_p": None,
        "expires_at": LATER,
        "issued_by": "acc_someone",
        "issued_at": ISSUED,
        "redeemed_at": None,
        "revoked_at": None,
    }
    values.update(overrides)
    columns = ", ".join(values)
    binds = ", ".join(f":{name}" for name in values)
    with factory.begin() as database:
        database.execute(
            text(f"INSERT INTO rca_invitations ({columns}) VALUES ({binds})"), values
        )


def test_an_undeclared_role_is_refused_by_the_column(factory: sessionmaker) -> None:
    organization_id, _ = _organization(factory)

    with pytest.raises(IntegrityError):
        _insert_raw(factory, organization_id, intended_role="superadmin")


@pytest.mark.parametrize("role", [OWNER_ROLE, MEMBER_ROLE])
def test_either_declared_role_is_accepted_by_the_column(
    factory: sessionmaker, role: str
) -> None:
    """Both roles are storable, so the refusal above rejects forgery rather than everything."""
    organization_id, _ = _organization(factory)

    _insert_raw(factory, organization_id, intended_role=role)


def test_an_invitation_cannot_be_both_redeemed_and_revoked(factory: sessionmaker) -> None:
    organization_id, _ = _organization(factory)

    with pytest.raises(IntegrityError):
        _insert_raw(factory, organization_id, redeemed_at=NOW, revoked_at=NOW)


def test_an_invitation_cannot_expire_at_or_before_its_issuance(factory: sessionmaker) -> None:
    organization_id, _ = _organization(factory)

    with pytest.raises(IntegrityError):
        _insert_raw(factory, organization_id, expires_at=ISSUED)


def test_a_half_destroyed_verifier_is_refused_by_the_column(factory: sessionmaker) -> None:
    """The invariant `AccountRow` does not carry. `credentials.py:77-80` records that destruction
    "cannot be done by halves"; held as five independently-nullable columns a salt-gone/digest-kept
    row is expressible, and nothing but this constraint refuses it."""
    organization_id, _ = _organization(factory)
    secret = issue_secret()

    with pytest.raises(IntegrityError):
        _insert_raw(
            factory,
            organization_id,
            secret_salt=None,
            secret_digest=secret.verifier.digest,
            kdf_n=secret.verifier.kdf.n,
            kdf_r=secret.verifier.kdf.r,
            kdf_p=secret.verifier.kdf.p,
        )


def test_dropping_one_kdf_parameter_is_also_refused(factory: sessionmaker) -> None:
    """The clause compares every column against `secret_salt` rather than chaining pairwise, so a
    gap in the middle cannot rely on transitivity holding across a missing link."""
    organization_id, _ = _organization(factory)
    secret = issue_secret()

    with pytest.raises(IntegrityError):
        _insert_raw(
            factory,
            organization_id,
            secret_salt=secret.verifier.salt,
            secret_digest=secret.verifier.digest,
            kdf_n=secret.verifier.kdf.n,
            kdf_r=secret.verifier.kdf.r,
            kdf_p=None,
        )


def test_a_complete_verifier_and_a_wholly_absent_one_are_both_accepted(
    factory: sessionmaker,
) -> None:
    """Both terminal shapes are storable, so the two refusals above reject halves rather than
    rejecting the verifier column set outright."""
    organization_id, _ = _organization(factory)
    secret = issue_secret()

    _insert_raw(factory, organization_id, invitation_id="inv_absent")
    _insert_raw(
        factory,
        organization_id,
        invitation_id="inv_present",
        secret_salt=secret.verifier.salt,
        secret_digest=secret.verifier.digest,
        kdf_n=secret.verifier.kdf.n,
        kdf_r=secret.verifier.kdf.r,
        kdf_p=secret.verifier.kdf.p,
    )


def test_the_organization_foreign_key_is_enforced(factory: sessionmaker) -> None:
    with pytest.raises(IntegrityError):
        _insert_raw(factory, "org_does_not_exist")


def test_there_is_no_unique_constraint_on_recipient_or_organization(
    factory: sessionmaker,
) -> None:
    """**A negative asserted deliberately**, per `R4-01` §3. The same person may hold two
    outstanding invitations to one organization -- the scenario §7's counter-example turns on -- and
    a `UNIQUE (organization_id, target_identity)` would hide that case rather than handle it.
    Encoding an unrequired cardinality is the defect `R7-02` spent a slice unwinding."""
    store, first, organization_id = _invitation(factory)
    _, actor_id = _organization(factory)

    second = Invitation.create(
        _offer(organization_id, actor_id),
        secret=issue_secret(),
        expires_at=LATER + timedelta(days=1),
        issued_at=ISSUED,
    )

    assert store.add_invitation(second)
    held = store.invitations_for_organization(organization_id, now=NOW)
    assert len(held) == 2
    assert {invitation.target_identity for invitation in held} == {TARGET}


# --- destroy on first touch (§3) --------------------------------------------------------------


def test_reading_an_expired_invitation_destroys_its_verifier(factory: sessionmaker) -> None:
    """`KHEPRI-DEC-015` §5 measures the harm of a surviving verifier in *days*, and expiry fires no
    event -- so nothing reaches the bytes unless a read does. `R4-01` §3's destroy-on-first-touch.

    Asserted on a second, independent read rather than only on the return value: a method that
    returned a verifier-less record without writing would pass a single-read assertion.
    """
    store, invitation, _ = _invitation(factory, expires_at=NOW - timedelta(hours=1))

    touched = store.find_for_redemption(invitation.invitation_id, now=NOW)

    assert touched is not None
    assert touched.verifier is None
    assert store.get_invitation(invitation.invitation_id, now=NOW).verifier is None


def test_reading_a_live_invitation_leaves_its_verifier_intact(factory: sessionmaker) -> None:
    """The other half. A read path that destroyed unconditionally would satisfy the test above and
    brick every live invitation the moment anyone presented one."""
    store, invitation, _ = _invitation(factory)

    found = store.find_for_redemption(invitation.invitation_id, now=NOW)

    assert found is not None
    assert found.verifier is not None
    assert store.get_invitation(invitation.invitation_id, now=NOW).verifier is not None


def test_the_expiry_boundary_instant_destroys(factory: sessionmaker) -> None:
    """`expires_at <= now`, matching `Invitation.is_expired_at` and RRA's `redeem`. A `<` here would
    leave a one-instant window in which an expired verifier survives a read."""
    store, invitation, _ = _invitation(factory, expires_at=NOW)

    touched = store.find_for_redemption(invitation.invitation_id, now=NOW)

    assert touched is not None
    assert touched.verifier is None


def test_reading_a_missing_invitation_returns_none(factory: sessionmaker) -> None:
    store = SqlInvitationStore(factory)

    assert store.find_for_redemption("inv_nothing", now=NOW) is None
    assert store.get_invitation("inv_nothing", now=NOW) is None


def test_every_read_path_destroys_an_expired_verifier(factory: sessionmaker) -> None:
    """**Found in review on #217, and this test replaces one that asserted the opposite.**

    An earlier version documented `get_invitation` as deliberately non-destroying, so `R4-04`'s
    revocation read and the tests could observe stored bytes unambiguously. That trade was wrong.
    The reviewer traced where it leads and the next test reproduces it; this one asserts the rule:
    *every* read destroys an expired verifier, because a read that does not is a day of unjustified
    survival under `KHEPRI-DEC-015` §5.

    Parametrizing would hide which path failed, so all three are asserted on their own rows.
    """
    store, first, organization_id = _invitation(factory, expires_at=NOW - timedelta(hours=1))
    assert store.get_invitation(first.invitation_id, now=NOW).verifier is None

    store, second, _ = _invitation(factory, expires_at=NOW - timedelta(hours=1))
    assert store.find_for_redemption(second.invitation_id, now=NOW).verifier is None

    store, third, third_org = _invitation(factory, expires_at=NOW - timedelta(hours=1))
    listed = store.invitations_for_organization(third_org, now=NOW)
    assert [held.verifier for held in listed] == [None]
    # Read the ROW, not the record. Asserting through `get_invitation` cannot catch a listing that
    # destroyed in memory without flushing, because that read destroys too and would repair exactly
    # what the missing flush left behind. Found by a surviving mutant.
    assert _stored_verifier_columns(factory, third.invitation_id) == (None,) * 5, (
        "the listing must destroy in the database, not only in what it returns"
    )


def test_an_expired_invitation_cannot_strand_its_verifier_when_revocation_is_refused(
    factory: sessionmaker,
) -> None:
    """**The dead end #217 traced, asserted end to end.**

    `R4-04` reads an invitation to revoke it; `Invitation.revoked` refuses once the horizon has
    passed (a guard added on `#215`); so nothing saves and, under the old non-destroying read,
    nothing ever destroyed. With no scheduled sweeper the bytes survived indefinitely.

    The read is now what closes it: by the time the refusal happens the verifier is already gone.
    """
    store, invitation, _ = _invitation(factory, expires_at=NOW - timedelta(hours=1))

    read = store.get_invitation(invitation.invitation_id, now=NOW)
    assert read is not None
    with pytest.raises(ValueError):
        read.revoked(at=NOW)

    assert store.get_invitation(invitation.invitation_id, now=NOW).verifier is None
    assert not verify_secret("anything", read.verifier)


def test_a_live_invitation_survives_every_read_path(factory: sessionmaker) -> None:
    """The other half. Reads that destroyed unconditionally would satisfy both tests above and
    brick every live invitation the moment anyone listed a team page."""
    store, invitation, organization_id = _invitation(factory)

    assert store.get_invitation(invitation.invitation_id, now=NOW).verifier is not None
    assert store.find_for_redemption(invitation.invitation_id, now=NOW).verifier is not None
    assert store.invitations_for_organization(organization_id, now=NOW)[0].verifier is not None
    assert store.get_invitation(invitation.invitation_id, now=NOW).verifier is not None


# --- state changes ----------------------------------------------------------------------------


@pytest.mark.parametrize("operation", ["redeemed", "revoked"])
def test_a_terminal_transition_persists_and_destroys_the_verifier(
    factory: sessionmaker, operation: str
) -> None:
    """The record's transitions return a verifier-less instance; a store that wrote the timestamp
    and left the bytes would undo the destruction the domain performed."""
    store, invitation, _ = _invitation(factory)

    changed = getattr(invitation, operation)(at=NOW)
    assert store.save_invitation(changed)

    restored = store.get_invitation(invitation.invitation_id, now=NOW)
    assert restored is not None
    assert getattr(restored, f"{operation}_at") == NOW
    assert restored.verifier is None
    assert not verify_secret("anything", restored.verifier)


def test_saving_a_vanished_invitation_returns_false(factory: sessionmaker) -> None:
    organization_id, actor_id = _organization(factory)
    store = SqlInvitationStore(factory)
    never_added = Invitation.create(
        _offer(organization_id, actor_id),
        secret=issue_secret(),
        expires_at=LATER,
        issued_at=ISSUED,
    )

    assert store.save_invitation(never_added) is False


# --- the retention sweep (§3) -----------------------------------------------------------------


def _sweep(factory: sessionmaker, *, now: datetime = NOW) -> int:
    return (
        InvitationRetentionSweeper(SqlInvitationStore(factory))
        .sweep(now=now)
        .purged_invitations
    )


def test_an_expired_unredeemed_invitation_is_purged_in_the_same_pass(
    factory: sessionmaker,
) -> None:
    """No horizon at all for this branch: the purpose ended when the verifier's did. `R4-01` §3
    forbids an interval in which such a row survives with its `target_identity` retained -- so the
    row goes, not merely its verifier."""
    store, invitation, _ = _invitation(factory, expires_at=NOW - timedelta(seconds=1))

    assert _sweep(factory) == 1
    assert store.get_invitation(invitation.invitation_id, now=NOW) is None


def test_a_revoked_invitation_is_purged_in_the_same_pass(factory: sessionmaker) -> None:
    store, invitation, _ = _invitation(factory)
    assert store.save_invitation(invitation.revoked(at=NOW - timedelta(days=1)))

    assert _sweep(factory) == 1
    assert store.get_invitation(invitation.invitation_id, now=NOW) is None


def test_a_live_unredeemed_invitation_survives_the_sweep(factory: sessionmaker) -> None:
    store, invitation, _ = _invitation(factory)

    assert _sweep(factory) == 0
    assert store.get_invitation(invitation.invitation_id, now=NOW) is not None


def test_a_recently_redeemed_invitation_survives_the_sweep(factory: sessionmaker) -> None:
    """Redeemed rows are retained while they must still refuse replay and attribute the membership
    they produced -- so this branch has a horizon where the expired branch has none."""
    store, invitation, _ = _invitation(factory)
    assert store.save_invitation(invitation.redeemed(at=NOW - timedelta(days=1)))

    assert _sweep(factory) == 0
    assert store.get_invitation(invitation.invitation_id, now=NOW) is not None


def test_a_redeemed_invitation_is_purged_once_its_membership_event_would_be(
    factory: sessionmaker,
) -> None:
    """The anchored horizon. Redeemed a day beyond the event retention window, so the
    `MembershipEvent` it produced is purgeable and it no longer has a purpose."""
    store, invitation, _ = _invitation(factory)
    long_ago = NOW - timedelta(days=31 * MEMBERSHIP_EVENT_RETENTION_MONTHS + 1)
    assert store.save_invitation(invitation.redeemed(at=long_ago))

    assert _sweep(factory) == 1
    assert store.get_invitation(invitation.invitation_id, now=NOW) is None


def test_the_redeemed_horizon_is_anchored_to_the_event_horizon_not_a_literal(
    factory: sessionmaker,
) -> None:
    """`R4-01` §3: `R4-03` must not write twelve months into this sweeper as a number.

    Asserted structurally rather than by value: the sweeper's default retention must be the *same
    object* the membership-event horizon names, so shortening one moves the other. A literal `12`
    would satisfy any equality assertion on the day it was written and diverge silently on the day
    the event horizon changed.
    """
    import inspect  # noqa: PLC0415

    default = inspect.signature(InvitationRetentionSweeper.__init__).parameters[
        "retention_months"
    ].default

    assert default == MEMBERSHIP_EVENT_RETENTION_MONTHS
    source = inspect.getsource(InvitationRetentionSweeper.__init__)
    assert "MEMBERSHIP_EVENT_RETENTION_MONTHS" in source, (
        "the default must name the event horizon, not restate its value"
    )
    assert "12" not in source, f"a literal horizon appears in the signature: {source!r}"


def test_the_unenforced_horizon_is_recorded_rather_than_assumed(factory: sessionmaker) -> None:
    """`R4-01` §8.1 asks `R4-03` to record that the horizon has no scheduled caller, so "the
    cadence is operational" cannot imply somebody is choosing one. Asserted so the note cannot be
    deleted quietly: no scheduler exists in this repository, and `RetentionPasses` is reached only
    by the manual `sweep` subcommand."""
    assert INVITATION_HORIZON_IS_UNENFORCED is True


def test_the_sweep_reports_counts_and_no_identifier(factory: sessionmaker) -> None:
    """`FR-040`: a report naming what it purged would reintroduce, in the audit trail, exactly the
    `target_identity` values the purge exists to remove."""
    import dataclasses  # noqa: PLC0415

    from khepri.rca.invitation_retention import InvitationSweepReport  # noqa: PLC0415

    fields = {field.name for field in dataclasses.fields(InvitationSweepReport)}

    assert fields == {"purged_invitations"}


def test_a_verifier_rebuilt_from_stored_columns_keeps_its_work_factor(
    factory: sessionmaker,
) -> None:
    """The KDF parameters are persisted per row so the factor can be raised later without
    invalidating existing invitations. A store that defaulted them on read would verify against the
    wrong cost and silently reject every older secret."""
    store, invitation, _ = _invitation(factory)

    restored = store.get_invitation(invitation.invitation_id, now=NOW)

    assert restored is not None
    assert restored.verifier is not None
    assert restored.verifier.kdf == KdfParams(n=2**14, r=8, p=1)
    assert isinstance(restored.verifier, Verifier)
