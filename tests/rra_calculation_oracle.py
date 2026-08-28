"""An independent calculation oracle for the deterministic retail correction.

**What this module is.** Datasets as rows, and hand-derived expected literals for
every metric the governed successor versions must publish. Nothing here calls a
production aggregation or analysis helper. `build_fact_package`, `aggregates.*`,
`analysis.comparison/growth/basket/concentration.derive` are never imported, and
the only production names imported at all are governed vocabulary constants that
carry no arithmetic. If a production helper computed a number here, this would not
be an oracle -- it would be a second copy of the thing under test, and it would
agree with a defect as readily as with a correction.

**Every literal shows its arithmetic.** Each expectation carries the derivation
that produced it, so a reader can check it with a pencil. That is the property the
mission depends on: the seven `V-*` slices prove themselves against these numbers,
and a number nobody can re-derive proves nothing.

**Every literal also records what production returns today, and why they differ.**
The RED verification the mission asks for lives in these docstrings rather than in
a plan file, because a plan directory is deleted at the end of a run and git is
not. Each `_RED:` note states the metric, this module's literal, the value current
production actually returns (established empirically, not guessed), and which
governed rule the current behaviour violates.

**No failing tests here, and none added to the seven `test_rra00*.py` files.** The
mission's own final bullet settles it: a branch carrying committed failures for
`V-package` through `V-concentration` cannot produce a green gate while only
`V-mapping` is implemented. The oracle is shared; the failing tests are not. Each
slice adds its own verified-RED cases immediately before its GREEN, reading its
literals from here.

**Rows, not packages.** `tests/rra009_fixtures.py` builds its fixture by calling
`build_fact_package`, which is right for a fixture exercising worksheets and wrong
for an oracle. These datasets are records. `to_csv` renders them to the bytes
production accepts, which is a serializer and not a calculation -- it is what lets
a slice feed production the exact rows a literal describes.

**The column names are load-bearing**, for the reason `rra009_fixtures.py` records:
`mapping.py` gates `discount` and `returns` behind `requires_amount_evidence=True`,
so `discount_amount` and `returns_amount` are the spellings that resolve. `cost`,
`store`, `product`, `category`, `invoice_no`, `units`, `revenue` and `date` carry
no such gate. Verified against `SEMANTIC_RULES` rather than assumed.

**`Decimal` throughout, half-even, never float.** Money and every value whose
rounding is asserted is a `Decimal` literal string. A float literal would make the
oracle's own arithmetic unreproducible, which is the defect it exists to catch.

**Two structural facts about current production that shape most of the gaps.**
Neither is a bug in this module; both are the correction's subject matter.

1. *There is no event-kind semantic.* `SEMANTIC_RULES` in `mapping.py` has no
   `sale`/`return` rule, and `_measures` reads `revenue` as one signed column with
   `returns` as a separate summed column. So a return event in these datasets
   renders to CSV as an ordinary row, and production's AOV and ASP divide
   return-inclusive revenue by all distinct transactions. `RRA-004` requires AOV
   over `sales_complete_revenue_transactions` and ASP over
   `sales_complete_revenue_units` -- sale-only populations. There is no column
   spelling that makes current code see the distinction, so the gap is recorded
   rather than papered over.

2. *A period is "settled" only when data sits on both sides of it.*
   `windows.settled` returns `buckets[1:-1]`, so a two-period dataset yields no
   comparison at all. `RRA-008` draws completeness from the coverage manifest, not
   from neighbouring buckets. That is itself one of the gaps, and it is why the
   growth datasets below carry four months rather than two.

**A third fact, about the datasets rather than the code.** `granularity_for` in
`aggregates.py` returns `GRANULARITY_MONTH` only when the observed date span
exceeds `GRANULARITY_DAY_SPAN = 92` days; otherwise every bucket is one day. Most
of the messy and adversarial datasets below span a few weeks and therefore bucket
by day, which is correct for what each of them measures -- they are about
populations, identity and signs, not about windows. The datasets whose literals
depend on month buckets say so and are built to clear 92 days: `CLEAN_ROWS`
(2026-01-05 to 2026-05-25), `NO_EXACT_PRIOR_PERIOD_ROWS` (2026-01-15 to
2026-05-15), and the four-month growth harness each `GrowthCase` describes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_PRODUCT,
)

# The governed rounding modes and scales, restated as literals rather than
# imported, so a production change to either is a visible disagreement with this
# module instead of a silent agreement with it.
MONETARY_PRECISION = 2
RATIO_PRECISION = 4
COUNT_PRECISION = 0

EVENT_SALE = "sale"
EVENT_RETURN = "return"
STATUS_POSTED = "posted"
STATUS_VOID = "void"


@dataclass(frozen=True, slots=True)
class OracleRow:
    """One normalized retail event, as `RRA-003` defines one.

    `event_kind` and `status` are carried because `RRA-003` requires every row
    used by a governed calculation to prove both. Current production has no
    semantic for either -- see the module docstring -- so `to_csv` does not emit
    them and every RED record below states where that costs a number.

    Optional dimensions are `None` rather than absent so a row with no category
    is distinguishable from one whose category is the empty string, which
    `RRA-003` requires: "an explicit zero differs from a missing value".
    """

    day: date
    event_kind: str
    status: str
    revenue: Decimal | None
    units: int | None
    invoice: str | None
    store: str | None
    product: str | None = None
    category: str | None = None
    cost: Decimal | None = None
    discount: Decimal | None = None
    terminal: str | None = None

    @property
    def canonical_transaction_key(self) -> str | None:
        """The composite key `RRA-003` requires when a bare identifier cannot prove
        package-wide uniqueness: source identifier plus store, business date and
        terminal.

        A bare `invoice` is admissible only when the source contract proves it
        unique across the package. None of these datasets carry such a contract,
        so the canonical key is the composite -- and that is precisely the
        difference the "repeated invoice IDs in different stores" proof measures.
        """
        if self.invoice is None or self.store is None:
            return None
        parts = (self.invoice, self.store, self.day.isoformat(), self.terminal or "")
        return "|".join(parts)


CSV_COLUMNS = (
    "date",
    "event_kind",
    "status",
    "revenue",
    "units",
    "invoice_no",
    "store",
    "product",
    "category",
    "cost",
    "discount_amount",
)


def to_csv(rows: tuple[OracleRow, ...]) -> bytes:
    """Render rows to the bytes production accepts. A serializer, not a calculation.

    `build_fact_package` rebuilds profile, mapping and admissibility from the bytes
    and refuses any artifact not derived from them, so a slice cannot hand
    production an abstract record. This is the bridge, and it computes no
    expectation: it writes each field exactly as the row states it.

    `event_kind` and `status` are emitted, and the columns are named rather than
    spelled to taste: `RRA-003` requires every row used by a governed calculation
    to prove both, and forbids establishing either "from generic headers and
    observed values". A consumer maps these columns through its source contract,
    which is the governed spelling `V-mapping` landed.

    **This discharges a forward dependency this bridge carried.** While the two
    columns were absent, `MESSY_RETURNS_ROWS` was unusable by any honest
    contract: its return is identifiable only by a negative revenue, so a
    consumer would have had to declare `sale_only` -- false of an extract
    containing a return -- or infer the kind from the sign, which is the
    inference the specification refuses. Neither could prove the sale-only
    AOV/ASP literals the case exists to state.
    """
    header = ",".join(CSV_COLUMNS).encode() + b"\n"

    def cell(value: object) -> str:
        return "" if value is None else str(value)

    body = b"".join(
        ",".join(
            (
                row.day.isoformat(),
                cell(row.event_kind),
                cell(row.status),
                cell(row.revenue),
                cell(row.units),
                cell(row.invoice),
                cell(row.store),
                cell(row.product),
                cell(row.category),
                cell(row.cost),
                cell(row.discount),
            )
        ).encode()
        + b"\n"
        for row in rows
    )
    return header + body


# ---------------------------------------------------------------------------
# Case 1: the clean two-store / two-period dataset.
# ---------------------------------------------------------------------------

CLEAN_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 1, 5), EVENT_SALE, STATUS_POSTED, Decimal("120.00"), 4,
              "INV-1001", "S1", "P1", "C1", Decimal("70.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 1, 5), EVENT_SALE, STATUS_POSTED, Decimal("30.00"), 2,
              "INV-1001", "S1", "P2", "C1", Decimal("18.00"), Decimal("0.00"), "T1"),
    # P1 repeats inside INV-1001 on a distinct line. `RRA-003`: "Repeated products
    # or categories in one transaction remain valid when their event identities
    # differ." Two lines, one transaction, one attach-rate membership.
    OracleRow(date(2026, 1, 5), EVENT_SALE, STATUS_POSTED, Decimal("50.00"), 1,
              "INV-1001", "S1", "P1", "C1", Decimal("28.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 1, 12), EVENT_SALE, STATUS_POSTED, Decimal("200.00"), 5,
              "INV-1002", "S1", "P3", "C2", Decimal("110.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 1, 20), EVENT_SALE, STATUS_POSTED, Decimal("80.00"), 2,
              "INV-2001", "S2", "P1", "C1", Decimal("44.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 1, 27), EVENT_SALE, STATUS_POSTED, Decimal("150.00"), 3,
              "INV-2002", "S2", "P3", "C2", Decimal("82.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 4), EVENT_SALE, STATUS_POSTED, Decimal("180.00"), 6,
              "INV-1003", "S1", "P1", "C1", Decimal("100.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 4), EVENT_SALE, STATUS_POSTED, Decimal("60.00"), 2,
              "INV-1003", "S1", "P2", "C1", Decimal("34.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 11), EVENT_SALE, STATUS_POSTED, Decimal("240.00"), 6,
              "INV-1004", "S1", "P3", "C2", Decimal("132.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 18), EVENT_SALE, STATUS_POSTED, Decimal("90.00"), 3,
              "INV-2003", "S2", "P2", "C1", Decimal("50.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 25), EVENT_SALE, STATUS_POSTED, Decimal("110.00"), 2,
              "INV-2004", "S2", "P1", "C1", Decimal("62.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 25), EVENT_SALE, STATUS_POSTED, Decimal("70.00"), 1,
              "INV-2004", "S2", "P3", "C2", Decimal("40.00"), Decimal("0.00"), "T1"),
)

CLEAN_MANIFEST_SCOPES = ("S1", "S2")
CLEAN_MANIFEST_EVENT_KINDS = (EVENT_SALE,)
CLEAN_MANIFEST_STATUSES = (STATUS_POSTED,)
CLEAN_MANIFEST_WINDOWS = (
    (date(2026, 1, 1), date(2026, 1, 31)),
    (date(2026, 5, 1), date(2026, 5, 31)),
)
"""Two complete full calendar months, both stores, sales-posted only.

`RRA-008` accepts these as structurally compatible: same complete admitted store
set, same event-kind and status filters. The 31/31-day equality is incidental --
the specification says natural length differences do not make otherwise complete
periods incompatible, which the 28/29/30/31 proof below exercises directly.
"""


CLEAN_HEADLINE = {
    # revenue = 120.00 + 30.00 + 50.00 + 200.00 + 80.00 + 150.00
    #         + 180.00 + 60.00 + 240.00 + 90.00 + 110.00 + 70.00
    #         = 630.00 (January) + 750.00 (May) = 1380.00
    # `RRA-004`: sum(financial signed revenue) over `financial_posted`.
    #
    # _RED: production returns "1380.00" today and agrees. Recorded because the
    # correction must not move a number that is already right; a slice that
    # changes this literal has changed the wrong thing.
    "revenue": Decimal("1380.00"),
    # units = 4+2+1+5+2+3 + 6+2+6+3+2+1 = 17 + 20 = 37
    # _RED: production returns "37" and agrees, for the same reason.
    "units": Decimal("37"),
    # transactions = count_distinct(canonical sale transaction key).
    # The eight canonical keys are INV-1001|S1|2026-01-05|T1, INV-1002|S1|...,
    # INV-2001|S2|..., INV-2002|S2|..., INV-1003|S1|..., INV-1004|S1|...,
    # INV-2003|S2|..., INV-2004|S2|... -- eight distinct.
    #
    # _RED: production returns "8" and agrees *here only because these invoice
    # identifiers happen to be globally unique*. `_distinct` in `facts.py`
    # operates on the bare mapped identifier, never a composite. The
    # `REPEATED_INVOICE_*` case below is the same metric on data where that
    # shortcut is wrong, and there production returns 3 against an oracle of 4.
    "transactions": Decimal("8"),
    # cost = 70+18+28+110+44+82 + 100+34+132+50+62+40 = 352.00 + 418.00 = 770.00
    "cost": Decimal("770.00"),
    # gross_profit = matched revenue - matched extended COGS = 1380.00 - 770.00
    "gross_profit": Decimal("610.00"),
    # gross_margin = gross profit / matched revenue = 610.00 / 1380.00
    #              = 0.442028985507... -> half-even at 4dp -> 0.4420
    "gross_margin": Decimal("0.4420"),
    # discounts = sum(non-negative sale discount) = twelve explicit zeros = 0.00.
    # `RRA-003`: "Proven absence states zero." Every row carries an explicit zero,
    # which is the admitted coverage, not an absent column.
    "discount": Decimal("0.00"),
}

CLEAN_SALE_ONLY = {
    # This dataset is return-free, so sale-only and return-inclusive coincide.
    # That is deliberate: it isolates the arithmetic from the population question,
    # which `MESSY_RETURNS_ROWS` then varies on its own.
    #
    # AOV = sales revenue / distinct sale transactions = 1380.00 / 8 = 172.50
    # _RED: production returns "172.50" and agrees, because no returns are
    # present to separate the two populations.
    "average_order_value": Decimal("172.50"),
    # ASP = sales revenue / positive sale units = 1380.00 / 37
    #     = 37.297297297... -> half-even at 2dp -> 37.30
    "average_selling_price": Decimal("37.30"),
    # items per transaction = sum(sale units) / distinct sale transactions
    #                       = 37 / 8 = 4.625 -> 4 dp -> 4.6250
    # `RRA-008`: never a row count. Twelve rows over eight transactions is 1.5
    # rows per transaction, and 4.6250 is the number that answers the question.
    "basket_items_per_transaction": Decimal("4.6250"),
}

CLEAN_PERIOD_TOTALS = {
    # January: 120.00+30.00+50.00+200.00+80.00+150.00 = 630.00 over 4+2+1+5+2+3 = 17
    "2026-01": {"revenue": Decimal("630.00"), "units": Decimal("17"),
                "transactions": Decimal("4"), "distinct_dates": Decimal("4")},
    # May: 180.00+60.00+240.00+90.00+110.00+70.00 = 750.00 over 6+2+6+3+2+1 = 20
    "2026-05": {"revenue": Decimal("750.00"), "units": Decimal("20"),
                "transactions": Decimal("4"), "distinct_dates": Decimal("4")},
}

CLEAN_COMPARISON = {
    # `RRA-008`, month granularity. **These two months are 2026-01 and 2026-05,
    # so this is NOT a governed comparison pair at all**, and the arithmetic below
    # is what a *correct* refusal must decline to publish -- not a result any
    # slice may produce.
    #
    # An earlier revision of this comment claimed the coverage manifest made the
    # pair comparable. That was wrong and is corrected here, because a later
    # slice reading it would have built the defect into `V-comparison`.
    # `RRA-008` L12-15 is exhaustive on window selection: "Period-over-period
    # uses the immediately preceding calendar period. Year-over-year uses the
    # exact same calendar period one year earlier. Nearest observed buckets never
    # substitute for missing exact counterparts." A manifest proves completeness;
    # it never licenses comparing arbitrary complete months. 2026-01 is neither
    # the period preceding 2026-05 nor 2025-05.
    #
    # The literals stay because they are the arithmetic of the pair a defective
    # implementation would report if it fell back to nearest observed buckets,
    # and `V-comparison` must prove it refuses rather than producing them. The
    # governed PoP and YoY arithmetic lives in `YEAR_OVER_YEAR_COMPARISON`, whose
    # pair `RRA-008` does admit.
    #
    # absolute delta = current - prior = 750.00 - 630.00 = 120.00
    "revenue_delta_absolute": Decimal("120.00"),
    # percentage delta = (current - prior) / prior = 120.00 / 630.00
    #                  = 0.190476190476... -> half-even at 4dp -> 0.1905
    "revenue_delta_percent": Decimal("0.1905"),
    # units delta = 20 - 17 = 3
    "units_delta_absolute": Decimal("3"),
}
"""_RED: production refuses both metrics with `prior_window_absent`.

Empirically confirmed: `windows.settled` is `buckets[1:-1]`, so a two-bucket
series has no settled period, `compared_labels` returns `None`, and
`comparison.derive` refuses. It never reaches an arithmetic disagreement.

The violated rule is `RRA-008`'s completeness contract: "Completeness and
alignment come only from the authoritative `RRA-003` coverage manifest and the
`RRA-004` structural coverage signatures". A neighbouring bucket is neither. Two
complete full calendar months with the same store set and filters are compatible
by specification, and current code cannot state their delta at all.
"""

YEAR_OVER_YEAR_ROWS: tuple[OracleRow, ...] = (
    # **A separate dataset, deliberately, and not extra rows on `CLEAN_ROWS`.**
    # `CLEAN_ROWS` spans 2026-01..2026-05, so no exact year-earlier counterpart
    # exists inside it. Adding prior-year rows would change `CLEAN_HEADLINE`'s
    # revenue, units, cost, transaction count and every ratio derived from them --
    # literals an external reviewer has already independently reproduced. A new
    # dataset keeps that verification intact, which is worth more than reusing
    # one fixture.
    #
    # Four month buckets spanning 2025-04-10 to 2026-06-10 (426 days, so
    # `granularity_for` yields months). `windows.settled` drops the first and last,
    # leaving 2025-05 and 2026-05 settled -- an exact year-apart pair, which is
    # what `RRA-008` requires YoY to compare: "the exact same calendar period one
    # year earlier".
    OracleRow(date(2025, 4, 10), EVENT_SALE, STATUS_POSTED, Decimal("100.00"), 4,
              "INV-Y001", "S1", "P1", "C1", Decimal("55.00"), Decimal("0.00"), "T1"),
    # 2025-05, the prior-year counterpart: 320.00 + 240.00 = 560.00 over 8 + 6 = 14.
    OracleRow(date(2025, 5, 12), EVENT_SALE, STATUS_POSTED, Decimal("320.00"), 8,
              "INV-Y002", "S1", "P1", "C1", Decimal("176.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2025, 5, 19), EVENT_SALE, STATUS_POSTED, Decimal("240.00"), 6,
              "INV-Y003", "S1", "P2", "C1", Decimal("132.00"), Decimal("0.00"), "T1"),
    # 2026-05, the current period: 430.00 + 300.00 = 730.00 over 10 + 7 = 17.
    OracleRow(date(2026, 5, 12), EVENT_SALE, STATUS_POSTED, Decimal("430.00"), 10,
              "INV-Y004", "S1", "P1", "C1", Decimal("236.50"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 19), EVENT_SALE, STATUS_POSTED, Decimal("300.00"), 7,
              "INV-Y005", "S1", "P2", "C1", Decimal("165.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 6, 10), EVENT_SALE, STATUS_POSTED, Decimal("120.00"), 5,
              "INV-Y006", "S1", "P1", "C1", Decimal("66.00"), Decimal("0.00"), "T1"),
)

YEAR_OVER_YEAR_PERIOD_TOTALS = {
    # 2025-05: 320.00 + 240.00 = 560.00 over 8 + 6 = 14 units, 2 transactions.
    "2025-05": {"revenue": Decimal("560.00"), "units": Decimal("14"),
                "transactions": Decimal("2")},
    # 2026-05: 430.00 + 300.00 = 730.00 over 10 + 7 = 17 units, 2 transactions.
    "2026-05": {"revenue": Decimal("730.00"), "units": Decimal("17"),
                "transactions": Decimal("2")},
}

YEAR_OVER_YEAR_COMPARISON = {
    # `RRA-008`: "Year-over-year uses the exact same calendar period one year
    # earlier." The compared pair is 2026-05 against 2025-05 -- not the adjacent
    # 2026-06 or 2025-04, both of which exist in this dataset precisely so a
    # positional or nearest-neighbour selection would pick the wrong one.
    "current_label": "2026-05",
    "prior_label": "2025-05",
    # absolute delta = current - prior = 730.00 - 560.00 = 170.00
    "revenue_delta_absolute": Decimal("170.00"),
    # percentage delta = (current - prior) / prior = 170.00 / 560.00
    #                  = 0.30357142857142857142857... -> half-even at 4 dp.
    #   Split at the retained place: 0.3035|714... The first discarded digit is
    #   7, above the tie, so it rounds UP to 0.3036 -- no half-even tie arises
    #   here. Chosen to be non-terminating on purpose: a ratio like 0.5000 would
    #   pass under any rounding mode and discriminate nothing.
    "revenue_delta_percent": Decimal("0.3036"),
    # units delta = 17 - 14 = 3
    "units_delta_absolute": Decimal("3"),
}
"""Year-over-year deltas -- brief bullet 2's "PoP/YoY deltas", YoY half.

The module previously carried only the YoY *refusal* case
(`NATURAL_MONTH_LENGTH_EXPECTED["leap_day_yoy_admitted"] = False`, from `RRA-008`'s
leap-day clause). That is one of two obligations. `RRA-008`'s verification clause
requires "exact PoP and YoY counterparts", which is the arithmetic case, and it
was missing.

_RED: production returns `revenue_delta_absolute.year_over_year` = "170.00" and
`revenue_delta_percent.year_over_year` = "0.3036", agreeing with both literals.
`comparison.mode_of` confirms the facts carry the year-over-year mode, and the
buckets are ('2025-04', '2025-05', '2026-05', '2026-06') at month granularity.

Empirically confirmed, and the agreement is narrower than it looks. The four
buckets leave 2025-05 and 2026-05 settled; `_year_earlier_label` decrements the
year field to reach 2025-05 from 2026-05, finds it settled, and the pair
resolves. So the YoY *arithmetic* and the counterpart *selection* are both correct
on current code, and `V-comparison` must not lose either.

What is absent is the precondition. Nothing proves either May complete -- no
manifest reaches this calculation at all -- and `RRA-008` makes completeness a
requirement of the comparison rather than an optional extra. So this pair is an
agreement on the numbers standing beside the same missing-manifest gap every other
comparison case in this module carries.

Note the contrast with `CLEAN_COMPARISON`, which refuses `prior_window_absent`:
there the two months are adjacent-in-data but the only two buckets, so neither is
settled. Here PoP refuses for that reason (2026-04 does not exist) while YoY
succeeds. The two cases together show the settled-window rule is orthogonal to
which mode is asked for.

The percentage is deliberately non-terminating. 170/560 = 0.3035714..., which
rounds to 0.3036 under half-even and under half-up alike, but would differ from a
truncating implementation -- and a round 0.5000 would have discriminated nothing.
"""


CLEAN_CONCENTRATION = {
    # Ranked product revenue over the full non-null distinct set, before display
    # truncation. `RRA-008`: concentration ranks the full admissible set.
    #   P3 = 200.00 + 150.00 + 240.00 + 70.00 = 660.00
    #   P1 = 120.00 + 50.00 + 80.00 + 180.00 + 110.00 = 540.00
    #   P2 = 30.00 + 60.00 + 90.00 = 180.00
    #   total ranked revenue = 660.00 + 540.00 + 180.00 = 1380.00
    "dimension": SEMANTIC_PRODUCT,
    "distinct_values": Decimal("3"),
    "ranked_values": Decimal("3"),
    # Cumulative revenue / total ranked revenue, at each rank, 4 dp half-even:
    #   rank 1: 660.00 / 1380.00 = 0.478260869565... -> 0.4783
    #   rank 2: 1200.00 / 1380.00 = 0.869565217391... -> 0.8696
    #   rank 3: 1380.00 / 1380.00 = 1                 -> 1.0000
    "curve": (Decimal("0.4783"), Decimal("0.8696"), Decimal("1.0000")),
    # Top decile share: cutoff is ceil(n / 10) = ceil(3 / 10) = ceil(0.3) = 1,
    # "with at least one value in either cutoff". Curve share after 1 value.
    "top_decile_share": Decimal("0.4783"),
    # Top quartile share: cutoff is ceil(n / 4) = ceil(0.75) = 1. Same point.
    "top_quartile_share": Decimal("0.4783"),
}
"""_RED: production returns exactly these four values on this dataset.

Empirically confirmed: distinct_values 3, ranked_values 3, decile and quartile
share both 0.4783. It agrees because three values sit far inside
`MAX_COMPARISON_BUCKETS = 20`, so the retained curve and the displayed buckets
coincide and no ceiling edge is exercised.

Recorded as an agreement rather than dropped. The concentration gaps are the ones
`ZERO_REVENUE_PRODUCT_ROWS` and `CONCENTRATION_TRUNCATION_*` below carry: a
zero-revenue value that current code drops from `ranked` while `RRA-008` keeps it
in `n`, and a distinct set larger than the display limit.
"""

CLEAN_ATTACH = {
    # attach rate for value = distinct containing keys / all eligible keys.
    # Denominator is the eight canonical sale transaction keys. Multiple lines of
    # one value in a transaction count once -- P1 appears twice in INV-1001 and
    # contributes one membership.
    #   P1 in INV-1001, INV-2001, INV-1003, INV-2004 -> 4 / 8 = 0.5000
    #   P2 in INV-1001, INV-1003, INV-2003           -> 3 / 8 = 0.3750
    #   P3 in INV-1002, INV-2002, INV-1004, INV-2004 -> 4 / 8 = 0.5000
    "denominator": Decimal("8"),
    "P1": Decimal("0.5000"),
    "P2": Decimal("0.3750"),
    "P3": Decimal("0.5000"),
}
"""_RED: production returns 0.5000 / 0.3750 / 0.5000 and agrees here.

Empirically confirmed. It agrees because every row carries a product and the bare
invoice identifiers are globally unique in this dataset, so
`Comparison.distinct_transactions` equals the canonical count. The attach gaps are
carried by `MISSING_PRODUCT_ZERO_REVENUE_ROWS` -- where `RRA-008` refuses the whole
dimension family and current code silently ranks an `unlabelled` bucket -- and by
`REPEATED_INVOICE_ROWS`, where the denominator itself is wrong.
"""


# ---------------------------------------------------------------------------
# Case 2: messy legitimate data.
# ---------------------------------------------------------------------------

MESSY_RETURNS_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("400.00"), 10,
              "INV-3001", "S1", "P1", "C1", Decimal("220.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, Decimal("600.00"), 15,
              "INV-3002", "S1", "P2", "C1", Decimal("330.00"), Decimal("0.00"), "T1"),
    # A posted return. `RRA-003`: return revenue is non-positive, recognized on
    # the return posting date, and `returns` is its positive magnitude.
    OracleRow(date(2026, 3, 18), EVENT_RETURN, STATUS_POSTED, Decimal("-100.00"), -2,
              "INV-3003", "S1", "P1", "C1", Decimal("-55.00"), None, "T1"),
)
"""Sale-only ratios beside return-inclusive headlines -- regression proof 6.

Derivation.
  Return-inclusive headline revenue = 400.00 + 600.00 - 100.00 = 900.00
  Headline units (net movement, includes returns) = 10 + 15 - 2 = 23
  returns = -sum(non-positive return revenue) = -(-100.00) = 100.00
  Sale-only revenue = 400.00 + 600.00 = 1000.00
  Distinct sale transactions = 2 (the return is not a sale; `RRA-004`:
    "Transactions count posted sales only")
  Positive posted-sale units = 10 + 15 = 25
  AOV = sale revenue / distinct sale transactions = 1000.00 / 2 = 500.00
  ASP = sale revenue / positive sale units = 1000.00 / 25 = 40.00
  Items per transaction = 25 / 2 = 12.5000

_RED: production returns revenue "900.00", units "23", transactions "3",
AOV "300.00", ASP "39.13", items per transaction "7.6667", returns refused with
`required_input_unavailable`.

Empirically confirmed. Five distinct gaps, each a different governed rule:

1. transactions 3 vs oracle 2. `facts.py` counts distinct values of the mapped
   identifier column with no event-kind filter, so the return event is counted as
   a transaction. `RRA-004`: "Transactions count posted sales only."
2. AOV 300.00 vs oracle 500.00. Production computes 900.00 / 3 -- return-inclusive
   revenue over a return-contaminated denominator. `RRA-004` assigns AOV the
   population `sales_complete_revenue_transactions`.
3. ASP 39.13 vs oracle 40.00. Production computes 900.00 / 23, netting the return
   into both numerator and denominator. `RRA-004` assigns ASP
   `sales_complete_revenue_units`, and `RRA-003` says "ASP and basket calculations
   use positive posted-sale units only".
4. items per transaction 7.6667 vs oracle 12.5000. Production divides net units 23
   by 3. `RRA-008`: "Returns, voids, and cancelled events enter neither numerator
   nor denominator."
5. returns refused. There is no `returns_amount` column here, and `RRA-003`
   forbids one: "No independently mapped return-amount measure is admitted." The
   magnitude must be derived from the return event's own revenue. Current code has
   no event kind, so it cannot derive it and refuses a metric the data proves.

Headline revenue 900.00 and headline units 23 agree, because `RRA-004` says
"Revenue and units include posted returns" and the signed column already does that.
"""

MESSY_RETURNS_EXPECTED = {
    "revenue": Decimal("900.00"),
    "units": Decimal("23"),
    "returns": Decimal("100.00"),
    "transactions": Decimal("2"),
    "average_order_value": Decimal("500.00"),
    "average_selling_price": Decimal("40.00"),
    "basket_items_per_transaction": Decimal("12.5000"),
}


PARTIAL_NULL_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("400.00"), 10,
              "INV-4001", "S1", "P1", "C1", Decimal("220.00"), Decimal("0.00"), "T1"),
    # Cost absent on one row. `RRA-004`: "Missing cost never suppresses complete
    # revenue", and cost/profit/margin require the *identical* complete financial
    # population -- so all three refuse together while revenue and units stand.
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, Decimal("600.00"), 15,
              "INV-4002", "S1", "P2", "C1", None, Decimal("0.00"), "T1"),
)
PARTIAL_NULL_EXPECTED = {
    # revenue = 400.00 + 600.00 = 1000.00, complete over both rows.
    "revenue": Decimal("1000.00"),
    # units = 10 + 15 = 25.
    "units": Decimal("25"),
    # cost, gross_profit, gross_margin all refuse: `financial_complete_revenue_cost`
    # is not complete, and `RRA-004` gives headline cost "no partial-coverage
    # vocabulary".
    "cost": None,
    "gross_profit": None,
    "gross_margin": None,
}
"""_RED: production returns cost "220.00", gross_profit "180.00",
gross_margin "0.4500", against an oracle that refuses all three.

Empirically confirmed. Production sums the one present cost (220.00) and then
computes gross profit over the *matched* rows only -- 400.00 - 220.00 = 180.00 --
and margin 180.00 / 400.00 = 0.4500, disclosing it with the
`derived_metrics_use_matched_rows` caveat. Revenue "1000.00" and units "25" agree
with the oracle, as they must: `RRA-004` says "Missing cost never suppresses
complete revenue", and both of those columns are complete here.

The violated rule is `RRA-004`'s population contract: "Headline revenue, cost,
units, discounts, and returns have no partial-coverage vocabulary and therefore
refuse when a required admitted column has gaps." A caveat is not a population. A
customer reading cost 220.00 beside revenue 1000.00 reads a 78% margin business.
"""


ZERO_MARGIN_DENOMINATOR_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("300.00"), 6,
              "INV-5001", "S1", "P1", "C1", Decimal("180.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 11), EVENT_RETURN, STATUS_POSTED, Decimal("-300.00"), -6,
              "INV-5002", "S1", "P1", "C1", Decimal("-170.00"), None, "T1"),
)
ZERO_MARGIN_EXPECTED = {
    # matched revenue = 300.00 - 300.00 = 0.00
    # matched cost    = 180.00 - 170.00 = 10.00
    # gross profit    = 0.00 - 10.00 = -10.00   -- negative, and stated.
    # gross margin    = refused: denominator <= 0.
    "cost": Decimal("10.00"),
    "gross_profit": Decimal("-10.00"),
    "gross_margin": None,
}
NEGATIVE_MARGIN_DENOMINATOR_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("300.00"), 6,
              "INV-6001", "S1", "P1", "C1", Decimal("180.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 11), EVENT_RETURN, STATUS_POSTED, Decimal("-500.00"), -10,
              "INV-6002", "S1", "P1", "C1", Decimal("-290.00"), None, "T1"),
)
NEGATIVE_MARGIN_EXPECTED = {
    # matched revenue = 300.00 - 500.00 = -200.00
    # matched cost    = 180.00 - 290.00 = -110.00
    # gross profit    = -200.00 - (-110.00) = -90.00
    # gross margin    = refused: denominator < 0.
    "cost": Decimal("-110.00"),
    "gross_profit": Decimal("-90.00"),
    "gross_margin": None,
}
"""Zero and negative gross-margin denominators -- regression proof 7.

`RRA-004`: "Gross margin alone refuses at a zero or negative matched revenue
denominator while complete cost and gross profit survive." Both cases keep cost
and profit and refuse only the ratio, which is the conditional-survival property.

_RED, zero denominator: production returns cost "10.00", gross_profit "-10.00",
and refuses gross_margin with `zero_denominator`. It agrees on all three. The
`_add_ratio` helper already refuses a zero denominator, and negative cost and
profit already survive. (It also refuses ASP with `zero_denominator` on this
dataset, because net units are 6 - 6 = 0. Correct under `RRA-004`'s "unit
denominator `<= 0`" rule, and independent of the margin question.)

_RED, negative denominator: production returns cost "-110.00",
gross_profit "-90.00", and gross_margin "0.4500".

The negative case is the gap. Production computes -90.00 / -200.00 = 0.45 and
publishes it as a 45% margin. `_add_ratio` guards `== 0` only, so a
sign-cancelling division survives. `RRA-004` requires refusal at a denominator
`<= 0`, and `RRA-008` gives the reason: against a negative base a percentage
"misleads -- a shrinking loss reads as growth". A period of net returns is
reported as the healthiest margin in the dataset.
"""


ALLOCATED_DISCOUNT_ROWS: tuple[OracleRow, ...] = (
    # One invoice carrying a 30.00 invoice-level promotion allocated across its
    # three lines exactly once -- 12.00 + 9.00 + 9.00 -- plus per-line discounts
    # of 10.00 and 5.00. `RRA-003`: discount "includes line, allocated invoice,
    # promotion, loyalty, and markdown discounts only when the source already
    # prevents overlap and allocates every invoice-level amount exactly once".
    #
    # The `discount` column carries the per-row total the source already
    # allocated. It is additive and non-negative, which is the whole admissibility
    # test; an unallocated invoice-level amount repeated on every line would be
    # the "repeated invoice total" `RRA-003` refuses, and is not what these rows
    # carry.
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("400.00"), 8,
              "INV-F001", "S1", "P1", "C1", Decimal("220.00"),
              Decimal("22.00"), "T1"),
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("300.00"), 6,
              "INV-F001", "S1", "P2", "C1", Decimal("165.00"),
              Decimal("14.00"), "T1"),
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("200.00"), 4,
              "INV-F001", "S1", "P3", "C2", Decimal("110.00"),
              Decimal("9.00"), "T1"),
)
ALLOCATED_DISCOUNT_EXPECTED = {
    # discounts = sum(non-negative sale discount) = 22.00 + 14.00 + 9.00 = 45.00
    #   of which the allocated invoice-level promotion is 12.00 + 9.00 + 9.00
    #   = 30.00, allocated exactly once, and the per-line part is
    #   10.00 + 5.00 + 0.00 = 15.00.
    "discount": Decimal("45.00"),
    "allocated_invoice_component": Decimal("30.00"),
    "line_component": Decimal("15.00"),
    # `RRA-003`: discount "never changes governed revenue, which is already net".
    # revenue = 400.00 + 300.00 + 200.00 = 900.00, unreduced by the 45.00.
    "revenue": Decimal("900.00"),
    # Three lines, one canonical transaction key.
    "transactions": Decimal("1"),
}
"""Allocated discounts -- brief bullet 3's remaining shape.

_RED: production returns discount "45.00" and revenue "900.00" and agrees on both.

Empirically confirmed. `_measures` maps `discount_amount` and `_sum_decimal` adds
the column, and nothing anywhere subtracts discount from revenue -- which is
correct, since `RRA-003` makes revenue already net.

Recorded as an agreement with one gap beside it. The two component literals,
`allocated_invoice_component` 30.00 and `line_component` 15.00, have no production
counterpart: the package carries a single `discount` total and no evidence of how
it decomposes, so nothing proves the invoice-level amount was allocated exactly
once rather than repeated on each line. `RRA-003` makes that the admissibility
test -- "a bare discount, rate, percentage, repeated invoice total, or overlapping
component set is refused" -- and current code cannot distinguish an allocated
30.00 from a 30.00 stamped on all three lines, which would sum to 90.00 and be
accepted just as readily. The components are stated so a slice adding allocation
evidence has the arithmetic to check.
"""


DUPLICATE_SIGNATURE_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("250.00"), 5,
              "INV-7001", "S1", "P1", "C1", Decimal("140.00"), Decimal("0.00"), "T1"),
    # Byte-identical to the row above in every admitted identity, dimension and
    # measure field. `RRA-003`: "Without an event key, a repeated canonical row
    # signature has the same effect because a legitimate repeated line cannot be
    # distinguished from a duplicated extract."
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("250.00"), 5,
              "INV-7001", "S1", "P1", "C1", Decimal("140.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, Decimal("300.00"), 6,
              "INV-7002", "S1", "P2", "C1", Decimal("165.00"), Decimal("0.00"), "T1"),
)
DUPLICATE_SIGNATURE_EXPECTED = {
    # Every additive or distinct-transaction result that could include the
    # repeated signature refuses. That is revenue, units, cost, profit, margin,
    # transactions, AOV, ASP and items per transaction -- the repeated row is in
    # every one of those populations.
    "revenue": None,
    "units": None,
    "transactions": None,
    "average_order_value": None,
    "average_selling_price": None,
}
"""_RED: production returns revenue "800.00", units "16", transactions "2",
AOV "400.00", ASP "50.00", cost "445.00", gross_profit "355.00",
gross_margin "0.4438" -- every one of them stated, none refused.

Empirically confirmed. Production emits the `duplicate_rows_present` caveat and
publishes the doubled figures anyway: 250.00 counted twice gives 800.00 where the
un-duplicated data would give 550.00.

The violated rule is `RRA-003`'s event-identity contract: "A repeated event key,
whether identical or conflicting, refuses every additive or distinct-transaction
result that could include it." A caveat is not a refusal. This is the single
largest magnitude error in the oracle -- a 45% revenue overstatement published as
a governed fact.
"""


# ---------------------------------------------------------------------------
# Case 3: adversarial data.
# ---------------------------------------------------------------------------

REPEATED_INVOICE_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("100.00"), 2,
              "INV-1", "S1", "P1", "C1", Decimal("55.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("200.00"), 4,
              "INV-2", "S1", "P2", "C1", Decimal("110.00"), Decimal("0.00"), "T1"),
    # Same bare invoice numbers, different store. Each POS numbers its own
    # receipts from 1, so this is the ordinary case rather than a corruption.
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("300.00"), 6,
              "INV-1", "S2", "P1", "C1", Decimal("165.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("400.00"), 8,
              "INV-2", "S2", "P3", "C2", Decimal("220.00"), Decimal("0.00"), "T1"),
)
REPEATED_INVOICE_EXPECTED = {
    # Canonical keys, per `RRA-003`: source identifier plus store, business date
    # and terminal.
    #   INV-1|S1|2026-03-04|T1
    #   INV-2|S1|2026-03-04|T1
    #   INV-1|S2|2026-03-04|T1
    #   INV-2|S2|2026-03-04|T1
    # -> 4 distinct transactions.
    "transactions": Decimal("4"),
    # revenue = 100.00 + 200.00 + 300.00 + 400.00 = 1000.00
    "revenue": Decimal("1000.00"),
    # units = 2 + 4 + 6 + 8 = 20
    "units": Decimal("20"),
    # AOV = 1000.00 / 4 = 250.00
    "average_order_value": Decimal("250.00"),
    # items per transaction = 20 / 4 = 5.0000
    "basket_items_per_transaction": Decimal("5.0000"),
}
"""Repeated invoice IDs in different stores -- regression proof 5.

_RED: production returns transactions "2", AOV "500.00", items per transaction
"10.0000", against an oracle of 4, 250.00 and 5.0000.

Empirically confirmed. `_distinct` in `facts.py` is
`len({v for v in values if v is not None})` over the bare mapped identifier, so
INV-1 from S1 and INV-1 from S2 collapse into one. Two stores' trading is reported
as two transactions.

The violated rule is `RRA-003`'s canonical-transaction-key contract: "A bare
source transaction identifier qualifies only when its recorded source contract
proves package-wide uniqueness. Otherwise the canonical key is an admitted
composite containing the source identifier and every field required for
uniqueness, normally store, business date, and terminal or register." No contract
is recorded here, so the composite is required and production uses the bare one.

Every transaction-denominated metric inherits the error at exactly 2x: AOV doubles,
items per transaction doubles. This is the defect `V-mapping` exists to correct.
"""


MISSING_TRANSACTION_IDENTITY_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("100.00"), 2,
              "INV-8001", "S1", "P1", "C1", Decimal("55.00"), Decimal("0.00"), "T1"),
    # No store, so the composite key cannot be formed. `RRA-003`: "Missing
    # components or collisions refuse transactions, AOV, items per transaction,
    # and attach rate."
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, Decimal("200.00"), 4,
              "INV-8002", None, "P2", "C1", Decimal("110.00"), Decimal("0.00"), "T1"),
)
MISSING_TRANSACTION_IDENTITY_EXPECTED = {
    # Independently proven facts survive: `RRA-004` requires "Every refusal leaves
    # facts whose own semantics and population remain independently proven."
    "revenue": Decimal("300.00"),
    "units": Decimal("6"),
    # The four transaction-dependent metrics refuse.
    "transactions": None,
    "average_order_value": None,
    "basket_items_per_transaction": None,
    "basket_attach_rate": None,
    # ASP does not depend on the transaction key: 300.00 / 6 = 50.00.
    "average_selling_price": Decimal("50.00"),
}
"""Four refusals owed, none made, independent metrics standing -- regression proof 9.

_RED: **all four** transaction-denominated metrics publish where the oracle
refuses. Re-measured on `9646223` through `ReportBundle.of`, which is
the customer surface -- `FactPackage.value` answers only for `rra004` facts and
returns `None` for an `rra008` family metric whether it refused or was never a
package fact at all, so it cannot be read as a refusal:

| metric | published | oracle |
|---|---|---|
| `transactions` | `2` | refuses |
| `average_order_value` | `150.00` | refuses |
| `basket_items_per_transaction` | `3.0000` | refuses |
| `basket_attach_rate` | `1.0000`, and `0.5000` twice | refuses |

Attach rate is the sharpest: it asserts that *every* transaction attached, over a
package whose canonical key cannot be formed -- and it reaches `ReportBundle.figures`
three times, the headline plus one bar per dimension value, so a fix refuses the
family and not one figure. The same four mismatch at `7088749`, so no `#310` slice
caused or corrected any of them.

`basket._identified` is the gate that should stop this, and it passes: it asks only
whether a `transactions` fact exists, and one does -- with the wrong value. So a
single fix at the canonical key closes all four.

The `_EXPECTED` literals below reach no assertion -- one of seven such dicts in
this module with no consumer under `tests/` -- so the oracle's own literals never
fired on this. `#295` carries both the fix and the obligation to consume them.

`transaction_identifiers_complete` in `_measures` checks
only whether the mapped *identifier* column has gaps. Both invoice numbers are
present, so production is satisfied and counts two -- while the store component
the canonical key needs is missing on one row and no composite can be formed.

The violated rule is `RRA-003`: the canonical key needs "every field required for
uniqueness", and a missing component refuses.

Revenue 300.00, units 6 and ASP 50.00 agree, which is the survival half of the
proof: `RRA-004` requires "every refusal leaves facts whose own semantics and
population remain independently proven", so a fix must refuse exactly the four and
leave these three standing. Nothing here establishes that production's breadth is
right -- on this package it refuses none of the four, so its breadth is untested
rather than correct.
"""


MISSING_PRODUCT_ZERO_REVENUE_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("400.00"), 8,
              "INV-9001", "S1", "P1", "C1", Decimal("220.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, Decimal("600.00"), 12,
              "INV-9002", "S1", "P2", "C1", Decimal("330.00"), Decimal("0.00"), "T1"),
    # A zero-revenue sale row with no product and no category. A free-gift or
    # price-override line. `RRA-008`: "A missing dimension on any eligible posted
    # sale, including a zero-revenue row, refuses that dimension."
    OracleRow(date(2026, 3, 18), EVENT_SALE, STATUS_POSTED, Decimal("0.00"), 1,
              "INV-9003", "S1", None, None, Decimal("0.00"), Decimal("0.00"), "T1"),
)
MISSING_PRODUCT_ZERO_REVENUE_EXPECTED = {
    # Product and category concentration and attach both refuse -- the whole
    # family for each dimension, not just the affected bucket.
    "concentration": None,
    "basket_attach_rate": None,
    # Everything not dimension-dependent stands.
    # revenue = 400.00 + 600.00 + 0.00 = 1000.00
    "revenue": Decimal("1000.00"),
    # units = 8 + 12 + 1 = 21
    "units": Decimal("21"),
    "transactions": Decimal("3"),
}
"""Missing product/category on a zero-revenue sale row -- regression proof 4.

_RED: production returns concentration distinct_values "3", ranked_values "3",
a curve of ('0.6000', '1.0000', '1.0000'), top_decile_share "0.6000" and
top_quartile_share "0.6000" -- against an oracle that refuses the family entirely.
For attach it returns two rates of "0.3333" each, over a denominator of 3.

Empirically confirmed, and note the correction to a natural first guess: the
`unlabelled` bucket IS ranked. `build_comparison` groups the missing product
under the `None` key, `_display_label` renders it `unlabelled`, and `_curve`
ranks every accumulator whose measure is *present* -- an explicit 0.00 is
present, so the row with no product joins the ranking as a third value and forms
a flat tail. `RRA-008` forbids exactly this: "`None` and synthetic `unlabelled`
are never ranked."

For attach, `basket._attachable` does exclude `unlabelled` from receiving a rate,
but the transaction it contains stays in `Comparison.distinct_transactions`. So
P1 and P2 are each reported at 1/3 = 0.3333 when the dimension-complete
population `RRA-008` requires does not exist at all. Every published rate is
understated by the unattributable transaction sitting in its denominator --
"silently entering only the denominator" in the specification's own words.

Two rules violated. `RRA-008`, concentration: "A missing dimension on any eligible
posted sale, including a zero-revenue row, refuses that dimension. `None` and
synthetic `unlabelled` are never ranked." And attach: "Every eligible sale row
must carry the dimension value; one missing value refuses that dimension's entire
attach family rather than silently entering only the denominator" -- which is
exactly and only what current code does.

Note this is *not* the zero-revenue tail rule. A zero-revenue row with a product
value stays distinct, ranks last and forms a flat tail; see
`ZERO_REVENUE_PRODUCT_ROWS`. The refusal here is caused by the missing dimension,
not by the zero.
"""


ZERO_REVENUE_PRODUCT_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("400.00"), 8,
              "INV-A001", "S1", "P1", "C1", Decimal("220.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, Decimal("600.00"), 12,
              "INV-A002", "S1", "P2", "C1", Decimal("330.00"), Decimal("0.00"), "T1"),
    # Zero revenue, but the product IS named. A genuine zero, not a gap.
    OracleRow(date(2026, 3, 18), EVENT_SALE, STATUS_POSTED, Decimal("0.00"), 1,
              "INV-A003", "S1", "P3", "C2", Decimal("0.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 25), EVENT_SALE, STATUS_POSTED, Decimal("0.00"), 1,
              "INV-A004", "S1", "P4", "C2", Decimal("0.00"), Decimal("0.00"), "T1"),
)
ZERO_REVENUE_PRODUCT_EXPECTED = {
    # `RRA-008`: "Zero-revenue values remain distinct, rank last, and form a flat
    # tail. They remain in distinct count `n`, affect the discrete cutoff, and
    # have their count disclosed in audit evidence."
    #   ranked order: P2 = 600.00, P1 = 400.00, then P3 = 0.00 and P4 = 0.00.
    #   total ranked revenue = 1000.00
    #   rank 1: 600.00 / 1000.00 = 0.6000
    #   rank 2: 1000.00 / 1000.00 = 1.0000
    #   rank 3: 1000.00 / 1000.00 = 1.0000   (flat tail)
    #   rank 4: 1000.00 / 1000.00 = 1.0000   (flat tail)
    "distinct_values": Decimal("4"),
    "ranked_values": Decimal("4"),
    "curve": (Decimal("0.6000"), Decimal("1.0000"),
              Decimal("1.0000"), Decimal("1.0000")),
    "zero_revenue_values": Decimal("2"),
    # decile cutoff = ceil(4 / 10) = 1 -> share after 1 value = 0.6000
    "top_decile_share": Decimal("0.6000"),
    # quartile cutoff = ceil(4 / 4) = 1 -> share after 1 value = 0.6000
    "top_quartile_share": Decimal("0.6000"),
}
"""_RED: production returns distinct_values "4", ranked_values "4", a curve of
('0.6000', '1.0000', '1.0000', '1.0000'), and both shares "0.6000" -- agreeing
with the oracle on every number.

Empirically confirmed. `_curve` in `aggregates.py` builds `ranked` from
`[entry.total for entry in ordered if entry.present]`, and `present` is set
whenever a non-`None` value was added -- an explicit `0.00` qualifies. So both
zero-revenue products stay in the ranking, sort last by `-total`, and produce the
flat tail `RRA-008` describes. The ceiling cutoffs are computed over n = 4, and
ceil(4/10) = ceil(4/4) = 1 gives 0.6000 for both.

Recorded as an agreement, and it is the load-bearing contrast with
`MISSING_PRODUCT_ZERO_REVENUE_ROWS`. The two datasets differ in one field -- here
the zero-revenue row names a product, there it does not -- and `RRA-008` gives
them opposite outcomes: this one ranks and forms a tail, that one refuses the
dimension. Current code treats them identically, which is why it gets this one
right and that one wrong. A slice that fixes the missing-dimension refusal by
dropping zero-revenue values from the ranking would break this case.

One literal above has no production counterpart. `zero_revenue_values` = 2 is the
disclosure `RRA-008` requires -- zero-revenue values "have their count disclosed
in audit evidence and the business caveat" -- and `ConcentrationCurve` carries
only `distinct_values`, `ranked_values` and `shares`. There is no field to
compare against, so it is recorded as a missing field rather than a wrong number.
"""


NO_EXACT_PRIOR_PERIOD_ROWS: tuple[OracleRow, ...] = (
    OracleRow(date(2026, 1, 15), EVENT_SALE, STATUS_POSTED, Decimal("500.00"), 10,
              "INV-B001", "S1", "P1", "C1", Decimal("275.00"), Decimal("0.00"), "T1"),
    # February is skipped entirely. `RRA-008`: "Nearest observed buckets never
    # substitute for missing exact counterparts."
    OracleRow(date(2026, 3, 15), EVENT_SALE, STATUS_POSTED, Decimal("700.00"), 14,
              "INV-B002", "S1", "P2", "C1", Decimal("385.00"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 5, 15), EVENT_SALE, STATUS_POSTED, Decimal("900.00"), 18,
              "INV-B003", "S1", "P3", "C2", Decimal("495.00"), Decimal("0.00"), "T1"),
)
NO_EXACT_PRIOR_PERIOD_EXPECTED = {
    # March's immediately preceding calendar period is February, which is absent.
    # PoP therefore refuses, and so does the growth decomposition that consumes
    # the same window.
    "revenue_delta_absolute": None,
    "revenue_delta_percent": None,
    "growth_revenue_change": None,
    # The observed trend itself survives: `RRA-008` says "observed trends may
    # survive but completeness-dependent comparison and growth refuse".
    "revenue": Decimal("2100.00"),
}
"""_RED: production refuses PoP with `prior_window_absent` and agrees.

Empirically confirmed. `windows.compared_labels` finds the settled bucket 2026-03,
computes its predecessor label 2026-02, finds it absent from the series, and
returns `None`. The refusal reason is the right one for the right reason.

Recorded as an agreement, and it is a load-bearing one: `V-comparison` must not
lose this behaviour while fixing the settled-window rule. A correction that
replaced label lookup with positional lookup would compare March against January
and reconcile perfectly, which is the defect `windows.py`'s own docstring says it
was written to prevent.
"""


DISJOINT_REVENUE_UNITS_ROWS: tuple[OracleRow, ...] = (
    # Revenue with no units.
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("500.00"), None,
              "INV-C001", "S1", "P1", "C1", Decimal("275.00"), Decimal("0.00"), "T1"),
    # Units with no revenue.
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, None, 10,
              "INV-C002", "S1", "P2", "C1", Decimal("110.00"), Decimal("0.00"), "T1"),
)
DISJOINT_REVENUE_UNITS_EXPECTED = {
    # Both headlines refuse: `RRA-004` gives revenue and units no partial-coverage
    # vocabulary, and each has a gap.
    "revenue": None,
    "units": None,
    # ASP requires `sales_complete_revenue_units` -- "complete revenue, strictly
    # positive units, and no unmatched eligible row". Both rows are unmatched, so
    # the intersection is empty and ASP refuses on a zero denominator as well as
    # on population.
    "average_selling_price": None,
}
"""_RED: production returns revenue "500.00", units "10", and refuses ASP with
`required_input_unavailable`.

Empirically confirmed. `_sum_decimal` skips `None` and sums what is left, so a
column with one gap reports the partial sum as the headline. `_matched` then finds
an empty intersection for ASP -- neither row carries both measures -- and refuses
it, correctly and for the right reason.

The violated rule is `RRA-004`'s partial-coverage prohibition, the same one
`PARTIAL_NULL_ROWS` exercises on cost. Here it is starker: revenue 500.00 is
published as the dataset's revenue when the other row's revenue is simply unknown,
and units 10 likewise. ASP's refusal is correct and must survive the correction.

Production also publishes concentration over this dataset with distinct_values 2
and ranked_values 1 -- ranking the single product that has revenue and reporting
its share as 1.0000. Two products exist in these two rows, P1 and P2, and only
P1 carries revenue; `_curve` ranks the accumulators whose measure is `present`,
so one of the two distinct values is ranked. `RRA-008` requires "complete sale
revenue" over the ranked
set, so the whole curve should refuse; a single product holding 100% of a revenue
total that is itself incomplete is the most misleading number in the oracle. That
gap belongs to `V-concentration` and is recorded here rather than given its own
dataset, because it is caused by the same incomplete revenue column.
"""


HIGH_PRECISION_ROWS: tuple[OracleRow, ...] = (
    # **Eight significant digits, not nine.** A first draft used 100.123456 and
    # 55.111111, and `build_profile` marked both columns `personal_data_risk`:
    # nine-digit runs look like telephone numbers to the personal-value
    # heuristic, so `build_mapping` dropped the columns and production refused
    # revenue outright. That is a setup failure, not the intended one -- the case
    # exists to measure rounding at six decimal places, and a refused revenue
    # measures the profiler instead. Verified with `is_personal_value`:
    # "100.123456" is True, "10.123456" is False.
    OracleRow(date(2026, 3, 4), EVENT_SALE, STATUS_POSTED, Decimal("10.123456"), 3,
              "INV-D001", "S1", "P1", "C1", Decimal("5.111111"), Decimal("0.00"), "T1"),
    OracleRow(date(2026, 3, 11), EVENT_SALE, STATUS_POSTED, Decimal("20.654321"), 4,
              "INV-D002", "S1", "P2", "C1", Decimal("11.222222"), Decimal("0.00"), "T1"),
)
HIGH_PRECISION_EXPECTED = {
    # `RRA-004`: monetary values use "the largest admitted monetary input scale,
    # with a minimum of two and maximum of six decimal places". Six here.
    "monetary_precision": 6,
    # revenue = 10.123456 + 20.654321 = 30.777777
    "revenue": Decimal("30.777777"),
    # cost = 5.111111 + 11.222222 = 16.333333
    "cost": Decimal("16.333333"),
    # gross profit = 30.777777 - 16.333333 = 14.444444
    "gross_profit": Decimal("14.444444"),
    # gross margin = 14.444444 / 30.777777 = 0.46931407684...
    #   -> half-even 4 dp -> 0.4693
    "gross_margin": Decimal("0.4693"),
    # ASP = 30.777777 / 7 = 4.39682528571... -> half-even 6 dp -> 4.396825
    "average_selling_price": Decimal("4.396825"),
    # AOV = 30.777777 / 2 = 15.3888885 exactly -- a genuine half-even tie.
    # The digit beyond the retained place is 5 with nothing after it; the
    # retained digit is 8, already even, so half-even keeps it. 15.388888.
    # Round-half-up would give 15.388889, and so would binary floating point.
    "average_order_value": Decimal("15.388888"),
}
"""_RED: production returns every one of these values and agrees.

Empirically confirmed, including the half-even tie on AOV: production returns
"15.388888", not "15.388889". `_decimal_values` tracks the maximum input scale,
`_quantize` uses `Decimal.quantize` whose default is `ROUND_HALF_EVEN`, and the
arithmetic runs at `ARITHMETIC_PRECISION = 60`.

Recorded as an agreement because it is the property most easily lost. `V-formula`
changes how these numbers are computed; if a rewrite introduces a float anywhere,
this tie is where it shows first -- 15.3888885 in binary floating point is not a
tie at all and rounds up.
"""


DISPLAY_TRUNCATION_ROWS: tuple[OracleRow, ...] = tuple(
    OracleRow(
        date(2026, 3, 1 + (index % 28)),
        EVENT_SALE,
        STATUS_POSTED,
        # Revenue descends by rank so the ranking is unambiguous and hand-checkable:
        # value i (0-based) has revenue (25 - i) * 100.00, i.e. 2500.00 down to 100.00.
        Decimal(f"{(25 - index) * 100}.00"),
        1,
        f"INV-E{index:03d}",
        "S1",
        f"P{index:02d}",
        "C1",
        Decimal(f"{(25 - index) * 50}.00"),
        Decimal("0.00"),
        "T1",
    )
    for index in range(25)
)
DISPLAY_TRUNCATION_EXPECTED = {
    # 25 distinct products, all with revenue, against MAX_COMPARISON_BUCKETS = 20.
    # The authoritative curve spans all 25; display truncation changes no
    # numerator, denominator, rank or cutoff.
    #
    # total ranked revenue = 100.00 * (25 + 24 + ... + 1)
    #                      = 100.00 * (25 * 26 / 2) = 100.00 * 325 = 32500.00
    "distinct_values": Decimal("25"),
    "ranked_values": Decimal("25"),
    # decile cutoff = ceil(25 / 10) = ceil(2.5) = 3 ranked values.
    # cumulative after 3 = (2500 + 2400 + 2300).00 = 7200.00
    #   7200.00 / 32500.00 = 0.2215384615... -> half-even 4 dp -> 0.2215
    "top_decile_share": Decimal("0.2215"),
    # quartile cutoff = ceil(25 / 4) = ceil(6.25) = 7 ranked values.
    # cumulative after 7 = 2500+2400+2300+2200+2100+2000+1900 = 15400.00
    #   15400.00 / 32500.00 = 0.4738461538... -> half-even 4 dp -> 0.4738
    "top_quartile_share": Decimal("0.4738"),
    # Presentation sampling keeps at most 100 points; 25 is under the bound, so
    # the full curve is presented unsampled and no sampling caveat is carried.
    "presentation_points": Decimal("25"),
    "sampling_applied": False,
}
"""Display truncation, and the ceiling cutoffs it must not disturb.

_RED: production returns distinct_values "25", ranked_values "25",
top_decile_share "0.2215", top_quartile_share "0.4738" -- and agrees on all four.

Empirically confirmed. This is exactly the defect `APP-014` already fixed:
`build_comparison` derives the curve *before* applying `limit`, so the twenty-five
values survive truncation into `ConcentrationCurve` even though only twenty-one
display buckets are published. `concentration._leading` implements the ceiling.

Recorded as an agreement, and the reason is in `concentration.py`'s own docstring:
"a test asserting `distinct.value == '57'` would have passed on exactly that
fabrication". `V-concentration` must not regress it.

The display side is visible in the same run: `revenue_by_product` publishes twenty
ranked buckets plus one `other` holding 1500.00 over five rows, and records
`truncated_values` 5 -- while the retained curve still spans all twenty-five. That
is the property `RRA-008` states as "Display truncation changes no numerator or
denominator", and it holds today.

The `sampling_applied` literal has no production counterpart -- there is no
sampling implementation and no sampling caveat anywhere in `src/` -- so it states
the expected behaviour for a slice to build against rather than a current value to
differ from. At twenty-five points it is under the hundred-point bound either way,
so this dataset cannot distinguish a correct sampler from an absent one; it fixes
only that no sampling may occur here.
"""


# ---------------------------------------------------------------------------
# Regression proofs with no current production counterpart.
# ---------------------------------------------------------------------------

MANIFEST_ABSENT_EXPECTED = {
    # `RRA-003`: "Without a valid manifest, observed trends may survive, but
    # completeness-dependent period comparisons and growth refuse."
    "revenue": Decimal("1380.00"),
    "units": Decimal("37"),
    "revenue_by_period": "survives",
    "revenue_delta_absolute": None,
    "revenue_delta_percent": None,
    "growth_revenue_change": None,
}
"""Missing manifest refusal -- regression proof 1, first half.

_RED: production has no coverage manifest concept in `build_fact_package` at all.
`facts.py` never imports `khepri.rra.coverage`, and `CoverageManifest` reaches no
calculation. So production's comparison decision is made entirely from bucket
adjacency, and on a dataset with three or more months it will publish a delta with
no manifest anywhere in the pipeline.

The violated rule is `RRA-003`'s "Coverage-manifest confirmation" clause:
"Completeness-dependent comparisons require a separate source-provided or
explicitly operator-attested coverage manifest." Current code requires nothing.
The gap is a missing precondition, not a wrong number, so this expectation states
which results must refuse and which must survive rather than naming a literal that
production could return.
"""

ATTESTED_ZERO_ACTIVITY_EXPECTED = {
    # A store closed for a proven day contributes zero, and the period stays
    # complete. `RRA-003`: "An attested closure proves complete zero activity; an
    # extraction gap does not." `RRA-008`: "Attested store closure is complete
    # zero activity. An extraction gap is not coverage."
    #
    # Same rows as CLEAN_ROWS, with 2026-01-15 attested closed for S2. January's
    # totals are unchanged -- 630.00 over 17 units -- because a closed day
    # genuinely contributed nothing, and the month remains a complete full
    # calendar period eligible for comparison.
    "2026-01_revenue": Decimal("630.00"),
    "2026-01_complete": True,
    "comparison_admitted": True,
    # The mirror case: the same missing day recorded as an extraction gap instead
    # refuses the comparison, because absence of events is not proof of absence of
    # activity.
    "extraction_gap_comparison_admitted": False,
}
"""Attested zero-activity acceptance -- regression proof 1, second half.

_RED: no production counterpart. `admits_completeness` in `coverage.py` implements
exactly this distinction already -- `_every_day_proven` requires each day attested
and not a gap, and its docstring records that a closure "is already a covered pair,
and it proves zero activity rather than missing activity". The function is correct
and unreachable: nothing in `facts.py` or `analysis/` calls it.

So the gap is wiring, not arithmetic. The literals above state the behaviour the
comparison family must exhibit once it consults the manifest. No current value can
be recorded because no current code path asks the question.
"""

PARTIAL_PREFIX_PROJECTION_EXPECTED = {
    # `RRA-008`: "An incomplete current month may compare the contiguous prefix
    # from day 1 through its last proven complete day `k` with the prior period's
    # deterministic day-`1..k` structural coverage projection."
    #
    # Prior month 2026-04 complete, 30 days. Current month 2026-05 proven complete
    # only through day 10, so k = 10.
    #   current prefix revenue (2026-05-01 .. 2026-05-10) = 300.00
    #   prior projection revenue (2026-04-01 .. 2026-04-10) = 250.00
    #   absolute delta = 300.00 - 250.00 = 50.00
    #   percentage delta = 50.00 / 250.00 = 0.2000
    "k": 10,
    "current_prefix_revenue": Decimal("300.00"),
    "prior_projection_revenue": Decimal("250.00"),
    "revenue_delta_absolute": Decimal("50.00"),
    "revenue_delta_percent": Decimal("0.2000"),
    # The projection restricts the parent daily bases and preserves parent
    # identities; it "never infers missing coverage, synthesizes an unproven day,
    # or changes a parent measure value". The prior month's own full total is
    # unchanged by the projection existing.
    "prior_full_month_revenue_unchanged": True,
    # The bilingual partial-window caveat is required by `RRA-009`.
    "partial_window_caveat_required": True,
}
"""Partial current prefix against a manifest-proven projection -- regression proof 2.

_RED: no production counterpart. There is no prefix projection in `src/`. Grepping
for a projection of a structural coverage signature returns nothing, and
`windows.settled` takes the opposite approach -- it *excludes* the last bucket
precisely because "nothing here can tell a whole month from a partial one".

That exclusion is the defect this proof measures. `RRA-008` says a partial current
month can be compared, against a day-1..k projection of the prior period, when the
manifest proves that prefix complete. Current code cannot do it and instead throws
away the most recent month on every dataset -- which is why `CLEAN_COMPARISON`
above refuses at all.

The literals state the arithmetic a slice must produce. They are derived from the
stated prefix totals rather than from rows, because the rows that would carry them
depend on a daily-basis structure that does not exist yet; a dataset invented to
match an unbuilt shape would constrain the slice's design rather than its answers.
"""

STORE_MISMATCH_EXPECTED = {
    # `RRA-008`: complete full calendar periods are structurally compatible only
    # when they have "the same governed aggregate scope or complete admitted store
    # set and the same event-kind and status filters", and "scope-mismatched,
    # store-mismatched, or filter-mismatched structures refuse".
    #
    # Prior month attested over {S1, S2}; current month attested over {S1, S2, S3}
    # after a third branch opened. Both months are individually complete. They are
    # still incompatible, because the populations are not the same set of stores.
    "prior_store_set": ("S1", "S2"),
    "current_store_set": ("S1", "S2", "S3"),
    "comparison_admitted": False,
    "growth_admitted": False,
    # The refusal is narrow: each month's own totals remain independently proven,
    # and `RRA-004` requires "Every refusal leaves facts whose own semantics and
    # population remain independently proven."
    "prior_revenue_survives": True,
    "current_revenue_survives": True,
    # The mirror case that must NOT refuse: identical store sets, different day
    # counts. That is `NATURAL_MONTH_LENGTH_EXPECTED` below.
    "same_store_set_different_lengths_admitted": True,
}
"""Store mismatch -- brief bullet 4's remaining shape.

_RED: no production counterpart, and the reason is the same wiring gap as the
other manifest proofs. Nothing in `facts.py` or `analysis/` reads a store roster
when deciding comparability. `windows.compared_labels` looks only at bucket labels
on the revenue trend, so a month covering three stores compares against a month
covering two without anything noticing, and the delta reports a new branch's
entire revenue as growth.

That number would be arithmetically correct and analytically false, which is why
`RRA-008` puts the test on the *population* rather than on the arithmetic. There
is no current value to record because no current code path asks the question, so
this states which results must refuse and which must survive.

The last literal is the one that keeps the refusal honest in the other direction:
a slice implementing store-set equality must not reach for structural signature
equality generally, because natural month-length differences are explicitly
compatible. The two literals constrain each other.
"""

NATURAL_MONTH_LENGTH_EXPECTED = {
    # `RRA-008`: "Natural calendar length differences, including 28-, 29-, 30-, and
    # 31-day months, do not make otherwise complete full periods incompatible."
    #
    # Four complete full months, each with one sale row, all one store, all
    # sales-posted:
    #   2026-02 -> 28 days, revenue 280.00
    #   2028-02 -> 29 days (2028 is a leap year), revenue 290.00
    #   2026-04 -> 30 days, revenue 300.00
    #   2026-05 -> 31 days, revenue 310.00
    # Every pair is comparable. February-to-April is 300.00 - 280.00 = 20.00,
    # and 20.00 / 280.00 = 0.0714285714... -> half-even 4 dp -> 0.0714.
    "day_counts": (28, 29, 30, 31),
    "all_pairs_compatible": True,
    "feb_to_apr_delta_absolute": Decimal("20.00"),
    "feb_to_apr_delta_percent": Decimal("0.0714"),
    # A leap-day YoY has no counterpart and refuses. `RRA-008`: "Leap-day YoY
    # refuses when the prior calendar has no exact counterpart."
    "leap_day_yoy_admitted": False,
}
"""Natural 28/29/30/31-day full-period compatibility -- regression proof 3.

_RED: production admits month-to-month comparison without consulting day counts at
all, so it does not *reject* these pairs -- it never asks. The compatibility test
is manifest-based in `RRA-008` and adjacency-based in `windows.py`.

The measurable half is the leap-day rule, and there production already agrees:
`windows._day_label` catches `ValueError` when `2028-02-29` has no 2027
counterpart and returns `None`, refusing rather than substituting 28 February. Its
docstring records the reasoning. That behaviour must survive `V-comparison`.

The month-length half has no current value to record, because current code reaches
the right answer for the wrong reason: it compares any two adjacent month buckets
regardless of length, which happens to satisfy this clause while satisfying none of
the completeness clauses around it. A slice that adds manifest checks must not
reintroduce a length equality test while doing so.
"""


# ---------------------------------------------------------------------------
# Growth decomposition and the half-even rounding residual.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GrowthCase:
    """One growth decomposition, stated entirely as hand-derived literals.

    Every field is the published value under `RRA-008`'s exact rule, which the
    owner ruling of 2026-08-25 confirms and which replaces today's
    `growth.py:238` behaviour:

        published revenue delta = round(R_c - R_p)
        published volume effect = round(unrounded volume effect)
        published price effect  = published revenue delta - published volume effect
        rounding residual       = published price effect - round(unrounded price effect)

    `residual` is growth-family evidence under `rra008.growth.v2`, carried on the
    growth facts and surfaced through bundle audit representation. It is not a
    field on the persisted package document and `rra004.package.v3` is not widened
    to hold one -- the decision doc settles that, and the code reason is that the
    number does not exist when the package document is digested.

    **How a slice drives one of these.** A case names one compared pair, and
    `windows.settled` excludes the first and last bucket, so the pair must sit in
    the middle of at least four month buckets spanning more than 92 days. The
    harness used to establish every `current_production_outcome` below places the
    prior period on 2026-02-10 and the current on 2026-03-10, with padding rows on
    2026-01-02 and 2026-04-28 -- a 116-day span, so `granularity_for` yields
    months, and `compared_labels` selects exactly ('2026-03', '2026-02'). Padding
    revenue and units are arbitrary and do not enter any literal here.
    """

    name: str
    prior_revenue: Decimal
    prior_units: int
    current_revenue: Decimal
    current_units: int
    unrounded_volume: Decimal
    unrounded_price: Decimal
    published_delta: Decimal
    published_volume: Decimal
    published_price: Decimal
    residual: Decimal
    current_production_outcome: str


GROWTH_RESIDUAL_POSITIVE = GrowthCase(
    name="residual_plus_one_unit_of_last_place",
    # R_p = 100.02 over U_p = 4;  R_c = 125.03 over U_c = 5.  Precision 2.
    prior_revenue=Decimal("100.02"),
    prior_units=4,
    current_revenue=Decimal("125.03"),
    current_units=5,
    # ASP_p = 100.02 / 4 = 25.005          (terminates exactly)
    # ASP_c = 125.03 / 5 = 25.006          (terminates exactly)
    # volume effect = ASP_p * (U_c - U_p) = 25.005 * 1 = 25.005
    unrounded_volume=Decimal("25.005"),
    # price effect = U_c * (ASP_c - ASP_p) = 5 * (25.006 - 25.005)
    #              = 5 * 0.001 = 0.005
    unrounded_price=Decimal("0.005"),
    # Unrounded additivity, the algebraic invariant:
    #   25.005 + 0.005 = 25.010 = 125.03 - 100.02 = R_c - R_p.  Exact.
    #
    # published revenue delta = round(125.03 - 100.02) = round(25.01) = 25.01
    published_delta=Decimal("25.01"),
    # published volume effect = round(25.005).  Tie: the digit after the retained
    # place is 5 with nothing beyond it. Retained digit is 0, already even, so
    # half-even keeps it -> 25.00.
    published_volume=Decimal("25.00"),
    # published price effect = published delta - published volume
    #                        = 25.01 - 25.00 = 0.01
    published_price=Decimal("0.01"),
    # rounding residual = published price - round(unrounded price)
    #   round(0.005): tie again; retained digit is 0, even, so it keeps -> 0.00.
    #   residual = 0.01 - 0.00 = +0.01, exactly one unit of the published last
    #   place. Within the bound, so this is an ACCEPT.
    residual=Decimal("0.01"),
    current_production_outcome="refused: decomposition_not_additive",
)
"""_RED: production refuses the entire decomposition with
`decomposition_not_additive`, against an oracle that publishes 25.01 / 25.00 / 0.01
with a +0.01 residual.

Empirically confirmed by running `growth.derive` on a four-month dataset carrying
these two periods as its settled pair. `growth.py:_split` rounds both effects
independently -- `round(25.005) = 25.00` and `round(0.005) = 0.00` -- finds
`25.00 + 0.00 = 25.00 != 25.01`, and returns the refusal.

The violated rule is `RRA-008`'s published-value formula, quoted in full in
`GrowthCase` above. Price is not rounded independently: it is *derived* as
`published delta - published volume`, which makes displayed reconciliation exact by
construction, and the discrepancy is recorded as the residual instead of destroying
the section. The decision doc measures this at 74 of 2304 ordinary fixtures on
`main`, always off by exactly one unit of last place.
"""

GROWTH_RESIDUAL_NEGATIVE = GrowthCase(
    name="residual_minus_one_unit_of_last_place",
    # R_p = 100.05 over U_p = 6;  R_c = 116.76 over U_c = 7.  Precision 2.
    prior_revenue=Decimal("100.05"),
    prior_units=6,
    current_revenue=Decimal("116.76"),
    current_units=7,
    # ASP_p = 100.05 / 6 = 16.675           (terminates exactly)
    # ASP_c = 116.76 / 7 = 16.68            (terminates exactly)
    # volume effect = 16.675 * (7 - 6) = 16.675
    unrounded_volume=Decimal("16.675"),
    # price effect = 7 * (16.68 - 16.675) = 7 * 0.005 = 0.035
    unrounded_price=Decimal("0.035"),
    # Unrounded additivity: 16.675 + 0.035 = 16.710 = 116.76 - 100.05.  Exact.
    #
    # published revenue delta = round(16.71) = 16.71
    published_delta=Decimal("16.71"),
    # published volume = round(16.675). Tie; retained digit 7 is ODD, so half-even
    # rounds up to the even 8 -> 16.68.
    published_volume=Decimal("16.68"),
    # published price = 16.71 - 16.68 = 0.03
    published_price=Decimal("0.03"),
    # rounding residual = 0.03 - round(0.035).
    #   round(0.035): tie; retained digit 3 is odd, rounds up to even 4 -> 0.04.
    #   residual = 0.03 - 0.04 = -0.01.  One unit of last place, negative.
    #
    # The sign matters: it proves the residual is a signed correction and not a
    # magnitude, and that half-even can push the independent rounding either way.
    residual=Decimal("-0.01"),
    current_production_outcome="refused: decomposition_not_additive",
)
"""_RED: production refuses with `decomposition_not_additive`, against an oracle
publishing 16.71 / 16.68 / 0.03 with a -0.01 residual.

Empirically confirmed on the same four-month harness. `_split` computes
`round(16.675) = 16.68` and `round(0.035) = 0.04`, sums to 16.72, compares against
`round(16.71) = 16.71`, and refuses.

Same violated rule as the positive case. This one is carried separately because it
rounds in the opposite direction: the positive case has both ties keeping an even
digit, this one has both rounding up. A slice that implemented the residual as an
absolute magnitude would pass the positive case and fail here.
"""

GROWTH_RESIDUAL_ZERO = GrowthCase(
    name="residual_zero_exact_decomposition",
    # R_p = 120.00 over U_p = 4;  R_c = 150.00 over U_c = 5.  Precision 2.
    prior_revenue=Decimal("120.00"),
    prior_units=4,
    current_revenue=Decimal("150.00"),
    current_units=5,
    # ASP_p = 120.00 / 4 = 30.00 ; ASP_c = 150.00 / 5 = 30.00.  Equal.
    # volume effect = 30.00 * (5 - 4) = 30.00
    unrounded_volume=Decimal("30.00"),
    # price effect = 5 * (30.00 - 30.00) = 0.00.  Pure volume growth.
    unrounded_price=Decimal("0.00"),
    # published delta = round(150.00 - 120.00) = 30.00
    published_delta=Decimal("30.00"),
    # published volume = round(30.00) = 30.00
    published_volume=Decimal("30.00"),
    # published price = 30.00 - 30.00 = 0.00
    published_price=Decimal("0.00"),
    # residual = 0.00 - round(0.00) = 0.00.  Nothing to record.
    residual=Decimal("0.00"),
    current_production_outcome="published: 30.00 / 30.00 / 0.00",
)
"""_RED: production publishes 30.00 / 30.00 / 0.00 and agrees, with no residual.

Empirically confirmed. Every quantity terminates at two places, so independent
rounding and derived rounding coincide and `_split`'s additivity guard passes.

Recorded as the control. It proves the residual rule is a refinement rather than a
replacement: the 2230-of-2304 fixtures that already reconcile must publish
byte-identical numbers after `V-growth` lands, and a residual of exactly zero must
not produce a caveat or an audit note where none is warranted.
"""

GROWTH_RESIDUAL_CASES = (
    GROWTH_RESIDUAL_POSITIVE,
    GROWTH_RESIDUAL_NEGATIVE,
    GROWTH_RESIDUAL_ZERO,
)

GROWTH_RESIDUAL_BOUND_NOTE = """The residual can never exceed one unit of the published last place.

`RRA-008` requires refusal when it does, and the decision doc repeats the bound. No
oracle case exhibits a violation, and the reason is algebraic rather than a gap in
the search.

**One correction first, because an earlier version of this note got it wrong.** It
claimed `v + p == D` exactly, "before any rounding", as an algebraic invariant.
That is true in real arithmetic and *false* in the `prec=60` decimal context
`growth.py` actually runs in: `ASP = R / U` generally does not terminate, so `v`
and `p` each carry a context-rounding error. Measured over 200,000 random admitted
pairs, `(v + p) - D` was nonzero in 55.7% of them. The conclusion below survives
that correction, but it does not follow from the invariant, so the derivation is
restated to carry the error term explicitly.

  Let `s` be the published scale and `ulp = 10**-s`.

  **Step 1 -- `round(D) = D`, and this is a property of the code, not of algebra.**
  `facts.py:834` sets the package's monetary scale to `max(MIN_MONETARY_PRECISION,
  observed input scale)`, and `facts.py:385` refuses a package whose scale exceeds
  `MAX_MONETARY_PRECISION`. So the published scale is at least as fine as every
  admitted monetary input, every admitted revenue is an exact multiple of `ulp`,
  and `D = R_c - R_p` -- one subtraction of two such multiples, exact at `prec=60`
  for any realistic magnitude -- is itself an exact multiple of `ulp`. Hence
  `round(D) = D` with no error. Verified: 0 counterexamples in 50,000 trials.

  **Step 2 -- carry the context error.** Write `eps = (v + p) - D`, the quantity
  the earlier note assumed away. Then:

      residual = published_price - round(p)
               = (round(D) - round(v)) - round(p)
               = D - round(v) - round(p)                     [step 1]
               = (v + p - eps) - round(v) - round(p)
               = (v - round(v)) + (p - round(p)) - eps

  **Step 3 -- the bound.** Each rounding bracket is bounded by `ulp / 2`, so
  `|residual| <= ulp + |eps|`. That alone would not quite give the bound, but
  `residual` is by construction a difference of `ulp`-quantized quantities --
  `published_price` is `round(D) - round(v)` and `round(p)` is quantized -- so it
  is always an exact integer multiple of `ulp`. An integer multiple of `ulp` whose
  magnitude is below `ulp + |eps|` is at most `ulp`, for any `|eps| < ulp`.

  **Step 4 -- how much room that leaves.** Measured `|eps| / ulp <= 3e-49` over
  200,000 random pairs with revenues to 1e6 and units to 1e4; the reviewer measured
  `<= 3e-42` on revenues to 1e12. Either way `|eps|` is some forty orders of
  magnitude below the `ulp` the argument needs, and the margin is only exhausted
  near 57 significant digits, where `prec=60` itself runs out -- far beyond
  `MAX_MEASURE_DIGITS = 18`. Verified directly: over 200,000 trials the residual
  was an integer multiple of `ulp` every time, and `max |residual| = 1 ulp`.

So the refusal branch `RRA-008` mandates is unreachable on admitted inputs, and
this module states no literal for it. `V-growth` must still implement the refusal
-- a governed bound whose guard is absent is a bound nobody can rely on, and the
proof above rests on the `facts.py` scale rule, which a later correction could
move. But no test can drive it with governed data, and a case fabricated by
feeding the formula a scale it would never receive would assert something about
the guard rather than about the decomposition.
"""


# ---------------------------------------------------------------------------
# Internal consistency.
# ---------------------------------------------------------------------------


def growth_case_reconciles(case: GrowthCase) -> bool:
    """Whether one growth case's own literals agree with each other.

    Checks the oracle against itself, never against production. Four properties,
    each derivable from `RRA-008` alone:

    1. Unrounded additivity -- the algebraic invariant. `v + p == R_c - R_p`.
    2. Published additivity -- what the derived-price rule buys. Exact by
       construction, and asserted because a typo'd literal would break it.
    3. The delta literal really is the rounded revenue change.
    4. The residual really is `published_price - round(unrounded_price)`.

    A typo in any literal above fails at least one of these, which is what keeps a
    hand-derived table honest without letting production supply the answer.
    """
    scale = Decimal(1).scaleb(-MONETARY_PRECISION)
    change = case.current_revenue - case.prior_revenue
    return all(
        (
            case.unrounded_volume + case.unrounded_price == change,
            case.published_volume + case.published_price == case.published_delta,
            case.published_delta == change.quantize(scale),
            case.residual == case.published_price - case.unrounded_price.quantize(scale),
        )
    )


def curve_is_monotone(shares: tuple[Decimal, ...]) -> bool:
    """Whether a cumulative share curve is non-decreasing and ends at exactly one.

    `RRA-008` calls the curve cumulative, and "a 'cumulative' curve that dips is
    not one". A flat tail is allowed -- that is what zero-revenue values produce --
    so the test is non-decreasing rather than strictly increasing.
    """
    if not shares:
        return False
    ordered = all(
        earlier <= later for earlier, later in zip(shares, shares[1:], strict=False)
    )
    return ordered and shares[-1] == Decimal("1.0000")


def leading_count(distinct_values: int, fraction: int) -> int:
    """`ceil(n / fraction)`, at least one -- the governed cutoff rule.

    Restated here rather than imported so a slice's cutoff can be checked against
    an independent statement of the rule. `RRA-008` fixes both the ceiling and the
    at-least-one floor, and names them "part of the concentration formula version".
    """
    return max(1, -(-distinct_values // fraction))


ORACLE_DIMENSIONS = (SEMANTIC_PRODUCT, SEMANTIC_CATEGORY)
