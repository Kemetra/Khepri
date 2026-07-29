from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import polars as pl

from khepri.rra.admissibility import AdmissibilityDecision
from khepri.rra.aggregates import (
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
)
from khepri.rra.profiling import (
    DatasetProfile,
    canonical_json,
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

CAVEAT_CURRENCY_NOT_DECLARED = "currency_not_declared"
CAVEAT_DUPLICATE_ROWS = "duplicate_rows_present"
CAVEAT_NEGATIVE_REVENUE = "negative_revenue_present"
CAVEAT_RETURNS_NOT_NETTED = "returns_not_netted"
CAVEAT_NULL_MEASURE_INPUTS = "null_measure_inputs"
CAVEAT_UNDATED_ROWS_EXCLUDED = "rows_without_time_field_excluded"
CAVEAT_BUCKETS_TRUNCATED = "comparison_buckets_truncated"

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
    series: Series
    caveats: tuple[str, ...]

    def as_document(self, *, revenue_precision: int) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "caveats": list(self.caveats),
            **self.series.as_document(revenue_precision=revenue_precision),
        }


@dataclass(frozen=True, slots=True)
class FactComparison:
    fact_id: str
    citation_id: str
    metric: str
    comparison: Comparison
    caveats: tuple[str, ...]

    def as_document(self, *, revenue_precision: int) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "caveats": list(self.caveats),
            **self.comparison.as_document(revenue_precision=revenue_precision),
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

    def comparison(self, dimension: str) -> FactComparison | None:
        return next(
            (
                entry
                for entry in self.comparisons
                if entry.comparison.dimension == dimension
            ),
            None,
        )

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
            "series": [
                entry.as_document(revenue_precision=self.monetary_precision)
                for entry in self.series
            ],
            "comparisons": [
                entry.as_document(revenue_precision=self.monetary_precision)
                for entry in self.comparisons
            ],
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


def build_fact_package(
    *,
    content: bytes,
    media_type: str,
    profile: DatasetProfile,
    mapping: RetailMapping,
    decision: AdmissibilityDecision,
    formula_version: str = FORMULA_VERSION,
) -> FactPackage:
    if not decision.admissible:
        raise FactsRefused("Dataset is not admissible for a governed fact package.")

    frame = materialize(content, media_type)
    measures = _measures(frame, profile, mapping)
    row_count = frame.height

    facts: list[Fact] = []
    refusals: list[RefusedResult] = []
    caveats: list[str] = []

    revenue_total = _sum_decimal(measures.revenue)
    units_total = _sum_integer(measures.units)
    transactions_total = _distinct(measures.transactions)
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

    series = _series(
        measures,
        formula_version=formula_version,
        refusals=refusals,
        caveats=caveats,
    )
    comparisons = _comparisons(
        frame,
        mapping,
        measures,
        revenue_total=revenue_total,
        units_total=units_total,
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


def _series(
    measures: _Measures,
    *,
    formula_version: str,
    refusals: list[RefusedResult],
    caveats: list[str],
) -> list[FactSeries]:
    dated = [value for value in measures.dates if value is not None]
    if not dated:
        refusals.append(
            RefusedResult(metric="revenue_by_period", reason=REASON_INPUT_UNAVAILABLE)
        )
        return []

    granularity = granularity_for(dated)
    series = build_series(
        dates=measures.dates,
        revenues=measures.revenue,
        units=measures.units,
        granularity=granularity,
    )

    covered = [
        (value, revenue, unit)
        for value, revenue, unit in zip(
            measures.dates, measures.revenue, measures.units, strict=True
        )
        if value is not None
    ]
    entry_caveats: list[str] = []
    if len(covered) != len(measures.dates):
        entry_caveats.append(CAVEAT_UNDATED_ROWS_EXCLUDED)
        caveats.append(CAVEAT_UNDATED_ROWS_EXCLUDED)

    if not reconciles(
        series.buckets,
        revenue_total=_sum_decimal([revenue for _, revenue, _ in covered]),
        units_total=_sum_integer([unit for _, _, unit in covered]),
        rows_total=len(covered),
    ):
        refusals.append(
            RefusedResult(metric="revenue_by_period", reason=REASON_RECONCILIATION_FAILED)
        )
        return []

    fact_id, citation_id = _identity(
        metric="revenue_by_period",
        scope=(granularity,),
        formula_version=formula_version,
    )
    return [
        FactSeries(
            fact_id=fact_id,
            citation_id=citation_id,
            metric="revenue_by_period",
            series=series,
            caveats=tuple(entry_caveats),
        )
    ]


def _comparisons(
    frame: pl.DataFrame,
    mapping: RetailMapping,
    measures: _Measures,
    *,
    revenue_total: Decimal | None,
    units_total: int | None,
    row_count: int,
    formula_version: str,
    refusals: list[RefusedResult],
    caveats: list[str],
) -> list[FactComparison]:
    results: list[FactComparison] = []
    for dimension in COMPARISON_DIMENSIONS:
        metric = f"revenue_by_{dimension}"
        column = mapping.for_semantic(dimension).column
        if column is None:
            refusals.append(
                RefusedResult(metric=metric, reason=REASON_INPUT_UNAVAILABLE)
            )
            continue
        comparison = build_comparison(
            dimension=dimension,
            labels=_label_values(frame, column.position),
            revenues=measures.revenue,
            units=measures.units,
        )
        if not reconciles(
            comparison.buckets,
            revenue_total=revenue_total,
            units_total=units_total,
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
                comparison=comparison,
                caveats=tuple(entry_caveats),
            )
        )
    return results


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
        monetary_precision=min(monetary_scale, MAX_MONETARY_PRECISION),
        null_measure_inputs=null_inputs,
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
) -> None:
    if numerator is None or denominator is None:
        add(metric, None, unit_kind=unit_kind, precision=precision, inputs=inputs)
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


def _label_values(frame: pl.DataFrame, position: int) -> list[str | None]:
    return [
        None if raw is None else safe_value_label(raw, fallback="unlabelled")
        for raw in _raw_values(frame, position)
    ]


def _raw_values(frame: pl.DataFrame, position: int) -> list[str | None]:
    column = frame.get_column(frame.columns[position]).cast(pl.String)
    return [
        None if value is None or not value.strip() else value.strip()
        for value in column.to_list()
    ]
