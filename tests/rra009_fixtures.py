"""A fact package rich enough to exercise every business worksheet.

`tests/test_rra006_html_sections.py`'s fixture carries
`date,revenue,units,invoice_no,product` and therefore produces no cost, profit,
margin, discount, or returns figure at all. Two of the information
architecture's business worksheets present exactly those, so testing them
against that fixture would assert that two empty sheets are correct.

**The column names are load-bearing.** `discount_amount` rather than `discount`,
and `returns_amount` rather than `returns`: `mapping.py` gates both semantics
behind `requires_amount_evidence=True`, so a column whose measure kind is not
declared resolves `STATE_AMBIGUOUS` and is "reported unresolved rather than
summed as currency". `cost` carries no such gate and needs no suffix. Verified by
building this package and diffing the metric set against the plain fixture's.

Fourteen rows over nine months: enough for a prior comparison window, a growth
decomposition, and more than one product to concentrate over.
"""

from __future__ import annotations

import hashlib

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import ReportBundle
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import TEST_CONTRACT

RICH_HEADER = b"date,revenue,units,invoice_no,product,cost,discount_amount,returns_amount\n"

RICH_ROWS: tuple[tuple[str, str, int, str, str, str, str, str], ...] = tuple(
    (
        f"2026-0{(index % 9) + 1}-01",
        f"{100 + index * 10}.00",
        4 + index,
        f"INV-{index}",
        f"P{index % 3}",
        f"{50 + index * 5}.00",
        f"{index}.00",
        f"{index * 2}.00",
    )
    for index in range(14)
)


def rich_content() -> bytes:
    body = b"".join(
        f"{date},{revenue},{units},{invoice},{product},{cost},{discount},{returns}\n".encode()
        for date, revenue, units, invoice, product, cost, discount, returns in RICH_ROWS
    )
    return RICH_HEADER + body


def rich_package() -> FactPackage:
    content = rich_content()
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return build_fact_package(
               AdmittedInput(
                   content=content,
                   media_type=CSV_MEDIA_TYPE,
                   profile=profile,
                   mapping=mapping,
                   decision=assess_admissibility(profile, mapping),
                   contract=TEST_CONTRACT,
               ),
           )


def rich_bundle() -> ReportBundle:
    return ReportBundle.of(rich_package())
