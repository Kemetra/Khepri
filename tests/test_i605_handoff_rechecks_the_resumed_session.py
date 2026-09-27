"""The artifact handoff refuses a session it resumed after that session's content ended (`#605`).

`POST .../analyses/{run}/artifacts/{kind}` decided reachability in `_locate`, then resumed the
session through the bridge and set its cookie on whatever came back. A deletion committing between
the two left the handoff answering `303` with a cookie for ended content -- `RCA-005` `FR-127`'s
uniform denial broken at the handoff, stopped only by the report API one step later.

`tests/test_w110_concurrent_postgres.py` drives that interleaving on PostgreSQL. These tests pin the
decision itself on SQLite, with no second transaction: the bridge resumes the real session, and a
wrapper returns it as the deletion or the expiry left it. The handoff must act on the session it
resumed, not on what `_locate` read before.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest

from khepri.rra.session_cookie import SESSION_COOKIE
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import completed_run, handoff_address, services_over
from tests.w107_support import NOW
from tests.w110_postgres_support import shell_with_bridge


class _ResumedAs:
    """The real bridge, whose `resume` returns the session with `changes` applied to it."""

    def __init__(self, inner: Any, **changes: Any) -> None:
        self._inner = inner
        self._changes = changes

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def resume(self, **kwargs: Any) -> Any:
        resumed = self._inner.resume(**kwargs)
        return None if resumed is None else replace(resumed, **self._changes)


def _handoff(**changes: Any):
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    bridge = _ResumedAs(services_over(j, who).bridge, **changes)
    return shell_with_bridge(j, who, bridge).post(
        handoff_address(who, run.run_id, "web"), follow_redirects=False
    )


class _ExpiresDuringResume:
    """The real bridge, whose `resume` returns while the clock reaches the session's expiry."""

    def __init__(self, inner: Any, clock: Any) -> None:
        self._inner = inner
        self._clock = clock

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def resume(self, **kwargs: Any) -> Any:
        resumed = self._inner.resume(**kwargs)
        self._clock.now = resumed.content_expires_at
        return resumed


def test_a_session_expiring_during_resume_is_refused_without_a_cookie() -> None:
    """The liveness decision reads the clock after `resume`, not the instant the request began."""
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    bridge = _ExpiresDuringResume(services_over(j, who).bridge, j.clock)
    answer = shell_with_bridge(j, who, bridge).post(
        handoff_address(who, run.run_id, "web"), follow_redirects=False
    )

    assert answer.status_code == 404, "handed off a session that expired while it was resumed"
    assert "set-cookie" not in answer.headers


def test_a_live_resumed_session_is_handed_over() -> None:
    """The control: with nothing changed, the handoff redirects and sets the session's cookie."""
    answer = _handoff()

    assert answer.status_code == 303
    assert answer.cookies.get(SESSION_COOKIE)


@pytest.mark.parametrize(
    "ended",
    [
        pytest.param({"deletion_requested_at": NOW}, id="deletion-requested"),
        pytest.param({"content_expires_at": NOW - timedelta(days=1)}, id="expired"),
    ],
)
def test_an_ended_resumed_session_is_refused_without_a_cookie(ended: dict[str, Any]) -> None:
    answer = _handoff(**ended)

    assert answer.status_code == 404, "handed off a session whose content had ended"
    assert "set-cookie" not in answer.headers
