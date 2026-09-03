from __future__ import annotations

import re
from importlib.resources import files

import pytest

from khepri.rra.journey.copy import JOURNEY_COPY
from tests.test_rra_journey_api import client

RED = pytest.mark.xfail(strict=True, reason="R8-10 RED: the report step renders seven equal cards.")


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


def _report_module() -> str:
    return files("khepri.rra.journey").joinpath("assets", "report.js").read_text(encoding="utf-8")


@RED
@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_report_step_separates_pages_to_open_from_files_to_download(language: str) -> None:
    """`R8-10`'s journey half: the reader is told where to look first, and what is a file.

    Two labelled groups, in a fixed order, each a landmark named by its own heading. The
    headings are the page's copy in its own language, not the module's, so a heading the
    module could forget is still on the page before any state loads.
    """
    body = client().get(f"/beta/{language}/report").text
    holder = re.search(r'<div id="report-links".*?</div>\s*<button', body, re.DOTALL).group(0)
    groups = re.findall(r'<section class="report-group" aria-labelledby="([^"]+)">', holder)
    assert groups == ["open-heading", "download-heading"]
    copy = JOURNEY_COPY[language]
    for heading_id, key in zip(groups, ("open_online", "downloads"), strict=True):
        assert f'<h2 id="{heading_id}">{copy[key]}</h2>' in holder
    assert re.findall(r'data-group="(\w+)"', holder) == ["open", "download"]
    assert holder.count('class="report-grid"') == 2


@RED
def test_the_report_module_files_every_surface_in_its_group() -> None:
    """Pages to open and files to download, decided per link and never by default.

    Every tuple names its group, so an eighth surface added later cannot land ungrouped.
    The page-language web report is first among the pages and is the one marked primary.
    """
    script = _report_module()
    tuples = re.findall(
        r'\[holder\.dataset\.(\w+), "([^"]+)", (\w+), "(open|download)"\]', script
    )
    assert len(tuples) == 7, "every one of the seven links carries a group"
    by_path = {path: group for _, path, _, group in tuples}
    assert {p for p, g in by_path.items() if g == "open"} == {
        "surfaces/web/en", "surfaces/web/ar", "surfaces/evidence/en", "surfaces/evidence/ar",
    }
    assert {p for p, g in by_path.items() if g == "download"} == {
        "surfaces/pdf/en", "surfaces/pdf/ar", "surfaces/excel",
    }
    assert "report-card--primary" in script
    # The page's own language leads: the module reorders rather than hardcoding English first.
    assert "language" in script.split("report-card--primary")[0]


@RED
def test_the_group_headings_name_an_affordance_and_no_figure() -> None:
    """`RRA-010` admits copy that names an affordance; a heading carrying a figure has left it."""
    for language in ("en", "ar"):
        for key in ("open_online", "downloads"):
            wording = JOURNEY_COPY[language][key]
            assert wording.strip(), f"{language}.{key} is empty"
            figure = re.search(r"[0-9%$€£]|[\u0660-\u0669]", wording)
            assert figure is None, f"{language}.{key} carries a figure"
