"""Fixtures shared by the C1-05 test modules: two real RRA-004 packages and one ordered pair.

Extracted so the surface tests and the admission tests each stay cohesive and under the
module size CodeScene tracks, while building their packages exactly one way.
"""

from __future__ import annotations

import functools
import hashlib
from dataclasses import replace
from datetime import date, timedelta

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis.compatibility import (
    CAUSE_CURRENCY,
    CAUSE_FILTERS,
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
    GRANULARITY_DAY,
    GRANULARITY_MONTH,
    DatasetPeriod,
)
from khepri.rra.crossversion_bundle import (
    CrossVersionBundle,
    CrossVersionRefusal,
    CrossVersionRequest,
    build_crossversion_bundle,
)
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import (
    PrintablePage,
)
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    attesting_manifest,
    published_mapping_identity,
)

__all__ = [
    "HEADER",
    "PROVENANCE_KEYS",
    "SCOPE",
    "START",
    "_Printer",
    "_bundle",
    "_compatibility_cases",
    "_content",
    "_labels",
    "_package",
    "_period",
    "_period_cases",
    "_refusal",
    "_store_request",
    "build_comparison_request",
]


HEADER = b"date,revenue,units,invoice_no,category,branch\n"


START = date(2026, 3, 1)


SCOPE = "org_a"


PROVENANCE_KEYS = {
    "subject_version_id",
    "subject_basis_id",
    "subject_manifest_id",
    "baseline_version_id",
    "baseline_basis_id",
    "baseline_manifest_id",
    "operand_order",
}


def _content(revenue: str) -> tuple[bytes, tuple[date, ...]]:
    days = tuple(START + timedelta(days=offset) for offset in range(3))
    rows = b"".join(
        f"{day.isoformat()},{revenue},2,INV-{index},Drinks,Cairo\n".encode()
        for index, day in enumerate(days, start=1)
    )
    return HEADER + rows, days


def _package(revenue: str) -> FactPackage:
    content, days = _content(revenue)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    manifest = attesting_manifest(content=content, contract=TEST_CONTRACT, days=days)
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
                manifest=manifest,
            )
        )


def _period(version_id: str) -> DatasetPeriod:
    return DatasetPeriod(
        dataset_version_id=version_id,
        start=START,
        end=START + timedelta(days=2),
        granularity=GRANULARITY_DAY,
        retail_day_start_hour=0,
        complete=True,
    )


@functools.lru_cache(maxsize=1)
def build_comparison_request() -> CrossVersionRequest:
    """One ordered pair of real packages, built once per process and shared read-only."""
    return CrossVersionRequest(
        subject=_package("120.00"),
        baseline=_package("100.00"),
        subject_organization_scope=SCOPE,
        baseline_organization_scope=SCOPE,
        subject_period=_period("dsv_subject"),
        baseline_period=_period("dsv_baseline"),
    )


def _bundle(request: CrossVersionRequest) -> CrossVersionBundle:
    result = build_crossversion_bundle(request)
    assert isinstance(result, CrossVersionBundle)
    return result


def _labels(bundle: CrossVersionBundle, metric: str) -> set[str | None]:
    return {figure.label for figure in bundle.figures if figure.metric == metric}


def _refusal(result: CrossVersionBundle | CrossVersionRefusal) -> CrossVersionRefusal:
    assert isinstance(result, CrossVersionRefusal)
    assert result.bundle is None
    assert result.figures == ()
    assert set(result.wording) == {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}
    return result


def _store_request(request: CrossVersionRequest, *, other: str) -> CrossVersionRequest:
    def signatures(package: FactPackage, scope: str):
        return tuple(replace(entry, scope=scope) for entry in package.coverage_signatures)

    subject = replace(
        request.subject,
        daily_bases=(),
        coverage_signatures=signatures(request.subject, "store_a"),
    )
    baseline = replace(
        request.baseline,
        daily_bases=(),
        coverage_signatures=signatures(request.baseline, other),
    )
    return replace(request, subject=subject, baseline=baseline)


def _compatibility_cases(request: CrossVersionRequest):
    baseline = request.baseline
    return (
        (CAUSE_SCOPE, replace(request, baseline_organization_scope="org_b")),
        (
            CAUSE_MAPPING_DRIFT,
            replace(request, baseline=replace(baseline, mapping_version="map.v0")),
        ),
        (
            CAUSE_FORMULA_DRIFT,
            replace(request, baseline=replace(baseline, formula_version="formula.v0")),
        ),
        (
            CAUSE_PACKAGE_DRIFT,
            replace(request, baseline=replace(baseline, package_version="package.v0")),
        ),
        (CAUSE_CURRENCY, replace(request, baseline=replace(baseline, currency="USD"))),
        (CAUSE_STORE_SET, _store_request(request, other="store_b")),
        (
            CAUSE_FILTERS,
            replace(
                request,
                baseline=replace(baseline, event_kind_filters=("return",)),
            ),
        ),
    )


def _period_cases(request: CrossVersionRequest):
    baseline = request.baseline_period
    return (
        (
            CAUSE_GRANULARITY,
            replace(
                request,
                baseline_period=replace(baseline, granularity=GRANULARITY_MONTH),
            ),
        ),
        (
            CAUSE_RETAIL_DAY,
            replace(
                request,
                baseline_period=replace(baseline, retail_day_start_hour=4),
            ),
        ),
        (
            CAUSE_INCOMPLETE,
            replace(request, baseline_period=replace(baseline, complete=False)),
        ),
        (
            CAUSE_UNORDERED_PAIR,
            replace(
                request,
                baseline_period=replace(
                    baseline,
                    dataset_version_id=request.subject_period.dataset_version_id,
                ),
            ),
        ),
    )


class _Printer:
    def print_to_pdf(self, page: PrintablePage) -> bytes:
        del page
        return (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/MarkInfo<</Marked true>>"
            b"/StructTreeRoot 9 0 R/Lang(ar)>>endobj\n"
            b"2 0 obj<</Type/FontDescriptor/FontName/AAAAAA+NotoSansArabic-Regular"
            b"/FontFile2 3 0 R>>endobj\n%%EOF\n"
        )
