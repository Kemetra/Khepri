"""R3-04: create, resolve, expire, and revoke — the session service.

**Scope, and what it deliberately does not do.** `R3-01` §4 describes a five-step resolution path.
This slice owns steps 1 and 2: look up the presented identifier and decide whether the session is
live. Step 3, `assert_account_active`, is `R3-05`; step 4, live membership and role, is `R6-04`;
the cookie is `R3-06`; organization switching is `R6-03`.

That boundary is asserted here rather than merely described — `test_the_account_chokepoint_is_not_
yet_wired` fails if a later edit reaches for `assert_account_active` from this service, because
`R3-05`'s entire deliverable is being its first production caller.

**The uniform-refusal rule is the security property under test.** `FR-004` and `FR-022` require an
absent, unknown, expired, and revoked session to be indistinguishable. A caller that could tell
"expired" from "never existed" could enumerate valid identifiers one refusal at a time.
"""

from __future__ import annotations

import inspect as inspect_module
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.sessions import SESSION_ID_PREFIX, hash_session_id
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)
PROVIDER = "clerk"
SUBJECT = "user_2abcDEF"


def _account(factory: sessionmaker, email: str = EMAIL) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL).account_id


def _service(factory: sessionmaker) -> SessionService:
    return SessionService(SqlSessionStore(factory), lifetime=LIFETIME)


class TestCreate:
    def test_a_created_session_resolves_with_its_token(self, factory: sessionmaker) -> None:
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        assert service.resolve(token, now=NOW).account_id == _account_of(service, token)

    def test_the_returned_token_is_the_raw_secret_not_the_stored_hash(
        self, factory: sessionmaker
    ) -> None:
        """The cookie gets the raw token; the table gets its hash. `R3-06` puts this in a cookie."""
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        assert token.startswith(SESSION_ID_PREFIX)
        assert SqlSessionStore(factory).get_session(token) is None
        assert SqlSessionStore(factory).get_session(hash_session_id(token)) is not None

    def test_two_sessions_for_one_account_are_independent(self, factory: sessionmaker) -> None:
        """An account may hold several sessions; revoking one must not end the other."""
        service = _service(factory)
        account = _account(factory)
        first = service.create(account, now=NOW)
        second = service.create(account, now=NOW)
        assert first != second
        service.revoke(first, now=NOW)
        with pytest.raises(AuthenticationFailed):
            service.resolve(first, now=NOW)
        assert service.resolve(second, now=NOW).account_id == account

    def test_a_new_session_starts_with_no_active_organization(
        self, factory: sessionmaker
    ) -> None:
        """`FR-028`: an account with no membership must still authenticate."""
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        assert service.resolve(token, now=NOW).active_organization_id is None

    def test_the_horizon_is_the_configured_lifetime(self, factory: sessionmaker) -> None:
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        assert service.resolve(token, now=NOW).expires_at == NOW + LIFETIME

    def test_a_collided_identifier_refuses_rather_than_returning_a_dead_token(
        self, factory: sessionmaker
    ) -> None:
        """`add_session` reports False on a duplicate identifier, and that must not be ignored.

        Unreachable in practice — the identifier is 18 CSPRNG bytes through SHA-256 — so it is
        driven here with a store that always reports a collision. Without the guard, `create`
        returns a token naming no stored row and the caller holds a credential that can never
        resolve. Recorded as a test rather than deleted as dead code, because the branch is cheap
        and its absence would be silent.
        """

        class _CollidingStore(SqlSessionStore):
            def add_session(self, session: object) -> bool:  # noqa: ARG002
                return False

        service = SessionService(_CollidingStore(factory), lifetime=LIFETIME)
        with pytest.raises(AuthenticationFailed):
            service.create(_account(factory), now=NOW)


class TestResolve:
    def test_an_unknown_token_is_refused(self, factory: sessionmaker) -> None:
        with pytest.raises(AuthenticationFailed):
            _service(factory).resolve(f"{SESSION_ID_PREFIX}nonexistent", now=NOW)

    def test_an_expired_session_is_refused(self, factory: sessionmaker) -> None:
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        with pytest.raises(AuthenticationFailed):
            service.resolve(token, now=NOW + LIFETIME + timedelta(seconds=1))

    def test_the_expiry_instant_itself_is_expired(self, factory: sessionmaker) -> None:
        """The boundary is closed, matching `Session.is_expired_at` and `MembershipEvent`.

        Pins the `<=` in `is_expired_at`: a test that probed only `horizon + 1s` would pass against
        a `<` that leaves a one-instant window where a session is neither live nor expired.
        """
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        with pytest.raises(AuthenticationFailed):
            service.resolve(token, now=NOW + LIFETIME)

    def test_one_instant_before_the_horizon_still_resolves(self, factory: sessionmaker) -> None:
        """The other half of the boundary. Without it, `is_expired_at` could return True always."""
        service = _service(factory)
        account = _account(factory)
        token = service.create(account, now=NOW)
        resolved = service.resolve(token, now=NOW + LIFETIME - timedelta(microseconds=1))
        assert resolved.account_id == account

    def test_a_revoked_session_is_refused(self, factory: sessionmaker) -> None:
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        service.revoke(token, now=NOW)
        with pytest.raises(AuthenticationFailed):
            service.resolve(token, now=NOW)

    def test_every_refusal_is_indistinguishable(self, factory: sessionmaker) -> None:
        """`FR-004`, `FR-022`. Four distinct causes, one message and one type.

        If these ever diverge, a caller can enumerate valid identifiers by probing refusals.
        """
        service = _service(factory)
        expired = service.create(_account(factory), now=NOW)
        revoked = service.create(_account(factory, OTHER_EMAIL), now=NOW)
        service.revoke(revoked, now=NOW)

        messages = set()
        for token, moment in (
            (f"{SESSION_ID_PREFIX}unknown", NOW),
            ("not-even-a-session-token", NOW),
            (expired, NOW + LIFETIME),
            (revoked, NOW),
        ):
            with pytest.raises(AuthenticationFailed) as raised:
                service.resolve(token, now=moment)
            messages.add(str(raised.value))
        assert len(messages) == 1

    def test_resolution_returns_no_authority(self, factory: sessionmaker) -> None:
        """`FR-030`: the resolved session carries identity, never a cached role or membership."""
        service = _service(factory)
        resolved = service.resolve(service.create(_account(factory), now=NOW), now=NOW)
        forbidden = {"role", "can_act", "owner_id", "is_owner", "permissions", "membership"}
        assert forbidden.isdisjoint(dir(resolved))


class TestRevoke:
    def test_revoking_an_unknown_token_is_refused(self, factory: sessionmaker) -> None:
        with pytest.raises(AuthenticationFailed):
            _service(factory).revoke(f"{SESSION_ID_PREFIX}unknown", now=NOW)

    def test_revoking_twice_is_refused(self, factory: sessionmaker) -> None:
        """`revoked_at` records when authority ended; a second revocation would re-date it."""
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        service.revoke(token, now=NOW)
        with pytest.raises(AuthenticationFailed):
            service.revoke(token, now=NOW + timedelta(seconds=1))

    def test_revoking_records_the_moment_authority_ended(self, factory: sessionmaker) -> None:
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        ended = NOW + timedelta(hours=1)
        service.revoke(token, now=ended)
        stored = SqlSessionStore(factory).get_session(hash_session_id(token))
        assert stored is not None and stored.revoked_at == ended

    def test_revoke_all_ends_every_session_for_one_account(self, factory: sessionmaker) -> None:
        """`FR-007`, `FR-008`. The requirement that made Khepri hold its own sessions at all."""
        service = _service(factory)
        account = _account(factory)
        tokens = [service.create(account, now=NOW) for _ in range(3)]
        assert service.revoke_all(account, now=NOW) == 3
        for token in tokens:
            with pytest.raises(AuthenticationFailed):
                service.resolve(token, now=NOW)

    def test_revoke_all_leaves_other_accounts_untouched(self, factory: sessionmaker) -> None:
        service = _service(factory)
        mine = _account(factory)
        theirs = _account(factory, OTHER_EMAIL)
        service.create(mine, now=NOW)
        survivor = service.create(theirs, now=NOW)
        assert service.revoke_all(mine, now=NOW) == 1
        assert service.resolve(survivor, now=NOW).account_id == theirs

    def test_revoke_all_on_an_account_with_no_sessions_reports_zero(
        self, factory: sessionmaker
    ) -> None:
        """Not a refusal. Nothing to revoke is a truthful zero, not a failure."""
        assert _service(factory).revoke_all(_account(factory), now=NOW) == 0

    def test_revoke_all_does_not_re_date_an_existing_revocation(
        self, factory: sessionmaker
    ) -> None:
        service = _service(factory)
        account = _account(factory)
        token = service.create(account, now=NOW)
        service.revoke(token, now=NOW)
        assert service.revoke_all(account, now=NOW + timedelta(hours=2)) == 0
        stored = SqlSessionStore(factory).get_session(hash_session_id(token))
        assert stored is not None and stored.revoked_at == NOW


class TestExternalIdentity:
    def test_a_linked_subject_resolves_to_its_account(self, factory: sessionmaker) -> None:
        service = _service(factory)
        account = _account(factory)
        assert service.link_identity(PROVIDER, SUBJECT, account, now=NOW) is True
        assert service.account_for_identity(PROVIDER, SUBJECT) == account

    def test_an_unlinked_subject_resolves_to_nothing(self, factory: sessionmaker) -> None:
        assert _service(factory).account_for_identity(PROVIDER, SUBJECT) is None

    def test_relinking_a_subject_to_another_account_is_refused(
        self, factory: sessionmaker
    ) -> None:
        """`KHEPRI-DEC-018` §7: re-pointing a link is account takeover."""
        service = _service(factory)
        first = _account(factory)
        second = _account(factory, OTHER_EMAIL)
        assert service.link_identity(PROVIDER, SUBJECT, first, now=NOW) is True
        assert service.link_identity(PROVIDER, SUBJECT, second, now=NOW) is False
        assert service.account_for_identity(PROVIDER, SUBJECT) == first

    def test_unlinking_removes_only_the_link(self, factory: sessionmaker) -> None:
        """The account and its sessions survive; `can_act` is untouched (`R3-09` §5)."""
        service = _service(factory)
        account = _account(factory)
        token = service.create(account, now=NOW)
        service.link_identity(PROVIDER, SUBJECT, account, now=NOW)
        assert service.unlink_identity(PROVIDER, SUBJECT) is True
        assert service.account_for_identity(PROVIDER, SUBJECT) is None
        assert service.resolve(token, now=NOW).account_id == account

    def test_unlinking_an_absent_link_reports_false(self, factory: sessionmaker) -> None:
        assert _service(factory).unlink_identity(PROVIDER, SUBJECT) is False


class TestSliceBoundary:
    """What `R3-04` must not do. These fail if a later edit absorbs the next slice's work."""

    def test_the_account_chokepoint_is_not_yet_wired(self) -> None:
        """`R3-05` owns step 3 of `R3-01` §4.

        `assert_account_active` ships deliberately unused (`lifecycle.py:151`). Wiring it here
        would empty the next slice and, worse, would place the `FR-008` chokepoint in a service
        whose tests do not cover disablement.
        """
        source = inspect_module.getsource(SessionService)
        assert "assert_account_active" not in source
        assert "AccountService" not in source

    def test_the_service_does_not_own_the_cookie(self) -> None:
        """`R3-06` owns the HTTP boundary. A cookie name defined here would be a second
        definition of a security-relevant name, which `R3-01` §5 exists to prevent."""
        source = inspect_module.getsource(SessionService)
        for token in ("Set-Cookie", "HttpOnly", "SameSite", "Max-Age"):
            assert token not in source

    def test_the_service_does_not_switch_organizations(self) -> None:
        """`R6-03` owns selection and switching, because authorizing a switch needs live
        membership — which is `R6-04`'s resolver, not this slice's."""
        assert not hasattr(SessionService, "switch_organization")
        assert "switched_to" not in inspect_module.getsource(SessionService)


class TestTokenHandling:
    def test_the_raw_token_is_never_returned_by_resolution(self, factory: sessionmaker) -> None:
        """`IssuedSession` pairs the token with a record that does not contain it. Resolution
        returns only the record, so the raw token exists exactly once, at creation."""
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        resolved = service.resolve(token, now=NOW)
        assert token not in repr(resolved)
        assert resolved.session_id_hash == hash_session_id(token)

    def test_a_token_that_hashes_to_a_stored_row_is_the_only_way_in(
        self, factory: sessionmaker
    ) -> None:
        """Presenting the stored hash as though it were the token must not authenticate.

        Otherwise a database disclosure would hand over live sessions, defeating the reason
        `R3-01` §9 settled on hashing at rest.
        """
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        with pytest.raises(AuthenticationFailed):
            service.resolve(hash_session_id(token), now=NOW)


def _account_of(service: SessionService, token: str) -> str:
    return service.resolve(token, now=NOW).account_id


class TestClockDiscipline:
    def test_a_naive_moment_is_refused(self, factory: sessionmaker) -> None:
        """SQLite drops `tzinfo`, and a naive/aware comparison raises rather than mis-deciding.

        Refusing at the boundary makes the failure a caller error instead of a `TypeError` from
        deep inside a comparison — and expiry is the one decision this column exists to make.
        """
        service = _service(factory)
        token = service.create(_account(factory), now=NOW)
        with pytest.raises(ValueError):
            service.resolve(token, now=datetime(2026, 8, 15, 12, 0, 0))  # noqa: DTZ001

    def test_creation_also_refuses_a_naive_moment(self, factory: sessionmaker) -> None:
        with pytest.raises(ValueError):
            _service(factory).create(_account(factory), now=datetime.now())  # noqa: DTZ005

    def test_an_aware_non_utc_moment_is_accepted(self, factory: sessionmaker) -> None:
        """Aware is the requirement, not UTC specifically — comparison is well-defined."""
        service = _service(factory)
        account = _account(factory)
        token = service.create(account, now=NOW.astimezone(UTC))
        assert service.resolve(token, now=NOW).account_id == account
