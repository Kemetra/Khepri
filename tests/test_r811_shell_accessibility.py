"""`RCA-010` `FR-200`: the master specification §11 accessibility floors, per shell surface.

`tests/` only. Where a floor fails, the fix lands in the slice that owns the file, not here --
this module changes no source file, and an evidence slice that edited a template to make its own
assertion pass would leave the failure in the product.

Two rosters, because one driver cannot serve both. `SHELL_SURFACES` renders through
`add_shell_routes(app, services=ShellServices(...))`; the legal pages render through
`add_legal_routes(app)`, which takes no services argument, and six of them share one template.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.runtime.legal_api import LEGAL_PAGES, LEGAL_PREFIX, add_legal_routes

#: The legal pages, by the state each renders. `about-us` and `refund-and-void` publish; the
#: other four hold a governed unpublished state and answer 503. Both are measurable documents --
#: each carries exactly one `h1` -- and driving only the unpublished four would be a run that can
#: only produce the null case.
LEGAL_PUBLISHED = ("about-us", "refund-and-void")
LEGAL_UNPUBLISHED = ("contact-us", "data-protection", "privacy-policy", "terms-and-conditions")


def _legal_client() -> TestClient:
    """The legal routes carry no session and no services, so this needs neither."""
    app = FastAPI()
    add_legal_routes(app)
    return TestClient(app, base_url="https://testserver")


def _legal_html(page: str, language: str) -> str:
    return _legal_client().get(f"{LEGAL_PREFIX}/{language}/{page}").text


def test_the_legal_roster_matches_the_served_inventory() -> None:
    """A legal page added to the product without a case here fails rather than going unmeasured."""
    assert LEGAL_PAGES, "no legal pages found, so this test proves nothing"
    assert set(LEGAL_PUBLISHED) | set(LEGAL_UNPUBLISHED) == set(LEGAL_PAGES)


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page", sorted(LEGAL_PAGES))
def test_every_legal_page_renders_one_heading_in_both_languages(page: str, language: str) -> None:
    """Both the published and the unpublished state are documents, not error pages."""
    html = _legal_html(page, language)
    assert html.count("<h1") == 1
    assert f'lang="{language}"' in html


def test_a_published_legal_page_carries_more_than_its_chrome() -> None:
    """Without this, every legal measurement below could pass over an empty document."""
    published = len(_legal_html("about-us", "en"))
    unpublished = len(_legal_html("contact-us", "en"))
    assert published > unpublished, "the published page must carry content the unpublished lacks"
