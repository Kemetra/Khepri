from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.rca.accounts import Account, AccountService
from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import Membership, OrganizationService
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
ACCOUNT = "acc_creator"
OTHER_ACCOUNT = "acc_stranger"

ADVERSARIAL_NAMES = [
    "Acme Pharmacy",
    "own_predictable",
    "owner@example.test",
    "acme-pharmacy",
    "ACME PHARMACY",
    "",
    "a" * 200,
]


def _fixture() -> tuple[MemoryOrganizationStore, OrganizationService, IsolationService]:
    """A store plus both services, with ACCOUNT and OTHER_ACCOUNT registered and enabled.

    `IsolationService` refuses a disabled account (#149), so the accounts these tests act as
    have to exist and be enabled or every resolution would fail for the wrong reason.
    """
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    for account_id in (ACCOUNT, OTHER_ACCOUNT):
        accounts.accounts[account_id] = Account._from_storage(
            account_id=account_id,
            email=f"{account_id}@example.test",
            verifier=None,
            disabled_at=None,
        )
    return store, OrganizationService(store), IsolationService(store, accounts)


def test_resolve_scope_returns_the_stored_owner_id() -> None:
    store, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    owner_id = isolation.resolve_scope(ACCOUNT, organization.organization_id)
    stored = store.get_scope(organization.organization_id)
    assert stored is not None
    assert owner_id == stored.owner_id


def test_resolve_scope_returns_a_string_not_a_session_scope() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    owner_id = isolation.resolve_scope(ACCOUNT, organization.organization_id)
    assert isinstance(owner_id, str)


def test_scope_is_stable_across_repeated_resolutions() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    resolutions = {
        isolation.resolve_scope(ACCOUNT, organization.organization_id) for _ in range(5)
    }
    assert len(resolutions) == 1


def _fixture_with_credentials() -> (
    tuple[MemoryOrganizationStore, OrganizationService, IsolationService]
):
    """As `_fixture`, but the accounts hold verifiers and therefore count as effective owners.

    `_fixture` builds accounts with `verifier=None`, which is all `IsolationService` needs. FR-013's
    guard asks a stricter question — `can_authenticate`, which a credential-less account fails,
    since an owner who cannot log in cannot exercise ownership. So the two tests below, which
    exercise owner-reducing operations, need accounts that can actually act or the guard refuses
    them for a reason unrelated to what they assert.
    """
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    service = AccountService(accounts)
    for account_id in (ACCOUNT, OTHER_ACCOUNT):
        created = service.create_account(f"{account_id}@example.test", "correct horse battery")
        accounts.accounts[account_id] = Account._from_storage(
            account_id=account_id,
            email=created.email,
            verifier=created.verifier,
            disabled_at=None,
        )
        del accounts.accounts[created.account_id]
    return store, OrganizationService(store), IsolationService(store, accounts)


def test_scope_is_stable_across_a_membership_change() -> None:
    """`FR-035`: one organization resolves to one scope "across membership changes".

    Untestable until `R2` supplied role-change operations — the clause named a change no code could
    make. Now it can, so it is asserted: a demotion alters the *role* the membership carries and
    must leave the isolation key untouched, because `FR-032`/`FR-033` derive the key from nothing
    but the organization. A scope that moved with a role would make authorization data reachable
    under one key and not another for the same organization.
    """
    store, organizations, isolation = _fixture_with_credentials()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)
    before = isolation.resolve_scope(ACCOUNT, organization.organization_id)

    # A second owner, so demoting the first is not the final-owner case FR-013 refuses.
    store.memberships[(organization.organization_id, OTHER_ACCOUNT)] = Membership.create(
        organization.organization_id, OTHER_ACCOUNT, "owner"
    )
    organizations.demote_to_member(
        organization.organization_id, ACCOUNT, actor_account_id=OTHER_ACCOUNT, now=NOW
    )

    after = isolation.resolve_scope(ACCOUNT, organization.organization_id)
    assert after == before, "the isolation key must not move with a role"


def test_a_revoked_membership_stops_resolving_its_scope() -> None:
    """The other half of the same clause: the scope is stable, access is not.

    `FR-023` decides access by membership lookup, so revocation must end resolution immediately —
    without which a revoked member would keep reaching organization data until something expired.
    Both halves are asserted because a naive reading of "stable across membership changes" would
    otherwise suggest revocation should keep working.
    """
    store, organizations, isolation = _fixture_with_credentials()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)
    store.memberships[(organization.organization_id, OTHER_ACCOUNT)] = Membership.create(
        organization.organization_id, OTHER_ACCOUNT, "owner"
    )
    assert isolation.resolve_scope(OTHER_ACCOUNT, organization.organization_id)

    organizations.revoke_membership(
        organization.organization_id, OTHER_ACCOUNT, actor_account_id=ACCOUNT, now=NOW
    )

    with pytest.raises(ScopeAccessDenied):
        isolation.resolve_scope(OTHER_ACCOUNT, organization.organization_id)


def test_distinct_organizations_resolve_to_distinct_scopes() -> None:
    _, organizations, isolation = _fixture()
    first = organizations.create_organization("Acme", ACCOUNT, now=NOW)
    second = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    assert first.organization_id != second.organization_id
    assert isolation.resolve_scope(ACCOUNT, first.organization_id) != isolation.resolve_scope(
        ACCOUNT, second.organization_id
    )


def _leaked_windows(sources: tuple[str, ...], owner_id: str, size: int = 8) -> list[str]:
    """Return every ``size``-character substring of any source that appears in owner_id.

    A whole-string containment check is too weak: ``owner_id`` is only 28 characters, so a
    longer identifier can never appear in it and the assertion would pass vacuously. A
    sliding window catches *partial* derivation, which is the real risk under FR-032.
    Sources shorter than ``size`` yield no windows, which is the correct no-op.
    """
    return [
        source[start : start + size]
        for source in sources
        for start in range(len(source) - size + 1)
        if source[start : start + size] in owner_id
    ]


def test_no_commercial_identifier_appears_in_a_resolved_scope() -> None:
    _, organizations, isolation = _fixture()
    for name in ADVERSARIAL_NAMES:
        organization = organizations.create_organization(name, ACCOUNT, now=NOW)
        owner_id = isolation.resolve_scope(ACCOUNT, organization.organization_id)
        body = owner_id.removeprefix("own_")
        assert organization.organization_id not in owner_id
        assert ACCOUNT not in owner_id
        plausible_substring = bool(name) and len(name) <= len(body)
        assert not plausible_substring or name.lower() not in body.lower()
        assert _leaked_windows((organization.organization_id, ACCOUNT, name), owner_id) == []


def test_scope_is_not_reproducible_from_organization_data() -> None:
    _, organizations, isolation = _fixture()
    first = organizations.create_organization("Identical Name", ACCOUNT, now=NOW)
    second = organizations.create_organization("Identical Name", ACCOUNT, now=NOW)

    assert isolation.resolve_scope(ACCOUNT, first.organization_id) != isolation.resolve_scope(
        ACCOUNT, second.organization_id
    )


def test_scopes_do_not_merge_for_multi_organization_membership() -> None:
    store, organizations, isolation = _fixture()
    first = organizations.create_organization("First", ACCOUNT, now=NOW)
    second = organizations.create_organization("Second", ACCOUNT, now=NOW)
    store.memberships[(second.organization_id, ACCOUNT)] = Membership._from_storage(
        organization_id=second.organization_id,
        account_id=ACCOUNT,
        role="owner",
    )

    assert isolation.resolve_scope(ACCOUNT, first.organization_id) != isolation.resolve_scope(
        ACCOUNT, second.organization_id
    )


def test_non_member_is_refused() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    with pytest.raises(ScopeAccessDenied):
        isolation.resolve_scope(OTHER_ACCOUNT, organization.organization_id)


def test_refusals_are_uniform_and_content_free() -> None:
    store, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    messages = []
    for account_id, organization_id in (
        (OTHER_ACCOUNT, organization.organization_id),
        (ACCOUNT, "org_does_not_exist"),
        (OTHER_ACCOUNT, "org_does_not_exist"),
    ):
        with pytest.raises(ScopeAccessDenied) as caught:
            isolation.resolve_scope(account_id, organization_id)
        messages.append(str(caught.value))

    del store.scopes[organization.organization_id]
    assert store.get_membership(organization.organization_id, ACCOUNT) is not None
    with pytest.raises(ScopeAccessDenied) as caught:
        isolation.resolve_scope(ACCOUNT, organization.organization_id)
    messages.append(str(caught.value))

    assert len(set(messages)) == 1
    assert "org_does_not_exist" not in messages[0]
    assert "Acme" not in messages[0]
