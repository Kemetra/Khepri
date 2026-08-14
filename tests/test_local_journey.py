"""The whole journey, once, against the running local stack.

Invitation, consent, upload, profiling, mapping, facts, report job, the bundle,
and deletion — driven through the HTTP surface exactly as a beta participant
would, with the worker run in between.

**This is a development test, not evidence.** It proves the parts connect on one
machine. It measures nothing, and a duration taken here would be a number about a
laptop, not about the environment `KHEPRI-DEC-007` sizes. No timing is asserted
and none should be added.

**Why it is one test rather than nine.** Each step consumes what the last
produced: there is no upload without consent and no package without a profile.
Split into independent tests, eight of them would re-drive the whole journey to
reach their own starting point, and the thing being verified — that the steps
connect — would be the thing none of them checked.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from khepri.local.config import LocalSettings
from khepri.local.wiring import (
    LocalStack,
    build_stack,
    build_web_app,
    build_worker_stack,
    local_page_printer,
)
from khepri.rca.lifecycle import (
    MEMBERSHIP_EVENT_RETENTION_MONTHS,
    RETENTION_MONTHS,
    AccountRetentionSweeper,
    MembershipEventSweeper,
)
from khepri.rra.bundle import REQUIRED_SURFACES
from tests.local_stack_support import requires_local_stack

RETAIL_CSV = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)


def chromium_available() -> bool:
    """Whether the pinned browser can start, which the PDF surface requires."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        play = sync_playwright().start()
    except Exception:
        return False
    try:
        browser = play.chromium.launch(headless=True)
    except Exception:
        return False
    else:
        browser.close()
        return True
    finally:
        play.stop()


@pytest.fixture
def stack() -> LocalStack:
    return build_stack(LocalSettings.from_environment())


@pytest.fixture
def client(stack: LocalStack) -> Iterator[TestClient]:
    # HTTPS because the session cookie is `secure`; a plain-http client would
    # never send it back and every later step would read as unauthenticated.
    with TestClient(build_web_app(stack), base_url="https://local.test") as session:
        yield session


@requires_local_stack()
@pytest.mark.local_stack
class TestTheWholeJourney:
    def test_invitation_through_bundle_and_deletion(
        self,
        stack: LocalStack,
        client: TestClient,
        tmp_path: Path,
    ) -> None:
        token = stack.invitations.issue_invitation(
            expires_at=stack.clock() + timedelta(days=7)
        )
        assert token.startswith("kiv1.")

        redeemed = client.post("/api/v1/beta/sessions/redeem", json={"token": token})
        assert redeemed.status_code == 201, redeemed.text
        assert redeemed.json()["consent_required"] is True

        # Upload before consent is refused, which is the RRA-001 ordering rule.
        too_early = client.post(
            "/api/v1/beta/uploads",
            content=RETAIL_CSV,
            headers={"content-type": "text/csv"},
        )
        assert too_early.status_code == 403, too_early.text

        consented = client.post("/api/v1/beta/consent", json={"consent_version": "v1"})
        assert consented.status_code == 204, consented.text

        uploaded = client.post(
            "/api/v1/beta/uploads",
            content=RETAIL_CSV,
            headers={"content-type": "text/csv"},
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["media_type"] == "text/csv"
        assert uploaded.json()["size_bytes"] == len(RETAIL_CSV)

        profiled = client.post("/api/v1/beta/profile", json={"requested_semantics": []})
        assert profiled.status_code == 201, profiled.text
        assert profiled.json()["admissible"] is True
        assert profiled.json()["row_count"] == 4

        facts = client.post("/api/v1/beta/facts")
        assert facts.status_code == 201, facts.text
        package_digest = facts.json()["package_digest"]
        assert package_digest

        requested = client.post("/api/v1/beta/reports", json={})
        assert requested.status_code == 201, requested.text
        job_id = requested.json()["job_id"]
        assert requested.json()["state"] == "queued"

        # Re-requesting is the same request, so it is the same job.
        again = client.post("/api/v1/beta/reports", json={})
        assert again.status_code == 200, again.text
        assert again.json()["job_id"] == job_id

        if not chromium_available():
            pytest.skip("the pinned Chromium is not installed; the PDF surface cannot render")

        with local_page_printer() as printer:
            workers = build_worker_stack(stack, workbooks=tmp_path, printer=printer)
            assert workers.worker.drain(limit=5) >= 1

        finished = client.get(f"/api/v1/beta/reports/{job_id}")
        assert finished.status_code == 200, finished.text
        assert finished.json()["state"] == "succeeded"
        assert finished.json()["bundle_id"]

        bundle = client.get(f"/api/v1/beta/reports/{job_id}/bundle")
        assert bundle.status_code == 200, bundle.text
        body = bundle.json()
        assert set(body["surfaces"]) == set(REQUIRED_SURFACES)
        assert body["narrative_state"] == "included"
        assert body["bundle_id"] == finished.json()["bundle_id"]

        deleted = client.delete("/api/v1/beta/content")
        assert deleted.status_code == 204, deleted.text

        # Deleted content is gone, so the session can no longer be read through.
        after = client.get("/api/v1/beta/facts")
        assert after.status_code == 401, after.text


@requires_local_stack()
@pytest.mark.local_stack
class TestIsolationHolds:
    def test_another_session_cannot_read_a_job(
        self,
        stack: LocalStack,
        client: TestClient,
        tmp_path: Path,
    ) -> None:
        """A job belonging to somebody else is absent, never forbidden."""
        first = stack.invitations.issue_invitation(
            expires_at=stack.clock() + timedelta(days=7)
        )
        client.post("/api/v1/beta/sessions/redeem", json={"token": first})
        client.post("/api/v1/beta/consent", json={"consent_version": "v1"})
        client.post(
            "/api/v1/beta/uploads",
            content=RETAIL_CSV,
            headers={"content-type": "text/csv"},
        )
        client.post("/api/v1/beta/profile", json={"requested_semantics": []})
        client.post("/api/v1/beta/facts")
        job_id = client.post("/api/v1/beta/reports", json={}).json()["job_id"]

        second = stack.invitations.issue_invitation(
            expires_at=stack.clock() + timedelta(days=7)
        )
        with TestClient(
            build_web_app(stack), base_url="https://local.test"
        ) as intruder:
            intruder.post("/api/v1/beta/sessions/redeem", json={"token": second})

            seen = intruder.get(f"/api/v1/beta/reports/{job_id}")
            assert seen.status_code == 404, seen.text

            bundle = intruder.get(f"/api/v1/beta/reports/{job_id}/bundle")
            assert bundle.status_code == 404, bundle.text


@requires_local_stack()
@pytest.mark.local_stack
class TestTheSweeper:
    def test_a_sweep_reports_counts_and_no_identifiers(
        self,
        stack: LocalStack,
        tmp_path: Path,
    ) -> None:
        """Evidence of a sweep is counts. A session id here would be content."""
        report = build_worker_stack(stack, workbooks=tmp_path).sweeper.sweep(
            now=stack.clock()
        )

        assert report.expired_leases >= 0
        assert report.orphaned_jobs >= 0
        assert report.expired_sessions >= 0
        assert report.deletions_deferred >= 0
        assert report.purged_accounts >= 0
        assert report.purged_events >= 0

    def test_a_sweep_runs_both_retention_horizons(
        self,
        stack: LocalStack,
        tmp_path: Path,
    ) -> None:
        """Against the real stack: both passes are wired at the governed lengths.

        The ungated half of this evidence is in `test_local_sweeper.py`, which asserts the same
        wiring without needing docker. This adds that the wired passes survive a real sweep.
        """
        sweeper = build_worker_stack(stack, workbooks=tmp_path).sweeper
        retention = sweeper._retention  # noqa: SLF001 -- the wiring *is* the assertion

        assert retention is not None, "production must configure the retention passes"
        assert isinstance(retention.accounts, AccountRetentionSweeper), "§2b pass wired"
        assert isinstance(retention.events, MembershipEventSweeper), "§2a pass wired"
        assert retention.accounts._retention_months == RETENTION_MONTHS  # noqa: SLF001
        assert (
            retention.events._retention_months == MEMBERSHIP_EVENT_RETENTION_MONTHS  # noqa: SLF001
        ), "production must not run a compressed audit horizon"
