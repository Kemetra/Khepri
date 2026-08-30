"""`T1-08`: the evidence projection the catalog routes must answer from.

Characterization of `build_context(...)["audit"]` -- the object the evidence
template renders and the catalog route reads. Every expectation comes from the
already-shipped rendering path, which this slice does not write, so these hold
the catalog to a surface it did not author.

The HTTP boundary is `test_rra011_catalog_routes.py`. The two modules are split
because they share no fixture and answer different questions: this one measures
a projection, that one drives a route.

Written flat, one question per test and no helper pyramid, because extracting
shared setup raises the module's complexity mean and every new file is held to a
CodeScene score of 10.00.
"""

from __future__ import annotations

from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering.html import build_cells, build_context
from tests.test_rra006_html_sections import ROWS, package_for

LANGUAGES = ("en", "ar")


def test_the_audit_region_names_no_fact_identifier() -> None:
    """Why the evidence route is keyed on a citation rather than a fact.

    `_identity` (`facts.py:2211`) derives `fct_<digest[:24]>` and
    `cit_<digest[:12]>` from one digest, so the two are different strings for the
    same fact. `FigureCell` carries the citation and deliberately drops the fact
    identifier, so no `fact_id` reaches the audit region at all.

    A route keyed on `fact_id` could therefore only answer by reading
    `bundle.figures` itself -- a second projection assembled from the bundle,
    which `RRA-011` forbids in the same sentence that requires exactly one. This
    test pins the reason so a later slice cannot "helpfully" add the field back.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    cells = build_cells(bundle, "en")

    audit = build_context(bundle, "en", cells)["audit"]

    assert {figure.fact_id for figure in bundle.figures}
    assert not any(hasattr(cell, "fact_id") for cell in audit["figures"])


def test_one_citation_answers_for_every_cell_that_quotes_it() -> None:
    """A series has one citation and many cells, so evidence groups rather than pairs.

    Measured rather than assumed: the shared fixture renders 49 figures over 22
    citations. An evidence surface that assumed one cell per citation would answer
    for the first and silently drop the rest.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    cells = build_cells(bundle, "en")

    citations = {cell.citation_id for cell in cells}

    assert len(cells) > len(citations)
    assert citations == set(build_context(bundle, "en", cells)["audit"]["citations"])


def test_every_cell_carries_a_citation_the_audit_region_lists() -> None:
    """No figure is displayed whose evidence path the audit region omits.

    This is the `T1-08` acceptance clause -- "every displayed figure has one
    definition and evidence path" -- read against the citation half.
    """
    for language in LANGUAGES:
        bundle = ReportBundle.of(package_for(ROWS, published=True))
        cells = build_cells(bundle, language)
        audit = build_context(bundle, language, cells)["audit"]

        listed = set(audit["citations"])

        assert listed
        assert all(cell.citation_id in listed for cell in cells)


def test_the_audit_region_states_a_reason_for_every_refused_section() -> None:
    """A refused section is the one carrying a reason, never the one carrying a state.

    `Section.state` is Internal tier and reaches no customer surface, so the audit
    region identifies refusal by `reason is not None`. The catalog must classify
    the same way or the two surfaces disagree about which analyses were answered.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=False))
    cells = build_cells(bundle, "en")

    audit = build_context(bundle, "en", cells)["audit"]

    refused = [entry for entry in audit["sections"] if entry["reason"] is not None]

    assert refused
    assert all(set(entry) == {"section_id", "reason"} for entry in audit["sections"])


def test_the_audit_region_carries_no_internal_tier_field() -> None:
    """`state` and `narrative_state` are Internal and appear on no catalog surface.

    Asserted against the projection itself rather than a response model, so it
    holds for every surface reading it -- including the ones this slice adds.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    cells = build_cells(bundle, "en")

    audit = build_context(bundle, "en", cells)["audit"]

    assert "narrative_state" not in audit
    assert all("state" not in entry for entry in audit["sections"])


