"""Production-composed evidence for the bounded Clerk private-beta journey."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import URL, func, select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import OWNER_ROLE, OrganizationService
from khepri.rca.persistence import (
    AccountRow,
    ExternalIdentityRow,
    MembershipRow,
    SessionRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.sessions import hash_session_id
from khepri.rra.persistence import Base as RraBase
from khepri.runtime.commercial_api import COMMERCIAL_PREFIX
from khepri.runtime.config import ClerkIdentitySettings, RuntimeSettings
from khepri.runtime.external_auth_api import EXTERNAL_SESSION_PATH, KHEPRI_SESSION_LIFETIME
from khepri.runtime.wiring import RuntimeClients, RuntimeStack, build_stack, build_web_app

NOW = datetime.now(UTC).replace(microsecond=0)
ISSUER = "https://private-beta.clerk.accounts.example"
AUDIENCE = "khepri-private-beta"
PARTY = "https://beta.khepri.example"
KEY_ID = "ins_private_beta"
SUBJECT = "user_private_beta_123"


class AwsClientStub:
    pass


PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY = PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")


def _token(subject: str = SUBJECT, **claims: object) -> str:
    issued_at = int(datetime.now(UTC).timestamp())
    payload: dict[str, object] = {
        "iss": ISSUER,
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + 60,
        "azp": PARTY,
        "aud": AUDIENCE,
    }
    payload.update(claims)
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": KEY_ID})


@dataclass(slots=True)
class PrivateBetaJourney:
    stack: RuntimeStack
    factory: sessionmaker
    client: TestClient

    def provision(self, subject: str, email: str, organization: str) -> tuple[str, str]:
        account = AccountService(SqlAccountStore(self.factory)).preprovision_external_account(
            email, "clerk", subject, now=NOW
        )
        created = OrganizationService(SqlOrganizationStore(self.factory)).create_organization(
            organization, account.account_id, now=NOW
        )
        return account.account_id, created.organization_id

    def login(self, subject: str, organization_id: str, *, token: str | None = None):
        return self.client.post(
            EXTERNAL_SESSION_PATH,
            json={"organization_id": organization_id},
            headers={"Authorization": f"Bearer {token or _token(subject)}"},
        )


@pytest.fixture(name="journey")
def journey_fixture(tmp_path) -> PrivateBetaJourney:
    settings = RuntimeSettings(
        database_url=URL.create("sqlite+pysqlite", database=str(tmp_path / "private-beta.db")),
        region="me-central-1",
        bucket="khepri-beta-content",
        kms_key_arn=(
            "arn:aws:kms:me-central-1:123456789012:"
            "key/12345678-1234-1234-1234-123456789abc"
        ),
        expected_bucket_owner="123456789012",
        queue_url="https://sqs.example/report-jobs",
        dead_letter_queue_url="https://sqs.example/report-jobs-dlq",
        clerk=ClerkIdentitySettings(
            mode="test",
            issuer=ISSUER,
            jwt_key=PUBLIC_KEY,
            key_id=KEY_ID,
            authorized_parties=(PARTY,),
            audience=AUDIENCE,
        ),
    )
    stack = build_stack(
        settings,
        clients=RuntimeClients(s3=AwsClientStub()),
        clock=lambda: NOW,
    )
    engine = stack.factory.kw["bind"]
    RcaBase.metadata.create_all(engine)
    RraBase.metadata.create_all(engine)
    client = TestClient(build_web_app(stack), base_url=PARTY)
    return PrivateBetaJourney(stack=stack, factory=stack.factory, client=client)


def _answer(response) -> tuple[int, bytes, str | None]:
    return response.status_code, response.content, response.headers.get("set-cookie")


def test_signed_clerk_identity_enters_the_existing_commercial_journey(
    journey: PrivateBetaJourney,
) -> None:
    _, organization_id = journey.provision(SUBJECT, "owner@example.test", "Acme")

    authenticated = journey.login(
        SUBJECT,
        organization_id,
        token=_token(
            SUBJECT,
            email="mutable@example.test",
            org_role="admin",
            permissions=["everything"],
        ),
    )

    assert authenticated.status_code == 204
    cookie = authenticated.headers["set-cookie"]
    assert "Path=/api/v1/commercial" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    opened = journey.client.post(f"{COMMERCIAL_PREFIX}/analyses")
    assert opened.status_code == 201, "the browser must carry the Khepri cookie without help"
    analysis_id = opened.json()["session_id"]
    resumed = journey.client.get(f"{COMMERCIAL_PREFIX}/analyses/{analysis_id}")
    assert (resumed.status_code, resumed.json()) == (200, {"session_id": analysis_id})


def test_provider_unlinked_disabled_and_purged_refusals_are_identical(
    journey: PrivateBetaJourney,
) -> None:
    accounts = SqlAccountStore(journey.factory)
    organizations = SqlOrganizationStore(journey.factory)
    lifecycle = LifecycleService(accounts, organizations)

    disabled = AccountService(accounts).preprovision_external_account(
        "disabled@example.test", "clerk", "disabled_subject", now=NOW
    )
    lifecycle.disable_account(disabled.account_id, now=NOW)
    purged = AccountService(accounts).preprovision_external_account(
        "purged@example.test", "clerk", "purged_subject", now=NOW
    )
    lifecycle.disable_account(purged.account_id, now=NOW)
    assert accounts.purge_if_still_eligible(purged.account_id, NOW)

    before = _identity_counts(journey.factory)
    refusals = [
        journey.login("ignored", "org_missing", token="not-a-jwt"),
        journey.login("unlinked_subject", "org_missing"),
        journey.login("disabled_subject", "org_missing"),
        journey.login("purged_subject", "org_missing"),
    ]

    assert all(_answer(response) == _answer(refusals[0]) for response in refusals)
    assert _answer(refusals[0]) == (404, b"", None)
    assert _identity_counts(journey.factory) == before, "login must never bootstrap an account/link"


def _identity_counts(factory: sessionmaker) -> tuple[int, int]:
    with factory() as database:
        return (
            database.scalar(select(func.count()).select_from(AccountRow)),
            database.scalar(select(func.count()).select_from(ExternalIdentityRow)),
        )


def test_wrong_or_revoked_khepri_membership_fails_at_the_same_handoff(
    journey: PrivateBetaJourney,
) -> None:
    account_id, organization_id = journey.provision(SUBJECT, "member@example.test", "Acme")
    other_account, other_organization = journey.provision(
        "other_subject", "other@example.test", "Other"
    )
    wrong = journey.login(SUBJECT, other_organization)

    with journey.factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization_id,
                account_id=other_account,
                role=OWNER_ROLE,
            )
        )
    OrganizationService(SqlOrganizationStore(journey.factory)).revoke_membership(
        organization_id,
        account_id,
        actor_account_id=other_account,
        now=NOW,
    )
    revoked = journey.login(SUBJECT, organization_id)

    assert _answer(wrong) == _answer(revoked) == (404, b"", None)


def test_an_existing_identity_link_cannot_be_moved_during_login(
    journey: PrivateBetaJourney,
) -> None:
    original, organization_id = journey.provision(SUBJECT, "owner@example.test", "Acme")
    other = AccountService(SqlAccountStore(journey.factory)).create_account(
        "local@example.test", "correct horse battery staple"
    )
    sessions = SessionService(
        SqlSessionStore(journey.factory), lifetime=KHEPRI_SESSION_LIFETIME
    )

    assert not sessions.link_identity("clerk", SUBJECT, other.account_id, now=NOW)
    assert sessions.account_for_identity("clerk", SUBJECT) == original
    assert journey.login(SUBJECT, organization_id).status_code == 204


def test_revoked_session_and_foreign_analysis_keep_the_existing_uniform_refusal(
    journey: PrivateBetaJourney,
) -> None:
    account_id, organization_id = journey.provision(SUBJECT, "owner@example.test", "Acme")
    assert journey.login(SUBJECT, organization_id).status_code == 204
    opened = journey.client.post(f"{COMMERCIAL_PREFIX}/analyses")
    analysis_id = opened.json()["session_id"]

    raw_cookie = journey.client.cookies.get("khepri_session")
    assert raw_cookie is not None
    SessionService(
        SqlSessionStore(journey.factory), lifetime=KHEPRI_SESSION_LIFETIME
    ).revoke(raw_cookie, now=NOW)
    revoked = journey.client.get(f"{COMMERCIAL_PREFIX}/analyses/{analysis_id}")

    assert journey.login(SUBJECT, organization_id).status_code == 204
    stale_cookie = journey.client.cookies.get("khepri_session")
    assert stale_cookie is not None
    with journey.factory.begin() as database:
        stale = database.get(SessionRow, hash_session_id(stale_cookie))
        assert stale is not None
        stale.expires_at = NOW
    expired = journey.client.get(f"{COMMERCIAL_PREFIX}/analyses/{analysis_id}")

    _, outsider_organization = journey.provision(
        "outsider_subject", "outsider@example.test", "Outsider"
    )
    assert journey.login("outsider_subject", outsider_organization).status_code == 204
    foreign = journey.client.get(f"{COMMERCIAL_PREFIX}/analyses/{analysis_id}")
    nonexistent = journey.client.get(f"{COMMERCIAL_PREFIX}/analyses/ses_nope")

    assert opened.status_code == 201
    assert (revoked.status_code, revoked.content) == (404, b"")
    assert (expired.status_code, expired.content) == (404, b"")
    assert (foreign.status_code, foreign.content) == (
        nonexistent.status_code,
        nonexistent.content,
    ) == (404, b"")
    assert account_id
