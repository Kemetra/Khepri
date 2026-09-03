from __future__ import annotations

from importlib.resources import files

from tests.test_rra_journey_api import client


def test_report_links_are_absent_from_initial_html() -> None:
    body = client().get("/beta/en/report").text
    assert 'id="report-links"' in body and " hidden" in body
    assert "/surfaces/web/en" not in body
    assert "Uploaded dataset" in body


def test_report_module_builds_exactly_seven_links_only_after_complete_bundle() -> None:
    script = files("khepri.rra.journey").joinpath("assets", "report.js").read_text(
        encoding="utf-8"
    )
    assert "if (!state || !state.bundle_complete) return" in script
    for path in (
        "surfaces/web/en", "surfaces/web/ar", "surfaces/evidence/en",
        "surfaces/evidence/ar", "surfaces/pdf/en", "surfaces/pdf/ar", "surfaces/excel",
    ):
        assert path in script
    assert "object_key" not in script


def test_the_report_page_shows_the_session_deletion_deadline() -> None:
    """A participant near expiry has to see when access ends, not a generic promise.

    The footer states the seven-day retention in general terms. A report generated
    late in a session may have hours left, so the page carries the governed
    `content_expires_at` for this session -- with its timezone, because a deadline
    read in the wrong zone is worse than none.
    """
    script = files("khepri.rra.journey").joinpath("assets", "report.js").read_text(
        encoding="utf-8"
    )
    assert "state.content_expires_at" in script
    assert "timeZoneName" in script

    for language, label in (("en", "Available until"), ("ar", "متاح حتى")):
        body = client().get(f"/beta/{language}/report").text
        # The slot the module fills, and the label naming it in this language.
        assert 'id="expires-at"' in body
        assert label in body
