"""The local operator's commands: issue an invitation, run a sweep, work jobs.

**Why issuing an invitation is a command and not a route.** RRA-001 excludes email
delivery mechanics, and `InvitationService.issue_invitation` accordingly has no
HTTP surface — that absence is the specification working, not a gap. A local
developer still needs a token to redeem, so it is printed here, where it is
obviously an operator action rather than a public signup path RRA-001 forbids.

**The token is printed once and never stored.** Only a salted scrypt hash reaches
the database, so a token lost here is gone and a new invitation is the remedy.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from khepri.local.config import LocalSettings
from khepri.local.wiring import build_stack, build_worker_stack, local_page_printer

DEFAULT_INVITATION_DAYS = 7


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="khepri-local",
        description="Local development commands. Not a deployment surface.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    invite = commands.add_parser("invite", help="issue a beta invitation token")
    invite.add_argument(
        "--days",
        type=int,
        default=DEFAULT_INVITATION_DAYS,
        help=f"validity in days (default {DEFAULT_INVITATION_DAYS})",
    )

    commands.add_parser("sweep", help="run one recovery and expiry pass")

    work = commands.add_parser("work", help="process due report jobs once")
    work.add_argument(
        "--workbooks",
        type=Path,
        default=Path("./.local-workbooks"),
        help="directory the Excel surface writes into",
    )
    work.add_argument("--limit", type=int, default=10, help="maximum jobs per run")

    arguments = parser.parse_args(argv)
    settings = LocalSettings.from_environment()

    if arguments.command == "invite":
        return _invite(settings, days=arguments.days)
    if arguments.command == "sweep":
        return _sweep(settings)
    return _work(settings, workbooks=arguments.workbooks, limit=arguments.limit)


def _invite(settings: LocalSettings, *, days: int) -> int:
    stack = build_stack(settings)
    token = stack.invitations.issue_invitation(
        expires_at=stack.clock() + timedelta(days=days)
    )
    print(token)
    return 0


def _sweep(settings: LocalSettings) -> int:
    stack = build_stack(settings)
    report = build_worker_stack(stack, workbooks=Path("./.local-workbooks")).sweeper.sweep(
        now=stack.clock()
    )
    print(
        f"expired_leases={report.expired_leases} "
        f"orphaned_jobs={report.orphaned_jobs} "
        f"expired_sessions={report.expired_sessions} "
        f"deletions_deferred={report.deletions_deferred}"
    )
    return 0


def _work(settings: LocalSettings, *, workbooks: Path, limit: int) -> int:
    """Drain due jobs with the browser held open for the whole run.

    The printer is built once around the loop rather than per job: launching
    Chromium costs far more than one render, and the deployed worker holds a
    browser for its lifetime too.
    """
    stack = build_stack(settings)
    workbooks.mkdir(parents=True, exist_ok=True)
    with local_page_printer() as printer:
        worker = build_worker_stack(stack, workbooks=workbooks, printer=printer).worker
        processed = worker.drain(limit=limit)
    print(f"processed={processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["DEFAULT_INVITATION_DAYS", "main"]
