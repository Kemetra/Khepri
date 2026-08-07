"""RRA-009: the business/audit split in the governed workbook."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from tests.rra009_fixtures import rich_bundle
from tests.test_rra006_html_sections import ROWS, package_for

LEAKAGE_METRICS = frozenset(
    {"cost", "gross_profit", "gross_margin", "discount", "returns"}
)


def _plain_bundle() -> ReportBundle:
    """The five-row fixture, which produces none of the leakage metrics."""
    return ReportBundle.of(package_for(ROWS))


def _workbook_bytes(bundle: ReportBundle, directory: Path) -> Path:
    renderer = ExcelSurfaceRenderer(directory=directory)
    renderer.render(bundle)
    return renderer.path_for(bundle)


def _sheet_names(bundle: ReportBundle, directory: Path) -> list[str]:
    with zipfile.ZipFile(_workbook_bytes(bundle, directory)) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
    return re.findall(r'name="([^"]+)" sheetId', workbook)


def _shared_strings(bundle: ReportBundle, directory: Path) -> str:
    with zipfile.ZipFile(_workbook_bytes(bundle, directory)) as archive:
        return archive.read("xl/sharedStrings.xml").decode()


def test_the_rich_fixture_carries_every_leakage_metric() -> None:
    """Two business worksheets present exactly these, and the five-row fixture
    produces none of them. A bare `discount` column is not enough: `mapping.py`
    requires the measure kind be declared, so the column is `discount_amount`.
    """
    metrics = {figure.metric for figure in rich_bundle().figures}

    assert not (LEAKAGE_METRICS - metrics), sorted(LEAKAGE_METRICS - metrics)


def test_the_plain_fixture_carries_none_of_them() -> None:
    """The contrast this fixture exists for, asserted rather than assumed: a
    business sheet set that varies by dataset is only testable against both."""
    metrics = {figure.metric for figure in _plain_bundle().figures}

    assert not (LEAKAGE_METRICS & metrics)


def test_the_rich_fixture_presents_every_section() -> None:
    assert [section.state for section in rich_bundle().sections] == ["present"] * 5


def test_the_rich_fixture_renders_in_both_languages(tmp_path: Path) -> None:
    bundle = rich_bundle()
    for language in REQUIRED_LANGUAGES:
        assert all(language in figure.renderings for figure in bundle.figures)
    assert _sheet_names(bundle, tmp_path)


def test_every_rendered_metric_is_named_or_labelled() -> None:
    """The workbook's business sheets need a name for every row they list, on the
    same terms the web surface does. `concentration_curve` is the one metric with
    no business name, and every one of its figures carries a label.
    """
    from khepri.rra.rendering.wording import business_metric_name

    for figure in rich_bundle().figures:
        named = business_metric_name(figure.metric, LANGUAGE_ENGLISH)
        assert named or figure.label, figure.metric
