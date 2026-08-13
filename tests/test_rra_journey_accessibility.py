from __future__ import annotations

import re
from importlib.resources import files

import pytest

from tests.test_rra_journey_api import client


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("step", ["upload", "review", "processing", "report"])
def test_pages_have_one_landmark_heading_and_unique_ids(language: str, step: str) -> None:
    body = client().get(f"/beta/{language}/{step}").text
    ids = re.findall(r'\bid="([^"]+)"', body)
    assert len(ids) == len(set(ids))
    assert body.count("<main") == 1
    assert body.count("<h1") == 1
    assert '<html lang=' in body
    assert 'aria-label=' in body or 'aria-labelledby=' in body


def test_upload_controls_have_labels_errors_and_progress_semantics() -> None:
    body = client().get("/beta/en/upload").text
    assert '<label class="consent-row">' in body
    assert 'for="sales-file"' in body
    assert 'role="alert"' in body
    assert 'aria-valuemin="0" aria-valuemax="100"' in body


def test_review_table_and_processing_status_have_required_semantics() -> None:
    review = client().get("/beta/en/review").text
    processing = client().get("/beta/en/processing").text
    assert "<caption" in review and 'scope="col"' in review
    assert 'role="region"' in review
    assert 'aria-live="polite"' in processing


def test_css_carries_focus_touch_narrow_and_reduced_motion_rules() -> None:
    css = files("khepri.rra.journey").joinpath("assets", "journey.css").read_text(
        encoding="utf-8"
    )
    assert ":focus-visible" in css
    assert "min-block-size: 44px" in css
    assert "@media (max-width: 640px)" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "animation: none" in css
    assert "overflow-x: auto" in css
