"""The version gate, on the paths that actually publish.

`tests/test_rra004_version_compatibility.py` proves the tables answer correctly.
This module proves something the tables cannot prove about themselves: that
publication consults them. A predicate nothing calls refuses nothing, and the
skew it was written to catch reaches a reader as a plausible number under an
identity that did not produce it.

**Two seams, refused at different scopes, and the difference is load-bearing.**

A mapping/package/formula mismatch is caught while the package is built, so it
refuses the package: no report exists, and `RRA-009` classifies that reason as
Internal because no customer can encounter it.

A family/formula mismatch must refuse only its own family. `RRA-008` requires
that "a failure or missing optional input refuses only dependent results,
leaving independently answerable facts and the rest of the report intact", and
the mission's shrinking refusing set is only meaningful if families refuse one
at a time. Raising the package refusal for a family pairing would black out
every independently answerable result until the last family merged.

**Why these tests patch a version constant rather than a table entry.** Emptying
the table would prove only that an empty table refuses everything. Moving one
version is the defect in the field: a slice lands, one identifier advances, and
its consumers have not caught up yet.
"""

from __future__ import annotations

import pytest

from khepri.rra.versions import (
    REASON_FAMILY_VERSION_UNADMITTED,
    REASON_PACKAGE_VERSION_UNADMITTED,
)


def test_building_a_package_refuses_an_unadmitted_triple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A moved mapping against an unmoved package refuses the package.

    Driven through `build_fact_package` rather than through the gate function,
    because calling the gate directly proves only that the gate works. It cannot
    fail when the builder stops consulting it -- and a first draft of this test
    did exactly that: deleting the call from `_build` left it green.
    """
    from khepri.rra import facts

    monkeypatch.setattr(facts, "MAPPING_VERSION", "rra003.mapping.v3")

    with pytest.raises(facts.FactsRefused) as refused:
        _package_with_two_settled_periods()

    assert REASON_PACKAGE_VERSION_UNADMITTED in str(refused.value)


def test_building_a_package_admits_the_shipped_triple() -> None:
    """The versions this build publishes must pass its own gate.

    Without this the refusal above would pass against a gate that refused
    everything, and the product would refuse all of its own output.
    """
    package = _package_with_two_settled_periods()

    assert package.facts


def test_a_family_on_an_unadmitted_formula_refuses_only_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of the family seam: the report survives.

    Growth is moved to a successor its formula does not admit. Growth refuses
    with the governed reason, and comparison -- which did not move -- still
    publishes. A package-level refusal here would return nothing at all.
    """
    from khepri.rra import bundle
    from khepri.rra.analysis import growth

    monkeypatch.setattr(growth, "GROWTH_FORMULA_VERSION", "rra008.growth.v2")

    package = _package_with_two_settled_periods()
    analysed = bundle._analysed(package)

    assert analysed.refusals.get(bundle.SECTION_GROWTH) == (
        REASON_FAMILY_VERSION_UNADMITTED
    )
    assert any(
        figure.section == bundle.SECTION_COMPARISON for figure in analysed.figures
    ), "comparison did not move, so it must still publish"


def test_the_concentration_curve_does_not_escape_its_family_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The curve is appended outside the family loop, so `continue` misses it.

    `_analysed` extends its figures with `_curve_figures(package)` after the
    loop, and `curve_series` stamps the family's own version. Skipping
    `concentration.derive` therefore refused the section while the curve was
    still published under the unadmitted pairing -- and `_section` reads present
    figures as a present section, discarding the recorded refusal.

    Asserting on the figures rather than on the refusal is what makes this test
    able to fail: the refusal was already being recorded correctly while the
    output escaped anyway.
    """
    from khepri.rra import bundle
    from khepri.rra.analysis import concentration

    monkeypatch.setattr(
        concentration,
        "CONCENTRATION_FORMULA_VERSION",
        "rra008.concentration.v2",
    )

    analysed = bundle._analysed(_package_with_a_concentration_curve())

    assert not [
        figure
        for figure in analysed.figures
        if figure.section == bundle.SECTION_CONCENTRATION
    ], "no concentration figure may publish under an unadmitted pairing"
    assert analysed.refusals.get(bundle.SECTION_CONCENTRATION) == (
        REASON_FAMILY_VERSION_UNADMITTED
    )


def test_the_concentration_curve_publishes_on_the_shipped_pairing() -> None:
    """Keeps the previous test honest: the curve is normally there to lose."""
    from khepri.rra import bundle

    analysed = bundle._analysed(_package_with_a_concentration_curve())

    assert [
        figure
        for figure in analysed.figures
        if figure.section == bundle.SECTION_CONCENTRATION
    ]


def _package_from(header: str, rows: list[tuple[str, ...]]) -> object:
    """One governed package over four consecutive days of the given columns.

    Both fixtures below want the same thing with one column's difference, and
    writing the pipeline out twice is how a later reader ends up fixing one copy.
    """
    import hashlib
    from datetime import date, timedelta

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.facts import build_fact_package
    from khepri.rra.intake import CSV_MEDIA_TYPE
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    start = date(2026, 1, 5)
    lines = [
        ",".join(((start + timedelta(days=index)).isoformat(), *row, f"INV-{index}"))
        for index, row in enumerate(rows)
    ]
    content = "\n".join([header, *lines]).encode() + b"\n"
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
    )


def _package_with_a_concentration_curve() -> object:
    """Rows over a product dimension, so concentration has a set to rank."""
    return _package_from(
        "date,revenue,units,product,invoice_no",
        [
            ("50.00", "5", "Aspirin"),
            ("100.00", "10", "Bandage"),
            ("180.00", "12", "Cough Syrup"),
            ("60.00", "6", "Dressing"),
        ],
    )


def _package_with_two_settled_periods() -> object:
    """Four consecutive days, which leaves two settled periods to compare."""
    return _package_from(
        "date,revenue,units,invoice_no",
        [("50.00", "5"), ("100.00", "10"), ("180.00", "12"), ("60.00", "6")],
    )


def test_the_version_refusal_names_which_analysis_is_unavailable() -> None:
    """`RRA-009` requires a refusal to name the unavailable capability.

    Every other section reason belongs to one family and so names itself. This
    one is shared by all four, and the Excel limitations sheet writes the
    message with no heading beside it -- so "this analysis" left a reader unable
    to tell which of comparison, concentration, growth or basket was missing,
    and two mismatches produced two identical lines.
    """
    from khepri.rra.bundle import (
        SECTION_BASKET,
        SECTION_COMPARISON,
        SECTION_CONCENTRATION,
        SECTION_GROWTH,
    )
    from khepri.rra.rendering.wording import (
        LANGUAGE_ARABIC,
        LANGUAGE_ENGLISH,
        SECTION_HEADINGS,
        refusal_message,
    )

    sections = (
        SECTION_COMPARISON,
        SECTION_CONCENTRATION,
        SECTION_GROWTH,
        SECTION_BASKET,
    )
    for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH):
        template = refusal_message(
            REASON_FAMILY_VERSION_UNADMITTED,
            context="section",
            language=language,
        )
        rendered = {
            template.format(section=SECTION_HEADINGS[language][section])
            for section in sections
        }
        assert len(rendered) == len(sections), (
            "each family's refusal must read differently from the others"
        )
        for section in sections:
            assert SECTION_HEADINGS[language][section] in template.format(
                section=SECTION_HEADINGS[language][section]
            )


def test_no_surface_renders_the_section_placeholder_literally() -> None:
    """A placeholder nobody fills is an internal token on a customer page.

    `caveat_prose` carries a section-tier refusal travelling as a scoped
    disclosure, and its section branch returned the template unfilled. The
    HTML surface renders exactly that string, so `{section}` would have reached
    a reader.
    """
    from khepri.rra.bundle import SECTION_GROWTH
    from khepri.rra.rendering.wording import (
        LANGUAGE_ARABIC,
        LANGUAGE_ENGLISH,
        caveat_prose,
    )

    code = f"{SECTION_GROWTH}:{REASON_FAMILY_VERSION_UNADMITTED}"
    for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH):
        assert "{" not in caveat_prose(code, language)


def test_no_chrome_hands_a_template_an_unfilled_placeholder() -> None:
    """The web and print surfaces are a third rendering path, and it leaked.

    `html` passes `REFUSAL_WORDING["section"]` into the template as
    `chrome.refusal_prose`, and `report.html.j2` indexes it by reason and prints
    the value. Filling the placeholder in `wording` and in the workbook left this
    one untouched, so a refused family put a literal `{section}` on the page and
    in the PDF that extends the same template.

    Asserted over the chrome mapping rather than a rendered page because that
    mapping is what the template is handed: any entry still carrying a brace is
    a token one section's refusal will print verbatim.
    """
    from khepri.rra.rendering.html import _CHROME

    for language, chrome in _CHROME.items():
        assert language
        for reason, prose in chrome["refusal_prose"].items():
            assert "{" not in prose, (
                f"{reason} reaches the template with an unfilled placeholder"
            )
