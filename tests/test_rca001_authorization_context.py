"""R6-02: an authorization context a handler cannot construct by accident.

**The task title says "cannot be constructed by handlers", and this suite deliberately asserts
something weaker.** `records.py` establishes that Python offers no private construction:
`object.__new__` allocates without a constructor, `object.__setattr__` mutates a frozen instance,
and any module may call `through_door()` itself. None is closable — a guard against
`object.__setattr__` is removable by `object.__setattr__`.

So the guarantee is that bypassing the door must be **deliberate and conspicuous**, never something
a caller does while writing ordinary-looking code. That distinction is the whole of it: nobody
writes `object.__new__(AuthorizationContext)` by accident, whereas
`dataclasses.replace(context, role=OWNER_ROLE)` is what a careful engineer writes *while trying to
do the right thing*. The first is out of scope; the second is the defect this type exists to make
impossible.

Claiming more would repeat the specific failure `records.py` records: `IsolationScope` once carried
a docstring asserting "no layer can construct a scope carrying an untrusted key", which was untrue
when written, and reviewers trusting it is part of why `#148` ran four review rounds.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import FrozenInstanceError, fields

import pytest

from khepri.rca.authorization import AuthorizationContext
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE
from khepri.rca.records import Sealed

ACCOUNT = "acc_example"
ORGANIZATION = "org_example"


def _context(role: str = OWNER_ROLE, organization_id: str | None = ORGANIZATION):
    return AuthorizationContext.create(
        account_id=ACCOUNT, organization_id=organization_id, role=role
    )


class TestTheShape:
    def test_it_carries_exactly_the_matrix_inputs(self) -> None:
        """`R6-01` §3: a cell is decided by the actor, the organization, and the role in it.

        An allowlist, following `SessionRow` and `VerifiedIdentity`: a field the matrix never
        reads is a field that will go stale without anything noticing.
        """
        assert {field.name for field in fields(AuthorizationContext)} == {
            "account_id",
            "organization_id",
            "role",
        }

    def test_the_organization_is_optional(self) -> None:
        """`FR-028`, scenario 18: an authenticated account with no membership still resolves.

        `None` is "this actor is in no organization right now", which is every organization-scoped
        cell in `R6-01` §3.1 denied — not an error, and not an absent context.
        """
        assert _context(role=None, organization_id=None).organization_id is None

    def test_a_role_without_an_organization_is_refused(self) -> None:
        """A role is a role *in* an organization. The pair is meaningless apart, and admitting it
        would let a context claim `owner` with nothing to be an owner of."""
        with pytest.raises(ValueError):
            AuthorizationContext.create(
                account_id=ACCOUNT, organization_id=None, role=OWNER_ROLE
            )

    def test_an_organization_without_a_role_is_refused(self) -> None:
        """The other half: naming an organization the actor holds no role in is the non-member
        case, and `R6-01` §3.1 denies it -- but the context must say so as `organization_id=None`
        rather than as an organization with a null role, or a cell has two spellings."""
        with pytest.raises(ValueError):
            AuthorizationContext.create(
                account_id=ACCOUNT, organization_id=ORGANIZATION, role=None
            )

    def test_an_unknown_role_is_refused(self) -> None:
        """`R2` left the domain accepting any string as a role, guarded only by no service taking
        one as input. This service takes one, so it checks."""
        with pytest.raises(ValueError):
            AuthorizationContext.create(
                account_id=ACCOUNT, organization_id=ORGANIZATION, role="superuser"
            )

    def test_it_carries_no_liveness_marker(self) -> None:
        """**Deliberately no `resolved_at`.** A context is valid for exactly one authorization
        decision, and a timestamp is an invitation to ask "is it still fresh?" -- which is the
        reuse `R6-01` §5 forbids. There is no expiry because there is no reuse."""
        names = {field.name for field in fields(AuthorizationContext)}
        for marker in ("resolved_at", "expires_at", "created_at", "valid_until"):
            assert marker not in names


class TestTheDoor:
    def test_it_is_sealed(self) -> None:
        assert issubclass(AuthorizationContext, Sealed)

    def test_direct_construction_is_refused(self) -> None:
        """The handler-shaped mistake: building the context inline instead of resolving it."""
        with pytest.raises(TypeError):
            AuthorizationContext(
                account_id=ACCOUNT, organization_id=ORGANIZATION, role=OWNER_ROLE
            )

    def test_dataclasses_replace_is_refused(self) -> None:
        """**The accident this type exists to prevent.**

        `dataclasses.replace(context, role=OWNER_ROLE)` is a privilege escalation written in the
        idiom of careful code. `records.py` records it as the bypass that reached review while
        someone was trying to do the right thing.
        """
        with pytest.raises(TypeError):
            dataclasses.replace(_context(role=MEMBER_ROLE), role=OWNER_ROLE)

    def test_deepcopy_cannot_substitute_a_field(self) -> None:
        """`copy.deepcopy(ctx, {id(ctx.role): "owner"})` is field substitution by another name.
        `Sealed.__deepcopy__` rebuilds from the source's own attributes."""
        context = _context(role=MEMBER_ROLE)
        substituted = copy.deepcopy(context, {id(context.role): OWNER_ROLE})
        assert substituted.role == MEMBER_ROLE

    def test_a_copy_is_faithful(self) -> None:
        context = _context()
        assert copy.copy(context) == context

    def test_it_is_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            _context(role=MEMBER_ROLE).role = OWNER_ROLE  # type: ignore[misc]

    def test_a_subclass_cannot_reach_the_constructor(self) -> None:
        """`records.py`'s fourth bypass: a subclass overriding construction. `assert_sealed`
        requires the exact declared type for the same reason."""

        class Forged(AuthorizationContext):
            pass

        with pytest.raises(TypeError):
            Forged(account_id=ACCOUNT, organization_id=ORGANIZATION, role=OWNER_ROLE)


class TestNoReconstructionDoor:
    def test_there_is_no_from_storage(self) -> None:
        """**One door, unlike every other sealed record in this package.**

        Creation and reconstruction exist because records are persisted and read back. An
        authorization context is never stored: it is derived from live state for one decision and
        discarded. A `_from_storage` would be a way to rebuild a past authorization, which is
        precisely the staleness `FR-008` and `FR-030` forbid.
        """
        assert not hasattr(AuthorizationContext, "_from_storage")

    def test_no_store_persists_a_context(self) -> None:
        """The absence above is only meaningful while nothing writes one."""
        import pathlib

        for path in pathlib.Path("src/khepri/rca").glob("*persistence*.py"):
            assert "AuthorizationContext" not in path.read_text(encoding="utf-8")


class TestTheMatrixReadsIt:
    def test_an_owner_context_reports_owner(self) -> None:
        assert _context(role=OWNER_ROLE).is_owner is True

    def test_a_member_context_does_not_report_owner(self) -> None:
        assert _context(role=MEMBER_ROLE).is_owner is False

    def test_an_organizationless_context_does_not_report_owner(self) -> None:
        """Scenario 18. No organization means no role in one, so no owner cell is reachable."""
        assert _context(role=None, organization_id=None).is_owner is False

    def test_membership_is_not_a_separate_flag(self) -> None:
        """`is_member` would be derivable from `organization_id is not None`, and a second
        spelling of one fact is how the two drift. `R2`'s `Account` records the same rule for
        `revoked_at`: derived state is never duplicated into a boolean."""
        names = {field.name for field in fields(AuthorizationContext)}
        assert "is_member" not in names
