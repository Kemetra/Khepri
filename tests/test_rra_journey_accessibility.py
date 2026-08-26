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


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("step", ["upload", "review", "processing", "report"])
def test_step_nav_marks_exactly_the_current_step(language: str, step: str) -> None:
    body = client().get(f"/beta/{language}/{step}").text
    nav = re.search(r'<nav class="step-nav".*?</nav>', body, re.DOTALL).group(0)
    links = re.findall(r"<a\s[^>]*>", nav)
    assert len(links) == 4
    current_links = [link for link in links if 'aria-current="step"' in link]
    assert len(current_links) == 1
    assert f"/beta/{language}/{step}" + '"' in current_links[0]
    hrefs_in_order = re.findall(r'href="([^"]+)"', nav)
    assert hrefs_in_order == [
        f"/beta/{language}/upload",
        f"/beta/{language}/review",
        f"/beta/{language}/processing",
        f"/beta/{language}/report",
    ]


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


@pytest.mark.parametrize("language", ["en", "ar"])
def test_refusal_and_transport_error_no_longer_share_paint(language: str) -> None:
    body = client().get(f"/beta/{language}/review").text
    error_div = re.search(r'<div id="error-summary"[^>]*>', body).group(0)
    findings_div = re.search(r'<div id="profile-findings"[^>]*', body).group(0)
    assert 'class="error-summary"' in error_div
    assert 'role="alert"' in error_div
    assert "refusal-summary" not in error_div
    assert 'class="refusal-summary"' in findings_div
    assert 'role="status"' in findings_div
    assert "error-summary" not in findings_div


def test_refusal_css_uses_the_disclosure_shape_not_the_danger_family() -> None:
    css = files("khepri.rra.journey").joinpath("assets", "journey.css").read_text(
        encoding="utf-8"
    )
    rule = re.search(r"\.refusal-summary\s*\{[^}]*\}", css)
    assert rule is not None
    declaration = rule.group(0)
    assert "border-inline-start: 4px solid var(--muted)" in declaration
    assert "italic" in declaration
    assert "--danger" not in declaration
    assert "#d9a49f" not in declaration
    assert "#faece9" not in declaration
    assert "#6d201b" not in declaration


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
