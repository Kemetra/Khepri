from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from khepri.rra.journey.state import JourneyResources, JourneySnapshot, snapshot

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("resources", "expected"),
    [
        ({}, "upload"),
        ({"upload_present": True}, "upload"),
        ({"profile_present": True}, "review"),
        ({"profile_present": True, "package_present": True}, "processing"),
        (
            {
                "profile_present": True,
                "package_present": True,
                "job_id": "job_alpha",
                "job_state": "succeeded",
                "bundle_complete": True,
            },
            "report",
        ),
    ],
)
def test_snapshot_derives_one_resumable_step(resources: dict[str, object], expected: str) -> None:
    assert snapshot(
        content_expires_at=NOW + timedelta(days=7),
        resources=JourneyResources(**resources),
    ).step == expected


def test_snapshot_refuses_a_complete_bundle_without_a_succeeded_job() -> None:
    with pytest.raises(ValueError, match="complete bundle"):
        JourneySnapshot(
            step="report",
            content_expires_at=NOW + timedelta(days=7),
            consent_recorded=True,
            upload_present=True,
            profile_present=True,
            profile_admissible=True,
            package_present=True,
            job_id="job_alpha",
            job_state="running",
            job_reason=None,
            row_count=10,
            generated_at=NOW,
            bundle_complete=True,
        )


def test_dead_letter_reason_is_safe_journey_recovery_state() -> None:
    found = snapshot(
        content_expires_at=NOW + timedelta(days=7),
        resources=JourneyResources(
            package_present=True,
            job_id="job_alpha",
            job_state="dead_lettered",
            job_reason="retries_exhausted",
        ),
    )
    assert found.step == "processing"
    assert found.job_reason == "retries_exhausted"
