"""`R4-06` -- the `FR-020` and identity-purge cascades.

Scope: the two membership-scoped triggers (§7) and the purge trigger (§7.1). Redemption is `R4-05`
and does not exist yet, so the motivating "a replacement account cannot redeem" assertion is
`R4-07`'s per §7.1; what is checkable here is the **state**, and that is what this file asserts.

**The test that carries this file is the negative one.** §7 puts the cascade in
`revoke_membership`'s `write` callback rather than in `_apply_membership_change`'s body, because
`demote_membership` delegates to the same helper -- so a cascade in the helper would invalidate a
*demoted* member's invitations, which §8.3 settles it must not. `TestDemotionLeavesInvitationsOpen`
is the only test that distinguishes the two placements, and a suite of happy paths omits it. It is
written first for that reason.

**Why the cascade deletes rather than marking `revoked_at`.** §3: "Both purposes therefore lapse
for a non-redeemed invitation the moment it is closed, and neither authorizes holding
`target_identity` past that point." Every row either predicate touches is `redeemed_at IS NULL` by
construction, so all of them are §3's first purge row. Recorded as a correction in `R4-01` §7 on
2026-08-20, because that section previously said to mark and keep -- contradicting §4.1's "§7's
cascades take the same shape" as its `DELETE`.

**The recipient reading, not the issuer reading alone.** §7's counter-example: a person holding two
invitations to `O` redeems one, is revoked for cause, and redeems the second to walk straight back
in -- untouched by an `issued_by` cascade, because that column names the *owner who sent it*.
`TestTheRecipientCascade` is that counter-example as a test.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_service import InvitationService
from khepri.rca.invitations import InvitationOffer, parse_token
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import (
    AccountRow,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    factory_fixture,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)
CREDENTIAL = "correct horse battery staple"

_COUNTER = itertools.count()


def _account(factory: sessionmaker, label: str) -> tuple[str, str]:
    """A registered account. Returns `(account_id, canonical_email)`."""
    email = f"r406-{label}{next(_COUNTER)}@example.com"
    account = AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL)
    return account.account_id, email


def _organization(factory: sessionmaker) -> tuple[str, str]:
    """An organization with a live owner. Returns `(organization_id, owner_account_id)`."""
    owner_id, _ = _account(factory, "owner")
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        f"Acme {next(_COUNTER)}", owner_id, now=NOW
    )
    return organization.organization_id, owner_id


def _grant(factory: sessionmaker, organization_id: str, account_id: str, role: str) -> None:
    """A membership row written directly, following the matrix file's helper.

    `R2`'s promotion path would work for the owner case but not for a plain member, and this file
    needs both without making membership creation part of what it tests.
    """
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization_id,
                account_id=account_id,
                role=role,
            )
        )


def _issue(
    factory: sessionmaker,
    organization_id: str,
    *,
    issued_by: str,
    target: str,
    role: str = MEMBER_ROLE,
    expires_at: datetime = LATER,
) -> str:
    """One open invitation. Returns its identifier."""
    token = InvitationService(SqlInvitationStore(factory)).issue(
        InvitationOffer(
            organization_id=organization_id,
            intended_role=role,
            target_identity=target,
            issued_by=issued_by,
        ),
        expires_at=expires_at,
        now=NOW,
    )
    return parse_token(token)[0]


def _open_at(factory: sessionmaker, invitation_id: str, *, now: datetime = NOW) -> bool:
    """Whether the invitation is still present and open.

    Absence counts as closed, which is the cascade's shape: it deletes rather than marking, so a
    caller cannot distinguish "cascaded" from "never existed" -- which is what §5 requires anyway.
    """
    invitation = SqlInvitationStore(factory).get_invitation(invitation_id, now=now)
    return invitation is not None and invitation.is_open_at(now)


class TestDemotionLeavesInvitationsOpen:
    """§8.3 -- demotion does **not** invalidate, and this is the placement test.

    `revoke_membership` and `demote_membership` both delegate to `_apply_membership_change`. A
    cascade in that shared helper's body runs on both verbs, so demotion would invalidate the
    demoted member's invitations -- reversing a decided question through a helper two verbs happen
    to share. This test fails on that placement and passes on the `write`-callback placement §7
    requires, which is why §7 names it rather than leaving it to review.
    """

    def test_demoting_an_owner_leaves_their_issued_invitations_open(
        self, factory: sessionmaker
    ) -> None:
        organization_id, owner_id = _organization(factory)
        second_owner, second_email = _account(factory, "second")
        _grant(factory, organization_id, second_owner, OWNER_ROLE)
        invitee_id, invitee_email = _account(factory, "invitee")

        issued = _issue(
            factory, organization_id, issued_by=second_owner, target=invitee_email
        )
        addressed = _issue(
            factory, organization_id, issued_by=owner_id, target=second_email
        )

        SqlOrganizationStore(factory).demote_membership(
            organization_id, second_owner, actor_account_id=owner_id, now=NOW
        )

        assert _open_at(factory, issued), (
            "demotion must not invalidate invitations the demoted member issued (§8.3); a cascade "
            "in `_apply_membership_change`'s body rather than `revoke`'s callback closes this"
        )
        assert _open_at(factory, addressed), (
            "nor invitations addressed to them"
        )
        assert invitee_id


class TestTheRecipientCascade:
    """§7's counter-example: revocation reaches invitations **addressed to** the revoked member."""

    def test_a_second_held_invitation_cannot_survive_revocation(
        self, factory: sessionmaker
    ) -> None:
        """The whole reason `FR-020` takes the recipient reading.

        Two invitations to `O` for one person. They redeem one and become a member -- modelled here
        by granting the membership, since redemption is `R4-05` -- and are then revoked. Under the
        narrow `issued_by` reading nothing touches the second invitation, because its issuer is the
        owner who sent it, and the revoked member redeems it and rejoins immediately.
        """
        organization_id, owner_id = _organization(factory)
        member_id, member_email = _account(factory, "member")

        first = _issue(factory, organization_id, issued_by=owner_id, target=member_email)
        second = _issue(factory, organization_id, issued_by=owner_id, target=member_email)
        _grant(factory, organization_id, member_id, MEMBER_ROLE)

        SqlOrganizationStore(factory).revoke_membership(
            organization_id, member_id, actor_account_id=owner_id, now=NOW
        )

        assert not _open_at(factory, first), "the redeemed-then-revoked path is not what this tests"
        assert not _open_at(factory, second), (
            "the second held invitation must be invalidated: an `issued_by`-only cascade leaves it "
            "open and the revoked member rejoins through a token they already hold (§7)"
        )

    def test_the_match_is_canonical(self, factory: sessionmaker) -> None:
        """§7 item 3: the cascade's own operand must be folded, and three layers hide that.

        **Why this writes the row directly instead of registering a mixed-case account.** The
        obvious form of this test -- create an account as `Alice@Example.COM`, issue to it, revoke,
        assert the invitation closed -- cannot fail on the cascade's fold, because the address is
        already canonical by the time the cascade sees it *three* times over: `Account.create`
        folds at the domain door (`accounts.py:130`), `SqlAccountStore` folds again at rest
        (`persistence.py:505`), and `InvitationService.issue` folds the invitation's copy. Verified
        by removing the cascade's `canonical_email` and watching all 11 tests stay green, then by
        removing the store's fold as well and watching them stay green again.

        So the mixed-case value is written **straight into `AccountRow.email`**, which is the one
        state a canonicalizing store cannot produce but a migration, a manual repair, or a future
        provider (`KHEPRI-DEC-018` §5 admits none *today*) could. The cascade must fold what it
        reads rather than trusting its input -- which is what defence in depth means here, and what
        the redundant-guard rule requires each layer to prove separately.
        """
        organization_id, owner_id = _organization(factory)
        member_id, member_email = _account(factory, "mixed")
        _grant(factory, organization_id, member_id, MEMBER_ROLE)
        invitation = _issue(
            factory, organization_id, issued_by=owner_id, target=member_email
        )

        # An un-canonical address at rest: what the cascade must not be defeated by.
        with factory.begin() as database:
            row = database.get(AccountRow, member_id)
            assert row is not None
            row.email = f"  {member_email.upper()} "

        SqlOrganizationStore(factory).revoke_membership(
            organization_id, member_id, actor_account_id=owner_id, now=NOW
        )

        assert not _open_at(factory, invitation), (
            "the cascade must canonicalize the address it reads; comparing a raw stored value "
            "against a canonical `target_identity` silently spares the invitation"
        )

    def test_another_organizations_invitation_is_untouched(
        self, factory: sessionmaker
    ) -> None:
        """Both membership cascades are organization-scoped (§7.1: "§7's two triggers stay scoped").

        A member revoked from `A` keeps an outstanding invitation to `B`: the trigger is that one
        membership ending, not the person's standing everywhere.
        """
        organization_a, owner_a = _organization(factory)
        organization_b, owner_b = _organization(factory)
        member_id, member_email = _account(factory, "shared")
        _grant(factory, organization_a, member_id, MEMBER_ROLE)

        in_a = _issue(factory, organization_a, issued_by=owner_a, target=member_email)
        in_b = _issue(factory, organization_b, issued_by=owner_b, target=member_email)

        SqlOrganizationStore(factory).revoke_membership(
            organization_a, member_id, actor_account_id=owner_a, now=NOW
        )

        assert not _open_at(factory, in_a)
        assert _open_at(factory, in_b), (
            "revocation from A must not reach B's invitation; the membership cascades are scoped"
        )


class TestTheIssuerCascade:
    """`KHEPRI-DEC-015` §2's fourth end trigger: "revocation of the inviting membership"."""

    def test_invitations_issued_by_the_revoked_member_are_invalidated(
        self, factory: sessionmaker
    ) -> None:
        """Governed rather than optional, and it closes a hole the recipient reading does not.

        An owner whose membership is revoked should not have outstanding invitations that still
        work: the authority under which they were issued is gone.
        """
        organization_id, owner_id = _organization(factory)
        issuer_id, _ = _account(factory, "issuer")
        _grant(factory, organization_id, issuer_id, OWNER_ROLE)
        _, invitee_email = _account(factory, "stranger")

        invitation = _issue(
            factory, organization_id, issued_by=issuer_id, target=invitee_email
        )

        SqlOrganizationStore(factory).revoke_membership(
            organization_id, issuer_id, actor_account_id=owner_id, now=NOW
        )

        assert not _open_at(factory, invitation), (
            "the issuer trigger is `KHEPRI-DEC-015` §2's fourth, not an optional extra"
        )

    def test_another_members_invitation_survives(self, factory: sessionmaker) -> None:
        """The cascade is anchored to the revoked member, not to the organization."""
        organization_id, owner_id = _organization(factory)
        issuer_id, _ = _account(factory, "issuer")
        _grant(factory, organization_id, issuer_id, OWNER_ROLE)
        _, first_email = _account(factory, "first")
        _, second_email = _account(factory, "second")

        theirs = _issue(factory, organization_id, issued_by=issuer_id, target=first_email)
        others = _issue(factory, organization_id, issued_by=owner_id, target=second_email)

        SqlOrganizationStore(factory).revoke_membership(
            organization_id, issuer_id, actor_account_id=owner_id, now=NOW
        )

        assert not _open_at(factory, theirs)
        assert _open_at(factory, others), (
            "an invitation issued by a different owner must survive"
        )


class TestTheTombstoneCase:
    """§7.1 -- a membership revoked *after* the addressee's account is purged.

    The recipient predicate cannot be constructed at all: `row.email is None`. The issuer predicate
    still can, because it keys on `account_id`, which the tombstone retains. So the cascade must do
    the issuer half rather than skipping both -- a `return` on an unresolvable address would drop a
    trigger `KHEPRI-DEC-015` §2 governs.
    """

    def test_a_purged_addressee_does_not_abort_the_issuer_half(
        self, factory: sessionmaker
    ) -> None:
        organization_id, owner_id = _organization(factory)
        purged_id, _ = _account(factory, "purged")
        _grant(factory, organization_id, purged_id, OWNER_ROLE)
        _, invitee_email = _account(factory, "invitee")

        issued = _issue(
            factory, organization_id, issued_by=purged_id, target=invitee_email
        )

        accounts = SqlAccountStore(factory)
        stored = accounts.get_account(purged_id)
        assert stored is not None
        accounts.save_account(stored.disabled(now=NOW))
        assert accounts.purge_if_still_eligible(purged_id, NOW + timedelta(days=800))

        SqlOrganizationStore(factory).revoke_membership(
            organization_id, purged_id, actor_account_id=owner_id, now=NOW
        )

        assert not _open_at(factory, issued), (
            "an unresolvable recipient address must not abort the issuer cascade: the tombstone "
            "still carries `account_id`, which is the issuer predicate's key"
        )


class TestThePurgeCascade:
    """§7.1 -- the third trigger, unscoped by organization.

    The identity ending is the trigger, so every outstanding offer to that person lapses at once.
    §7.1 assigns `R4-06` the **state** assertions only; the motivating "a replacement account at the
    released address cannot redeem" is `R4-07`'s, because it needs a verb that does not exist yet.
    """

    def test_purging_an_account_closes_its_invitations_everywhere(
        self, factory: sessionmaker
    ) -> None:
        organization_a, owner_a = _organization(factory)
        organization_b, owner_b = _organization(factory)
        addressee_id, addressee_email = _account(factory, "addressee")

        in_a = _issue(factory, organization_a, issued_by=owner_a, target=addressee_email)
        in_b = _issue(factory, organization_b, issued_by=owner_b, target=addressee_email)

        accounts = SqlAccountStore(factory)
        stored = accounts.get_account(addressee_id)
        assert stored is not None
        accounts.save_account(stored.disabled(now=NOW))

        assert accounts.purge_if_still_eligible(addressee_id, NOW + timedelta(days=800))

        assert not _open_at(factory, in_a), (
            "the purge cascade is unscoped by organization: the trigger is the identity ending"
        )
        assert not _open_at(factory, in_b)

    def test_an_expired_invitation_is_closed_too(self, factory: sessionmaker) -> None:
        """The purge predicate deliberately omits `expires_at > :now`.

        §4.1's clause exists so *revocation* cannot report success on a state its caller may not
        change -- an actor-facing distinction. This cascade has no actor and reports nothing, and an
        already-expired invitation to a purged address is exactly a row whose `target_identity` §3
        says may no longer be held. Leaving it would strand that identity until an unscheduled
        sweeper ran, and `R4-03` records that no scheduler exists. Corrected in `R4-01` §7.1 on
        2026-08-20, where the inheritance claim was too broad.
        """
        organization_id, owner_id = _organization(factory)
        addressee_id, addressee_email = _account(factory, "expired")

        invitation = _issue(
            factory,
            organization_id,
            issued_by=owner_id,
            target=addressee_email,
            expires_at=NOW + timedelta(hours=1),
        )

        accounts = SqlAccountStore(factory)
        stored = accounts.get_account(addressee_id)
        assert stored is not None
        accounts.save_account(stored.disabled(now=NOW))
        assert accounts.purge_if_still_eligible(addressee_id, NOW + timedelta(days=800))

        with factory.begin() as database:
            from khepri.rca.persistence import InvitationRow

            assert database.get(InvitationRow, invitation) is None, (
                "an expired invitation to a purged address must be deleted, not left holding a "
                "target identity whose authorized purposes have both lapsed"
            )

    def test_another_addressees_invitation_survives(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        purged_id, purged_email = _account(factory, "gone")
        _, kept_email = _account(factory, "kept")

        theirs = _issue(factory, organization_id, issued_by=owner_id, target=purged_email)
        others = _issue(factory, organization_id, issued_by=owner_id, target=kept_email)

        accounts = SqlAccountStore(factory)
        stored = accounts.get_account(purged_id)
        assert stored is not None
        accounts.save_account(stored.disabled(now=NOW))
        assert accounts.purge_if_still_eligible(purged_id, NOW + timedelta(days=800))

        assert not _open_at(factory, theirs)
        assert _open_at(factory, others), "only the purged addressee's invitations lapse"

    def test_a_skipped_purge_cascades_nothing(self, factory: sessionmaker) -> None:
        """`purge_if_still_eligible` re-checks inside its transaction and may decline.

        When it does, nothing was purged and nothing may be cascaded -- the invitation's addressee
        still exists. Asserted because a cascade placed *before* the eligibility check would close
        invitations for an account that is still live, which is the "erased a re-enabled account's
        email" defect that method exists to prevent, in a second column.
        """
        organization_id, owner_id = _organization(factory)
        addressee_id, addressee_email = _account(factory, "live")
        invitation = _issue(
            factory, organization_id, issued_by=owner_id, target=addressee_email
        )

        accounts = SqlAccountStore(factory)
        assert not accounts.purge_if_still_eligible(addressee_id, NOW), (
            "an enabled account is not purgeable, so the fixture must decline"
        )

        assert _open_at(factory, invitation), (
            "a declined purge must cascade nothing: the addressee still exists"
        )
