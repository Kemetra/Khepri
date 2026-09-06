"""`R4-03` -- the invitation retention sweep (§3).

Split from `test_rca001_invitation_persistence.py`, which held five responsibilities across 43
functions and so failed CodeScene's Low Cohesion rule as a *critical* violation (8.82 against
the 10.00 `AGENTS.md:18` requires). The seam is the one the original file already drew with its
own section header: everything here is about *when a row stops existing*, which is a lifecycle
rule, while the sibling file is about the store's round trip, its `CHECK` constraints, and
destroy-on-first-touch.

The substantive claim kept whole from the original: the sweep implements **two** lifecycle rules
rather than one horizon, and the redeemed horizon is anchored to the membership-event horizon
rather than a literal.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.credentials import KdfParams, Verifier
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_retention import (
    InvitationRetentionSweeper,
)
from khepri.rca.invitations import Invitation, InvitationOffer, issue_secret
from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS
from khepri.rca.organizations import MEMBER_ROLE, OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
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


# --- the retention sweep (§3) -----------------------------------------------------------------


def _sweep(factory: sessionmaker, *, now: datetime = NOW) -> int:
    return InvitationRetentionSweeper(SqlInvitationStore(factory)).sweep(now=now).purged_invitations


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

    default = (
        inspect.signature(InvitationRetentionSweeper.__init__)
        .parameters["retention_months"]
        .default
    )

    assert default == MEMBERSHIP_EVENT_RETENTION_MONTHS
    source = inspect.getsource(InvitationRetentionSweeper.__init__)
    assert "MEMBERSHIP_EVENT_RETENTION_MONTHS" in source, (
        "the default must name the event horizon, not restate its value"
    )
    assert "12" not in source, f"a literal horizon appears in the signature: {source!r}"


def test_the_horizon_has_a_caller_in_the_shipped_image() -> None:
    """`R4-01` §8.1 asks `R4-03` to record that "the cadence is operational" cannot imply somebody
    is choosing one. That obligation outlives the flag it used to be asserted through.

    Until `W1-07b` this asserted `INVITATION_HORIZON_IS_UNENFORCED is True`, which was accurate:
    `RetentionPasses` was reached only by `khepri.local.cli` and the wheel excludes it.
    `KHEPRI-DEC-033` §5 makes deleting that flag part of the evidence the gap closed, so what is
    asserted now is the fact that replaced it -- the deployed composition reaches this pass.

    Still not a claim that anything is *scheduled*. `tests/test_w107b_unenforced_flag.py` carries
    the scan that fails if any horizon is documented as unenforced again.
    """
    import inspect  # noqa: PLC0415

    from khepri.runtime.wiring import build_retention_sweep  # noqa: PLC0415

    assert "InvitationRetentionSweeper" in inspect.getsource(build_retention_sweep)


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
