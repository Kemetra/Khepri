"""`RCA-010` `FR-200`: the master specification §11 accessibility floors, per shell surface.

`tests/` only. Where a floor fails, the fix lands in the slice that owns the file, not here --
this module changes no source file, and an evidence slice that edited a template to make its own
assertion pass would leave the failure in the product.

Two rosters, because one driver cannot serve both. `SHELL_SURFACES` renders through
`add_shell_routes(app, services=ShellServices(...))`; the legal pages render through
`add_legal_routes(app)`, which takes no services argument, and six of them share one template.
"""

from __future__ import annotations

from html.parser import HTMLParser

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.runtime.legal_api import LEGAL_PAGES, LEGAL_PREFIX, add_legal_routes
from tests.test_r807_shell_quality import SHELL_SURFACES, _html

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


#: Landmarks `FR-200` requires to carry meaningful unique accessible names.
#:
#: `form` and `section` are deliberately absent. Both are landmarks **only when they carry an
#: accessible name**: an unnamed `<form>` is exposed as a plain grouping, not as a `form`
#: landmark, so requiring a name here would report the single-button revoke and download forms
#: on `team` and `analysis` as defects when the button is what names the action. Including them
#: would have made this floor fire on correct markup -- the opposite of the requirement.
_LANDMARKS = frozenset({"nav", "main", "header", "footer", "aside"})


class _Landmarks(HTMLParser):
    """Collects landmarks with their accessible names, by parser rather than by regex.

    Slice 8 settled the idiom after a substring scan counted `data-href=` as an anchor `href`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, str | None]] = []
        self.tabindex: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("tabindex") is not None:
            self.tabindex.append(str(values["tabindex"]))
        if tag in _LANDMARKS:
            self.found.append((tag, values.get("aria-label") or values.get("aria-labelledby")))


def _parse(html: str) -> _Landmarks:
    parser = _Landmarks()
    parser.feed(html)
    return parser


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_no_surface_carries_a_positive_tabindex(surface: str, language: str) -> None:
    """`FR-200`: focus order follows document order, so no positive `tabindex` anywhere."""
    for value in _parse(_html(surface, language)).tabindex:
        assert int(value) <= 0, f"{surface}/{language} carries tabindex={value}"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page", sorted(LEGAL_PAGES))
def test_no_legal_page_carries_a_positive_tabindex(page: str, language: str) -> None:
    """The same floor over the surfaces the shell roster cannot reach."""
    for value in _parse(_legal_html(page, language)).tabindex:
        assert int(value) <= 0, f"{page}/{language} carries tabindex={value}"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_repeated_landmarks_carry_distinct_accessible_names(surface: str, language: str) -> None:
    """`FR-200`: landmarks are meaningful and unique.

    A sole `main` needs no name -- naming it would be ARIA where native semantics suffice, which
    the same requirement forbids. The floor is that landmarks sharing a tag are *told apart*,
    which is where a screen-reader user is actually stranded. `decision` carries two `nav` regions
    ("Sections" and "Analysis") and is the case that makes this non-vacuous.
    """
    found = _parse(_html(surface, language)).found
    for tag in {element for element, _ in found}:
        names = [name for element, name in found if element == tag]
        if len(names) > 1:
            assert all(names), f"{surface}/{language}: repeated <{tag}> without a name"
            assert len(set(names)) == len(names), f"{surface}/{language}: duplicate <{tag}> names"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_surface_has_exactly_one_main_landmark(surface: str, language: str) -> None:
    """`FR-200`: semantic landmarks. One `main` is what the skip link targets."""
    found = _parse(_html(surface, language)).found
    assert len([tag for tag, _ in found if tag == "main"]) == 1
