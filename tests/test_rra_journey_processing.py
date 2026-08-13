from __future__ import annotations

from importlib.resources import files

from tests.test_rra_journey_api import client


def test_processing_page_claims_no_percentage_or_estimated_time() -> None:
    body = client().get("/beta/en/processing").text
    assert 'role="progressbar"' in body
    assert "%" not in body
    assert "minute" not in body.lower()
    assert body.count("<li>") == 4


def test_polling_is_bounded_pauses_hidden_and_resumes_visible() -> None:
    script = files("khepri.rra.journey").joinpath("assets", "processing.js").read_text(
        encoding="utf-8"
    )
    assert "let delay = 1000" in script
    assert "Math.min(delay * 2, 10000)" in script
    assert "document.hidden" in script
    assert 'visibilitychange' in script
    assert "timer = null" in script


def test_processing_recovers_missing_and_dead_lettered_jobs() -> None:
    script = files("khepri.rra.journey").joinpath("assets", "processing.js").read_text(
        encoding="utf-8"
    )
    assert "!state.job_id && state.package_present" in script
    assert 'api("/api/v1/beta/reports"' in script
    assert 'state.job_state === "dead_lettered"' in script
    assert "processing-recovery" in script
