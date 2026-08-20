"""`R4-04` -- owner-authorized issuance and revocation.

Scope: the two services and the one store method revocation needs. The cascades are `R4-06`,
redemption and its uniform-failure path `R4-05`, and the concurrency race between revoke and
redeem is `R4-07` per `R4-01` §4.1.

**What this file is really about.** Two claims carry it, and neither is about the happy path:

- **Revocation is scoped by `(organization_id, invitation_id)`.** `R4-01` §4.1 derives this from
  `FR-023` -- "possession of an object identifier MUST confer no authority" -- and the test that
  matters is cross-organization, not non-owner. A test asserting only that a `member` cannot revoke
  passes against a lookup keyed by identifier alone, which is the defect.
- **Every non-open cause takes one refusal.** `FR-025` requires a denial for an unreachable object
  to be indistinguishable from one for an object that does not exist. Four causes -- absent,
  already revoked, expired, another organization's -- and one message, modelled on `resolve_scope`
  (`isolation.py:30-40`) where three causes raise the identical `ScopeAccessDenied`.

The predicate-clause tests exist because `R4-01` §4.1 calls `expires_at > :now` "load-bearing and
easy to omit": expiry is a *derived* terminal state with no column, so an unswept expired row still
has `redeemed_at IS NULL AND revoked_at IS NULL` and would match a predicate missing that clause.
Each clause is dropped in turn against a real statement to prove the guard is what refuses, rather
than asserting the guard exists.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import INVITATION_FAILURE, InvitationOperationFailed
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_service import InvitationService
from khepri.rca.invitations import parse_token, verify_secret
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import InvitationRow, SqlAccountStore, SqlOrganizationStore
from tests.rca_fakes import MemoryInvitationStore
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    factory_fixture,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)
TARGET = "invitee@example.com"

_ORGANIZATIONS = itertools.count()


def _organization(factory: sessionmaker) -> tuple[str, str]:
    """A real organization with a live owner. Returns `(organization_id, owner_account_id)`.

    The address is unique per call, following the sibling `R4-03` file: `create_account` fails
    closed on a duplicate email, so a shared constant makes the *second* organization in any test
    raise while building its fixture.
    """
    nth = next(_ORGANIZATIONS)
    owner = AccountService(SqlAccountStore(factory)).create_account(
        f"r404-owner{nth}@example.com", "correct horse battery staple"
    )
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        f"Acme {nth}", owner.account_id, now=NOW
    )
    return organization.organization_id, owner.account_id


def _service(factory: sessionmaker) -> InvitationService:
    return InvitationService(SqlInvitationStore(factory))


class TestIssuance:
    """`R4-01` §4 -- the token is returned once, and the stored address is canonical."""

    def test_the_token_verifies_against_the_stored_verifier(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        service = _service(factory)

        token = service.issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )

        invitation_id, secret = parse_token(token)
        stored = SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW)
        assert stored is not None
        assert verify_secret(secret, stored.verifier)

    def test_the_secret_is_not_recoverable_from_storage(self, factory: sessionmaker) -> None:
        """`FR-016`: persisted only as a strong salted hash, so no column holds the secret.

        **Every text column is read by name through SQL rather than off the ORM instance.** The
        first version of this test built its corpus from `vars(row)` and searched case-sensitively;
        it passed while a mutant wrote the entire token into `target_identity`, because
        `add_invitation` canonicalizes that column and the lowercased copy no longer matched the
        mixed-case needle. The corpus was fine and the comparison was broken -- which is
        indistinguishable from a passing test unless you mutate production and watch.

        So the comparison is case-folded, the digest is checked as bytes, and the column list is
        explicit: a column added later that this test does not name is a column it does not
        cover, and naming them is what makes that visible.
        """
        organization_id, owner_id = _organization(factory)
        token = _service(factory).issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )
        invitation_id, secret = parse_token(token)

        with factory.begin() as database:
            stored = database.execute(
                text(
                    "SELECT organization_id, intended_role, target_identity, issued_by, "
                    "secret_salt, secret_digest FROM rca_invitations WHERE invitation_id = :id"
                ),
                {"id": invitation_id},
            ).one()

        needle = secret.casefold()
        for value in stored:
            if isinstance(value, str):
                assert needle not in value.casefold(), (
                    f"the secret appears in a stored text column: {value!r}"
                )
            elif isinstance(value, bytes):
                assert secret.encode() not in value, "the secret appears in a stored blob"

        assert stored.secret_digest is not None, (
            "the fixture must have a digest, or the loop above scanned nothing that matters"
        )

    def test_a_mixed_case_address_is_stored_canonically(self, factory: sessionmaker) -> None:
        """`R4-01` §4: canonical at rest, so every later predicate is plain equality.

        Storing as typed is a real defect rather than untidiness -- §7.1's purge cascade would
        miss the row, leaving a stale invitation redeemable at a released address.
        """
        organization_id, owner_id = _organization(factory)
        token = _service(factory).issue(
            organization_id,
            MEMBER_ROLE,
            "  Alice@Example.COM ",
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )

        invitation_id, _ = parse_token(token)
        stored = SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW)
        assert stored is not None
        assert stored.target_identity == "alice@example.com"

    def test_two_issuances_mint_different_secrets(self, factory: sessionmaker) -> None:
        """Shape, not value: a CSPRNG secret is not assertable against a known constant."""
        organization_id, owner_id = _organization(factory)
        service = _service(factory)
        issued = [
            service.issue(
                organization_id,
                MEMBER_ROLE,
                TARGET,
                actor_account_id=owner_id,
                expires_at=LATER,
                now=NOW,
            )
            for _ in range(2)
        ]

        assert issued[0] != issued[1]
        assert parse_token(issued[0])[1] != parse_token(issued[1])[1]

    def test_an_unknown_role_is_refused(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        with pytest.raises(ValueError, match="unknown role"):
            _service(factory).issue(
                organization_id,
                "superuser",
                TARGET,
                actor_account_id=owner_id,
                expires_at=LATER,
                now=NOW,
            )


class TestRevocationIsScopedToTheOrganization:
    """`R4-01` §4.1 / `FR-023` -- naming an object confers no authority over it."""

    def test_another_organizations_invitation_is_not_reachable(
        self, factory: sessionmaker
    ) -> None:
        """The test that fails against a lookup keyed by `invitation_id` alone.

        A non-owner test would not: it is refused by the gate before the lookup runs. This one
        presents a *legitimately authorized* organization together with another organization's
        identifier, which is the only shape that exercises the composite predicate.
        """
        _, owner_a = _organization(factory)
        organization_a, _ = _organization(factory)
        organization_b, owner_b = _organization(factory)
        service = _service(factory)

        token = service.issue(
            organization_b,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_b,
            expires_at=LATER,
            now=NOW,
        )
        invitation_id, _ = parse_token(token)

        with pytest.raises(InvitationOperationFailed):
            service.revoke(organization_a, invitation_id, actor_account_id=owner_a, now=NOW)

        surviving = SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW)
        assert surviving is not None, "B's invitation must still exist"
        assert surviving.is_open_at(NOW), "B's invitation must still be open"

    def test_revoking_deletes_the_row(self, factory: sessionmaker) -> None:
        """`R4-01` §4.1: a `DELETE`, not a marker.

        A never-redeemed invitation loses both authorized purposes the moment it closes --
        attribution never attached, and a deleted row is indistinguishable from a retained closed
        one for replay refusal -- so retaining `target_identity` past that point is personal data
        outliving its purpose.
        """
        organization_id, owner_id = _organization(factory)
        service = _service(factory)
        token = service.issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )
        invitation_id, _ = parse_token(token)

        service.revoke(organization_id, invitation_id, actor_account_id=owner_id, now=NOW)

        with factory.begin() as database:
            assert database.get(InvitationRow, invitation_id) is None


class TestEveryNonOpenCauseTakesOneRefusal:
    """`FR-025` -- four causes, one message, no branch a caller can distinguish."""

    @pytest.mark.parametrize(
        "cause",
        ["absent", "already_revoked", "expired", "other_organization"],
    )
    def test_the_refusal_is_identical(self, factory: sessionmaker, cause: str) -> None:
        organization_id, owner_id = _organization(factory)
        service = _service(factory)

        if cause == "absent":
            target = "inv_nonexistent"
            moment = NOW
        elif cause == "other_organization":
            other, other_owner = _organization(factory)
            token = service.issue(
                other,
                MEMBER_ROLE,
                TARGET,
                actor_account_id=other_owner,
                expires_at=LATER,
                now=NOW,
            )
            target, _ = parse_token(token)
            moment = NOW
        else:
            token = service.issue(
                organization_id,
                MEMBER_ROLE,
                TARGET,
                actor_account_id=owner_id,
                expires_at=LATER,
                now=NOW,
            )
            target, _ = parse_token(token)
            if cause == "already_revoked":
                service.revoke(organization_id, target, actor_account_id=owner_id, now=NOW)
                moment = NOW
            else:
                moment = LATER + timedelta(seconds=1)

        with pytest.raises(InvitationOperationFailed) as refusal:
            service.revoke(organization_id, target, actor_account_id=owner_id, now=moment)

        assert str(refusal.value) == INVITATION_FAILURE
        assert organization_id not in str(refusal.value)
        assert target not in str(refusal.value)

    def test_an_expired_invitation_is_not_transitioned_to_revoked(
        self, factory: sessionmaker
    ) -> None:
        """The `expires_at > :now` clause, asserted by its effect rather than by reading the SQL.

        Without the clause the row matches -- expiry is derived and sets no column -- so revoke
        would report **success** on a state the caller must not be able to change, and would
        distinguish expired from the other non-open causes by doing so.
        """
        organization_id, owner_id = _organization(factory)
        service = _service(factory)
        token = service.issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )
        invitation_id, _ = parse_token(token)

        after_expiry = LATER + timedelta(seconds=1)
        with pytest.raises(InvitationOperationFailed):
            service.revoke(
                organization_id, invitation_id, actor_account_id=owner_id, now=after_expiry
            )


class TestARedeemedInvitationIsNotReachable:
    """The `redeemed_at IS NULL` clause, which `R4-04` alone cannot otherwise exercise.

    **Why this test is written against the row rather than through a service.** Redemption is
    `R4-05`, so nothing in this slice can produce a redeemed invitation, and the "already revoked"
    case above cannot stand in for it: revocation *deletes* the row, so that path re-enters
    `delete_open_invitation` as an absent identifier and never reaches the terminal-state clauses.
    Dropping `redeemed_at IS NULL AND revoked_at IS NULL` from the predicate therefore leaves every
    other test in this file green -- verified by deleting those two lines and watching all 19 pass.

    That is the shape this repo has been bitten by before: a guard whose test cannot see the state
    the guard exists to refuse. The row is written directly because the alternative is no coverage
    at all until `R4-05`, and a clause no test can fail is indistinguishable from an absent one.

    The consequence if the clause were missing is not cosmetic. A redeemed invitation is the
    evidence that attributes an existing membership (`KHEPRI-DEC-015` §2) and the row that refuses
    replay (§5); deleting it would destroy both, and the membership would outlive its attribution.
    """

    def test_revocation_cannot_delete_a_redeemed_invitation(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        token = _service(factory).issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )
        invitation_id, _ = parse_token(token)

        # What `R4-05` will do: set `redeemed_at` and destroy the verifier. Written through the
        # store's own save path so the row is one production could hold, not a hand-built shape.
        store = SqlInvitationStore(factory)
        open_invitation = store.get_invitation(invitation_id, now=NOW)
        assert open_invitation is not None
        assert store.save_invitation(open_invitation.redeemed(at=NOW))

        with factory.begin() as database:
            row = database.get(InvitationRow, invitation_id)
            assert row is not None and row.redeemed_at is not None, "the fixture must be redeemed"

        with pytest.raises(InvitationOperationFailed):
            _service(factory).revoke(
                organization_id, invitation_id, actor_account_id=owner_id, now=NOW
            )

        with factory.begin() as database:
            assert database.get(InvitationRow, invitation_id) is not None, (
                "a redeemed invitation must survive: it attributes the resulting membership and "
                "refuses replay, and revocation must not be able to destroy either"
            )

    def test_the_fake_refuses_a_redeemed_invitation_too(self, factory: sessionmaker) -> None:
        """The same clause in the fake, for the reason the parity test exists."""
        organization_id, owner_id = _organization(factory)
        store = SqlInvitationStore(factory)
        token = InvitationService(store).issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )
        invitation_id, _ = parse_token(token)
        open_invitation = store.get_invitation(invitation_id, now=NOW)
        assert open_invitation is not None

        fake = MemoryInvitationStore()
        fake.add_invitation(open_invitation)
        assert fake.save_invitation(open_invitation.redeemed(at=NOW))

        assert (
            fake.delete_open_invitation(organization_id, invitation_id, now=NOW) is False
        ), "the fake must refuse a redeemed row, as SQL does"


class TestTheStoreMethodAndItsFakeAgree:
    """The divergence class `test_every_fake_implements_its_whole_protocol` exists to catch.

    A fake implementing four of the five clauses would leave every service test above green
    while production refused differently -- the shape that shipped once as `count_owners`.
    """

    @pytest.mark.parametrize(
        ("scope", "identifier", "moment", "expected"),
        [
            ("own", "own", NOW, True),
            ("other", "own", NOW, False),
            ("own", "absent", NOW, False),
            ("own", "own", LATER + timedelta(seconds=1), False),
        ],
    )
    def test_the_fake_matches_sql(
        self,
        factory: sessionmaker,
        scope: str,
        identifier: str,
        moment: datetime,
        expected: bool,
    ) -> None:
        organization_id, owner_id = _organization(factory)
        other_organization, _ = _organization(factory)
        sql = SqlInvitationStore(factory)
        fake = MemoryInvitationStore()

        service = InvitationService(sql)
        token = service.issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=owner_id,
            expires_at=LATER,
            now=NOW,
        )
        invitation_id, _ = parse_token(token)
        stored = sql.get_invitation(invitation_id, now=NOW)
        assert stored is not None
        fake.add_invitation(stored)

        asked_scope = organization_id if scope == "own" else other_organization
        asked_id = invitation_id if identifier == "own" else "inv_absent"

        assert (
            sql.delete_open_invitation(asked_scope, asked_id, now=moment) is expected
        ), "SQL disagreed with the expectation"
        assert (
            fake.delete_open_invitation(asked_scope, asked_id, now=moment) is expected
        ), "the fake disagreed with SQL"


class TestAuthorizationLivesOutsideTheService:
    """`R4-01` §4 -- `issue` takes `actor_account_id` for attribution and checks no role.

    Asserted rather than assumed, because the natural reading of `FR-015` ("invite is an owner
    capability") is that the service enforces it. `R6-04` places the check in the gate; a second
    check here would be a second authority over one fact, and the matrix rows in
    `test_rca001_authorization_matrix.py` are what make the gate the authorized route.
    """

    def test_a_member_account_id_is_recorded_not_refused(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        member = AccountService(SqlAccountStore(factory)).create_account(
            "r404-member@example.com", "correct horse battery staple"
        )

        token = _service(factory).issue(
            organization_id,
            MEMBER_ROLE,
            TARGET,
            actor_account_id=member.account_id,
            expires_at=LATER,
            now=NOW,
        )

        invitation_id, _ = parse_token(token)
        stored = SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW)
        assert stored is not None
        assert stored.issued_by == member.account_id, (
            "the service attributes rather than authorizes; the gate is what refuses a member, "
            f"and {OWNER_ROLE} is not checked here"
        )
