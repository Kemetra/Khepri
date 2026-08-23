"""DEC-024 hard-stop evidence for already-issued Khepri sessions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import URL, create_engine, func, select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import (
    AccountRow,
    ExternalIdentityRow,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rra.envelope import MasterKey
from khepri.runtime.clerk_hard_stop import revoke_clerk_sessions
from khepri.runtime.config import ClerkIdentitySettings, RuntimeConfigurationError, RuntimeSettings
from khepri.runtime.external_auth_api import KHEPRI_SESSION_LIFETIME

_MASTER_KEY = MasterKey(material=b"k" * 32)

NOW = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)


def _settings(database_url: URL, *, enabled: bool = False) -> RuntimeSettings:
    clerk = None
    if enabled:
        clerk = ClerkIdentitySettings(
            mode="test",
            issuer="https://test.clerk.accounts.example",
            jwt_key="-----BEGIN PUBLIC KEY-----x-----END PUBLIC KEY-----",
            key_id="test-key",
            authorized_parties=("https://test.khepri.example",),
            audience=None,
        )
    return RuntimeSettings(
        database_url=database_url,
        storage_endpoint="https://fra1.spaces.example",
        storage_region="fra1",
        bucket="test",
        master_key=_MASTER_KEY,
        clerk=clerk,
    )


def _counts(factory: sessionmaker) -> tuple[int, int, int]:
    with factory() as database:
        return (
            database.scalar(select(func.count()).select_from(AccountRow)),
            database.scalar(select(func.count()).select_from(ExternalIdentityRow)),
            database.scalar(select(func.count()).select_from(MembershipRow)),
        )


def test_hard_stop_revokes_every_clerk_linked_session_and_preserves_domain_state(
    tmp_path,
) -> None:
    database_url = URL.create("sqlite+pysqlite", database=str(tmp_path / "hard-stop.db"))
    engine = create_engine(database_url)
    RcaBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    accounts = AccountService(SqlAccountStore(factory))
    organizations = OrganizationService(SqlOrganizationStore(factory))
    sessions = SessionService(SqlSessionStore(factory), lifetime=KHEPRI_SESSION_LIFETIME)

    clerk_only = accounts.preprovision_external_account(
        "clerk@example.test", "clerk", "clerk-only", now=NOW
    )
    dual = accounts.create_account("dual@example.test", "correct horse battery staple")
    unrelated = accounts.create_account("unrelated@example.test", "correct horse battery staple")
    assert sessions.link_identity("clerk", "dual", dual.account_id, now=NOW)
    assert sessions.link_identity("other", "other", unrelated.account_id, now=NOW)
    organizations.create_organization("Clerk", clerk_only.account_id, now=NOW)

    clerk_token = sessions.create(clerk_only.account_id, now=NOW)
    dual_token = sessions.create(dual.account_id, now=NOW)
    unrelated_token = sessions.create(unrelated.account_id, now=NOW)
    before = _counts(factory)

    assert revoke_clerk_sessions(_settings(database_url), now=NOW) == 2
    assert revoke_clerk_sessions(_settings(database_url), now=NOW) == 0

    for token in (clerk_token, dual_token):
        with pytest.raises(AuthenticationFailed):
            sessions.resolve(token, now=NOW)
    assert sessions.resolve(unrelated_token, now=NOW).account_id == unrelated.account_id
    assert _counts(factory) == before
    assert sessions.account_for_identity("clerk", "clerk-only") == clerk_only.account_id
    assert sessions.account_for_identity("clerk", "dual") == dual.account_id
    engine.dispose()


def test_hard_stop_refuses_to_run_while_clerk_authentication_is_enabled(tmp_path) -> None:
    database_url = URL.create("sqlite+pysqlite", database=str(tmp_path / "enabled.db"))

    with pytest.raises(RuntimeConfigurationError, match="must be disabled"):
        revoke_clerk_sessions(_settings(database_url, enabled=True), now=NOW)


HARD_STOP_COMMAND = "khepri-clerk-hard-stop"


def test_the_hard_stop_is_registered_as_an_operator_command() -> None:
    """`KHEPRI-DEC-025` §4: the emergency procedure must be invokable, not merely implemented.

    Read from `pyproject.toml` rather than `importlib.metadata.entry_points()`. Installed metadata
    can be stale relative to the source declaration in an editable install, so a metadata-based
    assertion can pass against a previous install or fail without a reinstall — either way it would
    not be testing the declaration this slice adds.

    The target string is then resolved to the real callable, so a typo in the module path or
    function name fails here instead of at the operator's shell during an incident.
    """
    import importlib
    import tomllib
    from pathlib import Path

    manifest = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = manifest["project"]["scripts"]

    assert HARD_STOP_COMMAND in scripts, "the hard stop has no console entry point"
    module_path, _, attribute = scripts[HARD_STOP_COMMAND].partition(":")
    assert module_path == "khepri.runtime.clerk_hard_stop", (
        "the command must live in khepri.runtime; the wheel excludes src/khepri/local, so a "
        "command declared there would be absent from the image that has to run it"
    )
    resolved = getattr(importlib.import_module(module_path), attribute)

    from khepri.runtime import clerk_hard_stop

    assert resolved is clerk_hard_stop.main, "the command must invoke the existing implementation"


def test_the_registered_command_reuses_the_single_hard_stop_implementation() -> None:
    """`main` delegates rather than reimplementing, so one revocation rule cannot drift into two."""
    import inspect

    from khepri.runtime import clerk_hard_stop

    body = inspect.getsource(clerk_hard_stop.main)

    assert "revoke_clerk_sessions(" in body, "main must call the audited implementation"
    assert "revoke_all_for_provider" not in body, "main must not duplicate revocation logic"
