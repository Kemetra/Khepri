"""A disabled or revoked actor cannot use an existing RRA analysis session (`R7-03`).

**The claim.** `FR-030` requires a membership or role change to take effect for decisions made
after it, *"without requiring the affected session to end"*; `FR-008` requires a disabled account's
pre-existing sessions to stop authorizing *"with no dependence on session expiry"*. `R7-01` §4
applies both to the bridge: *"The authorization step is not skipped on resume… a resumed session
re-resolves the context, exactly as `R6-07`'s scenario-20 tests require. This is what `R7-03`
tests."* `KHEPRI-DEC-021` repeats it and names this the evidence slice.

## The gap this file fills, and why the two existing suites do not

Two suites look like they already cover this. Neither does, and the distinction is the reason this
file exists rather than more cases being added to either.

- **`test_rca001_stale_session_authorization.py`** (`R6-07`) drives a live `cse_` session through
  `AuthorizationResolver` and proves revocation, demotion and disablement take effect immediately.
  It stops at `resolve_scope`. **No RRA analysis exists anywhere in it**, so it cannot say what
  happens to one.
- **`test_r707_commercial_bridge.py`** (`R7-07`) proves the bridge re-resolves on resume. But every
  case passes `account_id` **directly** and constructs no session at all. A test that never mints a
  session cannot show that a *session-bearing* actor loses access -- which is the whole of what
  "cannot use an existing analysis session" claims.

This file is the join: a live authentication session, resolved through the canonical resolver, whose
resulting context drives the bridge to an RRA analysis **that already exists**. Authority is then
removed and the resume re-attempted.

## Two independent layers, asserted separately

The composition `AuthorizationResolver.resolve(token) -> AuthorizationContext -> bridge` is what
`R7-05`'s endpoint will do; `AuthorizationContext` carries exactly the `(account_id,
organization_id)` pair the bridge accepts, so no production seam is needed to test it here.

That composition puts **two** gates in the path, and a test asserting only the outcome could not say
which one held:

1. `ActorResolver` calls `assert_account_active` at step 3 of every resolution (`R3-05`), so a
   disabled account fails *authentication* before the bridge is reached.
2. `IsolationService.resolve_scope` refuses a non-member and a disabled account inside the bridge.

Both are asserted, because a slice that removed either would still pass a test that only checked the
actor was refused. `TestBothLayersRefuseIndependently` is where that is pinned down.

## What makes these tests non-vacuous

**The analysis row must still exist at the moment of refusal.** Otherwise "cannot resume" is
satisfied by "there was nothing to resume", which is a different and much weaker claim. Every
refusal case below asserts the `BetaSessionRow` is still present afterwards -- so the refusal is
authorization, not absence.

**The clock never advances.** Every case resolves at `NOW`, changes authority at `NOW`, and resolves
again at `NOW`. `FR-008`'s "no dependence on session expiry" and `FR-030`'s "without requiring the
affected session to end" are both claims about immediacy, and a test that let time pass between the
two attempts would pass against an implementation that only took effect at refresh.

**Demotion is the load-bearing case.** Revocation and disablement are total, so any assertion that
the actor lost *something* is also an assertion that they lost everything -- the two cannot be told
apart. A demoted owner is still a member, and `R6-01` §3.1 gives a member `PERMIT` for scope
resolution, so the demoted actor **must still resume successfully**. A file asserting only refusals
would accept a demotion that quietly revoked, which is exactly the defect `R6-07`'s docstring
records mutating `demote_to_member` into `revoke_membership` to find.

**No production code is expected to change.** `R7-07`'s bridge already re-resolves. If anything here
fails, that is a real defect in the merged slice and is to be reported rather than accommodated.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.errors import AuthenticationFailed, ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    OrganizationService,
)
from khepri.rca.persistence import MembershipRow, SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore as SqlRcaSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from khepri.rra.persistence import Base as RraBase
from khepri.rra.persistence import SqlSessionStore as SqlRraSessionStore
from khepri.runtime.bridge import CommercialBridge
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    NOW,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)


def _rca_sessions(factory: sessionmaker) -> SessionService:
    return SessionService(SqlRcaSessionStore(factory), lifetime=LIFETIME)


def _resolver(factory: sessionmaker) -> AuthorizationResolver:
    actors = ActorResolver(
        _rca_sessions(factory),
        LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory)),
    )
    return AuthorizationResolver(actors, SqlOrganizationStore(factory))


def _isolation(factory: sessionmaker) -> IsolationService:
    return IsolationService(SqlOrganizationStore(factory), SqlAccountStore(factory))


def _account(factory: sessionmaker, email: str) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL).account_id


def _grant(factory: sessionmaker, organization_id: str, account_id: str, role: str) -> None:
    with factory.begin() as database:
        database.add(
            MembershipRow(organization_id=organization_id, account_id=account_id, role=role)
        )


class Journey:
    """One organization with two owners and one member, each holding a live session, plus an
    already-open RRA analysis for the organization's scope.

    **Two owners, for the same reason `R6-07`'s fixture has two.** `FR-013` refuses to demote or
    revoke the final owner, so with one owner the demotion case would fail on an invariant that is
    not authorization and the test would report the wrong thing.

    **Separate databases for RCA and RRA, deliberately.** The two packages own separate schemas and
    `FR-039` requires RRA to remain independently testable. Wiring them to one engine would be a
    convenience that quietly asserts they share a database, which no artifact says.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self.factory = factory
        self.rra_factory = _rra_factory()
        self.rra_store = SqlRraSessionStore(self.rra_factory)
        self.bridge = CommercialBridge(isolation=_isolation(factory), store=self.rra_store)

        self.first = _account(factory, "first@example.test")
        self.second = _account(factory, "second@example.test")
        self.member = _account(factory, "member@example.test")

        organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
            "Acme", self.first, now=NOW
        )
        self.organization_id = organization.organization_id
        _grant(factory, self.organization_id, self.second, OWNER_ROLE)
        _grant(factory, self.organization_id, self.member, MEMBER_ROLE)

        self.first_token = self._session(self.first)
        self.second_token = self._session(self.second)
        self.member_token = self._session(self.member)

        # The analysis that already exists. Opened by the member through the full path, so the
        # fixture itself proves the happy case reaches RRA before anything is taken away.
        self.session_id = self.open_through_session(self.member_token).session_id

    def _session(self, account_id: str) -> str:
        token = _rca_sessions(self.factory).create(account_id, now=NOW)
        OrganizationSwitcher(
            _rca_sessions(self.factory), SqlOrganizationStore(self.factory)
        ).switch(token, self.organization_id, now=NOW)
        return token

    def open_through_session(self, token: str):
        """The composition `R7-05`'s endpoint will perform: token -> context -> bridge."""
        context = _resolver(self.factory).resolve(token, now=NOW)
        return self.bridge.open(
            account_id=context.account_id,
            organization_id=context.organization_id,
            now=NOW,
        )

    def resume_through_session(self, token: str, session_id: str | None = None):
        context = _resolver(self.factory).resolve(token, now=NOW)
        return self.bridge.resume(
            account_id=context.account_id,
            organization_id=context.organization_id,
            session_id=session_id or self.session_id,
            now=NOW,
        )

    def analysis_exists(self) -> bool:
        """Whether the RRA row is still there -- so a refusal is authorization, not absence."""
        with self.rra_factory() as database:
            count = database.scalar(
                sa.text("SELECT count(*) FROM rra_beta_sessions WHERE session_id = :s"),
                {"s": self.session_id},
            )
        return bool(count)

    def revoke_membership_row(self, account_id: str) -> None:
        with self.factory.begin() as database:
            database.execute(
                sa.delete(MembershipRow).where(
                    MembershipRow.organization_id == self.organization_id,
                    MembershipRow.account_id == account_id,
                )
            )

    def demote(self, account_id: str) -> None:
        """Through the production verb, not a raw UPDATE.

        A fixture that wrote `role=member` directly would assert the *consequence* of a demoted
        role without ever exercising `demote_to_member` -- so a demotion implemented as a
        revocation would leave these tests green. `FR-013` needs a second owner to permit this at
        all, which the fixture provides.
        """
        OrganizationService(SqlOrganizationStore(self.factory)).demote_to_member(
            self.organization_id,
            account_id,
            actor_account_id=self.first,
            now=NOW,
        )

    def disable(self, account_id: str) -> None:
        with self.factory.begin() as database:
            database.execute(
                sa.text("UPDATE rca_accounts SET disabled_at = :now WHERE account_id = :a"),
                {"now": NOW, "a": account_id},
            )


def _rra_factory() -> sessionmaker:
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    RraBase.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(name="journey")
def journey_fixture(factory: sessionmaker) -> Journey:
    return Journey(factory)


class TestTheFixtureItselfReachesRra:
    """Before any denial means anything, the permitted path must work.

    A suite of refusals proves nothing if the happy path was broken -- every case would pass for the
    wrong reason. This is the positive control.
    """

    def test_a_member_with_a_live_session_opened_an_analysis(self, journey: Journey) -> None:
        assert journey.analysis_exists()

    def test_that_member_can_resume_it(self, journey: Journey) -> None:
        resumed = journey.resume_through_session(journey.member_token)

        assert resumed is not None
        assert resumed.session_id == journey.session_id

    def test_the_analysis_carries_the_organizations_scope(self, journey: Journey) -> None:
        """`KHEPRI-DEC-019` §1: the organization's scope is the analysis scope."""
        expected = _isolation(journey.factory).resolve_scope(
            journey.member, journey.organization_id
        )
        resumed = journey.resume_through_session(journey.member_token)

        assert resumed is not None
        assert resumed.owner_id == expected


class TestARevokedMemberCannotResume:
    """Scenario 20 carried through to an RRA analysis. `FR-030`."""

    def test_the_resume_is_refused(self, journey: Journey) -> None:
        journey.revoke_membership_row(journey.member)

        with pytest.raises(ScopeAccessDenied):
            journey.resume_through_session(journey.member_token)

    def test_the_analysis_still_exists_so_the_refusal_is_authorization(
        self, journey: Journey
    ) -> None:
        """The assertion that makes the refusal mean something.

        Without this, "cannot resume" is satisfied by "there was nothing to resume" -- a much weaker
        claim, and one a revocation that cascaded into RRA would also satisfy. An RCA authority
        change must not delete an RRA analysis.
        """
        journey.revoke_membership_row(journey.member)

        with pytest.raises(ScopeAccessDenied):
            journey.resume_through_session(journey.member_token)

        assert journey.analysis_exists()

    def test_the_authentication_session_is_still_live(self, journey: Journey) -> None:
        """`FR-030`: "without requiring the affected session to end".

        If revoking a membership also ended the session, the refusal above would look identical
        while violating the requirement. Asserted by resolving the same token again.
        """
        journey.revoke_membership_row(journey.member)

        context = _resolver(journey.factory).resolve(journey.member_token, now=NOW)

        assert context.account_id == journey.member
        assert context.role is None, "a revoked member must resolve with no role"

    def test_no_time_passed(self, journey: Journey) -> None:
        """Immediacy, asserted structurally: every call above uses `NOW`.

        A change that only took effect after a refresh would pass a test that advanced the clock.
        This asserts the fixture's own discipline rather than a behaviour, and fails if someone
        introduces a second timestamp.
        """
        journey.revoke_membership_row(journey.member)

        with pytest.raises(ScopeAccessDenied):
            journey.resume_through_session(journey.member_token)

        session = _rca_sessions(journey.factory).resolve(journey.member_token, now=NOW)
        assert session.expires_at > NOW, "the session has not expired; the refusal is not expiry"

    def test_other_members_are_unaffected(self, journey: Journey) -> None:
        """The change is scoped to one actor, not to the organization."""
        journey.revoke_membership_row(journey.member)

        resumed = journey.resume_through_session(journey.first_token)

        assert resumed is not None
        assert resumed.session_id == journey.session_id


class TestADisabledAccountCannotResume:
    """Scenario 16 carried through to an RRA analysis. `FR-008`."""

    def test_the_resume_is_refused(self, journey: Journey) -> None:
        journey.disable(journey.member)

        with pytest.raises((AuthenticationFailed, ScopeAccessDenied)):
            journey.resume_through_session(journey.member_token)

    def test_the_analysis_still_exists(self, journey: Journey) -> None:
        journey.disable(journey.member)

        with pytest.raises((AuthenticationFailed, ScopeAccessDenied)):
            journey.resume_through_session(journey.member_token)

        assert journey.analysis_exists()

    def test_it_does_not_wait_for_session_expiry(self, journey: Journey) -> None:
        """`FR-008` verbatim: "with no dependence on session expiry to take effect".

        The session's own lifetime is twelve hours and the clock never moves, so a refusal here
        cannot be attributed to expiry.
        """
        journey.disable(journey.member)

        with pytest.raises((AuthenticationFailed, ScopeAccessDenied)):
            journey.resume_through_session(journey.member_token)

    def test_the_membership_row_is_untouched(self, journey: Journey) -> None:
        """Disablement is an account-level fact and must not rewrite membership.

        `KHEPRI-DEC-015`'s table and project memory both record that disablement never touches
        membership rows -- which is why `FR-013` counts *effective* authority through `can_act`
        rather than counting rows.
        """
        journey.disable(journey.member)

        membership = SqlOrganizationStore(journey.factory).get_membership(
            journey.organization_id, journey.member
        )

        assert membership is not None
        assert membership.role == MEMBER_ROLE

    def test_other_accounts_keep_working(self, journey: Journey) -> None:
        journey.disable(journey.member)

        resumed = journey.resume_through_session(journey.first_token)

        assert resumed is not None


class TestADemotedOwnerStillResumes:
    """The load-bearing case: the one change where the actor keeps some authority.

    `R6-01` §3.1 gives a member `PERMIT` for scope resolution, so a demoted owner must **still**
    reach their analysis. A file asserting only refusals would accept a demotion that quietly
    revoked -- the defect `R6-07` found by mutating `demote_to_member` into `revoke_membership`.
    """

    def test_the_demoted_owner_can_still_resume(self, journey: Journey) -> None:
        journey.demote(journey.second)

        resumed = journey.resume_through_session(journey.second_token)

        assert resumed is not None
        assert resumed.session_id == journey.session_id

    def test_they_resolve_the_same_scope_as_before(self, journey: Journey) -> None:
        """`FR-035`: one organization resolves to a stable key across membership changes.

        A demotion that changed the isolation key would silently strand the analysis while every
        refusal test still passed.
        """
        before = _isolation(journey.factory).resolve_scope(
            journey.second, journey.organization_id
        )
        journey.demote(journey.second)
        after = _isolation(journey.factory).resolve_scope(journey.second, journey.organization_id)

        assert before == after

    def test_their_role_reads_live_as_member(self, journey: Journey) -> None:
        journey.demote(journey.second)

        context = _resolver(journey.factory).resolve(journey.second_token, now=NOW)

        assert context.role == MEMBER_ROLE


class TestARevokedAuthenticationSessionCannotResume:
    """The session, not the membership, is what is taken away.

    Separated from the membership cases because they are different failure modes with the same
    surface at the refused call: one removes authority, the other removes the proof of identity. A
    suite that only revoked memberships could not tell them apart.
    """

    def test_the_resume_is_refused(self, journey: Journey) -> None:
        _rca_sessions(journey.factory).revoke(journey.member_token, now=NOW)

        with pytest.raises(AuthenticationFailed):
            journey.resume_through_session(journey.member_token)

    def test_the_membership_survives(self, journey: Journey) -> None:
        _rca_sessions(journey.factory).revoke(journey.member_token, now=NOW)

        membership = SqlOrganizationStore(journey.factory).get_membership(
            journey.organization_id, journey.member
        )

        assert membership is not None

    def test_re_authenticating_restores_access(self, journey: Journey) -> None:
        """Proves the refusal was about the session and nothing else.

        If revoking a session had also removed authority, a fresh session would still be refused --
        and every other test in this class would look identical.
        """
        _rca_sessions(journey.factory).revoke(journey.member_token, now=NOW)
        fresh = journey._session(journey.member)  # noqa: SLF001 - the fixture's own helper

        resumed = journey.resume_through_session(fresh)

        assert resumed is not None
        assert resumed.session_id == journey.session_id


class TestBothLayersRefuseIndependently:
    """Two gates stand in this path, and a slice removing either must fail something.

    `ActorResolver` refuses a disabled account at step 3 of resolution (`R3-05`); `resolve_scope`
    refuses one inside the bridge. An outcome-only test passes with either gate alone, which is the
    "redundant guards need separate evidence" shape this repo has recorded. Each is isolated here.
    """

    def test_the_resolver_refuses_a_disabled_account_before_the_bridge(
        self, journey: Journey
    ) -> None:
        """Layer 1 alone: resolution fails, so the bridge is never reached."""
        journey.disable(journey.member)

        with pytest.raises(AuthenticationFailed):
            _resolver(journey.factory).resolve(journey.member_token, now=NOW)

    def test_the_bridge_refuses_a_disabled_account_even_when_handed_a_context(
        self, journey: Journey
    ) -> None:
        """Layer 2 alone: bypass the resolver, call the bridge directly with a valid pair.

        This is what would still hold if `ActorResolver` stopped checking activity. Calling the
        bridge with identifiers rather than a token is precisely the bypass a caller could attempt,
        so asserting it is asserting the gate rather than the composition.
        """
        journey.disable(journey.member)

        with pytest.raises(ScopeAccessDenied):
            journey.bridge.resume(
                account_id=journey.member,
                organization_id=journey.organization_id,
                session_id=journey.session_id,
                now=NOW,
            )

    def test_the_bridge_refuses_a_revoked_member_even_when_handed_a_context(
        self, journey: Journey
    ) -> None:
        """The same isolation for revocation: the bridge's own gate, not the resolver's."""
        journey.revoke_membership_row(journey.member)

        with pytest.raises(ScopeAccessDenied):
            journey.bridge.resume(
                account_id=journey.member,
                organization_id=journey.organization_id,
                session_id=journey.session_id,
                now=NOW,
            )
