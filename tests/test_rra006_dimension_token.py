"""`RRA-006`: a figure's dimension is a governed token, and its label is the bare value (A3b).

SCRUM-26 A3b, the owner's reading recorded in `#637`. `basket.attached_label_of` composed
`f"{label} ({dimension})"` with the untranslated semantic key, so every Arabic chart and table
printed "Dairy (category)". The amendment moves the dimension onto the figure as a token from the
dimension vocabulary, keeps the label bare, and has each surface compose a governed qualifier name
in its own language. The token joins the identity document, so `BUNDLE_VERSION` advances to
`rra006.bundle.v9`.

The fixture is real CSV bytes through the real pipeline. Its product `Water` and its category
`Water` share one source value, which is the case the qualifier exists for.
"""

from __future__ import annotations

import hashlib
import io
import random
import re
import zipfile
from datetime import date, timedelta
from functools import cache

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import BUNDLE_VERSION, ReportBundle
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.semantic_views import projection
from tests.rra003_contract_fixtures import TEST_CONTRACT, manifest_for_csv

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)

_ATTACH = "basket_attach_rate"
#: The qualified names a reader must be able to tell apart, written out per language.
_QUALIFIED = {
    LANGUAGE_ENGLISH: ("Water (product)", "Water (category)"),
    LANGUAGE_ARABIC: ("Water (منتج)", "Water (فئة)"),
}
_ENGLISH_QUALIFIERS = ("(product)", "(category)")


def _csv() -> bytes:
    rng = random.Random(3)
    category_of = {"Water": "Drinks", "Juice": "Water", "Milk": "Dairy"}
    lines = [b"date,revenue,units,invoice_no,product,category\n"]
    for index in range(120):
        day = date(2026, 1, 5) + timedelta(days=index % 50)
        product = rng.choice(tuple(category_of))
        lines.append(
            f"{day.isoformat()},{rng.randint(1000, 9000) / 100:.2f},{rng.randint(1, 5)},"
            f"INV-{index // 2},{product},{category_of[product]}\n".encode()
        )
    return b"".join(lines)


@cache
def _bundle() -> ReportBundle:
    content = _csv()
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    package = build_fact_package(
        AdmittedInput(
            manifest=manifest_for_csv(content, TEST_CONTRACT),
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=TEST_CONTRACT,
        )
    )
    return ReportBundle.of(package)


def _attach_figures():
    return [figure for figure in _bundle().figures if figure.metric == _ATTACH]


def _text(markup: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", markup).split())


def _basket(language: str) -> str:
    page = HtmlReportRenderer().render_html(_bundle()).documents[language]
    start = page.index('<section id="basket"')
    end = page.find('<section id="', start + 1)
    return _text(page[start:] if end == -1 else page[start:end])


def test_the_fixture_shares_one_value_between_a_product_and_a_category() -> None:
    water = [figure for figure in _attach_figures() if figure.label == "Water"]

    assert {figure.dimension for figure in water} == {"product", "category"}


def test_an_attach_rate_carries_its_dimension_as_a_token_and_a_bare_label() -> None:
    figures = _attach_figures()
    assert figures

    for figure in figures:
        assert figure.dimension in {"product", "category"}, figure
        assert "(" not in (figure.label or ""), figure.label
        document = figure.as_document()
        assert document["dimension"] == figure.dimension
        assert document["label"] == figure.label


def test_a_figure_whose_label_needs_no_dimension_carries_none() -> None:
    others = [figure for figure in _bundle().figures if figure.metric != _ATTACH]
    assert others

    assert {figure.dimension for figure in others} == {None}
    assert all("dimension" in figure.as_document() for figure in others)


def test_the_identity_document_records_the_new_bundle_version() -> None:
    assert BUNDLE_VERSION == "rra006.bundle.v9"
    assert _bundle().as_document()["identity"]["bundle_version"] == "rra006.bundle.v9"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_tells_a_shared_value_apart_in_its_own_language(language: str) -> None:
    basket = _basket(language)

    for name in _QUALIFIED[language]:
        assert name in basket, f"{language}: {name}"


def test_the_arabic_page_prints_no_english_qualifier() -> None:
    basket = _basket(LANGUAGE_ARABIC)

    for qualifier in _ENGLISH_QUALIFIERS:
        assert qualifier not in basket, qualifier


def test_the_workbook_tells_a_shared_value_apart_in_each_language() -> None:
    content = ExcelSurfaceRenderer().render_materialized(_bundle()).artifacts[0].content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        strings = archive.read("xl/sharedStrings.xml").decode()

    for language in LANGUAGES:
        for name in _QUALIFIED[language]:
            assert name in strings, f"{language}: {name}"


def test_the_projection_reads_the_token_not_the_label() -> None:
    """The semantic projection states the dimension from the token (`RRA-006`: no parsing)."""
    water = {
        getattr(figure, "dimension", None): figure
        for figure in _attach_figures()
        if figure.label == "Water"
    }
    assert set(water) == {"product", "category"}, "the case under test is absent"

    for dimension, figure in water.items():
        assert projection._dimension(figure, None) == dimension


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_chart_names_each_bar_with_its_qualifier(language: str) -> None:
    page = HtmlReportRenderer().render_html(_bundle()).documents[language]
    start = page.index('<section id="basket"')
    end = page.find('<section id="', start + 1)
    block = page[start:] if end == -1 else page[start:end]
    labels = re.findall(r'<text class="chart__label"[^>]*>(.*?)</text>', block, re.S)

    assert labels, "the basket chart draws no labelled mark"
    for name in _QUALIFIED[language]:
        assert name in labels, f"{language}: {labels}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_audit_trail_tells_a_shared_value_apart_in_each_language(language: str) -> None:
    """The audit sheet writes the label too, so it composes the qualifier like every surface."""
    from khepri.rra.rendering.excel import _figure_cells

    labels = {
        _figure_cells(figure, language)[5]
        for figure in _attach_figures()
        if figure.label == "Water"
    }

    assert labels == set(_QUALIFIED[language]), labels
