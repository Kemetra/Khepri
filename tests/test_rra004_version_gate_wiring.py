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
from tests.rra003_contract_fixtures import TEST_CONTRACT


def test_building_a_package_refuses_an_unadmitted_triple() -> None:
    """A moved mapping against an unmoved package refuses the package.

    Driven through `build_fact_package` rather than through the gate function,
    because calling the gate directly proves only that the gate works. It cannot
    fail when the builder stops consulting it -- and a first draft of this test
    did exactly that: deleting the call from `_build` left it green.

    **The mapping is moved on the mapping, not on the module.** An earlier form
    of this test patched `facts.MAPPING_VERSION`, which was the only way to
    simulate a moved mapping while `_build` read that global instead of the
    version on the object it was handed. It now reads the object, so the moved
    version travels the real data path and no patching is required.
    """
    from khepri.rra import facts

    with pytest.raises(facts.FactsRefused) as refused:
        _package_with_two_settled_periods(mapping_version="rra003.mapping.v3")

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


def _package_from(
    header: str,
    rows: list[tuple[str, ...]],
    *,
    mapping_version: str | None = None,
) -> object:
    """One governed package over four consecutive days of the given columns.

    Both fixtures below want the same thing with one column's difference, and
    writing the pipeline out twice is how a later reader ends up fixing one copy.
    """
    import hashlib
    from dataclasses import replace
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
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    if mapping_version is not None:
        mapping = replace(mapping, mapping_version=mapping_version)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
        contract=TEST_CONTRACT,
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


def _package_with_two_settled_periods(
    *,
    mapping_version: str | None = None,
) -> object:
    """Four consecutive days, which leaves two settled periods to compare.

    `mapping_version` restamps the mapping before the package is built, which is
    how a caller moves one version ahead of its consumers without patching a
    module global.
    """
    return _package_from(
        "date,revenue,units,invoice_no",
        [("50.00", "5"), ("100.00", "10"), ("180.00", "12"), ("60.00", "6")],
        mapping_version=mapping_version,
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
    a token one section's refusal will print verbatim. A page assertion would
    only cover whichever section the fixture happened to refuse.

    **Descends to the messages, and that is the whole point of the case.** The
    first version stopped one level short. Once the mapping gained its section
    level, `prose` was a `dict`, so `"{" not in prose` was no longer a substring
    search -- it was a key lookup for a key named `{`, which no mapping has. The
    test written to catch the placeholder leak could not catch it: replacing
    every message with a literal `LEAK {section} LEAK` left it green.
    """
    from khepri.rra.rendering.html import _CHROME

    checked = 0
    for language, chrome in _CHROME.items():
        for section, by_reason in chrome["refusal_prose"].items():
            for reason, prose in by_reason.items():
                assert "{" not in prose, (
                    f"{language}/{section}/{reason} reaches the template with an "
                    "unfilled placeholder"
                )
                checked += 1

    # The mapping is built by comprehension over `ORDERED_SECTIONS`, so an empty or renamed
    # source would make every loop body above unreachable and pass this case a second, different
    # vacuous way.
    assert checked, "the chrome mapping handed the template no refusal prose at all"


class TestTheInternalPackageRefusalStaysInternal:
    """`RRA-009` tiers `package_version_pairing_unadmitted` Internal, and that is a claim.

    The justification it shipped with -- "it fires while a package is being built, so no report is
    published and no customer can encounter it" -- is true of the report, and silently assumed the
    report was the only surface. It is not. `build_session_package` catches `FactsRefused` and
    re-raises it as `PackageRefused(str(error))`, and both `409` handlers in `api` answered with
    `str(error)`, so `POST /api/v1/beta/facts` returned the governed reason code and all three
    internal version identifiers to the caller:

        package_version_pairing_unadmitted: rra003.mapping.v3, rra004.package.v2 and
        rra004.formula.v1 were not authorized to be combined.

    A tier is a claim about every path the text can travel. These cases assert the claim on the
    path that falsified it.
    """

    def test_the_reason_does_not_reach_the_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Driven through the route, because the route is where the text escaped.

        Asserts the *absence* of the code and the three identifiers rather than an exact phrase:
        what matters is what escapes, and freezing the replacement wording would make this case
        fail on a rewording that leaks nothing.
        """
        from khepri.rra import mapping
        from tests.test_rra004_packages import prepared

        # Patched where `build_mapping` *stamps* the version, because the route
        # builds its own mapping internally and there is no object to restamp.
        # `facts` no longer reads a module global -- it reads the version on the
        # mapping it is handed -- so moving the stamp is what moves the mapping.
        monkeypatch.setattr(mapping, "MAPPING_VERSION", "rra003.mapping.v3")
        response = prepared().client.post("/api/v1/beta/facts")
        detail = response.json()["detail"]

        assert response.status_code == 409
        assert REASON_PACKAGE_VERSION_UNADMITTED not in detail
        for identifier in ("rra003.mapping.v3", "rra004.package.v2", "rra004.formula.v1"):
            assert identifier not in detail, identifier

    def test_a_refusal_written_for_the_caller_still_reaches_them(self) -> None:
        """The guard is selective, and a blanket one would be a different defect.

        Most `PackageRefused` text is the only account a caller gets of what to fix -- a stored
        profile that no longer describes the input, a package published under a superseded
        version. Replacing all of it would trade a leak for a dead end. Without this case, a
        mutant that always answers `PACKAGE_UNAVAILABLE` survives.
        """
        from khepri.rra.packages import (
            PACKAGE_UNAVAILABLE,
            PackageRefused,
            package_refused_detail,
        )

        written_for_the_caller = "Stored profile does not describe the current governed input."

        assert (
            package_refused_detail(PackageRefused(written_for_the_caller))
            == written_for_the_caller
        )
        assert (
            package_refused_detail(
                PackageRefused(f"{REASON_PACKAGE_VERSION_UNADMITTED}: a, b and c")
            )
            == PACKAGE_UNAVAILABLE
        )

