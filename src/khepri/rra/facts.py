from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, InvalidOperation, localcontext

import polars as pl

from khepri.rra.admissibility import (
    AdmissibilityDecision,
    ReportRequest,
    assess_admissibility,
)
from khepri.rra.admission import (
    EVENT_RETURN,
    EVENT_SALE,
    STATUS_POSTED,
    AdmittedEvents,
    EventsRefused,
    admit_events,
)
from khepri.rra.aggregates import (
    REDACTION_SENTINEL,
    UNLABELLED_BUCKET_LABEL,
    Comparison,
    Series,
    build_comparison,
    build_series,
    granularity_for,
    reconciles,
)
from khepri.rra.bases import BasisBinding, RetainedBasis, retain_bases
from khepri.rra.coverage import CoverageManifest
from khepri.rra.coverage_signature import (
    CoverageSignature,
    SignatureRefused,
    build_coverage_signature,
)
from khepri.rra.daily_bases import AlignedDailyBasis, DailyValue
from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_CHANNEL,
    SEMANTIC_COST,
    SEMANTIC_DISCOUNT,
    SEMANTIC_PRODUCT,
    SEMANTIC_RETURNS,
    SEMANTIC_REVENUE,
    SEMANTIC_STORE,
    SEMANTIC_TRANSACTION_DATE,
    SEMANTIC_TRANSACTION_ID,
    SEMANTIC_UNITS,
    STATE_AMBIGUOUS,
    RetailMapping,
    build_mapping,
)
from khepri.rra.populations import (
    POPULATION_FINANCIAL_COMPLETE_REVENUE_COST,
    POPULATION_FINANCIAL_POSTED,
    POPULATION_SALES_COMPLETE_REVENUE,
    POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS,
    POPULATION_SALES_COMPLETE_REVENUE_UNITS,
    POPULATION_SALES_COMPLETE_TRANSACTIONS,
    POPULATION_SALES_COMPLETE_UNITS,
    POPULATION_SALES_COMPLETE_UNITS_TRANSACTIONS,
    POPULATION_SALES_POSTED,
)
from khepri.rra.profiling import (
    DatasetProfile,
    build_profile,
    canonical_json,
    is_personal_value,
    materialize,
    parse_date,
    safe_value_label,
)
from khepri.rra.source_contract import BasisDeclaration, SourceContract
from khepri.rra.versions import (
    REASON_PACKAGE_VERSION_UNADMITTED,
    admits_package,
)

# v2 carries the five items APP-014 added to RRA-004: the retained concentration
# curve, distinct transaction counts, per-bucket date counts, the recorded
# comparison window, and the formula version as a field on every emitted fact.
PACKAGE_VERSION = "rra004.package.v3"
FORMULA_VERSION = "rra004.formula.v2"

# The governed comparison window, recorded rather than chosen by whichever module
# needs one. `RRA-008` asks for "a prior window of equal length" and names no
# length; one period at the package's own granularity is the only reading that
# invents nothing. An earlier comparison revision took half the available history,
# so prepending old rows changed a reported delta while recent rows were identical.
COMPARISON_WINDOW_PERIODS = 1

UNIT_MONETARY = "monetary"
UNIT_COUNT = "count"
UNIT_RATIO = "ratio"

METRIC_REVENUE = "revenue"
METRIC_UNITS = "units"
METRIC_TRANSACTIONS = "transactions"
METRIC_AVERAGE_ORDER_VALUE = "average_order_value"
METRIC_AVERAGE_SELLING_PRICE = "average_selling_price"
METRIC_COST = "cost"
METRIC_GROSS_PROFIT = "gross_profit"
METRIC_GROSS_MARGIN = "gross_margin"
METRIC_DISCOUNT = "discount"
METRIC_RETURNS = "returns"

REASON_INPUT_UNAVAILABLE = "required_input_unavailable"
REASON_ZERO_DENOMINATOR = "zero_denominator"
REASON_RECONCILIATION_FAILED = "reconciliation_failed"
REASON_INCOMPLETE_IDENTIFIERS = "incomplete_transaction_identifiers"
REASON_AMBIGUOUS_MAPPING = "ambiguous_mapping"

CAVEAT_CURRENCY_NOT_DECLARED = "currency_not_declared"
CAVEAT_DUPLICATE_ROWS = "duplicate_rows_present"
CAVEAT_NEGATIVE_REVENUE = "negative_revenue_present"
CAVEAT_RETURNS_NOT_NETTED = "returns_not_netted"
CAVEAT_NULL_MEASURE_INPUTS = "null_measure_inputs"
CAVEAT_UNDATED_ROWS_EXCLUDED = "rows_without_time_field_excluded"
CAVEAT_BUCKETS_TRUNCATED = "comparison_buckets_truncated"
CAVEAT_PERSONAL_VALUES_REDACTED = "personal_values_redacted"
CAVEAT_DERIVED_OVER_MATCHED_ROWS = "derived_metrics_use_matched_rows"

RATIO_PRECISION = 4
MIN_MONETARY_PRECISION = 2
MAX_MONETARY_PRECISION = 6
# Bounded so a governed total stays exact under the serializing context too,
# and so no value can exceed the arithmetic context when it is quantized.
MAX_MEASURE_DIGITS = 18
ARITHMETIC_PRECISION = 60

COMPARISON_DIMENSIONS = (
    SEMANTIC_PRODUCT,
    SEMANTIC_CATEGORY,
    SEMANTIC_STORE,
    SEMANTIC_CHANNEL,
)


class FactsRefused(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Fact:
    """One governed number, stating which formula produced it.

    `formula_version` is a field and not only an input to `fact_identity` because
    a hash names a fact and cannot be read back off one. Two versions do yield
    different identifiers, but a stored citation still could not say which
    formula produced the number it cites -- the provenance `RRA-008` requires and
    hashing does not supply. `APP-014` amended `RRA-004` to require it here.
    """

    fact_id: str
    citation_id: str
    metric: str
    value: str
    precision: int
    unit_kind: str
    inputs: tuple[str, ...]
    caveats: tuple[str, ...]
    formula_version: str = FORMULA_VERSION

    def as_document(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "value": self.value,
            "precision": self.precision,
            "unit_kind": self.unit_kind,
            "inputs": list(self.inputs),
            "caveats": list(self.caveats),
            "formula_version": self.formula_version,
        }


@dataclass(frozen=True, slots=True)
class FactSeries:
    fact_id: str
    citation_id: str
    metric: str
    measure: str
    precision: int
    unit_kind: str
    series: Series
    caveats: tuple[str, ...]
    formula_version: str = FORMULA_VERSION

    def as_document(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "measure": self.measure,
            "precision": self.precision,
            "unit_kind": self.unit_kind,
            "caveats": list(self.caveats),
            "formula_version": self.formula_version,
            **self.series.as_document(precision=self.precision),
        }


@dataclass(frozen=True, slots=True)
class FactComparison:
    fact_id: str
    citation_id: str
    metric: str
    measure: str
    precision: int
    unit_kind: str
    comparison: Comparison
    caveats: tuple[str, ...]
    formula_version: str = FORMULA_VERSION

    def as_document(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "measure": self.measure,
            "precision": self.precision,
            "unit_kind": self.unit_kind,
            "caveats": list(self.caveats),
            "formula_version": self.formula_version,
            **self.comparison.as_document(precision=self.precision),
        }


@dataclass(frozen=True, slots=True)
class RefusedResult:
    metric: str
    reason: str

    def as_document(self) -> dict[str, object]:
        return {"metric": self.metric, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class FactPackage:
    package_version: str
    formula_version: str
    mapping_version: str
    profile_digest: str
    source_sha256_hex: str
    row_count: int
    monetary_precision: int
    facts: tuple[Fact, ...]
    series: tuple[FactSeries, ...]
    comparisons: tuple[FactComparison, ...]
    refusals: tuple[RefusedResult, ...]
    caveats: tuple[str, ...]
    comparison_window_periods: int = COMPARISON_WINDOW_PERIODS
    # --- `rra004.package.v3` population, basis and coverage provenance -------
    #
    # `RRA-004`'s "Fact-package provenance" requires the package to record
    # "dimensions, units, input digest, coverage-manifest identity, coverage
    # signatures, canonical transaction keys or their stable basis identity, and
    # aligned daily bases", and every fact to disclose a readable population
    # code. Before v3 none of it was recorded: `_matched` built the AOV, ASP and
    # margin populations and returned only their values.
    #
    # Defaulted so this shape can land before every producer fills it, and
    # enumerated in `package_source.rebuild_fact_package` so an absent field is
    # refused on read rather than defaulted back into existence.
    #
    # **No growth rounding-residual field.** `RRA-004`: package v3 "authorizes no
    # growth rounding-residual field; that evidence belongs wholly to
    # `rra008.growth.v2`" and does not widen this document.
    #: One uppercase ISO 4217 code when the package carries monetary facts.
    currency: str | None = None
    #: `sum(positive posted-sale units)` -- the basket numerator `RRA-008`
    #: names, or `None` where no sale carries positive units.
    #:
    #: A package field and not a `Fact`, deliberately. `RRA-004`'s metric
    #: assignments are exact and name no such metric, and a package holds
    #: "every numerical claim that may appear on any report surface" -- so
    #: publishing it as a fact both authorizes a number the specification
    #: does not, and puts two near-identical unit counts in front of a reader
    #: with nothing to tell them apart. It is an input to items per
    #: transaction, which is the governed metric.
    #:
    #: Distinct from the `units` fact, whose population is `financial_posted`
    #: and therefore includes posted return units.
    sale_units_total: int | None = None
    #: The event kinds and statuses every population here was filtered to.
    event_kind_filters: tuple[str, ...] = ()
    status_filters: tuple[str, ...] = ()
    #: The attestation this package's coverage claims rest on, by identity.
    coverage_manifest_identity: str | None = None
    #: Structural coverage signatures, one per accepted window and scope.
    coverage_signatures: tuple[CoverageSignature, ...] = ()
    #: Daily revenue and unit bases bound to those windows.
    daily_bases: tuple[AlignedDailyBasis, ...] = ()
    #: The reconciliation bases a fact may cite.
    retained_bases: tuple[RetainedBasis, ...] = ()

    def fact(self, metric: str) -> Fact | None:
        return next((fact for fact in self.facts if fact.metric == metric), None)

    def value(self, metric: str) -> str | None:
        found = self.fact(metric)
        return None if found is None else found.value

    def refusal(self, metric: str) -> RefusedResult | None:
        return next(
            (refusal for refusal in self.refusals if refusal.metric == metric),
            None,
        )

    def comparison(self, dimension: str, measure: str = METRIC_REVENUE) -> FactComparison | None:
        return next(
            (
                entry
                for entry in self.comparisons
                if entry.comparison.dimension == dimension and entry.measure == measure
            ),
            None,
        )

    def trend(self, measure: str = METRIC_REVENUE) -> FactSeries | None:
        return next((entry for entry in self.series if entry.measure == measure), None)

    @property
    def citation_ids(self) -> tuple[str, ...]:
        return tuple(
            entry.citation_id
            for entry in (*self.facts, *self.series, *self.comparisons)
        )

    def as_document(self) -> dict[str, object]:
        return {
            "package_version": self.package_version,
            "formula_version": self.formula_version,
            "mapping_version": self.mapping_version,
            "profile_digest": self.profile_digest,
            "source_sha256_hex": self.source_sha256_hex,
            "row_count": self.row_count,
            "sale_units_total": self.sale_units_total,
            "monetary_precision": self.monetary_precision,
            "comparison_window_periods": self.comparison_window_periods,
            "facts": [fact.as_document() for fact in self.facts],
            "series": [entry.as_document() for entry in self.series],
            "comparisons": [entry.as_document() for entry in self.comparisons],
            "refusals": [refusal.as_document() for refusal in self.refusals],
            "caveats": list(self.caveats),
            "currency": self.currency,
            "event_kind_filters": sorted(self.event_kind_filters),
            "status_filters": sorted(self.status_filters),
            "coverage_manifest_identity": self.coverage_manifest_identity,
            "coverage_signatures": [
                signature.as_document() for signature in self.coverage_signatures
            ],
            "daily_bases": [basis.as_document() for basis in self.daily_bases],
            "retained_bases": [basis.as_document() for basis in self.retained_bases],
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.as_document()).encode()).hexdigest()


@dataclass
class _Measures:
    revenue: list[Decimal | None]
    units: list[int | None]
    dates: list[date | None]
    transactions: list[str | None]
    #: Each admitted row's event kind, in frame order. `RRA-004` assigns
    #: sale-only populations to Transactions, AOV, ASP and items per
    #: transaction, and `RRA-003` forbids establishing the kind from observed
    #: values -- so it travels from admission rather than being re-derived.
    event_kinds: list[str]
    cost: list[Decimal | None]
    discount: list[Decimal | None]
    returns: list[Decimal | None]
    monetary_precision: int
    null_measure_inputs: bool
    transaction_identifiers_complete: bool


@dataclass(frozen=True, slots=True)
class _Aggregated:
    measure: str
    values: list[Decimal | None]
    total: Decimal | None
    precision: int
    unit_kind: str


@dataclass(frozen=True, slots=True)
class AdmittedInput:
    """One reading of one file: what it is, and what it was declared to mean.

    Grouped rather than passed as five parallel arguments, because they are not
    independent -- `_assert_derived_from_profile` re-derives every one of them
    from `content` and refuses the package if any disagrees. A caller cannot
    legitimately vary one alone, so the signature no longer offers to.

    The contract belongs in the group for the same reason it is required at all:
    under `rra003.mapping.v3` the mapping is a function of profile *and*
    declaration, so a mapping travelling without its contract cannot be checked.
    """

    content: bytes
    media_type: str
    profile: DatasetProfile
    mapping: RetailMapping
    decision: AdmissibilityDecision
    contract: SourceContract
    #: The coverage attestation this reading rests on, or `None` where the
    #: operator attested none. `RRA-008` is explicit that "without an
    #: authoritative valid manifest, observed trends may survive but
    #: completeness-dependent comparison and growth refuse" -- so an absent
    #: manifest is an ordinary state that refuses those results rather than the
    #: package. Defaulted because the profile route carries one only when the
    #: customer attested.
    manifest: CoverageManifest | None = None


def build_fact_package(
    admitted: AdmittedInput,
    *,
    formula_version: str = FORMULA_VERSION,
) -> FactPackage:
    """One package, or a refusal."""
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        return _build(admitted, formula_version=formula_version)


def assert_versions_admitted(
    *,
    mapping_version: str,
    package_version: str,
    formula_version: str,
) -> None:
    """Refuse a package whose three versions were never authorized together.

    `RRA-004` requires a new mapping, formula or serialized shape to create a new
    recorded identity. Enforcing that on production alone is half the rule: it
    stops a changed shape reusing an old identity, and does nothing about a
    changed *input* published under an unmoved one. Between two slices of a
    version-moving mission that is the live defect, so the package builder asks
    the table before it builds anything.

    Refused here rather than in the route, because a package is the thing whose
    identity is at stake and every caller reaches it through this module.
    `RRA-009` classifies the reason as Internal: when this fires no report is
    published, so no customer can encounter it.
    """
    if not admits_package(
        mapping_version=mapping_version,
        package_version=package_version,
        formula_version=formula_version,
    ):
        raise FactsRefused(
            f"{REASON_PACKAGE_VERSION_UNADMITTED}: "
            f"{mapping_version}, {package_version} and {formula_version} "
            "were not authorized to be combined."
        )


@dataclass(frozen=True, slots=True)
class _Totals:
    """The package-level sums, each already answering the currency question."""

    revenue: Decimal | None
    units: int | None
    transactions: int | None
    transactions_reason: str
    cost: Decimal | None
    discount: Decimal | None
    returns: Decimal | None


def _totals(
    measures: _Measures,
    admitted_events: AdmittedEvents,
    basis: BasisDeclaration,
) -> _Totals:
    """Every package total, with the monetary ones gated on one proven currency.

    Grouped so the gate is applied in one place. `RRA-003` refuses monetary
    facts "and their derived results" when the currency is missing, malformed or
    mixed, "but does not suppress independently proven count-only facts" -- so
    the split runs through this function and not through eight call sites that
    each have to remember which side they are on.

    **Cost and discount carry a second gate, on the basis declaration.** The
    currency question is whether the amounts are comparable; the basis question
    is whether the column may be *summed at all*. `RRA-003` refuses the discount
    metric on "a bare discount, rate, percentage, repeated invoice total, or
    overlapping component set", and refuses a cost that is unit, average,
    standard or list rather than extended COGS -- so where the operator has not
    attested the basis, admission has no proof the column is additive and there
    is no total to publish. Gated here, on the published figure, because that is
    the only figure anybody reads: honouring it on `AdmittedEvent` alone leaves
    the refusal true of an intermediate object and false of the report.
    """
    complete = measures.transaction_identifiers_complete
    return _Totals(
        revenue=_monetary(admitted_events, measures.revenue),
        units=_sum_integer(measures.units),
        # `RRA-004`:92 -- "Transactions count posted sales only." A return
        # is a posted event and belongs in revenue and units; it is not a
        # transaction, and counting it inflates every ratio dividing by one.
        transactions=(
            _distinct(_sale_only(measures.transactions, measures))
            if complete
            else None
        ),
        transactions_reason=(
            REASON_INPUT_UNAVAILABLE if complete else REASON_INCOMPLETE_IDENTIFIERS
        ),
        cost=_on_attested_basis(
            _monetary(admitted_events, measures.cost), basis.cost_is_extended
        ),
        discount=_on_attested_basis(
            _monetary(admitted_events, measures.discount),
            basis.discount_is_additive,
        ),
        # `RRA-004`:83 -- `-sum(non-positive return revenue)`. `RRA-003`
        # forbids the alternative outright: "No independently mapped
        # return-amount measure is admitted." A return event states its own
        # magnitude, so a separate column is a second answer to one question.
        returns=_returns_magnitude(admitted_events, measures),
    )


def _on_attested_basis(total: Decimal | None, attested: bool) -> Decimal | None:
    """A total the basis declaration permits, or nothing.

    Withholding, not recomputing: the number this returns when the basis *is*
    attested is byte-identical to the one before this gate existed, so no
    published figure changes value and no formula moves. What changes is that an
    unattested basis now yields a refusal where it previously yielded a figure
    the declaration itself disclaimed.
    """
    return total if attested else None


def _margin_inputs(
    admitted_events: AdmittedEvents,
    margin: _Matched,
    basis: BasisDeclaration,
) -> tuple[Decimal | None, Decimal | None]:
    """The revenue and gross profit the margin is computed from, or refusals.

    Gated like the totals: `RRA-003` refuses monetary facts "and their derived
    results", and gross profit is derived from two of them.

    **The cost side carries the basis gate too.** Refusing the `cost` total
    while publishing a margin computed from the same unattested column would
    republish the refused number under a different name -- and a margin is the
    figure more likely to be read than the cost it came from. Withheld, not
    recomputed: where the basis is attested this returns exactly what it
    returned before the gate existed.

    Returned as a pair because both callers downstream need `margin_revenue` --
    gross profit as a term, gross margin as its denominator -- and re-deriving
    it beside the profit is how the two come to disagree.
    """
    revenue = _monetary(admitted_events, margin.left)
    cost = _on_attested_basis(
        _monetary(admitted_events, margin.right), basis.cost_is_extended
    )
    if revenue is None or cost is None:
        return revenue, None
    return revenue, revenue - cost


def _admitted_frame(frame: pl.DataFrame, admitted_events: AdmittedEvents) -> pl.DataFrame:
    """The frame narrowed to the rows admission kept.

    `RRA-003` excludes explicitly void and cancelled events from *every*
    population, and a population read off the unfiltered frame is one they were
    not excluded from -- which would leave the exclusion true of an intermediate
    object and false of every figure anybody sees.

    Narrowed once here rather than re-filtered per measure, so every published
    figure is computed over one population and no later reader has to remember
    the exclusion.
    """
    if not admitted_events.excluded_count:
        return frame
    return frame[list(admitted_events.kept_positions)]


def _monetary(
    admitted_events: AdmittedEvents,
    values: list[Decimal | None],
) -> Decimal | None:
    """A monetary total, or nothing when the currency was not proven.

    `RRA-003`: "Missing, malformed, or mixed currency refuses monetary facts and
    their derived results but does not suppress independently proven count-only
    facts." So this withholds the total while the unit and transaction counts
    beside it stand.
    """
    if admitted_events.monetary_refused:
        return None
    return _sum_decimal(values)


def _admitted_events(admitted: AdmittedInput) -> AdmittedEvents:
    """`RRA-003` admission, run before any measure is read.

    An unknown event kind or status refuses the whole population here rather
    than silently excluding its row; a mixed or missing currency reports what it
    costs, which is the monetary facts alone.

    **`EventsRefused` is translated, not allowed to escape.** It and
    `FactsRefused` are sibling `ValueError` subclasses, so the `except
    FactsRefused` in `packages.build_session_package` -- the only place a refusal
    becomes `PackageRefused`, and so the only path to the governed 409 -- does
    not catch it. Letting it through returns HTTP 500 for ordinary bad input,
    which both misreports a correctly-detected declaration defect as a server
    fault and discards the reason `RRA-003` requires be stated. The `from error`
    keeps the original for the server-side log.
    """
    try:
        return admit_events(
            content=admitted.content,
            media_type=admitted.media_type,
            mapping=admitted.mapping,
            contract=admitted.contract,
        )
    except EventsRefused as error:
        raise FactsRefused(str(error)) from error


def _build(
    admitted: AdmittedInput,
    *,
    formula_version: str,
) -> FactPackage:
    content = admitted.content
    media_type = admitted.media_type
    profile = admitted.profile
    mapping = admitted.mapping
    decision = admitted.decision
    if formula_version != FORMULA_VERSION:
        # One builder implements one formula version. A caller asking for
        # another would receive this builder's arithmetic stamped with that
        # other identity, which is precisely the mislabelling the version
        # system exists to prevent -- so this refuses rather than obliging.
        raise FactsRefused("Formula version is not implemented by this package builder.")
    assert_versions_admitted(
        # The mapping this package actually combines, read from the mapping
        # itself rather than from `MAPPING_VERSION`. The module constant is
        # what `build_mapping` *stamps*; it is not necessarily what the caller
        # handed over, and the gate asks whether the versions a result combines
        # were authorized together. Reading the global answers a different
        # question -- one where a package built from a v2 mapping is checked as
        # though it were v3 -- and `_assert_derived_from_profile` below already
        # proves the mapping belongs to this input.
        mapping_version=mapping.mapping_version,
        package_version=PACKAGE_VERSION,
        formula_version=formula_version,
    )
    _assert_derived_from_profile(admitted)
    if not decision.admissible:
        raise FactsRefused("Dataset is not admissible for a governed fact package.")

    admitted_events = _admitted_events(admitted)
    frame = _admitted_frame(materialize(content, media_type), admitted_events)
    measures = _measures(frame, profile, mapping, admitted_events)
    if measures.monetary_precision > MAX_MONETARY_PRECISION:
        raise FactsRefused("Monetary input precision exceeds the governed maximum.")
    row_count = frame.height

    facts: list[Fact] = []
    refusals: list[RefusedResult] = []
    caveats: list[str] = []

    totals = _totals(measures, admitted_events, admitted.contract.basis)
    revenue_total = totals.revenue
    units_total = totals.units
    transactions_total = totals.transactions
    transactions_reason = totals.transactions_reason
    cost_total = totals.cost
    discount_total = totals.discount
    returns_total = totals.returns

    def add(
        metric: str,
        value: Decimal | int | None,
        *,
        unit_kind: str,
        precision: int,
        inputs: tuple[str, ...],
        reason: str = REASON_INPUT_UNAVAILABLE,
    ) -> None:
        if value is None:
            refusals.append(RefusedResult(metric=metric, reason=reason))
            return
        facts.append(
            _fact(
                metric=metric,
                value=value,
                precision=precision,
                unit_kind=unit_kind,
                inputs=inputs,
                formula_version=formula_version,
            )
        )

    money = measures.monetary_precision
    add(
        METRIC_REVENUE,
        revenue_total,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_REVENUE,),
    )
    add(
        METRIC_UNITS,
        units_total,
        unit_kind=UNIT_COUNT,
        precision=0,
        inputs=(SEMANTIC_UNITS,),
    )
    add(
        METRIC_TRANSACTIONS,
        transactions_total,
        unit_kind=UNIT_COUNT,
        precision=0,
        inputs=(SEMANTIC_TRANSACTION_ID,),
        reason=transactions_reason,
    )
    add(
        METRIC_COST,
        cost_total,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_COST,),
    )
    add(
        METRIC_DISCOUNT,
        discount_total,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_DISCOUNT,),
        reason=_unavailable_reason(mapping, SEMANTIC_DISCOUNT),
    )
    add(
        METRIC_RETURNS,
        returns_total,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_RETURNS,),
        reason=_unavailable_reason(mapping, SEMANTIC_RETURNS),
    )

    # A metric combining two measures is computed over the rows that carry both.
    # Dividing a revenue total drawn from one set of rows by a count drawn from
    # another publishes an average of a population that never existed.
    # `RRA-004` assigns AOV `sales_complete_revenue_transactions` and ASP
    # `sales_complete_revenue_units`, so both pair over sale rows only.
    # Gross margin keeps `financial_complete_revenue_cost`, which `RRA-004`
    # defines over financial rows -- returns included.
    sale_revenue = _sale_only(measures.revenue, measures)
    orders = _matched(sale_revenue, _sale_only(measures.transactions, measures))
    selling = _matched(sale_revenue, _positive_units(measures))
    # `RRA-004`: `sales_complete_revenue_units` admits "no unmatched eligible
    # row", and `RRA-003`: "a sale or return event with zero units refuses
    # unit-dependent facts". A sale carrying revenue but no positive units is
    # eligible and unmatched, so the population does not exist for this dataset
    # and ASP has nothing to average -- averaging the rest publishes a figure
    # that reconciles against neither the revenue nor the units beside it.
    complete_selling = not _unmatched(sale_revenue, _positive_units(measures))
    margin = _matched(measures.revenue, measures.cost)
    if any(pairing.partial for pairing in (orders, selling, margin)):
        caveats.append(CAVEAT_DERIVED_OVER_MATCHED_ROWS)

    _add_ratio(
        add,
        metric=METRIC_AVERAGE_ORDER_VALUE,
        numerator=(
            _monetary(admitted_events, orders.left)
            if measures.transaction_identifiers_complete
            else None
        ),
        denominator=_distinct(orders.right) if measures.transaction_identifiers_complete else None,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_REVENUE, SEMANTIC_TRANSACTION_ID),
        unavailable_reason=transactions_reason,
    )
    _add_ratio(
        add,
        metric=METRIC_AVERAGE_SELLING_PRICE,
        numerator=(
            _monetary(admitted_events, selling.left)
            if complete_selling
            else None
        ),
        denominator=_sum_integer(selling.right),
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_REVENUE, SEMANTIC_UNITS),
    )

    margin_revenue, gross_profit = _margin_inputs(
        admitted_events, margin, admitted.contract.basis
    )
    add(
        METRIC_GROSS_PROFIT,
        gross_profit,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_REVENUE, SEMANTIC_COST),
    )
    _add_ratio(
        add,
        metric=METRIC_GROSS_MARGIN,
        numerator=gross_profit,
        denominator=margin_revenue,
        unit_kind=UNIT_RATIO,
        precision=RATIO_PRECISION,
        inputs=(SEMANTIC_REVENUE, SEMANTIC_COST),
    )

    aggregated = (
        _Aggregated(
            measure=SEMANTIC_REVENUE,
            values=measures.revenue,
            total=revenue_total,
            precision=money,
            unit_kind=UNIT_MONETARY,
        ),
        _Aggregated(
            measure=SEMANTIC_UNITS,
            values=[None if value is None else Decimal(value) for value in measures.units],
            total=None if units_total is None else Decimal(units_total),
            precision=0,
            unit_kind=UNIT_COUNT,
        ),
    )
    series = _series(
        measures,
        aggregated,
        formula_version=formula_version,
        refusals=refusals,
        caveats=caveats,
    )
    comparisons = _comparisons(
        frame,
        mapping,
        aggregated,
        row_count=row_count,
        formula_version=formula_version,
        transactions=_countable_transactions(measures),
        event_kinds=measures.event_kinds,
        refusals=refusals,
        caveats=caveats,
    )

    if admitted_events.currency is None and any(
        fact.unit_kind == UNIT_MONETARY for fact in facts
    ):
        # Conditional under `rra004.package.v3`, unconditional before it. Under
        # `v2` the package recorded no currency at all, so "not declared" was
        # true of the document however the extract had been read. `v3` records
        # the admitted currency, and a package stating both `EGP` and "currency
        # not declared" contradicts itself -- visibly, since `RRA-009` renders
        # caveats to customers.
        caveats.append(CAVEAT_CURRENCY_NOT_DECLARED)
    if measures.null_measure_inputs:
        caveats.append(CAVEAT_NULL_MEASURE_INPUTS)
    if revenue_total is not None and any(
        value is not None and value < 0 for value in measures.revenue
    ):
        caveats.append(CAVEAT_NEGATIVE_REVENUE)
    if returns_total is not None:
        caveats.append(CAVEAT_RETURNS_NOT_NETTED)
    if row_count and int(frame.is_duplicated().sum()):
        caveats.append(CAVEAT_DUPLICATE_ROWS)

    # Bound once and used for both the recorded filter and the signature gate,
    # so the population the package publishes and the one the attestation is
    # checked against cannot drift apart.
    admitted_kinds = _admitted_kinds(admitted_events)

    return FactPackage(
        package_version=PACKAGE_VERSION,
        formula_version=formula_version,
        mapping_version=mapping.mapping_version,
        profile_digest=profile.digest,
        source_sha256_hex=profile.source_sha256_hex,
        row_count=row_count,
        monetary_precision=money,
        sale_units_total=_sum_integer(_positive_units(measures)),
        facts=tuple(facts),
        series=tuple(series),
        comparisons=tuple(comparisons),
        refusals=tuple(sorted(refusals, key=lambda refusal: refusal.metric)),
        caveats=tuple(sorted(set(caveats))),
        # `rra004.package.v3` provenance. `RRA-004` requires the package to
        # record these, and requires every derived fact to cite "exactly one
        # compatible basis" -- so a v3 package retaining none would leave every
        # derived fact citing nothing.
        currency=admitted_events.currency,
        event_kind_filters=admitted_kinds,
        status_filters=(STATUS_POSTED,),
        coverage_manifest_identity=(
            None if admitted.manifest is None else admitted.manifest.input_digest
        ),
        coverage_signatures=_signatures_of(admitted, measures, admitted_kinds),
        daily_bases=_daily_bases_of(
            admitted, measures, admitted_kinds, admitted_events.currency
        ),
        retained_bases=retain_bases(
            events=admitted_events.events,
            binding=BasisBinding(
                input_digest=profile.source_sha256_hex,
                mapping_version=mapping.mapping_version,
                currency=admitted_events.currency,
                precision=money,
            ),
            counts=_population_counts(measures),
            transaction_counts=_population_transaction_counts(measures),
        ),
    )


def _population_counts(measures: _Measures) -> dict[str, int]:
    """How many admitted events each governed population actually contains.

    `RRA-004` defines the populations by the measures a row carries, not by its
    event kind alone: `sales_complete_revenue_units` is the sales complete in
    *both*, and a basis counting every sale claims a completeness the package
    does not have. Computed here rather than in `bases` because the measures and
    the sale-only helpers are here.

    A population with no eligible event counts zero rather than being omitted:
    `retain_bases` produces its bases "wherever the events allow rather than
    being optional", so the honest count is the answer and absence is never the
    disclosure.
    """
    sales = _sale_only(measures.revenue, measures)
    sale_units = _positive_units(measures)
    sale_keys = _sale_only(measures.transactions, measures)
    financial = len(measures.revenue)
    kinds = len([kind for kind in measures.event_kinds if kind == EVENT_SALE])

    def both(left: list, right: list) -> int:
        return sum(
            1
            for index in range(len(left))
            if left[index] is not None and right[index] is not None
        )

    def present(values: list) -> int:
        return sum(1 for value in values if value is not None)

    return {
        POPULATION_FINANCIAL_POSTED: financial,
        POPULATION_SALES_POSTED: kinds,
        POPULATION_SALES_COMPLETE_REVENUE: present(sales),
        POPULATION_SALES_COMPLETE_UNITS: present(sale_units),
        POPULATION_SALES_COMPLETE_REVENUE_UNITS: both(sales, sale_units),
        POPULATION_SALES_COMPLETE_TRANSACTIONS: present(sale_keys),
        POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS: both(sales, sale_keys),
        POPULATION_SALES_COMPLETE_UNITS_TRANSACTIONS: both(sale_units, sale_keys),
        POPULATION_FINANCIAL_COMPLETE_REVENUE_COST: both(
            measures.revenue, measures.cost
        ),
    }


def _population_transaction_counts(measures: _Measures) -> dict[str, int | None]:
    """How many distinct canonical transactions each population contains.

    The companion to `_population_counts`, and needed separately because a
    transaction count is a *distinct key* count rather than a row count: two
    rows of one invoice are two events and one transaction.

    `retain_bases` previously took one count across all sales and gave it to
    every basis recording transactions, so `sales_complete_transactions`,
    `sales_complete_revenue_transactions` and
    `sales_complete_units_transactions` reported the same number while naming
    three different populations -- a keyed sale with revenue but no units is
    in the first two and not the third.

    `None` rather than zero where no eligible row carries a key, for the
    reason `bases._sale_keys` records: zero asserts the population was counted
    and found empty, which is a different claim from having no key to count.
    """
    sale_keys = _sale_only(measures.transactions, measures)
    revenue_keys = _matched(_sale_only(measures.revenue, measures), sale_keys)
    units_keys = _matched(_positive_units(measures), sale_keys)
    return {
        POPULATION_SALES_COMPLETE_TRANSACTIONS: _distinct(sale_keys),
        POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS: _distinct(revenue_keys.right),
        POPULATION_SALES_COMPLETE_UNITS_TRANSACTIONS: _distinct(units_keys.right),
    }

def _daily_bases_of(
    admitted: AdmittedInput,
    measures: _Measures,
    admitted_kinds: tuple[str, ...],
    currency: str | None,
) -> tuple[AlignedDailyBasis, ...]:
    """One aligned daily basis per attested scope, or none.

    `RRA-004:120` requires the package to retain "aligned daily revenue and
    unit bases bound to each accepted comparison window", recording "exact
    start and end dates, store or aggregate scope, event and status filters,
    population identity, currency and precision where applicable, and daily
    revenue and unit values, including attested zero-activity days".

    **The days come from the manifest, the values from the data.** A day the
    operator attested and no row landed on is a covered day stating no
    revenue -- not a hole, and not a zero. A day the manifest does not attest
    is simply not in the basis, because `RRA-004` says observed bounds "are
    evidence but are not coverage-manifest completeness proof": a basis built
    from the rows alone would be exactly that proof-by-observation.

    Empty where nothing is attested, for the same reason `_signatures_of` is:
    this is coverage evidence, and a package with no manifest has none to
    give. The population is `financial_posted`, which is what these daily
    values sum: `RRA-008` narrows to a sale-only population when it consumes
    them, and recording a narrower code here would name a population these
    values are not.
    """
    manifest = admitted.manifest
    if manifest is None:
        return ()
    return tuple(
        AlignedDailyBasis(
            scope=scope,
            start=min(days),
            end=max(days),
            population=POPULATION_FINANCIAL_POSTED,
            event_kinds=admitted_kinds,
            statuses=(STATUS_POSTED,),
            values=_daily_values(measures, days),
            precision=measures.monetary_precision,
            currency=currency,
        )
        for scope, days in _attested_days(manifest)
    )


def _attested_days(
    manifest: CoverageManifest,
) -> tuple[tuple[str, tuple[date, ...]], ...]:
    """Each attested scope with the days it covers, in a stable order.

    An extraction gap is excluded for the reason `coverage_signature._covered`
    excludes it: `RRA-003` separates a gap, whose size is unknown, from an
    attested closure, which proves complete zero activity and is covered.
    """
    covered: dict[str, list[date]] = {}
    for scope, day in sorted(manifest.covered_pairs):
        if (scope, day) in manifest.extraction_gaps:
            continue
        covered.setdefault(scope, []).append(day)
    return tuple(
        (scope, tuple(days)) for scope, days in sorted(covered.items()) if days
    )


def _daily_values(
    measures: _Measures,
    days: tuple[date, ...],
) -> tuple[DailyValue, ...]:
    """What each attested day measured, `None` where it carried no row.

    `None` and not zero: an attested day with no admitted row proves the
    operator saw no activity, which is a different statement from a day whose
    rows summed to nothing, and `DailyValue` keeps the two apart.
    """
    revenue: dict[date, Decimal] = {}
    units: dict[date, int] = {}
    for index, day in enumerate(measures.dates):
        if day is None:
            continue
        value = measures.revenue[index]
        if value is not None:
            revenue[day] = revenue.get(day, Decimal(0)) + value
        count = measures.units[index]
        if count is not None:
            units[day] = units.get(day, 0) + count
    return tuple(
        DailyValue(day=day, revenue=revenue.get(day), units=units.get(day))
        for day in days
    )

def _signatures_of(
    admitted: AdmittedInput,
    measures: _Measures,
    admitted_kinds: tuple[str, ...],
) -> tuple[CoverageSignature, ...]:
    """One structural signature per attested scope, over the dates admitted.

    Empty where the operator attested no coverage. `RRA-008` makes that an
    ordinary state -- "observed trends may survive but completeness-dependent
    comparison and growth refuse" -- so an absent manifest yields no signature
    and the families that need one refuse for themselves.

    The window comes from the admitted dates and the *proof* comes from the
    manifest: `build_coverage_signature` reads only attested pairs, so a day the
    frame carries and the manifest does not is simply not covered. Deriving the
    window from data and its coverage from the attestation is the division
    `RRA-004` draws -- observed bounds "are evidence but are not
    coverage-manifest completeness proof".
    """
    manifest = admitted.manifest
    if manifest is None:
        return ()
    days = [day for day in measures.dates if day is not None]
    if not days:
        return ()
    if not _attests_the_admitted_population(manifest, admitted_kinds):
        return ()
    signatures = []
    for scope in sorted(manifest.scopes):
        try:
            signatures.append(
                build_coverage_signature(
                    manifest,
                    scope=scope,
                    start=min(days),
                    end=max(days),
                    admitted_kinds=admitted_kinds,
                )
            )
        except SignatureRefused:
            # A scope this window is not wholly attested for proves nothing about
            # it, and a partial list would read as a complete one.
            return ()
    return tuple(signatures)


def _attests_the_admitted_population(
    manifest: CoverageManifest,
    admitted_kinds: tuple[str, ...],
) -> bool:
    """Whether the attestation describes the population the package computed over.

    `RRA-004` binds a coverage signature to the filters it was attested under,
    and `comparison._structurally_compatible` compares those filters *between
    windows* -- so an attestation naming a wider population than the package
    admitted is not caught by that comparison: both windows carry the same wrong
    declaration and agree. The mismatch has to be refused where the signature is
    built, against the data, or it is never detected at all.

    Compared as sets, and the relation is **subset, not equality**: every kind
    the package admitted must be attested, while an attestation naming more is
    accepted. An operator attesting that sales *and* returns are complete for a
    window makes a strictly stronger claim than the sale-only package needs, and
    the sales it computed over are covered by it. Requiring equality would
    refuse that ordinary, generic attestation.

    The defect runs the other way: a manifest attesting sales alone over an
    extract the package admitted returns from leaves the returns with no
    completeness proof, while the signature would report the window proven.

    Statuses are not compared here: `facts` admits `STATUS_POSTED` alone and
    `admission` refuses every other status outright, so the package has no
    status population that could diverge. When that stops being true this
    becomes the place the comparison belongs.
    """
    return set(admitted_kinds) <= set(manifest.event_kinds)


def _admitted_kinds(admitted_events: AdmittedEvents) -> tuple[str, ...]:
    """The event kinds this package actually admitted, in a stable order.

    Read off the events rather than declared, because the filter a package
    records must describe what it computed over: a contract admitting returns
    over an extract containing none produced a sale-only package, and recording
    the declaration would overstate the population.
    """
    return tuple(sorted({event.event_kind for event in admitted_events.events}))


def _positive_units(measures: _Measures) -> list:
    """Sale units, keeping only the strictly positive ones.

    `RRA-003`: "ASP and basket calculations use positive posted-sale units only,
    including free or bonus items." A zero-unit sale refuses unit-dependent
    facts rather than contributing a zero, so it is blanked here too.
    """
    return [
        value if value is not None and value > 0 else None
        for value in _sale_only(measures.units, measures)
    ]


def _returns_magnitude(
    admitted_events: AdmittedEvents,
    measures: _Measures,
) -> Decimal | None:
    """The positive magnitude of admitted return revenue, per `RRA-004`:83.

    `None` where the package proves no return magnitude -- `RRA-003` is
    explicit that "absence of event-kind evidence cannot establish zero", so a
    package with no admitted return event states nothing rather than zero.

    **One check, not two.** An earlier form asked separately whether any return
    event was admitted and whether any carried non-positive revenue. Both
    answered `None`, so the first could be deleted with every test still green
    -- a mutation check found exactly that. The two questions *should* differ:
    `RRA-004`:48-49 lets an empty eligible population state zero "only when
    admitted event-kind and status evidence proves that event class is absent",
    so a package that admitted returns and found none is entitled to publish
    zero. That is a `Returns` refusal-rule change rather than a population one,
    and it is not this commit's row to move -- so the redundant branch is
    removed rather than left standing as an untested claim.
    """
    magnitudes = [
        value
        for value, kind in zip(measures.revenue, measures.event_kinds, strict=False)
        if kind == EVENT_RETURN and value is not None and value <= 0
    ]
    if not magnitudes:
        return None
    return _monetary(admitted_events, [-value for value in magnitudes])


def _sale_only(values: list, measures: _Measures) -> list:
    """The same list with every non-sale row blanked out.

    `RRA-004`:92 -- "Transactions count posted sales only" -- and the same rule
    governs AOV, ASP and items per transaction through their populations
    (`RRA-004`:35-42). Blanking rather than compacting keeps the list
    index-aligned with every other measure, which is what lets `_matched` pair
    two of them without a join.

    Returns stay inside revenue and units: `RRA-004`:92 keeps those net.
    """
    return [
        value if kind == EVENT_SALE else None
        for value, kind in zip(values, measures.event_kinds, strict=False)
    ]


@dataclass(frozen=True, slots=True)
class _Matched:
    left: list
    right: list
    partial: bool


def _unmatched(left: list, right: list) -> bool:
    """Whether some row carries one measure of a pairing and not the other.

    `_matched` keeps the rows where both are present and reports `partial` so the
    package can disclose the loss. This asks the stricter question a *ratio*
    population needs: not "did we lose a row" but "is this population complete at
    all". `RRA-004` puts "no unmatched eligible row" on
    `sales_complete_revenue_units` and on none of the plain filters beside it.

    A pairing with no left-hand values at all is not unmatched -- the measure is
    absent rather than incomplete, and the metric is refused for that instead.
    """
    if not any(value is not None for value in left):
        return False
    return any(
        (left[index] is None) != (right[index] is None) for index in range(len(left))
    )


def _matched(left: list, right: list) -> _Matched:
    """Keep only the rows where both measures are present.

    `partial` says whether that cost a row one of the two measures would
    otherwise have contributed, so the package can disclose it. A measure that
    is absent altogether is not a partial pairing -- the metric is refused.
    """
    kept = [
        index
        for index in range(len(left))
        if left[index] is not None and right[index] is not None
    ]
    populated = [sum(1 for value in side if value is not None) for side in (left, right)]
    return _Matched(
        left=[left[index] for index in kept],
        right=[right[index] for index in kept],
        partial=min(populated) > 0 and len(kept) != max(populated),
    )


def _unavailable_reason(mapping: RetailMapping, semantic: str) -> str:
    """Say why a measure is absent: never found, or found and unresolved.

    A column named only `discount` states no measure kind, so the mapper leaves
    it ambiguous rather than letting it be summed as currency. Reporting that as
    a plain missing input would hide that the data is present and the *label* is
    what falls short.
    """
    if mapping.state_of(semantic) == STATE_AMBIGUOUS:
        return REASON_AMBIGUOUS_MAPPING
    return REASON_INPUT_UNAVAILABLE


def _assert_derived_from_profile(admitted: AdmittedInput) -> None:
    """Refuse artifacts that were not derived from this exact input.

    Profile, mapping, and admissibility are all deterministic functions of the
    bytes, so each is rebuilt and compared in full rather than spot-checked. A
    digest check alone would accept a profile that carries the right source
    hash while misstating labels, inferred types, or personal-data risk.
    """
    content = admitted.content
    profile = admitted.profile
    mapping = admitted.mapping
    decision = admitted.decision
    digest = hashlib.sha256(content).hexdigest()
    if digest != profile.source_sha256_hex:
        raise FactsRefused("Content does not match the profile it is attributed to.")
    if build_profile(
        content=content,
        media_type=admitted.media_type,
        source_sha256_hex=digest,
    ) != profile:
        raise FactsRefused("Profile does not describe the supplied content.")
    if build_mapping(profile, contract=admitted.contract) != mapping:
        raise FactsRefused("Mapping was not derived from the supplied profile.")
    positions = [
        entry.column.position for entry in mapping.mappings if entry.column is not None
    ]
    if len(positions) != len(set(positions)):
        raise FactsRefused("Mapping reuses one column for more than one measure.")
    expected = assess_admissibility(
        profile,
        mapping,
        request=ReportRequest(requested_semantics=frozenset(decision.requested_semantics)),
    )
    if expected != decision:
        raise FactsRefused("Admissibility was not decided for the supplied artifacts.")


def _series(
    measures: _Measures,
    aggregated: tuple[_Aggregated, ...],
    *,
    formula_version: str,
    refusals: list[RefusedResult],
    caveats: list[str],
) -> list[FactSeries]:
    dated = [value for value in measures.dates if value is not None]
    covered = [index for index, value in enumerate(measures.dates) if value is not None]
    entry_caveats: list[str] = []
    if dated and len(covered) != len(measures.dates):
        entry_caveats.append(CAVEAT_UNDATED_ROWS_EXCLUDED)
        caveats.append(CAVEAT_UNDATED_ROWS_EXCLUDED)

    granularity = granularity_for(dated)
    results: list[FactSeries] = []
    for entry in aggregated:
        metric = f"{entry.measure}_by_period"
        if not dated or entry.total is None:
            refusals.append(
                RefusedResult(metric=metric, reason=REASON_INPUT_UNAVAILABLE)
            )
            continue
        series = build_series(
            dates=measures.dates,
            values=entry.values,
            granularity=granularity,
        )
        if not reconciles(
            series.buckets,
            total=_sum_decimal([entry.values[index] for index in covered]),
            rows_total=len(covered),
        ):
            refusals.append(
                RefusedResult(metric=metric, reason=REASON_RECONCILIATION_FAILED)
            )
            continue
        fact_id, citation_id = _identity(
            metric=metric,
            scope=(granularity,),
            formula_version=formula_version,
        )
        results.append(
            FactSeries(
                fact_id=fact_id,
                citation_id=citation_id,
                metric=metric,
                measure=entry.measure,
                precision=entry.precision,
                unit_kind=entry.unit_kind,
                series=series,
                caveats=tuple(entry_caveats),
                formula_version=formula_version,
            )
        )
    return results


def _countable_transactions(measures: _Measures) -> list[str | None] | None:
    """The identifiers, only when every row has one.

    An incomplete column undercounts silently: three rows with one null
    identifier would report two transactions as though that were the answer.
    `METRIC_TRANSACTIONS` already refuses with `incomplete_transaction_identifiers`
    for the same input, and a per-bucket count may not be more confident than the
    total it belongs to.

    **Sale keys only.** These become `Comparison.distinct_transactions` and every
    bucket's transaction count, which attach rate divides by. `RRA-008` names
    that denominator as "the exact distinct canonical transaction set in
    `dimension_complete_sales:<product|category>`" and puts returns in "neither
    numerator nor denominator" -- so counting every posted transaction divided
    by a set larger than the population the rate claims, and published every
    rate too low.

    A return's key is masked rather than dropped, so the list stays in frame
    order and keeps aligning with the values it is zipped against.
    """
    if not measures.transaction_identifiers_complete:
        return None
    if all(value is None for value in measures.transactions):
        return None
    return _sale_only(measures.transactions, measures)


def _comparisons(
    frame: pl.DataFrame,
    mapping: RetailMapping,
    aggregated: tuple[_Aggregated, ...],
    *,
    row_count: int,
    formula_version: str,
    transactions: list[str | None] | None,
    event_kinds: list[str],
    refusals: list[RefusedResult],
    caveats: list[str],
) -> list[FactComparison]:
    results: list[FactComparison] = []
    sales = [kind == EVENT_SALE for kind in event_kinds]
    for dimension in COMPARISON_DIMENSIONS:
        column = mapping.for_semantic(dimension).column
        keys = None if column is None else _raw_values(frame, column.position)
        for entry in aggregated:
            metric = f"{entry.measure}_by_{dimension}"
            if keys is None or entry.total is None:
                refusals.append(
                    RefusedResult(metric=metric, reason=REASON_INPUT_UNAVAILABLE)
                )
                continue
            comparison = build_comparison(
                dimension=dimension,
                keys=keys,
                values=entry.values,
                display=_display_label,
                transactions=transactions,
                sales=sales,
            )
            if not reconciles(
                comparison.buckets,
                total=entry.total,
                rows_total=row_count,
            ):
                refusals.append(
                    RefusedResult(metric=metric, reason=REASON_RECONCILIATION_FAILED)
                )
                continue
            entry_caveats: list[str] = []
            if comparison.truncated_values:
                entry_caveats.append(CAVEAT_BUCKETS_TRUNCATED)
                caveats.append(CAVEAT_BUCKETS_TRUNCATED)
            if comparison.redacted_values:
                entry_caveats.append(CAVEAT_PERSONAL_VALUES_REDACTED)
                caveats.append(CAVEAT_PERSONAL_VALUES_REDACTED)
            fact_id, citation_id = _identity(
                metric=metric,
                scope=(dimension,),
                formula_version=formula_version,
            )
            results.append(
                FactComparison(
                    fact_id=fact_id,
                    citation_id=citation_id,
                    metric=metric,
                    measure=entry.measure,
                    precision=entry.precision,
                    unit_kind=entry.unit_kind,
                    comparison=comparison,
                    caveats=tuple(entry_caveats),
                    formula_version=formula_version,
                )
            )
    return results


def _display_label(value: str) -> str:
    if is_personal_value(value):
        return REDACTION_SENTINEL
    return safe_value_label(value, fallback=UNLABELLED_BUCKET_LABEL)


def _measures(
    frame: pl.DataFrame,
    profile: DatasetProfile,
    mapping: RetailMapping,
    admitted_events: AdmittedEvents,
) -> _Measures:
    height = frame.height
    null_inputs = False
    monetary_scale = MIN_MONETARY_PRECISION

    def monetary(semantic: str) -> list[Decimal | None]:
        nonlocal null_inputs, monetary_scale
        column = mapping.for_semantic(semantic).column
        if column is None:
            return [None] * height
        values, scale = _decimal_values(frame, column.position)
        monetary_scale = max(monetary_scale, scale)
        null_inputs = null_inputs or any(value is None for value in values)
        return values

    revenue = monetary(SEMANTIC_REVENUE)
    cost = monetary(SEMANTIC_COST)
    discount = monetary(SEMANTIC_DISCOUNT)
    returns = monetary(SEMANTIC_RETURNS)

    units_column = mapping.for_semantic(SEMANTIC_UNITS).column
    units: list[int | None] = (
        [None] * height
        if units_column is None
        else _integer_values(frame, units_column.position)
    )
    null_inputs = null_inputs or (
        units_column is not None and any(value is None for value in units)
    )

    date_column = mapping.for_semantic(SEMANTIC_TRANSACTION_DATE).column
    dates: list[date | None] = [None] * height
    if date_column is not None:
        date_format = profile.column_at(date_column.position).date_format
        if date_format is not None:
            dates = _date_values(frame, date_column.position, date_format)

    # The canonical transaction key admission built, never the bare mapped
    # column. `RRA-003`: "A bare source transaction identifier qualifies only
    # when its recorded source contract proves package-wide uniqueness.
    # Otherwise the canonical key is an admitted composite containing the source
    # identifier and every field required for uniqueness". `admission` decides
    # which of those two a contract earned; reading the column here re-decided
    # it as "always the bare one", so two stores' identically-numbered receipts
    # collapsed into one transaction and every transaction-denominated metric
    # inherited the error.
    #
    # Index-aligned rather than joined: `_admitted_frame` narrows the frame with
    # `admitted_events.kept_positions`, and `events` is built over that same
    # kept list in the same order, so frame row `i` is `events[i]`.
    transaction_column = mapping.for_semantic(SEMANTIC_TRANSACTION_ID).column
    transactions: list[str | None] = (
        [None] * height
        if transaction_column is None
        else [event.transaction_key for event in admitted_events.events]
    )

    return _Measures(
        revenue=revenue,
        units=units,
        dates=dates,
        transactions=transactions,
        event_kinds=[event.event_kind for event in admitted_events.events],
        cost=cost,
        discount=discount,
        returns=returns,
        monetary_precision=monetary_scale,
        null_measure_inputs=null_inputs,
        transaction_identifiers_complete=(
            transaction_column is None
            or all(value is not None for value in transactions)
        ),
    )


def _add_ratio(
    add: Callable[..., None],
    *,
    metric: str,
    numerator: Decimal | int | None,
    denominator: Decimal | int | None,
    unit_kind: str,
    precision: int,
    inputs: tuple[str, ...],
    unavailable_reason: str = REASON_INPUT_UNAVAILABLE,
) -> None:
    if numerator is None or denominator is None:
        add(
            metric,
            None,
            unit_kind=unit_kind,
            precision=precision,
            inputs=inputs,
            reason=unavailable_reason,
        )
        return
    if Decimal(denominator) == 0:
        add(
            metric,
            None,
            unit_kind=unit_kind,
            precision=precision,
            inputs=inputs,
            reason=REASON_ZERO_DENOMINATOR,
        )
        return
    add(
        metric,
        Decimal(numerator) / Decimal(denominator),
        unit_kind=unit_kind,
        precision=precision,
        inputs=inputs,
    )


def _fact(
    *,
    metric: str,
    value: Decimal | int,
    precision: int,
    unit_kind: str,
    inputs: tuple[str, ...],
    formula_version: str,
) -> Fact:
    fact_id, citation_id = _identity(
        metric=metric,
        scope=(),
        formula_version=formula_version,
    )
    return Fact(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=metric,
        value=_quantize(value, precision),
        precision=precision,
        unit_kind=unit_kind,
        inputs=tuple(inputs),
        caveats=(),
        formula_version=formula_version,
    )


def fact_identity(
    *,
    metric: str,
    scope: tuple[str, ...],
    formula_version: str = FORMULA_VERSION,
) -> tuple[str, str]:
    """The stable identity of a derived fact, for the `RRA-008` analysis modules.

    Public because those modules derive facts of their own and must name them the
    same way this one does. A second derivation would be a second chance to
    collide, and `RRA-008` requires stable identifiers rather than merely unique
    ones -- two runs over the same input must reach the same identity.
    """
    return _identity(metric=metric, scope=scope, formula_version=formula_version)


def _identity(
    *,
    metric: str,
    scope: tuple[str, ...],
    formula_version: str,
) -> tuple[str, str]:
    digest = hashlib.sha256(
        canonical_json(
            {
                "metric": metric,
                "scope": list(scope),
                "formula_version": formula_version,
            }
        ).encode()
    ).hexdigest()
    return f"fct_{digest[:24]}", f"cit_{digest[:12]}"


def _quantize(value: Decimal | int, precision: int) -> str:
    return str(Decimal(value).quantize(Decimal(1).scaleb(-precision)))


def _sum_decimal(values: list[Decimal | None]) -> Decimal | None:
    present = [value for value in values if value is not None]
    return sum(present, Decimal(0)) if present else None


def _sum_integer(values: list[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _distinct(values: list[str | None]) -> int | None:
    present = {value for value in values if value is not None}
    return len(present) if present else None


def _decimal_values(frame: pl.DataFrame, position: int) -> tuple[list[Decimal | None], int]:
    values: list[Decimal | None] = []
    scale = 0
    for raw in _raw_values(frame, position):
        if raw is None:
            values.append(None)
            continue
        try:
            value = Decimal(raw)
        except InvalidOperation as error:
            raise FactsRefused("Governed measure contains an unparsable value.") from error
        if len(value.as_tuple().digits) > MAX_MEASURE_DIGITS:
            raise FactsRefused("Monetary input magnitude exceeds the governed maximum.")
        exponent = value.as_tuple().exponent
        scale = max(scale, -int(exponent)) if isinstance(exponent, int) else scale
        values.append(value)
    return values, scale


def _integer_values(frame: pl.DataFrame, position: int) -> list[int | None]:
    values: list[int | None] = []
    for raw in _raw_values(frame, position):
        if raw is None:
            values.append(None)
            continue
        try:
            count = int(raw)
        except ValueError as error:
            raise FactsRefused("Governed measure contains an unparsable value.") from error
        if len(str(abs(count))) > MAX_MEASURE_DIGITS:
            raise FactsRefused("Count input magnitude exceeds the governed maximum.")
        values.append(count)
    return values


def _date_values(frame: pl.DataFrame, position: int, date_format: str) -> list[date | None]:
    return [
        None if raw is None else parse_date(raw, date_format)
        for raw in _raw_values(frame, position)
    ]


def _text_values(frame: pl.DataFrame, position: int) -> list[str | None]:
    return list(_raw_values(frame, position))


def _raw_values(frame: pl.DataFrame, position: int) -> list[str | None]:
    column = frame.get_column(frame.columns[position]).cast(pl.String)
    return [
        None if value is None or not value.strip() else value.strip()
        for value in column.to_list()
    ]
