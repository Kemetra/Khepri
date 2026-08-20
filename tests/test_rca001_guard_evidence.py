"""Adversarial evidence for the membership guards (`R2-09`, `#150`).

Three themes the roadmap names, in very different states — which is itself the finding:

**Event omission is already proven** by `test_rca001_event_coverage.py`: every write path emits
exactly one event, no write path exists without one, the table is append-only across every
operation, and an AST audit refuses any production deleter outside the retention sweep. Nothing here
restates that.

**Role forgery is open, and not in the way the phrase suggests.** Forgery does not fail. The
domain accepts `Membership.create(role="superadmin")` and `rca_membership_events` stores a forged
`next_role` without complaint — it carries no CHECK constraint. What actually prevents forgery
today is that *no service takes a role as input*: `promote_to_owner` and `demote_to_member` each
name their destination, and the founding role is fixed. A caller has nothing to forge with because
the parameter does not exist. That is a genuinely strong design, and it is also entirely ambient —
undocumented, and lost the moment a future slice adds `invite(role=...)`. These tests convert it
into an asserted property, and record the two places where validation is absent rather than
implying it is present.

**Stale fakes are open and the highest-leverage item.** `MemoryOrganizationStore` mirrors ten
protocol methods. Every one is a place it can silently diverge from SQL, and one such defect
already shipped: `count_owners` counted membership rows where the real store counted *effective*
owners, so a disabled account read as a live owner in unit tests only. The parity check here fails
closed when a later slice widens the protocol and forgets the fake.
"""

from __future__ import annotations

import ast
import inspect
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.invitations import (
    Invitation,
    InvitationOffer,
    issue_secret,
)
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    ROLES,
    Membership,
    MembershipEvent,
    OrganizationService,
)
from khepri.rca.persistence import (
    MembershipEventRow,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.stores import AccountStore, InvitationStore, OrganizationStore
from tests.rca_fakes import MemoryAccountStore, MemoryInvitationStore, MemoryOrganizationStore
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
)

_FORGED_ROLE = "superadmin"


def _real_organization(factory: sessionmaker) -> tuple[str, str]:
    """A committed organization and a second committed account, both satisfying the foreign keys.

    `rca_memberships` has `RESTRICT` foreign keys onto both parents, so the raw-row writes below
    need real ones — a literal `"org_x"` fails on the key before reaching the CHECK the test is
    about, which would make a forgery test pass for the wrong reason.
    """
    accounts = SqlAccountStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    subject = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    return organization.organization_id, subject.account_id


# --- role forgery: what actually stops it ---------------------------------------------------


def test_no_role_change_operation_accepts_a_role_from_its_caller() -> None:
    """The load-bearing guard against forgery, asserted because it is otherwise invisible.

    `promote_to_owner` and `demote_to_member` each name their destination role in the method name,
    so neither has a parameter a caller could pass `"superadmin"` to. `create_organization` fixes
    the founding role at `owner` (`FR-013` requires an organization to start with an owner, so a
    caller-chosen founding role could not be honoured anyway).

    This is why the missing validation documented below has never been exploitable: there is no
    input to validate. A future slice adding a role parameter — `R4`'s invitation is the obvious
    candidate — makes this test fail, which is the moment validation has to be added rather than
    assumed.
    """
    operations = {
        name: inspect.signature(method)
        for name, method in inspect.getmembers(OrganizationService, inspect.isfunction)
        if not name.startswith("_")
    }
    assert operations, "the service exposes operations"

    offenders = {
        name: str(signature)
        for name, signature in operations.items()
        if "role" in signature.parameters
    }
    assert not offenders, (
        f"an operation takes a role from its caller: {offenders}. Either the role must be "
        "validated against ROLES before it reaches a record, or the operation should name its "
        "destination role as the existing ones do."
    )


@pytest.mark.parametrize("role", [*ROLES])
def test_every_declared_role_survives_a_round_trip(factory: sessionmaker, role: str) -> None:
    """Both roles are storable, so the CHECK below refuses forgery rather than refusing everything.

    A constraint that rejected `member` would also make every forgery test pass, for the wrong
    reason.
    """
    organization, subject = _real_organization(factory)

    with factory.begin() as database:
        database.add(MembershipRow(organization_id=organization, account_id=subject, role=role))

    with factory() as database:
        stored = database.scalars(
            select(MembershipRow.role).where(MembershipRow.account_id == subject)
        ).all()
    assert stored == [role]


def test_the_membership_table_refuses_a_forged_role(factory: sessionmaker) -> None:
    """`ck_rca_membership_role` (`20260814_0015`) is the backstop on live state.

    Live membership state is what authorization will read, so a role outside `ROLES` reaching this
    table is the case that matters most — and the database refuses it independently of any
    application check.

    The parents are real rows, so a foreign-key failure cannot masquerade as the CHECK refusing
    the role.
    """
    organization, subject = _real_organization(factory)

    with (
        pytest.raises(Exception) as refusal,  # noqa: B017, PT011 -- IntegrityError is dialect-shaped
        factory.begin() as database,
    ):
        database.add(
            MembershipRow(organization_id=organization, account_id=subject, role=_FORGED_ROLE)
        )

    assert "ck_rca_membership_role" in str(refusal.value) or "CHECK" in str(refusal.value).upper()


def test_the_event_table_does_not_constrain_its_roles(factory: sessionmaker) -> None:
    """**A recorded gap, not an endorsement.** `rca_membership_events` has no role CHECK.

    Verified rather than assumed: a forged `next_role` is stored without complaint. `FR-014`
    attribution claiming a role that cannot exist in live state is two sources disagreeing about one
    fact, which is the drift `Constitution I` forbids.

    It is not currently reachable — no service accepts a role, per the test above — so this is
    latent rather than live, and closing it is a schema change that belongs in its own slice with
    its own migration, not in a test-only one. Asserted here so the gap is visible in the suite
    rather than discovered by whoever first writes an event from caller input. When a CHECK is
    added, this test should fail and be replaced by its inverse.
    """
    with factory.begin() as database:
        database.add(
            MembershipEventRow(
                event_id="mev_forged",
                organization_id="org_x",
                account_id="acc_subject",
                actor_account_id="acc_actor",
                prior_role=OWNER_ROLE,
                next_role=_FORGED_ROLE,
                occurred_at=NOW,
            )
        )

    with factory() as database:
        stored = database.scalars(
            select(MembershipEventRow.next_role).where(MembershipEventRow.event_id == "mev_forged")
        ).all()
    assert stored == [_FORGED_ROLE], (
        "if this fails, a role CHECK was added to rca_membership_events -- replace this test "
        "with one asserting the refusal"
    )


def test_the_domain_records_do_not_validate_roles_either(factory: sessionmaker) -> None:
    """The other half of the same recorded gap: `Membership.create` accepts any string.

    Both halves are asserted together because a reader finding only the schema gap would reasonably
    assume the domain compensates. It does not. The protection is the absent parameter, nothing
    else.
    """
    forged = Membership.create("org_x", "acc_forged", _FORGED_ROLE)
    assert forged.role == _FORGED_ROLE, "no domain validation today"

    event = MembershipEvent.role_changed(
        "org_x",
        "acc_forged",
        prior_role=OWNER_ROLE,
        next_role=_FORGED_ROLE,
        actor_account_id="acc_actor",
        now=NOW,
    )
    assert event.next_role == _FORGED_ROLE, "no domain validation today"


def test_the_transition_methods_can_only_produce_declared_roles() -> None:
    """`promoted()` and `demoted()` are total over `ROLES` and closed within it.

    So the *operational* path cannot reach a role outside `ROLES` even though the constructor can:
    every transition is a method with a fixed destination, not an assignment.
    """
    assert Membership.create("org", "acc", MEMBER_ROLE).promoted().role == OWNER_ROLE
    assert Membership.create("org", "acc", OWNER_ROLE).demoted().role == MEMBER_ROLE

    reachable = {
        Membership.create("org", "acc", MEMBER_ROLE).promoted().role,
        Membership.create("org", "acc", OWNER_ROLE).demoted().role,
    }
    assert reachable <= set(ROLES)


def test_a_role_change_records_the_role_the_row_actually_held(factory: sessionmaker) -> None:
    """`prior_role` comes from the stored row, not from the caller (`FR-014`).

    A forged `prior_role` would make the audit trail describe a transition that never happened, so
    the store re-reads the row inside the transaction rather than trusting the event handed to it.
    Regression cover for a defect review caught in `R2-04`: only the destination was validated, so
    an event claiming `prior_role="owner"` against a `member` row committed.
    """
    accounts, store = SqlAccountStore(factory), SqlOrganizationStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    subject = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(store).create_organization("Acme", owner.account_id, now=NOW)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=subject.account_id,
                role=MEMBER_ROLE,
            )
        )

    # An event whose prior_role lies about the row it describes.
    lying = MembershipEvent.role_changed(
        organization.organization_id,
        subject.account_id,
        prior_role=OWNER_ROLE,  # the row holds MEMBER_ROLE
        next_role=OWNER_ROLE,
        actor_account_id=owner.account_id,
        now=NOW,
    )
    promoted = Membership.create(organization.organization_id, subject.account_id, OWNER_ROLE)

    assert not store.promote_membership(promoted, lying), (
        "a write whose event misdescribes the row's prior role must be refused"
    )
    surviving = store.get_membership(organization.organization_id, subject.account_id)
    assert surviving is not None
    assert surviving.role == MEMBER_ROLE, "the refused write changed nothing"


# --- stale fakes ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("protocol", "fake"),
    [
        pytest.param(OrganizationStore, MemoryOrganizationStore, id="organizations"),
        pytest.param(AccountStore, MemoryAccountStore, id="accounts"),
        pytest.param(InvitationStore, MemoryInvitationStore, id="invitations"),
    ],
)
def test_every_fake_implements_its_whole_protocol(protocol: type, fake: type) -> None:
    """Fails closed when a slice widens a store protocol and forgets the fake.

    This is the actual future failure mode, not a hypothetical: a fake missing a method makes tests
    that use it fail loudly, but a fake whose method *disagrees* with SQL makes them pass wrongly.
    One such defect shipped in this slice — `count_owners` counted membership rows where SQL counted
    effective owners, so a disabled account read as a live owner in unit tests only.

    Signatures are compared, not just names, because a fake accepting different arguments cannot be
    exercised by the same test as the real store.
    """
    required = {
        name: inspect.signature(method)
        for name, method in inspect.getmembers(protocol, inspect.isfunction)
        if not name.startswith("__")
    }
    assert required, f"{protocol.__name__} declares methods"

    implemented = dict(inspect.getmembers(fake, inspect.isfunction))
    missing = sorted(name for name in required if name not in implemented)
    assert not missing, f"{fake.__name__} does not implement {missing}"

    mismatched = {
        name: (str(expected), str(inspect.signature(implemented[name])))
        for name, expected in required.items()
        if str(inspect.signature(implemented[name])) != str(expected)
    }
    assert not mismatched, f"{fake.__name__} signatures diverge from the protocol: {mismatched}"


def test_the_memory_invitation_store_refuses_a_conflicting_terminal_save() -> None:
    """Second regression cover of the same class, from `#217`.

    `SqlInvitationStore.save_invitation` refuses a snapshot proposing the terminal state the row
    already excludes, because `ck_rca_invitation_terminal_state` forbids a row holding both. The
    fake took the two fields independently (`stored.x or invitation.x` each) and so *built* that
    row instead -- accepting a write production rejects with `IntegrityError`.

    Without this, removing the fake's guard breaks nothing: the whole invitation suite passed
    against a fake constructing a state the schema excludes, which is exactly the
    "passes wrongly" failure the protocol test above is about, one level deeper -- signatures
    agreed the entire time.
    """
    store = MemoryInvitationStore()
    invitation = Invitation.create(
        InvitationOffer(
            organization_id="org_1",
            intended_role=MEMBER_ROLE,
            target_identity=EMAIL,
            issued_by="acc_1",
        ),
        secret=issue_secret(),
        expires_at=NOW + timedelta(days=7),
        issued_at=NOW,
    )
    store.add_invitation(invitation)

    assert store.save_invitation(invitation.revoked(at=NOW))
    assert store.save_invitation(invitation.redeemed(at=NOW)) is False, (
        "the fake must refuse the conflicting transition, as SQL does"
    )

    stored = store.invitations[invitation.invitation_id]
    assert stored.revoked_at == NOW, "the first transition stands"
    assert stored.redeemed_at is None, (
        "a fake holding both timestamps is a row `ck_rca_invitation_terminal_state` forbids"
    )


def test_the_memory_store_counts_effective_owners_not_rows() -> None:
    """Regression cover for the divergence that already shipped.

    A disabled account keeps its owner-role membership row, because the account foreign key is
    `RESTRICT` and the row cannot be deleted. So counting rows reports a live owner where there is
    none, and `FR-013`'s guard would let the last effective owner be removed.
    """
    accounts = MemoryAccountStore()
    organizations = MemoryOrganizationStore(accounts)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    organizations.memberships[(organization.organization_id, second.account_id)] = (
        Membership.create(organization.organization_id, second.account_id, OWNER_ROLE)
    )
    assert (
        organizations.count_owners(organization.organization_id, excluding_account_id="acc_absent")
        == 2
    )

    LifecycleService(accounts, organizations).disable_account(second.account_id, now=NOW)

    assert (
        organizations.count_owners(organization.organization_id, excluding_account_id="acc_absent")
        == 1
    ), "a disabled account still holds its row but must not count as an owner"


# --- the guard is one implementation, not two -----------------------------------------------


def _method_source(name: str) -> str:
    return inspect.getsource(getattr(SqlOrganizationStore, name))


@pytest.mark.parametrize("operation", ["revoke_membership", "demote_membership"])
def test_no_owner_reducing_operation_decides_the_guard_itself(operation: str) -> None:
    """`FR-013` is decided in one place (`R2-06`), asserted on the source.

    Two operations each implementing the invariant would be two chances to get it wrong, and the
    #155 defect showed the failure is not detectable by observation on a passing run. Each operation
    delegates to `_apply_membership_change`, which owns the lock, the count, and the refusal.
    """
    source = _method_source(operation)

    assert "_apply_membership_change" in source, "the operation must use the shared guard"
    tree = ast.parse(inspect.cleandoc(source).replace("    ", "", 1))
    decisions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "OWNER_CHANGE_FINAL_OWNER"
    ]
    assert not decisions, (
        f"{operation} decides the final-owner outcome itself; only the shared guard may"
    )
