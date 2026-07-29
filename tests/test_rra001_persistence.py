from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.persistence import (
    Base,
    InvitationRow,
    SqlSessionStore,
    invitation_for_update_statement,
)
from khepri.rra.sessions import InvitationRejected, InvitationService

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def store_and_factory() -> tuple[SqlSessionStore, sessionmaker]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return SqlSessionStore(factory), factory


def test_sql_store_roundtrips_only_the_invitation_hash() -> None:
    store, factory = store_and_factory()
    service = InvitationService(store)

    token = service.issue_invitation(expires_at=NOW + timedelta(hours=1))
    invitation_id, secret = service.parse_token(token)

    with factory() as database:
        row = database.get(InvitationRow, invitation_id)
        assert row is not None
        assert "secret" not in inspect(InvitationRow).columns
        assert secret.encode() not in row.secret_digest
        assert secret.encode() not in row.secret_salt

    restored = store.get_invitation(invitation_id)
    assert restored is not None
    assert service.verify_secret(secret, restored)


def test_sql_store_atomically_rejects_invitation_replay() -> None:
    store, _ = store_and_factory()
    service = InvitationService(store)
    token = service.issue_invitation(expires_at=NOW + timedelta(hours=1))

    first = service.redeem(token, now=NOW)

    with pytest.raises(InvitationRejected):
        service.redeem(token, now=NOW)
    assert store.get_session(first.session_id) == first


def test_sql_store_persists_versioned_consent() -> None:
    store, _ = store_and_factory()
    service = InvitationService(store)
    session = service.redeem(
        service.issue_invitation(expires_at=NOW + timedelta(hours=1)),
        now=NOW,
    )

    service.record_consent(
        session.session_id,
        consent_version="beta-privacy-v1",
        now=NOW + timedelta(minutes=1),
    )

    restored = store.get_session(session.session_id)
    assert restored is not None
    assert restored.consent_version == "beta-privacy-v1"
    assert restored.consented_at == NOW + timedelta(minutes=1)


def test_redemption_query_locks_the_invitation_on_postgresql() -> None:
    statement = invitation_for_update_statement("inv_example")

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert "WHERE rra_invitations.invitation_id =" in sql
