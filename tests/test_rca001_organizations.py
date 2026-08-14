from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest

from khepri.rca.errors import OrganizationCreationFailed
from khepri.rca.organizations import (
    OWNER_ROLE,
    OrganizationService,
    allocate_owner_id,
)
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
ACCOUNT = "acc_creator"


def test_creating_an_organization_makes_the_creator_an_owner() -> None:
    store = MemoryOrganizationStore(MemoryAccountStore())
    service = OrganizationService(store)
    organization = service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    membership = store.get_membership(organization.organization_id, ACCOUNT)
    assert membership is not None
    assert membership.role == OWNER_ROLE


def test_the_membership_row_carries_no_attribution() -> None:
    """FR-014's attribution lives on the event, and nowhere else.

    This used to assert `changed_by`/`changed_at` on the membership itself. That coverage did
    not disappear with the columns -- it moved to
    `test_rca001_membership_events.py::test_creating_an_organization_emits_one_creation_event`,
    which asserts the emitted event names the creator as its actor. What is asserted here is
    the other half: that the state row does not *also* carry it. Two homes for one fact is the
    drift the move was made to end, so a future field named `last_changed_by` fails here.
    """
    store = MemoryOrganizationStore(MemoryAccountStore())
    service = OrganizationService(store)
    organization = service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    membership = store.get_membership(organization.organization_id, ACCOUNT)
    assert membership is not None
    assert {field.name for field in fields(membership)} == {
        "organization_id",
        "account_id",
        "role",
    }


def test_creation_allocates_an_isolation_scope() -> None:
    store = MemoryOrganizationStore(MemoryAccountStore())
    service = OrganizationService(store)
    organization = service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    scope = store.get_scope(organization.organization_id)
    assert scope is not None
    assert scope.owner_id.startswith("own_")


def test_failed_creation_leaves_nothing_behind() -> None:
    store = MemoryOrganizationStore(MemoryAccountStore(), fail_on_create=True)
    service = OrganizationService(store)
    with pytest.raises(OrganizationCreationFailed):
        service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    assert store.organizations == {}
    assert store.memberships == {}
    assert store.scopes == {}


def test_allocated_owner_ids_are_distinct() -> None:
    assert len({allocate_owner_id() for _ in range(200)}) == 200


def test_owner_id_shape_matches_the_rra_beta_shape() -> None:
    owner_id = allocate_owner_id()
    assert owner_id.startswith("own_")
    assert len(owner_id) == len("own_") + 24
