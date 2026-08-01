"""Whether the local docker stack is reachable, decided once.

The tests that need it are skipped rather than failed when it is absent, which is
the same contract the `browser` marker already uses: CI runs neither Chromium nor
this stack, and a suite that went red without them would make `uv run pytest`
useless as the handoff gate `AGENTS.md` requires.

The probe is a socket connection, not an API call. It answers "is anything
listening" in milliseconds, and a stack that is listening but broken should fail
its test loudly rather than be skipped quietly.
"""

from __future__ import annotations

import socket
from functools import cache
from urllib.parse import urlparse

import pytest

from khepri.local.config import LocalSettings

CONNECT_TIMEOUT_SECONDS = 0.4


def _listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


@cache
def local_stack_available(settings: LocalSettings | None = None) -> bool:
    """True when both PostgreSQL and the object endpoint accept a connection."""
    resolved = settings or LocalSettings.from_environment()
    endpoint = urlparse(resolved.s3_endpoint)
    database = urlparse(resolved.database_url)
    if endpoint.hostname is None or database.hostname is None:
        return False
    return _listening(endpoint.hostname, endpoint.port or 4566) and _listening(
        database.hostname, database.port or 5432
    )


def requires_local_stack() -> pytest.MarkDecorator:
    """Skip unless `docker compose -f docker-compose.local.yml up -d` is running."""
    return pytest.mark.skipif(
        not local_stack_available(),
        reason="the local stack is not running (docker-compose.local.yml)",
    )


__all__ = ["CONNECT_TIMEOUT_SECONDS", "local_stack_available", "requires_local_stack"]
