"""FR-013: an organization must never reach zero owner-role members (`RCA-001` #149)."""

from __future__ import annotations

import pytest

from khepri.rca.accounts import AccountService
from khepri.rca.errors import (
    FinalOwnerProtected,
)
from khepri.rca.organizations import OWNER_ROLE, Membership, OrganizationService
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
    memory_stack,
)

# --- FR-013: the final owner ------------------------------------------------------------


def test_disabling_the_final_owner_fails_closed() -> None:
    accounts, organizations, lifecycle = memory_stack()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )

    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(owner.account_id, now=NOW)

    # Fails *closed*: the account is still enabled and the organization still has its owner.
    # A guard that raised after writing would pass the assertion above and fail these.
    stored = accounts.get_account(owner.account_id)
    assert stored is not None and stored.is_enabled
    assert organizations.count_owners(organization.organization_id, excluding_account_id="") == 1


def test_the_final_owner_refusal_names_its_cause() -> None:
    """FR-013 requires the refusal to "state that the final owner cannot be removed".

    A deliberate exception to FR-004's content-free discipline: the caller is already an
    authenticated member, so there is nothing to leak, and a uniform refusal would leave an
    owner unable to distinguish this from a generic failure. Writing this guard with the
    surrounding style's uniform message would satisfy every other test and violate FR-013.
    """
    accounts, organizations, lifecycle = memory_stack()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(organizations).create_organization("Acme", owner.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected) as caught:
        lifecycle.disable_account(owner.account_id, now=NOW)

    assert "final owner" in str(caught.value).lower()


def test_a_non_final_owner_can_be_disabled() -> None:
    """The guard must not refuse every owner — only the last one."""
    accounts, organizations, lifecycle = memory_stack()
    first = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", first.account_id, now=NOW
    )
    organizations.memberships[(organization.organization_id, second.account_id)] = (
        Membership.create(
            organization.organization_id,
            second.account_id,
            OWNER_ROLE,
            changed_by=first.account_id,
            now=NOW,
        )
    )

    disabled = lifecycle.disable_account(first.account_id, now=NOW)
    assert not disabled.is_enabled


def test_a_non_owner_member_can_be_disabled() -> None:
    accounts, organizations, lifecycle = memory_stack()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    organizations.memberships[(organization.organization_id, member.account_id)] = (
        Membership.create(
            organization.organization_id,
            member.account_id,
            "member",
            changed_by=owner.account_id,
            now=NOW,
        )
    )

    assert not lifecycle.disable_account(member.account_id, now=NOW).is_enabled


def test_the_guard_checks_every_organization_not_only_the_first() -> None:
    """An account owning two organizations must be refused if it is the last owner of either.

    A guard that returned after inspecting one membership would let this through, and which
    membership comes first is an ordering accident.
    """
    accounts, organizations, lifecycle = memory_stack()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second_owner = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    shared = OrganizationService(organizations).create_organization(
        "Shared", owner.account_id, now=NOW
    )
    organizations.memberships[(shared.organization_id, second_owner.account_id)] = (
        Membership.create(
            shared.organization_id,
            second_owner.account_id,
            OWNER_ROLE,
            changed_by=owner.account_id,
            now=NOW,
        )
    )
    # The second organization has this account as its only owner.
    OrganizationService(organizations).create_organization("Solo", owner.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(owner.account_id, now=NOW)


def test_the_guard_does_not_abandon_the_scan_at_a_non_owner_membership() -> None:
    """A plain membership encountered first must not stop the scan.

    The distinction from the test above is the *skip* branch, not the loop length. There every
    membership is owner-role, so a guard that returned on the non-owner branch would never
    execute that line and the test would pass while the bug was live — confirmed by mutation
    (`continue` to `return` stayed green). Here the account is a plain member of one
    organization and the sole owner of another, which is the realistic shape of this bug.
    """
    accounts, organizations, lifecycle = memory_stack()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    other = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    # A plain membership in someone else's organization...
    theirs = OrganizationService(organizations).create_organization(
        "Theirs", other.account_id, now=NOW
    )
    organizations.memberships[(theirs.organization_id, owner.account_id)] = Membership.create(
        theirs.organization_id,
        owner.account_id,
        "member",
        changed_by=other.account_id,
        now=NOW,
    )
    # ...and sole ownership of their own.
    OrganizationService(organizations).create_organization("Solo", owner.account_id, now=NOW)

    scanned = [m.role for m in organizations.memberships_for_account(owner.account_id)]
    assert "member" in scanned and OWNER_ROLE in scanned, "both membership kinds must be present"

    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(owner.account_id, now=NOW)


