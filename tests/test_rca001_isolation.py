from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import IsolationScope, Membership, Organization, OrganizationService

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


class MemoryOrganizationStore:
    def __init__(self) -> None:
        self.organizations: dict[str, Organization] = {}
        self.memberships: dict[tuple[str, str], Membership] = {}
        self.scopes: dict[str, IsolationScope] = {}

    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
    ) -> bool:
        self.organizations[organization.organization_id] = organization
        self.memberships[(membership.organization_id, membership.account_id)] = membership
        self.scopes[scope.organization_id] = scope
        return True

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None:
        return self.memberships.get((organization_id, account_id))

    def get_scope(self, organization_id: str) -> IsolationScope | None:
        return self.scopes.get(organization_id)


def _fixture() -> tuple[MemoryOrganizationStore, OrganizationService, IsolationService]:
    store = MemoryOrganizationStore()
    return store, OrganizationService(store), IsolationService(store)


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
    assert not hasattr(owner_id, "session_id")


def test_scope_is_stable_across_repeated_resolutions() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    resolutions = {
        isolation.resolve_scope(ACCOUNT, organization.organization_id) for _ in range(5)
    }
    assert len(resolutions) == 1


def test_distinct_organizations_resolve_to_distinct_scopes() -> None:
    _, organizations, isolation = _fixture()
    first = organizations.create_organization("Acme", ACCOUNT, now=NOW)
    second = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    assert first.organization_id != second.organization_id
    assert isolation.resolve_scope(ACCOUNT, first.organization_id) != isolation.resolve_scope(
        ACCOUNT, second.organization_id
    )


def test_no_commercial_identifier_appears_in_a_resolved_scope() -> None:
    _, organizations, isolation = _fixture()
    for name in ADVERSARIAL_NAMES:
        organization = organizations.create_organization(name, ACCOUNT, now=NOW)
        owner_id = isolation.resolve_scope(ACCOUNT, organization.organization_id)
        body = owner_id.removeprefix("own_")
        assert organization.organization_id not in owner_id
        assert ACCOUNT not in owner_id
        if name:
            assert name.lower() not in body.lower()


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
    store.memberships[(second.organization_id, ACCOUNT)] = Membership(
        organization_id=second.organization_id,
        account_id=ACCOUNT,
        role="owner",
        changed_by=ACCOUNT,
        changed_at=NOW,
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
    _, organizations, isolation = _fixture()
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

    assert len(set(messages)) == 1
    assert "org_does_not_exist" not in messages[0]
    assert "Acme" not in messages[0]
