"""FR-013: an organization must never reach zero owner-role members (`RCA-001` #149)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import FinalOwnerProtected
from khepri.rca.lifecycle import AccountRetentionSweeper
from khepri.rca.organizations import OWNER_ROLE, OrganizationService
from khepri.rca.persistence import MembershipRow
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
    grant_membership,
    memory_stack,
    two_owner_organization,
)


def _owners(stack) -> int:
    return stack.organizations.count_owners(
        stack.organization.organization_id, excluding_account_id=""
    )


# --- the guard refuses the last owner ----------------------------------------------------


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


# --- ...but only the last one ------------------------------------------------------------


def test_a_non_final_owner_can_be_disabled() -> None:
    """The guard must not refuse every owner, only the last."""
    stack = two_owner_organization()

    assert not stack.lifecycle.disable_account(stack.first.account_id, now=NOW).is_enabled


def test_a_non_owner_member_can_be_disabled() -> None:
    accounts, organizations, lifecycle = memory_stack()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    organizations.memberships[(organization.organization_id, member.account_id)] = (
        organizations.memberships[(organization.organization_id, owner.account_id)]
    )

    assert not lifecycle.disable_account(member.account_id, now=NOW).is_enabled


# --- the scan covers every organization --------------------------------------------------


def test_the_guard_checks_every_organization_not_only_the_first() -> None:
    """Sole ownership of a *second* organization must still refuse."""
    stack = two_owner_organization()
    OrganizationService(stack.organizations).create_organization(
        "Solo", stack.first.account_id, now=NOW
    )

    with pytest.raises(FinalOwnerProtected):
        stack.lifecycle.disable_account(stack.first.account_id, now=NOW)


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
    theirs = OrganizationService(organizations).create_organization(
        "Theirs", other.account_id, now=NOW
    )
    grant_membership_inline(organizations, theirs.organization_id, owner.account_id, "member")
    OrganizationService(organizations).create_organization("Solo", owner.account_id, now=NOW)

    scanned = [m.role for m in organizations.memberships_for_account(owner.account_id)]
    assert "member" in scanned and OWNER_ROLE in scanned, "both membership kinds must be present"

    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(owner.account_id, now=NOW)


def grant_membership_inline(organizations, organization_id, account_id, role) -> None:
    """One-off membership grant for the single test that needs a bespoke shape."""
    from khepri.rca.organizations import Membership

    organizations.memberships[(organization_id, account_id)] = Membership.create(
        organization_id, account_id, role, changed_by=account_id, now=NOW
    )


# --- effective ownership, not owner-role rows --------------------------------------------


def test_disabling_owners_one_after_another_cannot_strand_an_organization(
    factory: sessionmaker,
) -> None:
    """FR-013 counts owners who can act, not owner-role rows.

    The defect this pins, confirmed against the real store before the fix: disablement never
    touches `rca_memberships`, so a disabled account kept its owner-role row and was counted as
    a live owner by the guard meant to prevent stranding. Disabling a two-owner organization's
    owners one after the other passed the guard *both times* and left the organization with zero
    owners able to authenticate, resolve a scope, or act at all.

    No concurrency and no forgery — two ordinary API calls.
    """
    stack = two_owner_organization(factory)

    stack.lifecycle.disable_account(stack.first.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected):
        stack.lifecycle.disable_account(stack.second.account_id, now=NOW)

    survivor = stack.accounts.get_account(stack.second.account_id)
    assert survivor is not None and survivor.is_enabled
    assert _owners(stack) == 1, "exactly one owner remains, and they can act"


def test_the_memory_fake_counts_owners_the_same_way_the_store_does() -> None:
    """Guards the fake against drifting from `SqlOrganizationStore`.

    Every FR-013 test using the fake is only meaningful if its `count_owners` agrees with
    production on the case FR-013 turns on: a disabled account keeps its owner-role row and must
    stop counting. A fake that counted rows would make those tests pass while the real store had
    the defect — which is how the row-counting bug reached review in the first place.
    """
    stack = two_owner_organization()
    assert _owners(stack) == 2

    stack.lifecycle.disable_account(stack.first.account_id, now=NOW)
    assert _owners(stack) == 1, "the disabled owner keeps its row but stops counting"

    # ...and re-enabling does not restore effective ownership, because the verifier stays
    # destroyed. This is the `can_authenticate` half of the rule, exercised through the fake
    # so the property has a test of its own rather than relying on the SQL join.
    revived = stack.lifecycle.enable_account(stack.first.account_id)
    assert revived.is_enabled and not revived.has_verifier
    assert _owners(stack) == 1, "an enabled owner with no credential still cannot act"

    with pytest.raises(FinalOwnerProtected):
        stack.lifecycle.disable_account(stack.second.account_id, now=NOW)


def test_a_purged_owner_does_not_count_as_an_owner(factory: sessionmaker) -> None:
    """A tombstone keeps its membership row, because the foreign key is RESTRICT.

    So the guard has to discount it by the holder's state, or a purged account would count as an
    owner forever — the sharpest form of the row-counting defect.
    """
    stack = two_owner_organization(factory)
    stack.lifecycle.disable_account(stack.first.account_id, now=NOW)
    AccountRetentionSweeper(stack.accounts).sweep(now=NOW + timedelta(days=760))

    with factory() as database:
        surviving = database.get(
            MembershipRow, (stack.organization.organization_id, stack.first.account_id)
        )
    assert surviving is not None, "the row survives the purge"

    assert _owners(stack) == 1, "but it is not an owner any more"
    with pytest.raises(FinalOwnerProtected):
        stack.lifecycle.disable_account(stack.second.account_id, now=NOW)


def test_a_re_enabled_owner_without_a_credential_does_not_count(
    factory: sessionmaker,
) -> None:
    """FR-013 asks whether an owner can *act*, and an owner with no credential cannot.

    Two correct decisions combined into a defect. `enable_account` deliberately leaves the
    verifier destroyed — KHEPRI-DEC-015 §5 gives it no path back — and `can_act` meant only
    "enabled and not purged". So disabling owner A, re-enabling A, then disabling owner B
    passed the guard, leaving an organization whose sole owner could not authenticate.
    Reproduced against the real store before `can_authenticate` existed.
    """
    stack = two_owner_organization(factory)
    stack.lifecycle.disable_account(stack.first.account_id, now=NOW)
    revived = stack.lifecycle.enable_account(stack.first.account_id)

    assert revived.is_enabled and not revived.has_verifier, "the setup this test turns on"
    assert _owners(stack) == 1, "a credential-less owner is not an effective owner"

    with pytest.raises(FinalOwnerProtected):
        stack.lifecycle.disable_account(stack.second.account_id, now=NOW)
