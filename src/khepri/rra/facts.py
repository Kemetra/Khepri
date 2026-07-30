from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import polars as pl

from khepri.rra.admissibility import (
    AdmissibilityDecision,
    ReportRequest,
    assess_admissibility,
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
    RetailMapping,
    build_mapping,
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

PACKAGE_VERSION = "rra004.package.v1"
FORMULA_VERSION = "rra004.formula.v1"

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

CAVEAT_CURRENCY_NOT_DECLARED = "currency_not_declared"
CAVEAT_DUPLICATE_ROWS = "duplicate_rows_present"
CAVEAT_NEGATIVE_REVENUE = "negative_revenue_present"
CAVEAT_RETURNS_NOT_NETTED = "returns_not_netted"
CAVEAT_NULL_MEASURE_INPUTS = "null_measure_inputs"
CAVEAT_UNDATED_ROWS_EXCLUDED = "rows_without_time_field_excluded"
CAVEAT_BUCKETS_TRUNCATED = "comparison_buckets_truncated"
CAVEAT_PERSONAL_VALUES_REDACTED = "personal_values_redacted"
CAVEAT_DISCOUNT_AS_AMOUNT = "discount_interpreted_as_amount"

RATIO_PRECISION = 4
MIN_MONETARY_PRECISION = 2
MAX_MONETARY_PRECISION = 6

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
    fact_id: str
    citation_id: str
    metric: str
    value: str
    precision: int
    unit_kind: str
    inputs: tuple[str, ...]
    caveats: tuple[str, ...]

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
        }


@dataclass(frozen=True, slots=True)
class FactSeries:
    fact_id: str
    citation_id: str
    metric: str
    measure: str
    precision: int
    series: Series
    caveats: tuple[str, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "measure": self.measure,
            "precision": self.precision,
            "caveats": list(self.caveats),
            **self.series.as_document(precision=self.precision),
        }


@dataclass(frozen=True, slots=True)
class FactComparison:
    fact_id: str
    citation_id: str
    metric: str
    measure: str
    precision: int
    comparison: Comparison
    caveats: tuple[str, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "measure": self.measure,
            "precision": self.precision,
            "caveats": list(self.caveats),
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
            "monetary_precision": self.monetary_precision,
            "facts": [fact.as_document() for fact in self.facts],
            "series": [entry.as_document() for entry in self.series],
            "comparisons": [entry.as_document() for entry in self.comparisons],
            "refusals": [refusal.as_document() for refusal in self.refusals],
            "caveats": list(self.caveats),
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


def build_fact_package(
    *,
    content: bytes,
    media_type: str,
    profile: DatasetProfile,
    mapping: RetailMapping,
    decision: AdmissibilityDecision,
    formula_version: str = FORMULA_VERSION,
) -> FactPackage:
    if formula_version != FORMULA_VERSION:
        raise FactsRefused("Formula version is not implemented by this package builder.")
    _assert_derived_from_profile(content, media_type, profile, mapping, decision)
    if not decision.admissible:
        raise FactsRefused("Dataset is not admissible for a governed fact package.")

    frame = materialize(content, media_type)
    measures = _measures(frame, profile, mapping)
    if measures.monetary_precision > MAX_MONETARY_PRECISION:
        raise FactsRefused("Monetary input precision exceeds the governed maximum.")
    row_count = frame.height

    facts: list[Fact] = []
    refusals: list[RefusedResult] = []
    caveats: list[str] = []

    revenue_total = _sum_decimal(measures.revenue)
    units_total = _sum_integer(measures.units)
    transactions_total = (
        _distinct(measures.transactions)
        if measures.transaction_identifiers_complete
        else None
    )
    transactions_reason = (
        REASON_INPUT_UNAVAILABLE
        if measures.transaction_identifiers_complete
        else REASON_INCOMPLETE_IDENTIFIERS
    )
    cost_total = _sum_decimal(measures.cost)
    discount_total = _sum_decimal(measures.discount)
    returns_total = _sum_decimal(measures.returns)

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
    )
    add(
        METRIC_RETURNS,
        returns_total,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_RETURNS,),
    )

    _add_ratio(
        add,
        metric=METRIC_AVERAGE_ORDER_VALUE,
        numerator=revenue_total,
        denominator=transactions_total,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_REVENUE, SEMANTIC_TRANSACTION_ID),
        unavailable_reason=transactions_reason,
    )
    _add_ratio(
        add,
        metric=METRIC_AVERAGE_SELLING_PRICE,
        numerator=revenue_total,
        denominator=units_total,
        unit_kind=UNIT_MONETARY,
        precision=money,
        inputs=(SEMANTIC_REVENUE, SEMANTIC_UNITS),
    )

    gross_profit = (
        None if revenue_total is None or cost_total is None else revenue_total - cost_total
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
        denominator=revenue_total,
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
        ),
        _Aggregated(
            measure=SEMANTIC_UNITS,
            values=[None if value is None else Decimal(value) for value in measures.units],
            total=None if units_total is None else Decimal(units_total),
            precision=0,
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
        refusals=refusals,
        caveats=caveats,
    )

    if any(fact.unit_kind == UNIT_MONETARY for fact in facts):
        caveats.append(CAVEAT_CURRENCY_NOT_DECLARED)
    if measures.null_measure_inputs:
        caveats.append(CAVEAT_NULL_MEASURE_INPUTS)
    if revenue_total is not None and any(
        value is not None and value < 0 for value in measures.revenue
    ):
        caveats.append(CAVEAT_NEGATIVE_REVENUE)
    if returns_total is not None:
        caveats.append(CAVEAT_RETURNS_NOT_NETTED)
    if discount_total is not None:
        caveats.append(CAVEAT_DISCOUNT_AS_AMOUNT)
    if row_count and int(frame.is_duplicated().sum()):
        caveats.append(CAVEAT_DUPLICATE_ROWS)

    return FactPackage(
        package_version=PACKAGE_VERSION,
        formula_version=formula_version,
        mapping_version=mapping.mapping_version,
        profile_digest=profile.digest,
        source_sha256_hex=profile.source_sha256_hex,
        row_count=row_count,
        monetary_precision=money,
        facts=tuple(facts),
        series=tuple(series),
        comparisons=tuple(comparisons),
        refusals=tuple(sorted(refusals, key=lambda refusal: refusal.metric)),
        caveats=tuple(sorted(set(caveats))),
    )


def _assert_derived_from_profile(
    content: bytes,
    media_type: str,
    profile: DatasetProfile,
    mapping: RetailMapping,
    decision: AdmissibilityDecision,
) -> None:
    """Refuse artifacts that were not derived from this exact input.

    Profile, mapping, and admissibility are all deterministic functions of the
    bytes, so each is rebuilt and compared in full rather than spot-checked. A
    digest check alone would accept a profile that carries the right source
    hash while misstating labels, inferred types, or personal-data risk.
    """
    digest = hashlib.sha256(content).hexdigest()
    if digest != profile.source_sha256_hex:
        raise FactsRefused("Content does not match the profile it is attributed to.")
    if build_profile(
        content=content,
        media_type=media_type,
        source_sha256_hex=digest,
    ) != profile:
        raise FactsRefused("Profile does not describe the supplied content.")
    if build_mapping(profile) != mapping:
        raise FactsRefused("Mapping was not derived from the supplied profile.")
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
                series=series,
                caveats=tuple(entry_caveats),
            )
        )
    return results


def _comparisons(
    frame: pl.DataFrame,
    mapping: RetailMapping,
    aggregated: tuple[_Aggregated, ...],
    *,
    row_count: int,
    formula_version: str,
    refusals: list[RefusedResult],
    caveats: list[str],
) -> list[FactComparison]:
    results: list[FactComparison] = []
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
                    comparison=comparison,
                    caveats=tuple(entry_caveats),
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

    transaction_column = mapping.for_semantic(SEMANTIC_TRANSACTION_ID).column
    transactions: list[str | None] = (
        [None] * height
        if transaction_column is None
        else _text_values(frame, transaction_column.position)
    )

    return _Measures(
        revenue=revenue,
        units=units,
        dates=dates,
        transactions=transactions,
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
    )


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
            values.append(int(raw))
        except ValueError as error:
            raise FactsRefused("Governed measure contains an unparsable value.") from error
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
