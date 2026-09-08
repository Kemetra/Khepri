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
