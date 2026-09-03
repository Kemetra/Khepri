from __future__ import annotations

import re
from datetime import date
from importlib.resources import files

import pytest

from khepri.rra.journey.copy import JOURNEY_COPY
from tests.test_rra_journey_api import client

_JOURNEY_MODULES = ("common.js", "upload.js", "review.js", "processing.js", "report.js")


def test_every_journey_page_has_a_secure_bilingual_document_shell() -> None:
    test = client()
    for language, direction in (("en", "ltr"), ("ar", "rtl")):
        for step in ("upload", "review", "processing", "report"):
            response = test.get(f"/beta/{language}/{step}")
            assert response.status_code == 200
            assert f'<html lang="{language}" dir="{direction}">' in response.text
            assert response.text.count("<h1") == 1
            assert '<main id="main-content"' in response.text
            assert 'href="#main-content"' in response.text
            assert "/beta/assets/journey.css" in response.text
            assert "http://" not in response.text
            assert "https://" not in response.text
            assert "onclick=" not in response.text
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["content-security-policy"].startswith("default-src 'none'")


def test_entry_route_is_the_upload_bootstrap_and_unknown_language_is_absent() -> None:
    test = client()
    assert test.get("/beta/en").status_code == 200
    assert 'data-step="upload"' in test.get("/beta/en").text
    assert test.get("/beta/fr/upload").status_code == 404


def test_only_allowlisted_local_assets_are_served() -> None:
    test = client()
    css = test.get("/beta/assets/journey.css")
    assert css.status_code == 200
    assert css.headers["cache-control"] == "public, max-age=0, must-revalidate"
    typeface = test.get("/beta/assets/NotoSansArabic-Regular-arabic.woff2")
    assert typeface.status_code == 200
    assert typeface.headers["content-type"] == "font/woff2"
    assert test.get("/beta/assets/../routes.py").status_code == 404


def test_expired_page_is_a_closed_local_journey_state() -> None:
    response = client().get("/beta/en/expired")
    assert response.status_code == 200
    assert 'data-step="expired"' in response.text


def test_common_module_routes_an_unavailable_session_to_expired() -> None:
    script = client().get("/beta/assets/common.js").text
    assert "error.status === 401" in script
    assert 'current !== "expired"' in script
    assert 'location.replace(routeFor("expired"))' in script
    assert "error.status !== 503" in script
    assert "?deletion=requested" in script


def test_no_journey_module_authors_a_customer_facing_string() -> None:
    test = client()
    assert _JOURNEY_MODULES
    for name in _JOURNEY_MODULES:
        script = test.get(f"/beta/assets/{name}")
        assert script.status_code == 200
        literals = re.findall(r'"([^"\\]*)"', script.text)
        arabic = [text for text in literals if re.search(r"[؀-ۿ]", text)]
        assert arabic == [], f"{name} authors Arabic copy: {arabic}"
        sentences = [
            text
            for text in literals
            if re.fullmatch(r"[A-Z][A-Za-z0-9 ,'’-]{14,}\.", text)
        ]
        assert sentences == [], f"{name} authors English copy: {sentences}"


def test_upload_module_reads_its_wording_from_the_page() -> None:
    body = client().get("/beta/en/upload").text
    assert "data-file-invalid=" in body
    assert "data-upload-failed=" in body
    script = client().get("/beta/assets/upload.js").text
    assert "dataset.fileInvalid" in script
    assert "dataset.uploadFailed" in script


def test_upload_page_collects_an_operator_coverage_attestation() -> None:
    body = client().get("/beta/en/upload").text
    for field in (
        "timezone",
        "covered_start",
        "covered_end",
        "aggregate_scope",
        "covered_days",
        "event_kinds",
        "statuses",
        "closed_days",
        "extraction_gap_days",
        "partial_terminal_boundary",
    ):
        assert f'data-manifest-field="{field}"' in body


def test_the_attestation_surface_separates_a_closure_from_a_gap() -> None:
    """`RRA-003`: "An attested closure proves complete zero activity; an
    extraction gap does not." The two have opposite consequences -- a closed day
    stays covered, a gap fails completeness for any window holding it -- so an
    operator who cannot tell them apart from the page will attest the wrong one.

    Asserted as distinct rendered wording rather than as two field names,
    because two controls sharing a description are two controls the operator
    cannot choose between.
    """
    body = client().get("/beta/en/upload").text
    closed = re.search(r'for="manifest-closed-days"[^>]*>([^<]+)<', body)
    gap = re.search(r'for="manifest-extraction-gap-days"[^>]*>([^<]+)<', body)
    assert closed is not None and gap is not None
    assert closed.group(1).strip() != gap.group(1).strip()
    # Each must say what it does to the answer, not merely name itself.
    assert "manifest-closed-days-hint" in body
    assert "manifest-extraction-gap-days-hint" in body
    assert "manifest-partial-terminal-boundary-hint" in body


def test_the_attestation_the_upload_page_emits_is_one_the_domain_admits() -> None:
    """The page's own controls, filled, produce a manifest `RRA-003` accepts.

    Asserting the markup alone would pass on a surface that collects the right
    field names in a shape `build_coverage_manifest` refuses, which is the
    failure this slice exists to prevent -- an attestation unreachable from a
    browser is not fixed by one the browser cannot get accepted.
    """
    from khepri.rra.coverage_request import CoverageManifestBody

    body = client().get("/beta/en/upload").text
    fields = re.findall(r'data-manifest-field="([^"]+)"', body)
    lists = {"covered_days", "event_kinds", "statuses", "closed_days", "extraction_gap_days"}
    typed = {
        "timezone": "Africa/Cairo",
        "attested_by": "Mona Farouk, branch manager",
        "covered_start": "2026-01-01",
        "covered_end": "2026-01-02",
        "aggregate_scope": "All stores",
        "covered_days": ["2026-01-01", "2026-01-02"],
        "event_kinds": ["sale"],
        "statuses": ["posted"],
        "closed_days": ["2026-01-02"],
        "extraction_gap_days": [],
        "partial_terminal_boundary": False,
    }
    assert set(fields) == set(typed)
    emitted = {name: typed[name] for name in fields}
    assert all(isinstance(emitted[name], list) for name in lists)

    manifest = CoverageManifestBody(**emitted)

    assert manifest.covered_start.isoformat() == "2026-01-01"
    assert manifest._scopes() == ("All stores",)
    assert len(manifest._pairs(manifest.covered_days)) == 2
    # The closed day is still a covered day: a closure proves zero activity
    # rather than missing activity, so it must not be subtracted from coverage.
    assert manifest._pairs(manifest.closed_days) == (("All stores", date(2026, 1, 2)),)


def test_upload_module_omits_the_manifest_when_nothing_is_attested() -> None:
    script = client().get("/beta/assets/upload.js").text
    assert "manifestFields" in script
    assert "coverage_manifest" in script
    assert "attestation()" in script


def test_pending_deletion_has_a_stable_confirmation_page() -> None:
    body = client().get("/beta/en/expired?deletion=requested").text
    assert "Deletion requested" in body
    assert "continue automatically" in body


def _report_module() -> str:
    return files("khepri.rra.journey").joinpath("assets", "report.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_report_step_leads_with_the_report_and_evidence(language: str) -> None:
    """`R8-10`'s journey half: the reader is told where to look first.

    Two labelled groups, in a fixed order, each a landmark named by its own heading: the
    report and its evidence, then the other formats. The headings are the page's copy in
    its own language, not the module's, so a heading the module could forget is still on
    the page before any state loads. They name what each group holds and claim nothing
    about mechanism -- every surface is served as an attachment (`report_api.py:562`).
    """
    body = client().get(f"/beta/{language}/report").text
    holder = re.search(r'<div id="report-links".*?</div>\s*<button', body, re.DOTALL).group(0)
    groups = re.findall(r'<section class="report-group" aria-labelledby="([^"]+)">', holder)
    assert groups == ["read-heading", "formats-heading"]
    copy = JOURNEY_COPY[language]
    for heading_id, key in zip(groups, ("report_and_evidence", "other_formats"), strict=True):
        assert f'<h2 id="{heading_id}">{copy[key]}</h2>' in holder
    assert re.findall(r'data-group="(\w+)"', holder) == ["read", "formats"]
    assert holder.count('class="report-grid"') == 2


def test_the_report_module_files_every_surface_in_its_group() -> None:
    """The report and evidence, then the other formats, decided per link and never by default.

    Every tuple names its group, so an eighth surface added later cannot land ungrouped.
    The page-language web report is first in the read group and is the one marked primary.
    """
    script = _report_module()
    tuples = re.findall(
        r'\[holder\.dataset\.(\w+), "([^"]+)", (\w+), "(read|formats)"\]', script
    )
    assert len(tuples) == 7, "every one of the seven links carries a group"
    by_path = {path: group for _, path, _, group in tuples}
    assert {p for p, g in by_path.items() if g == "read"} == {
        "surfaces/web/en", "surfaces/web/ar", "surfaces/evidence/en", "surfaces/evidence/ar",
    }
    assert {p for p, g in by_path.items() if g == "formats"} == {
        "surfaces/pdf/en", "surfaces/pdf/ar", "surfaces/excel",
    }
    assert "report-card--primary" in script
    # The page's own language leads: the module reorders rather than hardcoding English first.
    assert "language" in script.split("report-card--primary")[0]


def test_the_group_headings_name_an_affordance_and_no_figure() -> None:
    """`RRA-010` admits copy that names an affordance; a heading carrying a figure has left it."""
    for language in ("en", "ar"):
        for key in ("report_and_evidence", "other_formats"):
            wording = JOURNEY_COPY[language][key]
            assert wording.strip(), f"{language}.{key} is empty"
            figure = re.search(r"[0-9%$€£]|[\u0660-\u0669]", wording)
            assert figure is None, f"{language}.{key} carries a figure"
