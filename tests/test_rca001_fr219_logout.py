"""An authenticated actor ends their own session (`RCA-001` `FR-219`, acceptance row 21).

Driven through `build_web_app`, the production composition root, so a route that exists as a
library function but is never registered cannot pass. Two stacks:

- **provider-less** (`clerk=None`): sessions are minted directly through `SessionService`, because
  a live session can still be presented to an app whose provider was disabled before the operator
  ran `clerk_hard_stop`. Logout must work there too.
- **Clerk-enabled**: the realistic path, a session obtained through the provider handoff.

Every server-side claim is read back from the RCA session store rather than inferred from the
response, because `FR-219`'s point is that the *store* stops authorizing, not the browser.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import URL
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.persistence import SessionRow, SqlAccountStore
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.sessions import hash_session_id
from khepri.rra.persistence import Base as RraBase
from khepri.runtime.config import RuntimeSettings
from khepri.runtime.external_auth_api import KHEPRI_SESSION_LIFETIME
from khepri.runtime.session_end_api import SESSION_END_PATH, add_session_end_route
from khepri.runtime.wiring import RuntimeClients, build_stack, build_web_app
from tests.test_clerk_private_beta_e2e import (
    _MASTER_KEY,
    NOW,
    PARTY,
    SUBJECT,
    AwsClientStub,
    PrivateBetaJourney,
    build_private_beta_journey,
)

GARBAGE = "not-a-session-token"


@dataclass(slots=True)
class ProviderlessApp:
    engine: Engine
    factory: sessionmaker
    client: TestClient

    def sessions(self) -> SessionService:
        return SessionService(SqlSessionStore(self.factory), lifetime=KHEPRI_SESSION_LIFETIME)

    def account(self, email: str = "owner@example.test", subject: str = SUBJECT) -> str:
        created = AccountService(SqlAccountStore(self.factory)).preprovision_external_account(
            email, "clerk", subject, now=NOW
        )
        return created.account_id

    def is_live(self, token: str) -> bool:
        try:
            self.sessions().resolve(token, now=NOW)
        except AuthenticationFailed:
            return False
        return True

    def logout(self, token: str | None):
        return _logout(self.client, token)


def _logout(client: TestClient, token: str | None):
    """POST logout presenting exactly `token`, never whatever the client's jar holds."""
    client.cookies.clear()
    headers = {} if token is None else {"Cookie": f"{SESSION_COOKIE}={token}"}
    return client.post(SESSION_END_PATH, headers=headers)


def _answer(response) -> tuple[int, bytes, str | None]:
    return response.status_code, response.content, response.headers.get("set-cookie")


def _assert_clears_the_cookie(response) -> None:
    """The success shape, asserted in full so a missing route's 404 cannot pass for it."""
    assert response.status_code == 204
    assert response.content == b""
    cookie = response.headers.get("set-cookie")
    assert cookie is not None
    parts = {part.strip() for part in cookie.split(";")}
    assert f'{SESSION_COOKIE}=""' in parts
    assert {"Max-Age=0", "Path=/", "HttpOnly", "Secure", "SameSite=strict"} <= parts


@pytest.fixture(name="app")
def providerless_app_fixture(tmp_path) -> Iterator[ProviderlessApp]:
    settings = RuntimeSettings(
        database_url=URL.create("sqlite+pysqlite", database=str(tmp_path / "logout.db")),
        storage_endpoint="https://fra1.spaces.example",
        storage_region="fra1",
        bucket="khepri-beta-content",
        master_key=_MASTER_KEY,
        clerk=None,
    )
    stack = build_stack(settings, clients=RuntimeClients(s3=AwsClientStub()), clock=lambda: NOW)
    assert stack.identity_provider is None
    engine = stack.factory.kw["bind"]
    RcaBase.metadata.create_all(engine)
    RraBase.metadata.create_all(engine)
    # `Origin` as a browser sends it: a cookie-bearing mutation without either browser signal is
    # refused (`require_same_origin`, `#434` §2).
    client = TestClient(build_web_app(stack), base_url=PARTY, headers={"Origin": PARTY})
    try:
        yield ProviderlessApp(engine=engine, factory=stack.factory, client=client)
    finally:
        client.close()
        engine.dispose()


@pytest.fixture(name="journey")
def journey_fixture(tmp_path) -> Iterator[PrivateBetaJourney]:
    journey = build_private_beta_journey(tmp_path)
    try:
        yield journey
    finally:
        journey.close()


def test_logout_revokes_the_session_in_the_store_and_clears_the_cookie(
    app: ProviderlessApp,
) -> None:
    """Revoked server-side, so the same token no longer resolves -- and the cookie is cleared.

    Registered with no provider configured: the session below was minted directly, as one that
    outlived its provider's configuration would have been.
    """
    token = app.sessions().create(app.account(), now=NOW)
    assert app.is_live(token)

    response = app.logout(token)

    _assert_clears_the_cookie(response)
    assert not app.is_live(token), "a cookie-only logout leaves the token authorizing"
    with app.factory() as database:
        row = database.get(SessionRow, hash_session_id(token))
        assert row is not None and row.revoked_at is not None


def test_logout_leaves_the_accounts_other_sessions_live(app: ProviderlessApp) -> None:
    account_id = app.account()
    ended = app.sessions().create(account_id, now=NOW)
    other = app.sessions().create(account_id, now=NOW)

    app.logout(ended)

    assert not app.is_live(ended)
    assert app.is_live(other), "logout must end only the presented session"


def test_the_answer_is_identical_whether_or_not_the_session_was_live(
    app: ProviderlessApp,
) -> None:
    """Live, already revoked, unknown, and absent: one status, one body, one Set-Cookie."""
    live = app.sessions().create(app.account(), now=NOW)
    revoked = app.sessions().create(app.account("second@example.test", "user_2"), now=NOW)
    app.sessions().revoke(revoked, now=NOW)
    expired = app.sessions().create(
        app.account("third@example.test", "user_3"), now=NOW - timedelta(hours=13)
    )
    assert not app.is_live(expired)

    answers = {
        "live": app.logout(live),
        "already-revoked": app.logout(revoked),
        "expired": app.logout(expired),
        "garbage": app.logout(GARBAGE),
        "empty": app.logout(""),
        "absent": app.logout(None),
    }

    for response in answers.values():
        _assert_clears_the_cookie(response)
    assert len({_answer(response) for response in answers.values()}) == 1


def test_logging_out_twice_answers_the_same_both_times(app: ProviderlessApp) -> None:
    token = app.sessions().create(app.account(), now=NOW)

    first = app.logout(token)
    second = app.logout(token)

    assert _answer(first) == _answer(second)
    _assert_clears_the_cookie(second)


def test_a_session_from_the_provider_handoff_ends_at_logout(
    journey: PrivateBetaJourney,
) -> None:
    """The deployed path: sign in through Clerk twice, log out one, the other keeps working."""
    _, organization_id = journey.provision(SUBJECT, "owner@example.test", "Acme")
    first = journey.login(SUBJECT, organization_id).cookies.get(SESSION_COOKIE)
    second = journey.login(SUBJECT, organization_id).cookies.get(SESSION_COOKIE)
    assert first and second and first != second
    sessions = SessionService(SqlSessionStore(journey.factory), lifetime=KHEPRI_SESSION_LIFETIME)

    response = _logout(journey.client, first)

    _assert_clears_the_cookie(response)
    with pytest.raises(AuthenticationFailed):
        sessions.resolve(first, now=NOW)
    assert sessions.resolve(second, now=NOW).session_id_hash == hash_session_id(second)


class _FailingStore:
    """A session service whose store is unavailable: `revoke` fails for a non-governed reason."""

    def revoke(self, token: str, *, now) -> None:
        raise RuntimeError("session store unavailable")


def test_a_failed_revoke_does_not_clear_the_cookie() -> None:
    """FR-219's ordering: the cookie is cleared only after the store has revoked the session.

    Only the governed refusal is answered as success. A store failure must not produce a cleared
    cookie over a token that still authorizes.
    """
    bare = FastAPI()
    add_session_end_route(bare, sessions=_FailingStore(), clock=lambda: NOW)
    client = TestClient(bare, base_url=PARTY, raise_server_exceptions=False)

    response = _logout(client, "cse_some_live_looking_token")

    assert response.status_code == 500
    assert response.headers.get("set-cookie") is None


def test_a_cross_site_logout_is_refused_before_it_touches_the_session(
    app: ProviderlessApp,
) -> None:
    """The app-global same-origin middleware refuses a forced logout.

    No revoke and no cleared cookie: the refusal happens before the route runs.
    """
    token = app.sessions().create(app.account(), now=NOW)
    app.client.cookies.clear()

    response = app.client.post(
        SESSION_END_PATH,
        headers={
            "Cookie": f"{SESSION_COOKIE}={token}",
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )

    assert response.status_code == 403
    assert response.headers.get("set-cookie") is None
    assert app.is_live(token)
