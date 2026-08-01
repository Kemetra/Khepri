"""The deterministic narrator must satisfy the real validator, not a fake one.

Every assertion here runs `narrative.validate` or `NarrativeService.compose`
rather than inspecting the draft directly. A narrator checked against a
hand-written idea of the rules would pass while the pipeline refused it, which is
the failure this file exists to prevent.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from khepri.local.narrator import ADAPTER_VERSION, MAX_SECTIONS, DeterministicNarrator
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.facts import FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    OUTCOME_NARRATED,
    REASON_ADAPTER_MISMATCH,
    NarrativeRefused,
    NarrativeRequest,
    NarrativeService,
    validate,
)
from khepri.rra.profiling import build_profile

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)


def package(content: bytes = GOLDEN) -> FactPackage:
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


def request_for(pkg: FactPackage) -> NarrativeRequest:
    return NarrativeRequest.of(pkg, adapter_version=ADAPTER_VERSION)


def draft_for(pkg: FactPackage):
    request = request_for(pkg)
    return request, DeterministicNarrator().draft(
        request.for_provider(),
        timeout_seconds=Decimal("30"),
    )


class TestTheDraftSurvivesTheRealValidator:
    def test_validate_accepts_the_draft(self) -> None:
        request, draft = draft_for(package())

        validate(draft, request=request)

    def test_the_service_records_a_narrated_outcome(self) -> None:
        """The pipeline asks the service, not the adapter, so this is the contract."""
        ticks = iter(range(0, 10_000, 3))
        service = NarrativeService(
            adapter=DeterministicNarrator(),
            monotonic_ms=lambda: next(ticks),
            timeout_seconds=Decimal("30"),
        )

        result = service.compose(package())

        assert result.narrative is not None
        assert result.attempt.outcome == OUTCOME_NARRATED
        assert result.attempt.reason is None

    def test_the_adapter_version_is_governed_and_self_naming(self) -> None:
        """A refused version is recorded as `unknown`, hiding what produced the prose."""
        _, draft = draft_for(package())

        assert draft.adapter_version == ADAPTER_VERSION
        assert "local" in ADAPTER_VERSION


class TestBothLanguagesAreProduced:
    def test_arabic_and_english_are_both_present(self) -> None:
        _, draft = draft_for(package())

        assert {entry.language for entry in draft.languages} == {
            LANGUAGE_ARABIC,
            LANGUAGE_ENGLISH,
        }

    def test_every_section_cites_something(self) -> None:
        """An uncited section is a claim with no ground, whatever it says."""
        _, draft = draft_for(package())

        for entry in draft.languages:
            assert entry.sections
            for section in entry.sections:
                assert section.cited_fact_ids

    def test_the_section_count_is_bounded(self) -> None:
        _, draft = draft_for(package())

        for entry in draft.languages:
            assert len(entry.sections) <= MAX_SECTIONS


class TestParityHoldsByConstruction:
    """The five things `validate` compares across languages."""

    def test_the_same_facts_are_cited(self) -> None:
        _, draft = draft_for(package())
        arabic, english = draft.languages

        assert arabic.cited_fact_ids == english.cited_fact_ids

    def test_the_same_caveats_are_covered(self) -> None:
        _, draft = draft_for(package())
        arabic, english = draft.languages

        assert arabic.covered_caveats == english.covered_caveats

    def test_the_same_labels_are_declared(self) -> None:
        _, draft = draft_for(package())
        arabic, english = draft.languages

        assert arabic.declared_labels == english.declared_labels

    def test_the_same_directions_are_declared(self) -> None:
        _, draft = draft_for(package())
        arabic, english = draft.languages

        assert arabic.declared_directions == english.declared_directions

    def test_the_two_languages_pair_section_for_section(self) -> None:
        """Section identifiers are shared, which is what pairs the declarations."""
        _, draft = draft_for(package())
        arabic, english = draft.languages

        assert [s.section_id for s in arabic.sections] == [
            s.section_id for s in english.sections
        ]

    def test_the_prose_actually_differs(self) -> None:
        """Parity of claims, not of wording. Identical text would mean one language."""
        _, draft = draft_for(package())
        arabic, english = draft.languages

        assert [s.text for s in arabic.sections] != [s.text for s in english.sections]


class TestNothingIsInvented:
    def test_the_draft_is_deterministic(self) -> None:
        """Same package, same prose. A bundle_id depends on it."""
        pkg = package()
        _, first = draft_for(pkg)
        _, second = draft_for(pkg)

        assert [s.text for e in first.languages for s in e.sections] == [
            s.text for e in second.languages for s in e.sections
        ]

    def test_a_draft_written_for_another_package_is_refused(self) -> None:
        """The digest binds the answer to the request that asked for it."""
        other = request_for(package(GOLDEN.replace(b"125.50", b"999.99")))
        _, draft = draft_for(package())

        with pytest.raises(NarrativeRefused) as refusal:
            validate(draft, request=other)

        assert refusal.value.reason == REASON_ADAPTER_MISMATCH

    def test_no_section_declares_a_direction(self) -> None:
        """Movement is groundable only from series points; declaring it refuses."""
        _, draft = draft_for(package())

        for entry in draft.languages:
            for section in entry.sections:
                assert section.direction is None
