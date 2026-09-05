"""`W1-07a` -- the owner-only deletion route (`RCA-005` `FR-123`).

Every test here drives the **real route**. A test that calls the owner gate directly survives
deletion of its call site, which is the failure this repo has recorded more than once; and a test
asserting only the status code passes while the version is gone, so each refusal asserts the
*effect* as well.
"""

from __future__ import annotations

from khepri.rca.workspace.audit import ACTION_VERSION_DELETED
from tests.w104_support import member
from tests.w107_support import (
    audit_events_for,
    delete_address,
    journey,
    sealed_version,
    shell_with_deletion,
)


def test_an_owner_deletes_the_version_through_the_route() -> None:
    """The capability, end to end: the version is tombstoned and its runs cascade."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who, with_run=True)

    response = shell_with_deletion(j, who).post(delete_address(who, version.version_id))

    assert response.status_code in (200, 303)
    assert j.w.store.get_dataset_version(version.version_id, who.owner_id) is None


def test_someone_who_does_not_own_the_organization_cannot_delete_from_it() -> None:
    """`FR-123` is owner-only, and the gate resolves the actor's live role in *the organization the
    address names* -- not in one they happen to own elsewhere.

    Asserting the **effect**, not the status code: a status-only test passes while the row is gone,
    which is the defect that matters. Driven through the real route, because a test that calls
    `require_owner` directly survives deletion of its call site.
    """
    j = journey()
    owner = member(j.w)
    outsider = member(j.w, email="outsider@example.test", name="Outsider")
    version, _ = sealed_version(j, owner)

    response = shell_with_deletion(j, outsider).post(delete_address(owner, version.version_id))

    assert response.status_code != 303
    assert j.w.store.get_dataset_version(version.version_id, owner.owner_id) is not None
    assert j.w.store.tombstones_for_scope(owner.owner_id) == ()


def test_a_refused_deletion_records_no_completed_event() -> None:
    """A refusal is not an ending, and the audit trail must not read as though it were."""
    j = journey()
    owner = member(j.w)
    outsider = member(j.w, email="outsider@example.test", name="Outsider")
    version, _ = sealed_version(j, owner)

    shell_with_deletion(j, outsider).post(delete_address(owner, version.version_id))

    deletions = [
        event
        for event in audit_events_for(j, owner.owner_id)
        if event.action == ACTION_VERSION_DELETED
    ]
    assert deletions == []


def test_the_route_is_unknown_where_deletion_is_not_wired() -> None:
    """`FR-046`/`FR-049`: a surface this deployment does not offer is an unknown address, not a
    different refusal -- the same reasoning `with_provenance=False` follows on Analyses."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)

    response = shell_with_deletion(j, who, wired=False).post(
        delete_address(who, version.version_id)
    )

    assert response.status_code != 303
    assert j.w.store.get_dataset_version(version.version_id, who.owner_id) is not None


def test_deleting_an_unknown_version_is_the_uniform_refusal() -> None:
    """A version this scope does not hold and one that never existed are the same answer, so the
    route cannot be used to learn that another organization's identifier exists."""
    j = journey()
    who = member(j.w)

    response = shell_with_deletion(j, who).post(f"{delete_address(who, 'dsv-nobody')}")

    assert response.status_code in (200, 303, 404)
    assert j.w.store.tombstones_for_scope(who.owner_id) == ()


def test_the_address_organization_is_compared_with_the_sessions() -> None:
    """`FR-042` scenario 3: an address naming another organization fails closed, and the route
    compares rather than trusting.

    **The comparison is asserted here rather than through the outsider case above**, because that
    one cannot see it: an outsider resolves to their *own* scope, which holds no such version, so
    the deletion is a no-op whether or not the route compares. This drives a session whose resolved
    organization disagrees with the address while the *scope* is the owner's, which is exactly the
    shape review on `#373` found on a read surface -- one organization's records under another's
    address.
    """
    j = journey()
    owner = member(j.w)
    version, _ = sealed_version(j, owner)
    client = shell_with_deletion(j, owner)

    response = client.post(delete_address(owner, version.version_id, organization="org-elsewhere"))

    assert response.status_code != 303
    assert j.w.store.get_dataset_version(version.version_id, owner.owner_id) is not None
    assert j.w.store.tombstones_for_scope(owner.owner_id) == ()


def test_a_member_of_the_organization_who_is_not_its_owner_cannot_delete() -> None:
    """`FR-123` is owner-only, and this is the case that isolates the gate.

    The outsider test above cannot: an outsider resolves to their own scope, which holds no such
    version, so the route is a no-op with or without the gate. Here the session resolves to *this*
    organization -- the address agrees, the scope is right, the version exists -- and only
    `require_owner` stands between the request and the customer's data.
    """
    j = journey()
    owner = member(j.w)
    version, _ = sealed_version(j, owner)

    response = shell_with_deletion(j, owner, owner=False).post(
        delete_address(owner, version.version_id)
    )

    assert response.status_code != 303
    assert j.w.store.get_dataset_version(version.version_id, owner.owner_id) is not None
    assert j.w.store.tombstones_for_scope(owner.owner_id) == ()
