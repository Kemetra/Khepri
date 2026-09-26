"""The bilingual wording every cross-version refusal and caveat owes.

`RRA-008` §Refusals and caveats freezes the complete set of causes this family
introduces and requires each carry "its complete customer wording in **both
Arabic and English in the same code slice that raises it**". `#400` declined to
put those strings in the specification, because no specification in this
repository holds customer copy -- and named this slice as where they belong.

**Parity is asserted against the frozen cause set, not against itself.** Two
language tables compared only to each other both pass when a cause is absent
from both, which is why the coverage test iterates the causes `C1-02` and
`C1-03` actually raise and demands an entry for each. `#402`'s own predicates
are the source of truth here.

**No figure enters a refusal.** `RCA-005` `FR-131` requires that a refused pair
show "no partial, indicative, or best-effort figure", and `FR-133` that the
audit event carry no figure, delta, version name or refusal detail. A refusal
string that interpolated a value would defeat both, so the wording is static
and the test proves it.
"""

from __future__ import annotations

import pytest

from khepri.rra.analysis import compatibility, dataset_period
from khepri.rra.analysis.comparison_narrative import (
    CROSSVERSION_CAVEATS,
    CROSSVERSION_REFUSALS,
    refusal_wording,
)
from khepri.rra.analysis.compatibility import (
    CAUSE_BASIS,
    CAUSE_FORMULA_DRIFT,
    CAUSE_MAPPING_DRIFT,
    CAUSE_PACKAGE_DRIFT,
    CAUSE_SCOPE,
    CAUSE_STORE_SET,
)
from khepri.rra.analysis.dataset_period import (
    CAUSE_GRANULARITY,
    CAUSE_INCOMPLETE,
    CAUSE_RETAIL_DAY,
    CAUSE_UNORDERED_PAIR,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES

#: Every cause the family raises, taken from the modules that raise them rather
#: than retyped. A retyped list would drift silently from the frozen set.
ALL_CAUSES = (
    CAUSE_SCOPE,
    CAUSE_MAPPING_DRIFT,
    CAUSE_FORMULA_DRIFT,
    CAUSE_PACKAGE_DRIFT,
    CAUSE_BASIS,
    CAUSE_STORE_SET,
    CAUSE_GRANULARITY,
    CAUSE_RETAIL_DAY,
    CAUSE_INCOMPLETE,
    CAUSE_UNORDERED_PAIR,
)


def _raised_causes() -> frozenset[str]:
    """Every cause the raising modules export, read from their `__all__`.

    A set, because `CAUSE_CURRENCY` and `CAUSE_FILTERS` alias `CAUSE_BASIS`.
    """
    return frozenset(
        getattr(module, name)
        for module in (compatibility, dataset_period)
        for name in module.__all__
        if name.startswith("CAUSE_")
    )


RAISED_CAUSES = tuple(sorted(_raised_causes()))

#: `RRA-009` §Refusals part 3, stated on every whole-response refusal (`#532` A-28).
REST_STANDS = {
    LANGUAGE_ENGLISH: "Neither period's own report is affected.",
    LANGUAGE_ARABIC: "لا يتأثر تقرير أي من الفترتين.",
}

#: `RRA-009` §Refusals part 4 for the one cause whose evidence the text did not
#: name. The refusal carries no period, and `FR-131`/`FR-133` keep the wording
#: static, so it names the missing evidence without naming which period. It must
#: also hold where `crossversion_assembly` raises this cause for two packages that
#: share no measured figure.
INCOMPLETE_EVIDENCE = {
    LANGUAGE_ENGLISH: (
        "What is missing is a complete record: one of the two datasets does not "
        "cover its whole period, or does not record the same figures as the other."
    ),
    LANGUAGE_ARABIC: (
        "الناقص هو سجل مكتمل: إحدى المجموعتين لا تغطي فترتها كاملة، أو لا تسجل "
        "الأرقام نفسها التي تسجلها الأخرى."
    ),
}

#: `RRA-009` §Refusals part 1: which business analysis was unavailable, named as
#: a capability. Every cross-version refusal opens with it (`#560` item 7).
PART_ONE = {
    LANGUAGE_ENGLISH: "The comparison between these two datasets is not available.",
    LANGUAGE_ARABIC: "المقارنة بين مجموعتي البيانات هاتين غير متاحة.",
}

#: Part 5 for the two causes that ended on part 3, and part 4 for `CAUSE_SCOPE`,
#: which named no field. Committed literals, so what merges is what was approved.
APPROVED_SENTENCES = {
    CAUSE_STORE_SET: {
        LANGUAGE_ENGLISH: "Compare two datasets covering the same stores.",
        LANGUAGE_ARABIC: "قارن مجموعتي بيانات تغطيان المتاجر نفسها.",
    },
    CAUSE_GRANULARITY: {
        LANGUAGE_ENGLISH: (
            "Compare two datasets stated at the same granularity, both by day or "
            "both by month."
        ),
        LANGUAGE_ARABIC: (
            "قارن مجموعتي بيانات مذكورتين بالدقة نفسها، كلتاهما باليوم أو كلتاهما "
            "بالشهر."
        ),
    },
    CAUSE_SCOPE: {
        LANGUAGE_ENGLISH: (
            "What decides the scope is the Store or branch column: both datasets "
            "must list the same stores, or both must state one aggregate."
        ),
        LANGUAGE_ARABIC: (
            "ما يحدد النطاق هو عمود المتجر أو الفرع: يجب أن تذكر المجموعتان المتاجر "
            "نفسها، أو أن تذكر كلتاهما مستوى إجماليًا واحدًا."
        ),
    },
}


class TestRefusalParts:
    """`RRA-009` §Refusals: why, whether the rest stands, what is missing, how."""

    def test_the_raised_set_is_the_worded_set(self) -> None:
        """An empty derivation would skip every case below green."""
        assert len(RAISED_CAUSES) == 10
        assert set(RAISED_CAUSES) == set(CROSSVERSION_REFUSALS)

    @pytest.mark.parametrize("cause", RAISED_CAUSES)
    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_every_refusal_states_that_the_rest_stands(
        self, cause: str, language: str
    ) -> None:
        assert REST_STANDS[language] in CROSSVERSION_REFUSALS[cause][language]

    @pytest.mark.parametrize("cause", RAISED_CAUSES)
    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_the_rest_stands_follows_the_why_and_precedes_the_remedy(
        self, cause: str, language: str
    ) -> None:
        text = CROSSVERSION_REFUSALS[cause][language]
        sentence = REST_STANDS[language]

        assert not text.startswith(sentence)
        assert not text.endswith(sentence), "part 3 is never the last part"

    @pytest.mark.parametrize("cause", RAISED_CAUSES)
    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_every_refusal_opens_by_naming_the_unavailable_analysis(
        self, cause: str, language: str
    ) -> None:
        assert CROSSVERSION_REFUSALS[cause][language].startswith(PART_ONE[language])

    @pytest.mark.parametrize("cause", sorted(APPROVED_SENTENCES))
    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_the_approved_sentence_follows_part_three(self, cause: str, language: str) -> None:
        text = CROSSVERSION_REFUSALS[cause][language]
        approved = APPROVED_SENTENCES[cause][language]

        assert approved in text
        assert text.index(REST_STANDS[language]) < text.index(approved)

    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_incomplete_coverage_names_the_missing_evidence_after_part_three(
        self, language: str
    ) -> None:
        text = CROSSVERSION_REFUSALS[CAUSE_INCOMPLETE][language]

        assert INCOMPLETE_EVIDENCE[language] in text
        assert text.index(REST_STANDS[language]) < text.index(
            INCOMPLETE_EVIDENCE[language]
        )


class TestCoverage:
    """Asserted against the emitted cause set, never table against table."""

    @pytest.mark.parametrize("cause", ALL_CAUSES)
    def test_every_cause_has_wording(self, cause: str) -> None:
        assert cause in CROSSVERSION_REFUSALS

    @pytest.mark.parametrize("cause", ALL_CAUSES)
    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_every_cause_has_both_languages(self, cause: str, language: str) -> None:
        assert CROSSVERSION_REFUSALS[cause][language].strip()

    def test_no_cause_is_worded_that_the_family_cannot_raise(self) -> None:
        """The set is frozen, so a wording with no cause is a wording for nothing."""
        assert set(CROSSVERSION_REFUSALS) == set(ALL_CAUSES)


class TestBothLanguagesAreReal:
    @pytest.mark.parametrize("cause", ALL_CAUSES)
    def test_arabic_is_arabic_script(self, cause: str) -> None:
        """An English string copied into the Arabic slot passes a parity check."""
        arabic = CROSSVERSION_REFUSALS[cause][LANGUAGE_ARABIC]

        assert any("؀" <= character <= "ۿ" for character in arabic)

    @pytest.mark.parametrize("cause", ALL_CAUSES)
    def test_english_carries_no_arabic_script(self, cause: str) -> None:
        english = CROSSVERSION_REFUSALS[cause][LANGUAGE_ENGLISH]

        assert not any("؀" <= character <= "ۿ" for character in english)

    @pytest.mark.parametrize("cause", ALL_CAUSES)
    def test_the_two_languages_differ(self, cause: str) -> None:
        wording = CROSSVERSION_REFUSALS[cause]

        assert wording[LANGUAGE_ARABIC] != wording[LANGUAGE_ENGLISH]


class TestNoFigureLeaks:
    """`FR-131`: a refused pair shows no partial or indicative figure."""

    @pytest.mark.parametrize("cause", ALL_CAUSES)
    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_wording_has_no_interpolation_placeholder(self, cause: str, language: str) -> None:
        text = CROSSVERSION_REFUSALS[cause][language]

        assert "{" not in text
        assert "%" not in text

    @pytest.mark.parametrize("cause", ALL_CAUSES)
    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_wording_carries_no_digit(self, cause: str, language: str) -> None:
        """No figure, and no version name either -- `FR-133`'s rule."""
        text = CROSSVERSION_REFUSALS[cause][language]

        assert not any(character.isdigit() for character in text)


class TestLookup:
    def test_returns_both_languages_for_a_known_cause(self) -> None:
        wording = refusal_wording(CAUSE_MAPPING_DRIFT)

        assert set(wording) == set(REQUIRED_LANGUAGES)

    def test_an_unknown_cause_raises(self) -> None:
        """Fail closed: an unworded cause must not reach a customer silently."""
        with pytest.raises(KeyError):
            refusal_wording("not a governed cause")


class TestCaveats:
    def test_the_admitted_pair_carries_a_caveat_in_both_languages(self) -> None:
        """A cross-version comparison is not a period comparison, and says so."""
        for language in REQUIRED_LANGUAGES:
            assert CROSSVERSION_CAVEATS[language].strip()

    def test_the_caveat_languages_differ(self) -> None:
        assert CROSSVERSION_CAVEATS[LANGUAGE_ARABIC] != CROSSVERSION_CAVEATS[LANGUAGE_ENGLISH]

    def test_the_arabic_caveat_is_wholly_arabic(self) -> None:
        """Every word, not merely some of it.

        Mutation testing was instructive here twice over. A mutant replacing one
        line of the three-line Arabic caveat with English **survived** -- and the
        first reading was that the test was weak. It was not: the string was
        still mostly Arabic, so a script check over the whole string correctly
        passed. The mutant had not implemented the defect.

        Replacing the *whole* string did fail. But a partly translated caveat is
        a real shipping hazard, so this asserts the absence of Latin letters
        rather than the presence of Arabic ones: "any Arabic character" passes
        for a string that is nine-tenths English, while "no Latin letter" fails
        on the first English word. A first attempt split on an Arabic comma and
        missed a substituted clause that carried none.
        """
        arabic = CROSSVERSION_CAVEATS[LANGUAGE_ARABIC]
        latin = [character for character in arabic if "a" <= character.lower() <= "z"]

        assert latin == []

    @pytest.mark.parametrize("cause", ALL_CAUSES)
    def test_no_refusal_mixes_an_english_clause_into_the_arabic(self, cause: str) -> None:
        """The same per-clause rule for every refusal string."""
        arabic = CROSSVERSION_REFUSALS[cause][LANGUAGE_ARABIC]
        latin = [character for character in arabic if "a" <= character.lower() <= "z"]

        assert latin == []
