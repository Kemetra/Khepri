from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.facts import FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    NARRATIVE_VERSION,
    OUTCOME_NARRATED,
    OUTCOME_REFUSED,
    REASON_ADAPTER_MISMATCH,
    REASON_CAVEAT_COVERAGE_DIFFERS,
    REASON_EMPTY_NARRATIVE,
    REASON_FACT_COVERAGE_DIFFERS,
    REASON_MISSING_LANGUAGE,
    REASON_PROVIDER_FAILED,
    REASON_PROVIDER_REFUSED,
    REASON_PROVIDER_TIMEOUT,
    REASON_UNCITED_SECTION,
    REASON_UNGROUNDED_NUMBER,
    REASON_UNKNOWN_CAVEAT,
    REASON_UNKNOWN_CITATION,
    REASON_UNKNOWN_LANGUAGE,
    REASON_UNSAFE_TEXT,
    LanguageNarrative,
    NarrativeDraft,
    NarrativeGround,
    NarrativeRefused,
    NarrativeRequest,
    NarrativeSection,
    NarrativeService,
    NarrativeUnavailable,
    ProviderRefused,
    validate,
)
from khepri.rra.profiling import build_profile, canonical_json

ADAPTER_VERSION = "test.adapter.v1"

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)

WITH_COST = (
    b"date,revenue,cost,units,invoice_no\n"
    b"2026-01-05,100.00,40.00,2,INV-1\n"
    b"2026-01-06,200.00,80.00,4,INV-2\n"
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


def request_for(content: bytes = GOLDEN) -> NarrativeRequest:
    return NarrativeRequest.of(package(content), adapter_version=ADAPTER_VERSION)


def section(
    text: str,
    *,
    cited: tuple[str, ...],
    caveats: tuple[str, ...] = (),
    section_id: str = "summary",
) -> NarrativeSection:
    return NarrativeSection(
        section_id=section_id,
        text=text,
        cited_fact_ids=cited,
        caveats=caveats,
    )


def draft(
    *,
    arabic: tuple[NarrativeSection, ...],
    english: tuple[NarrativeSection, ...],
    package_version: str | None = None,
    adapter_version: str = ADAPTER_VERSION,
) -> NarrativeDraft:
    return NarrativeDraft(
        adapter_version=adapter_version,
        package_version=package_version or package().package_version,
        languages=(
            LanguageNarrative(language=LANGUAGE_ARABIC, sections=arabic),
            LanguageNarrative(language=LANGUAGE_ENGLISH, sections=english),
        ),
    )


def revenue_fact_id(request: NarrativeRequest) -> str:
    entry = next(
        fact for fact in request.document["facts"] if fact["metric"] == "revenue"
    )
    return str(entry["fact_id"])


def grounded_draft(request: NarrativeRequest) -> NarrativeDraft:
    fact_id = revenue_fact_id(request)
    return draft(
        arabic=(section("بلغت الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
        english=(section("Revenue was 500.00.", cited=(fact_id,)),),
    )


class StubAdapter:
    def __init__(self, response: object) -> None:
        self._response = response
        self.requests: list[NarrativeRequest] = []

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    def draft(self, request: NarrativeRequest, *, timeout_seconds: Decimal) -> NarrativeDraft:
        self.requests.append(request)
        if isinstance(self._response, Exception):
            raise self._response
        if callable(self._response):
            return self._response(request)
        return self._response


def service(response: object, *, ticks: list[int] | None = None) -> NarrativeService:
    times = iter(ticks or [1000, 1250])
    return NarrativeService(
        adapter=StubAdapter(response),
        monotonic_ms=lambda: next(times),
    )


# --- request minimization -------------------------------------------------


def test_the_request_carries_only_the_fields_the_schema_names() -> None:
    document = request_for().document

    assert set(document) == {
        "narrative_version",
        "adapter_version",
        "package_version",
        "formula_version",
        "mapping_version",
        "languages",
        "monetary_precision",
        "facts",
        "series",
        "comparisons",
        "refusals",
        "caveats",
    }


def test_the_request_withholds_the_content_digests_the_package_carries() -> None:
    # They authenticate customer content rather than describe it, and a
    # narrative provider has no use for either.
    source = package().as_document()
    document = request_for().document

    assert "profile_digest" in source
    assert "source_sha256_hex" in source
    assert "profile_digest" not in document
    assert "source_sha256_hex" not in document
    assert "row_count" not in document


class _GrownPackage:
    """A package whose document carries a field the narrative schema never named.

    Asserting that today's raw column values are absent proves nothing: RRA-004
    already excludes them, so such a test passes whether or not this module
    filters anything. The claim worth testing is that a field the package gains
    *later* does not reach a provider by default.
    """

    def __init__(self, inner: FactPackage) -> None:
        self._inner = inner
        self.package_version = inner.package_version

    def as_document(self) -> dict:
        document = self._inner.as_document()
        document["raw_rows"] = [{"invoice_no": "INV-1", "revenue": "125.50"}]
        for fact in document["facts"]:
            fact["source_column"] = "invoice_no"
        for entry in document["series"]:
            for point in entry["points"]:
                point["source_value"] = "INV-1"
        return document


def test_a_field_the_package_gains_later_does_not_reach_the_provider() -> None:
    grown = _GrownPackage(package())
    assert "raw_rows" in grown.as_document()

    document = NarrativeRequest.of(grown, adapter_version=ADAPTER_VERSION).document

    serialized = canonical_json(document)
    assert "raw_rows" not in document
    assert "source_column" not in serialized
    assert "INV-1" not in serialized


def test_a_request_assembled_outside_the_projection_is_still_gated() -> None:
    from khepri.rra import narrative

    document = dict(request_for().document)
    document["operator_note"] = "internal"

    with pytest.raises(NarrativeRefused) as refusal:
        narrative._assert_minimal(document)

    assert refusal.value.reason == REASON_ADAPTER_MISMATCH


def test_comparison_bucket_labels_are_supplied_because_prose_needs_them() -> None:
    document = request_for().document

    comparison = next(
        entry for entry in document["comparisons"] if entry["dimension"] == "category"
    )
    labels = {bucket["label"] for bucket in comparison["buckets"]}
    assert labels == {"Beverages", "Snacks"}


def test_refusals_travel_with_the_request_so_gaps_can_be_narrated() -> None:
    document = request_for().document

    reasons = {entry["metric"]: entry["reason"] for entry in document["refusals"]}
    assert reasons["cost"] == "required_input_unavailable"


def test_a_ratio_is_supplied_as_a_percent_so_the_provider_never_converts() -> None:
    document = NarrativeRequest.of(
        package(WITH_COST), adapter_version=ADAPTER_VERSION
    ).document

    margin = next(
        entry for entry in document["facts"] if entry["metric"] == "gross_margin"
    )
    assert margin["value"] == "0.6000"
    assert margin["value_percent"] == "60.0000"


def test_a_monetary_fact_is_not_given_a_percent_rendering() -> None:
    revenue = next(
        entry for entry in request_for().document["facts"] if entry["metric"] == "revenue"
    )

    assert "value_percent" not in revenue


def test_both_languages_are_required_of_a_request() -> None:
    with pytest.raises(NarrativeRefused) as refusal:
        NarrativeRequest.of(
            package(),
            adapter_version=ADAPTER_VERSION,
            languages=(LANGUAGE_ENGLISH,),
        )

    assert refusal.value.reason == REASON_MISSING_LANGUAGE


def test_an_unsupported_language_is_refused_rather_than_dropped() -> None:
    with pytest.raises(NarrativeRefused) as refusal:
        NarrativeRequest.of(
            package(),
            adapter_version=ADAPTER_VERSION,
            languages=(LANGUAGE_ARABIC, LANGUAGE_ENGLISH, "fr"),
        )

    assert refusal.value.reason == REASON_UNKNOWN_LANGUAGE


# --- grounding vocabulary -------------------------------------------------


def test_the_ground_is_derived_from_the_request_that_was_sent() -> None:
    request = request_for()

    ground = NarrativeGround.of(request)

    assert revenue_fact_id(request) in ground.identifiers
    assert Decimal("500.00") in ground.stateable((revenue_fact_id(request),)).numbers
    assert "currency_not_declared" in ground.caveats


def test_a_fact_is_reachable_by_either_of_its_identifiers() -> None:
    # Which name a provider happens to cite must not decide what it may say.
    request = request_for()
    entry = next(
        fact for fact in request.document["facts"] if fact["metric"] == "revenue"
    )

    ground = NarrativeGround.of(request)

    assert ground.stateable((str(entry["fact_id"]),)) == ground.stateable(
        (str(entry["citation_id"]),)
    )


def test_a_number_belonging_to_a_fact_the_section_did_not_cite_is_refused() -> None:
    # Citing revenue and stating the units count produces a report that is
    # cited and wrong. The number exists in the package, which is why a single
    # pool of supplied numbers cannot answer the question a reader needs.
    request = request_for()

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ١١.", cited=(revenue_fact_id(request),)),),
                english=(section("Revenue was 11.", cited=(revenue_fact_id(request),)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_citing_both_facts_permits_stating_both_figures() -> None:
    request = request_for()
    revenue = revenue_fact_id(request)
    units = str(
        next(fact for fact in request.document["facts"] if fact["metric"] == "units")[
            "fact_id"
        ]
    )

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠٫٠٠ عبر ١١ وحدة.", cited=(revenue, units)),),
            english=(section("Revenue 500.00 over 11 units.", cited=(revenue, units)),),
        ),
        request=request,
    )


def test_a_sign_reverses_a_figure_and_is_not_grounded_by_its_positive() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات -٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(section("Revenue was -500.00.", cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_a_hyphen_between_digits_stays_a_separator() -> None:
    # Reading the hyphens in 2026-01-05 as signs would turn a supplied label
    # into a run of negative numbers nobody supplied.
    request = request_for()
    fact_id = str(request.document["series"][0]["fact_id"])

    validate(
        draft(
            arabic=(section("في 2026-01-05 ارتفعت المبيعات.", cited=(fact_id,)),),
            english=(section("On 2026-01-05 sales rose.", cited=(fact_id,)),),
        ),
        request=request,
    )


def test_a_duplicated_language_is_refused_before_it_can_be_collapsed() -> None:
    # A mapping keeps the last entry, so the earlier copy would go unvalidated
    # while the service still handed back the draft containing it.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            NarrativeDraft(
                adapter_version=ADAPTER_VERSION,
                package_version=request.package_version,
                languages=(
                    LanguageNarrative(
                        language=LANGUAGE_ARABIC,
                        sections=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                    ),
                    LanguageNarrative(
                        language=LANGUAGE_ENGLISH,
                        sections=(
                            section("Revenue 99999 =cmd|calc", cited=("fct_invented",)),
                        ),
                    ),
                    LanguageNarrative(
                        language=LANGUAGE_ENGLISH,
                        sections=(section("Revenue was 500.00.", cited=(fact_id,)),),
                    ),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_ADAPTER_MISMATCH


# --- response validation --------------------------------------------------


def test_a_grounded_bilingual_draft_is_accepted() -> None:
    request = request_for()

    validate(grounded_draft(request), request=request)


def test_arabic_indic_digits_ground_against_the_same_value() -> None:
    # ٥٠٠٫٠٠ and 500.00 are the same figure written in two scripts. Grounding
    # compares values, so it cannot depend on which script a reader gets.
    request = request_for()
    fact_id = revenue_fact_id(request)

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠٫٠٠ جنيه.", cited=(fact_id,)),),
            english=(section("Revenue 500.00.", cited=(fact_id,)),),
        ),
        request=request,
    )


def test_a_value_restated_without_trailing_zeros_is_still_grounded() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠.", cited=(fact_id,)),),
            english=(section("Revenue was 500.", cited=(fact_id,)),),
        ),
        request=request,
    )


def test_a_number_the_request_never_supplied_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(section("Revenue was 501.00.", cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_a_number_the_provider_computed_itself_is_refused() -> None:
    # 500.00 over 3 transactions is 166.67, which the package does supply — but
    # a growth rate nobody supplied is a model-generated calculation.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("نمو ١٢٫٥٪.", cited=(fact_id,)),),
                english=(section("Growth of 12.5%.", cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_a_percent_rendering_the_request_supplied_is_grounded() -> None:
    request = NarrativeRequest.of(package(WITH_COST), adapter_version=ADAPTER_VERSION)
    margin = next(
        entry for entry in request.document["facts"] if entry["metric"] == "gross_margin"
    )
    fact_id = str(margin["fact_id"])

    validate(
        NarrativeDraft(
            adapter_version=ADAPTER_VERSION,
            package_version=request.package_version,
            languages=(
                LanguageNarrative(
                    language=LANGUAGE_ARABIC,
                    sections=(section("الهامش ٦٠٫٠٠٠٠٪.", cited=(fact_id,)),),
                ),
                LanguageNarrative(
                    language=LANGUAGE_ENGLISH,
                    sections=(section("Margin of 60.0000%.", cited=(fact_id,)),),
                ),
            ),
        ),
        request=request,
    )


def test_a_period_label_is_read_as_a_label_not_as_loose_numbers() -> None:
    request = request_for()
    fact_id = str(request.document["series"][0]["fact_id"])

    validate(
        draft(
            arabic=(section("في 2026-01-05 ارتفعت المبيعات.", cited=(fact_id,)),),
            english=(section("On 2026-01-05 sales rose.", cited=(fact_id,)),),
        ),
        request=request,
    )


def test_a_year_named_on_its_own_is_grounded_by_the_labels_that_contain_it() -> None:
    # Refusing "in 2026" would cost a governed figure to protect nothing: the
    # year was supplied inside every period label of the series being cited.
    # Quoting part of a supplied string is not a derivation.
    request = request_for()
    revenue = revenue_fact_id(request)
    trend = str(request.document["series"][0]["fact_id"])

    validate(
        draft(
            arabic=(section("خلال ٢٠٢٦ بلغت الإيرادات ٥٠٠٫٠٠.", cited=(revenue, trend)),),
            english=(
                section("In January 2026 revenue reached 500.00.", cited=(revenue, trend)),
            ),
        ),
        request=request,
    )


def test_a_formatting_precision_is_not_stateable_as_a_figure() -> None:
    # Monetary precision is 2. It says how a figure is written, not what it
    # is, so it must not pass as the value of the fact beside it.
    request = request_for()
    assert request.document["monetary_precision"] == 2

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٢.", cited=(revenue_fact_id(request),)),),
                english=(section("Revenue was 2.", cited=(revenue_fact_id(request),)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


@pytest.mark.parametrize(
    ("dash", "name"),
    [
        ("−", "minus sign U+2212"),
        ("–", "en dash U+2013"),
        ("—", "em dash U+2014"),
        ("－", "fullwidth hyphen-minus U+FF0D"),
        ("‒", "figure dash U+2012"),
        ("‐", "hyphen U+2010"),
        ("‑", "non-breaking hyphen U+2011"),
        ("﹘", "small em dash U+FE58"),
        ("־", "hebrew maqaf U+05BE"),
    ],
)
def test_any_dash_a_reader_would_take_for_a_minus_reverses_the_figure(
    dash: str,
    name: str,
) -> None:
    # Recognizing only ASCII `-` would reopen the sign hole under a different
    # code point, which is the same defect wearing a different character.
    request = request_for()
    fact_id = revenue_fact_id(request)
    claim = f"Revenue was {dash}500.00."

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section(claim, cited=(fact_id,)),),
                english=(section(claim, cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER, name


@pytest.mark.parametrize(
    ("claim", "name"),
    [
        ("Revenue was ９９９.００.", "fullwidth digits"),
        ("Revenue was ٩٩٩٫٠٠.", "arabic-indic digits"),
        ("Revenue was ۹۹۹.۰۰.", "extended arabic-indic digits"),
    ],
)
def test_a_figure_in_any_decimal_script_is_read_rather_than_skipped(
    claim: str,
    name: str,
) -> None:
    # A scanner that silently sees nothing is worse than one that refuses,
    # because it reports success. Unicode is asked which characters are digits
    # instead of a table naming the blocks this module happens to know about.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section(claim, cited=(fact_id,)),),
                english=(section(claim, cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER, name


def test_a_supplied_figure_written_in_another_script_still_grounds() -> None:
    # The same normalization has to admit as well as refuse, or it would be a
    # ban on scripts rather than a check on values.
    request = request_for()
    fact_id = revenue_fact_id(request)

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
            english=(section("Revenue was ５００.００.", cited=(fact_id,)),),
        ),
        request=request,
    )


@pytest.mark.parametrize(
    ("claim_ar", "claim_en", "name"),
    [
        ("الإيرادات ٥٠٠ ألف.", "Revenue was 500 thousand.", "scale word"),
        ("الإيرادات ٥٠٠ مليون.", "Revenue was 500 million.", "larger scale word"),
        ("الإيرادات ‏$٥٠٠٫٠٠.", "Revenue was $500.00.", "currency symbol"),
        ("الإيرادات ﷼٥٠٠٫٠٠.", "Revenue was ﷼500.00.", "another currency symbol"),
        ("الإيرادات ٥٠٠٫٠٠ EGP.", "Revenue was 500.00 EGP.", "currency code after"),
        ("الإيرادات USD ٥٠٠٫٠٠.", "Revenue was USD 500.00.", "currency code before"),
    ],
)
def test_a_marker_that_changes_the_claim_is_refused_with_it(
    claim_ar: str,
    claim_en: str,
    name: str,
) -> None:
    # `500 thousand` is not the supplied `500`, and `$500.00` names a currency
    # this package raises `currency_not_declared` about precisely because it
    # does not know one. Both modifiers sit outside the candidate, where `%`
    # was too.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section(claim_ar, cited=(fact_id,)),),
                english=(section(claim_en, cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER, name


def test_an_ordinary_word_beside_a_figure_is_not_a_modifier() -> None:
    # The refusal above must not become a ban on writing sentences.
    request = request_for()
    fact_id = revenue_fact_id(request)

    validate(
        draft(
            arabic=(section("بلغت الإيرادات ٥٠٠٫٠٠ إجمالا.", cited=(fact_id,)),),
            english=(section("Revenue was 500.00 overall.", cited=(fact_id,)),),
        ),
        request=request,
    )


@pytest.mark.parametrize("numeral", ["½", "²", "Ⅳ"])
def test_a_numeral_that_forms_no_candidate_is_refused_rather_than_ignored(
    numeral: str,
) -> None:
    # These state quantities while falling outside every candidate, so leaving
    # them alone would let a figure travel in prose the scanner never examines.
    request = request_for()
    fact_id = revenue_fact_id(request)
    claim = f"Revenue was 500.00 and {numeral} more."

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section(claim, cited=(fact_id,)),),
                english=(section(claim, cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_a_percent_sign_separated_by_a_space_is_still_part_of_the_claim() -> None:
    # `500.00 %` is the most ordinary way of writing a percentage. Reading the
    # suffix only when flush against the digits let it escape the check
    # entirely — and I previously recorded the spaced form as refused without
    # running it, which it was not.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠ ٪.", cited=(fact_id,)),),
                english=(section("Revenue was 500.00 %.", cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_a_supplied_percent_written_with_a_space_is_accepted() -> None:
    request = NarrativeRequest.of(package(WITH_COST), adapter_version=ADAPTER_VERSION)
    fact_id = str(
        next(
            fact
            for fact in request.document["facts"]
            if fact["metric"] == "gross_margin"
        )["fact_id"]
    )
    claim = "Margin was 60.0000 %."

    validate(
        NarrativeDraft(
            adapter_version=ADAPTER_VERSION,
            package_version=request.package_version,
            languages=(
                LanguageNarrative(
                    language=LANGUAGE_ARABIC,
                    sections=(section(claim, cited=(fact_id,)),),
                ),
                LanguageNarrative(
                    language=LANGUAGE_ENGLISH,
                    sections=(section(claim, cited=(fact_id,)),),
                ),
            ),
        ),
        request=request,
    )


def test_a_percent_suffix_is_part_of_the_claim_not_decoration_after_it() -> None:
    # `500.00%` is not the revenue `500.00`; the suffix changes what the digits
    # assert, so a monetary figure cannot wear one.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠٪.", cited=(fact_id,)),),
                english=(section("Revenue was 500.00%.", cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


@pytest.mark.parametrize(
    ("claim_ar", "claim_en"),
    [
        ("الهامش ٠٫٦٠٠٠٪.", "Margin was 0.6000%."),  # the decimal wearing a percent
        ("الهامش ٦٠٫٠٠٠٠.", "Margin was 60.0000."),  # the percent without one
    ],
)
def test_a_ratio_must_be_stated_in_a_rendering_that_was_supplied(
    claim_ar: str,
    claim_en: str,
) -> None:
    # 0.6000 and 60.0000% say the same thing; 0.6000% and 60.0000 say two
    # different wrong things, and one set of numbers could not tell them apart.
    request = NarrativeRequest.of(package(WITH_COST), adapter_version=ADAPTER_VERSION)
    fact_id = str(
        next(
            fact
            for fact in request.document["facts"]
            if fact["metric"] == "gross_margin"
        )["fact_id"]
    )

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            NarrativeDraft(
                adapter_version=ADAPTER_VERSION,
                package_version=request.package_version,
                languages=(
                    LanguageNarrative(
                        language=LANGUAGE_ARABIC,
                        sections=(section(claim_ar, cited=(fact_id,)),),
                    ),
                    LanguageNarrative(
                        language=LANGUAGE_ENGLISH,
                        sections=(section(claim_en, cited=(fact_id,)),),
                    ),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_each_language_may_cite_a_fact_by_a_different_one_of_its_names() -> None:
    # Both identifiers are accepted names for the same fact, so comparing the
    # spellings rather than the facts would refuse an equivalent draft.
    request = request_for()
    entry = next(
        fact for fact in request.document["facts"] if fact["metric"] == "revenue"
    )

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(str(entry["fact_id"]),)),),
            english=(section("Revenue was 500.00.", cited=(str(entry["citation_id"]),)),),
        ),
        request=request,
    )


def test_a_period_a_section_never_cited_is_not_grounded_by_another_fact() -> None:
    # The year is supplied by the series, not by the revenue total. A section
    # that names a period is citing the series whether it says so or not.
    request = request_for()

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("خلال ٢٠٢٦ الإيرادات ٥٠٠٫٠٠.", cited=(revenue_fact_id(request),)),),
                english=(
                    section("In 2026 revenue was 500.00.", cited=(revenue_fact_id(request),)),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


@pytest.mark.parametrize(
    "claim",
    [
        "Margin grew .5 points.",  # no leading digit: previously matched nothing
        "Revenue was 500k.",  # digits fused to a letter mean more than the digits
        "Revenue was 500,000.",  # a supplied 500 does not carry five hundred thousand
        "Revenue 500.00x",  # a trailing letter is not a boundary
        "Revenue was 500,00.",  # grouping that is neither convention
    ],
)
def test_a_numeric_form_that_is_not_wholly_recognized_is_refused(claim: str) -> None:
    # The unit checked is the whole candidate, not whatever a pattern matches
    # inside it. Matching leaves everything unrecognized unexamined, which is a
    # hole shaped exactly like the forms nobody thought of.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section(claim, cited=(fact_id,)),),
                english=(section(claim, cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_an_ambiguous_grouping_is_refused_even_when_it_parses_to_a_supplied_value() -> None:
    # `500,00` is neither convention's way of writing 50000: read as grouping
    # it is malformed, read as a decimal comma it is five hundred. Stripping
    # the separator and comparing the value would accept it here, because this
    # dataset really does total 50000.00 — so the form has to be rejected on
    # its shape, before its value is consulted.
    content = (
        b"date,revenue,units,invoice_no\n"
        b"2026-01-05,20000.00,2,INV-1\n"
        b"2026-01-06,30000.00,4,INV-2\n"
    )
    request = request_for(content)
    revenue = next(
        fact for fact in request.document["facts"] if fact["metric"] == "revenue"
    )
    assert revenue["value"] == "50000.00"
    fact_id = str(revenue["fact_id"])
    claim = "Revenue was 500,00."

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            NarrativeDraft(
                adapter_version=ADAPTER_VERSION,
                package_version=request.package_version,
                languages=(
                    LanguageNarrative(
                        language=LANGUAGE_ARABIC,
                        sections=(section(claim, cited=(fact_id,)),),
                    ),
                    LanguageNarrative(
                        language=LANGUAGE_ENGLISH,
                        sections=(section(claim, cited=(fact_id,)),),
                    ),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNGROUNDED_NUMBER


def test_a_grouped_figure_in_the_usual_form_is_still_writable() -> None:
    content = (
        b"date,revenue,units,invoice_no\n"
        b"2026-01-05,20000.00,2,INV-1\n"
        b"2026-01-06,30000.00,4,INV-2\n"
    )
    request = request_for(content)
    fact_id = str(
        next(fact for fact in request.document["facts"] if fact["metric"] == "revenue")[
            "fact_id"
        ]
    )
    claim = "Revenue was 50,000.00."

    validate(
        NarrativeDraft(
            adapter_version=ADAPTER_VERSION,
            package_version=request.package_version,
            languages=(
                LanguageNarrative(
                    language=LANGUAGE_ARABIC,
                    sections=(section(claim, cited=(fact_id,)),),
                ),
                LanguageNarrative(
                    language=LANGUAGE_ENGLISH,
                    sections=(section(claim, cited=(fact_id,)),),
                ),
            ),
        ),
        request=request,
    )


def test_ordinary_punctuation_around_a_figure_still_reads_as_punctuation() -> None:
    # The tightening above must not cost the ways a figure is ordinarily
    # written: a closing bracket and a sentence-ending stop are not part of it.
    request = request_for()
    fact_id = revenue_fact_id(request)

    validate(
        draft(
            arabic=(section("بلغت الإيرادات ٥٠٠٫٠٠ (نهائي).", cited=(fact_id,)),),
            english=(section("Revenue was 500.00 (final).", cited=(fact_id,)),),
        ),
        request=request,
    )


def test_an_adapter_cannot_edit_the_request_it_will_be_judged_against() -> None:
    # frozen=True freezes the dataclass shell, not the document inside it. An
    # adapter handed the authority could raise a supplied 500.00 to 999.00 and
    # then state 999.00 — marking its own paper.
    class Tampering:
        adapter_version = ADAPTER_VERSION

        def draft(
            self,
            request: NarrativeRequest,
            *,
            timeout_seconds: Decimal,
        ) -> NarrativeDraft:
            for fact in request.document["facts"]:
                if fact["metric"] == "revenue":
                    fact["value"] = "999.00"
            fact_id = revenue_fact_id(request)
            return draft(
                arabic=(section("الإيرادات ٩٩٩٫٠٠.", cited=(fact_id,)),),
                english=(section("Revenue was 999.00.", cited=(fact_id,)),),
            )

    times = iter([0, 4])
    result = NarrativeService(
        adapter=Tampering(),
        monotonic_ms=lambda: next(times),
    ).compose(package())

    assert result.refused is True
    assert result.attempt.reason == REASON_UNGROUNDED_NUMBER


def test_the_copy_handed_to_the_adapter_carries_the_same_request() -> None:
    # The copy is a defence, not a different request: what the provider is
    # asked must still be exactly what the authority says.
    request = request_for()

    assert canonical_json(request.for_provider().document) == canonical_json(
        request.document
    )


def test_a_citation_that_resolves_to_nothing_is_refused() -> None:
    request = request_for()

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("نص.", cited=("fct_invented",)),),
                english=(section("Text.", cited=("fct_invented",)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNKNOWN_CITATION


def test_a_citation_identifier_is_accepted_alongside_a_fact_identifier() -> None:
    request = request_for()
    entry = next(
        fact for fact in request.document["facts"] if fact["metric"] == "revenue"
    )
    citation_id = str(entry["citation_id"])

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(citation_id,)),),
            english=(section("Revenue was 500.00.", cited=(citation_id,)),),
        ),
        request=request,
    )


def test_prose_with_no_citation_at_all_is_refused() -> None:
    request = request_for()

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("أداء قوي هذا الشهر.", cited=()),),
                english=(section("Strong performance this month.", cited=()),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNCITED_SECTION


def test_a_caveat_the_package_never_raised_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,), caveats=("invented",)),),
                english=(section("Revenue 500.00.", cited=(fact_id,), caveats=("invented",)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNKNOWN_CAVEAT


def test_an_empty_section_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("   ", cited=(fact_id,)),),
                english=(section("Revenue 500.00.", cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_EMPTY_NARRATIVE


def test_a_language_with_no_sections_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(arabic=(), english=(section("Revenue 500.00.", cited=(fact_id,)),)),
            request=request,
        )

    assert refusal.value.reason == REASON_EMPTY_NARRATIVE


# --- unsafe text ----------------------------------------------------------


def test_text_a_workbook_would_execute_as_a_formula_is_refused() -> None:
    # RRA-006 renders this prose into a workbook, where a leading = is a
    # formula rather than a sentence.
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(
                    section("Revenue 500.00.\n=cmd|calc", cited=(fact_id,)),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNSAFE_TEXT


def test_control_characters_in_the_prose_are_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(section("Revenue\x07 500.00.", cited=(fact_id,)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNSAFE_TEXT


def test_ordinary_prose_with_a_hyphenated_clause_is_not_read_as_a_formula() -> None:
    # The check is on what a cell would execute, which is a leading character;
    # a dash inside a sentence must stay writable in both languages.
    request = request_for()
    fact_id = revenue_fact_id(request)

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠٫٠٠ - وهي مستقرة.", cited=(fact_id,)),),
            english=(section("Revenue 500.00 - steady overall.", cited=(fact_id,)),),
        ),
        request=request,
    )


# --- bilingual parity -----------------------------------------------------


def test_a_fact_told_to_one_language_only_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)
    other = str(request.document["series"][0]["fact_id"])

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(section("Revenue 500.00.", cited=(fact_id, other)),),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_FACT_COVERAGE_DIFFERS


def test_a_caveat_warned_of_in_one_language_only_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(
                    section(
                        "Revenue 500.00.",
                        cited=(fact_id,),
                        caveats=("currency_not_declared",),
                    ),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_CAVEAT_COVERAGE_DIFFERS


def test_wording_may_differ_while_coverage_matches() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    validate(
        draft(
            arabic=(
                section(
                    "سجلت الفترة إيرادات قدرها ٥٠٠٫٠٠ دون تحديد العملة.",
                    cited=(fact_id,),
                    caveats=("currency_not_declared",),
                ),
            ),
            english=(
                section(
                    "Revenue reached 500.00; the currency is not stated in the data.",
                    cited=(fact_id,),
                    caveats=("currency_not_declared",),
                ),
            ),
        ),
        request=request,
    )


def test_coverage_is_compared_across_sections_not_section_by_section() -> None:
    # The languages need not be split into the same number of sections; what
    # must match is what a reader is told in total.
    request = request_for()
    fact_id = revenue_fact_id(request)
    other = str(request.document["series"][0]["fact_id"])

    validate(
        draft(
            arabic=(section("الإيرادات ٥٠٠٫٠٠ والاتجاه صاعد.", cited=(fact_id, other)),),
            english=(
                section("Revenue was 500.00.", cited=(fact_id,), section_id="kpi"),
                section("The trend is upward.", cited=(other,), section_id="trend"),
            ),
        ),
        request=request,
    )


def test_a_missing_language_in_the_response_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            NarrativeDraft(
                adapter_version=ADAPTER_VERSION,
                package_version=request.package_version,
                languages=(
                    LanguageNarrative(
                        language=LANGUAGE_ENGLISH,
                        sections=(section("Revenue 500.00.", cited=(fact_id,)),),
                    ),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_MISSING_LANGUAGE


def test_a_language_nobody_asked_for_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            NarrativeDraft(
                adapter_version=ADAPTER_VERSION,
                package_version=request.package_version,
                languages=(
                    LanguageNarrative(
                        language=LANGUAGE_ARABIC,
                        sections=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                    ),
                    LanguageNarrative(
                        language=LANGUAGE_ENGLISH,
                        sections=(section("Revenue 500.00.", cited=(fact_id,)),),
                    ),
                    LanguageNarrative(
                        language="fr",
                        sections=(section("Revenu 500.00.", cited=(fact_id,)),),
                    ),
                ),
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_UNKNOWN_LANGUAGE


# --- provenance of the answer ---------------------------------------------


def test_a_draft_answering_a_different_package_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(section("Revenue 500.00.", cited=(fact_id,)),),
                package_version="rra004.package.v0",
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_ADAPTER_MISMATCH


def test_a_draft_from_a_different_adapter_build_is_refused() -> None:
    request = request_for()
    fact_id = revenue_fact_id(request)

    with pytest.raises(NarrativeRefused) as refusal:
        validate(
            draft(
                arabic=(section("الإيرادات ٥٠٠٫٠٠.", cited=(fact_id,)),),
                english=(section("Revenue 500.00.", cited=(fact_id,)),),
                adapter_version="test.adapter.v2",
            ),
            request=request,
        )

    assert refusal.value.reason == REASON_ADAPTER_MISMATCH


# --- service behaviour ----------------------------------------------------


def test_a_valid_narrative_is_returned_with_its_attempt_recorded() -> None:
    result = service(lambda request: grounded_draft(request)).compose(package())

    assert result.refused is False
    assert result.narrative is not None
    assert result.attempt.outcome == OUTCOME_NARRATED
    assert result.attempt.reason is None
    assert result.attempt.narrative_version == NARRATIVE_VERSION
    assert result.attempt.duration_ms == 250


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (TimeoutError(), REASON_PROVIDER_TIMEOUT),
        (NarrativeUnavailable(), REASON_PROVIDER_FAILED),
        (ProviderRefused(), REASON_PROVIDER_REFUSED),
    ],
)
def test_a_provider_that_does_not_answer_produces_a_refusal(
    error: Exception,
    reason: str,
) -> None:
    result = service(error).compose(package())

    assert result.refused is True
    assert result.narrative is None
    assert result.attempt.outcome == OUTCOME_REFUSED
    assert result.attempt.reason == reason


@pytest.mark.parametrize(
    "failure",
    [ConnectionError("upstream down"), ValueError("bad json"), KeyError("missing")],
)
def test_an_unanticipated_provider_failure_is_still_a_refusal(
    failure: Exception,
) -> None:
    # The narrative is the optional part of the report. Letting a provider's
    # exception propagate would take down a delivery the deterministic facts
    # could have carried on their own.
    result = service(failure).compose(package())

    assert result.refused is True
    assert result.attempt.reason == REASON_PROVIDER_FAILED


def test_an_adapter_that_cannot_name_its_own_build_is_a_refusal() -> None:
    # Reading the version is already the adapter's code running, so it belongs
    # inside the failure policy rather than in front of it.
    class Misconfigured:
        @property
        def adapter_version(self) -> str:
            raise RuntimeError("no configuration")

        def draft(
            self,
            request: NarrativeRequest,
            *,
            timeout_seconds: Decimal,
        ) -> NarrativeDraft:
            raise AssertionError("never reached")

    times = iter([0, 3])
    result = NarrativeService(
        adapter=Misconfigured(),
        monotonic_ms=lambda: next(times),
    ).compose(package())

    assert result.refused is True
    assert result.attempt.reason == REASON_PROVIDER_FAILED
    assert result.attempt.adapter_version == "unknown"


def test_a_malformed_draft_is_a_refusal_rather_than_a_crash() -> None:
    # An adapter can return an object that breaks `validate` before any guard
    # runs. That is still a provider that did not answer.
    result = service(lambda request: object()).compose(package())

    assert result.refused is True
    assert result.attempt.reason == REASON_PROVIDER_FAILED


def test_nothing_is_written_in_place_of_a_narrative_that_failed_validation() -> None:
    ungrounded = lambda request: draft(  # noqa: E731
        arabic=(section("الإيرادات ٩٩٩.", cited=(revenue_fact_id(request),)),),
        english=(section("Revenue was 999.", cited=(revenue_fact_id(request),)),),
    )

    result = service(ungrounded).compose(package())

    assert result.narrative is None
    assert result.attempt.reason == REASON_UNGROUNDED_NUMBER


def test_the_attempt_record_has_no_field_customer_content_could_occupy() -> None:
    # Checking that today's values are absent would pass on any record; what is
    # worth asserting is that the record has no free-text field at all.
    result = service(lambda request: grounded_draft(request)).compose(package())

    assert set(result.attempt.as_document()) == {
        "narrative_version",
        "adapter_version",
        "package_version",
        "languages",
        "duration_ms",
        "outcome",
        "reason",
    }


def test_a_refusal_records_a_reason_code_rather_than_provider_text() -> None:
    result = service(NarrativeUnavailable("upstream said: customer Cairo failed")).compose(
        package()
    )

    assert result.attempt.reason == REASON_PROVIDER_FAILED
    assert "Cairo" not in canonical_json(result.attempt.as_document())


def test_the_adapter_is_handed_the_minimized_request_and_nothing_else() -> None:
    adapter = StubAdapter(lambda request: grounded_draft(request))
    times = iter([0, 10])
    NarrativeService(adapter=adapter, monotonic_ms=lambda: next(times)).compose(package())

    sent = adapter.requests[0].document
    assert "profile_digest" not in sent
    assert "source_sha256_hex" not in sent


def test_a_provider_is_replaceable_without_changing_the_contract() -> None:
    class OtherAdapter(StubAdapter):
        @property
        def adapter_version(self) -> str:
            return "other.adapter.v9"

    adapter = OtherAdapter(
        lambda request: NarrativeDraft(
            adapter_version="other.adapter.v9",
            package_version=request.package_version,
            languages=(
                LanguageNarrative(
                    language=LANGUAGE_ARABIC,
                    sections=(section("الإيرادات ٥٠٠٫٠٠.", cited=(revenue_fact_id(request),)),),
                ),
                LanguageNarrative(
                    language=LANGUAGE_ENGLISH,
                    sections=(section("Revenue 500.00.", cited=(revenue_fact_id(request),)),),
                ),
            ),
        )
    )
    times = iter([0, 5])

    result = NarrativeService(adapter=adapter, monotonic_ms=lambda: next(times)).compose(
        package()
    )

    assert result.refused is False
    assert result.attempt.adapter_version == "other.adapter.v9"
