"""Operator entry point for DEC-024's fail-closed Clerk hard stop."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.runtime.config import RuntimeConfigurationError, RuntimeSettings
from khepri.runtime.external_auth_api import KHEPRI_SESSION_LIFETIME

CLERK_PROVIDER = "clerk"


def revoke_clerk_sessions(settings: RuntimeSettings, *, now: datetime) -> int:
    """Revoke all affected Khepri sessions, but only after Clerk authentication is disabled."""
    if settings.clerk is not None:
        raise RuntimeConfigurationError(
            "KHEPRI_CLERK_MODE must be disabled before the Clerk hard stop runs."
        )
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        sessions = SessionService(
            SqlSessionStore(sessionmaker(bind=engine, future=True)),
            lifetime=KHEPRI_SESSION_LIFETIME,
        )
        return sessions.revoke_all_for_provider(CLERK_PROVIDER, now=now)
    finally:
        engine.dispose()


def main() -> None:
    """Run after disabled configuration is deployed and enabled instances are drained."""
    now = datetime.now(UTC)
    revoked = revoke_clerk_sessions(RuntimeSettings.from_environment(), now=now)
    print(
        json.dumps(
            {
                "event": "clerk_private_beta_hard_stop",
                "occurred_at": now.isoformat(),
                "revoked_sessions": revoked,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()


__all__ = ["CLERK_PROVIDER", "main", "revoke_clerk_sessions"]
