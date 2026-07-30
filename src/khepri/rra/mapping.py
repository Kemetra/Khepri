from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from khepri.rra.profiling import (
    TYPE_DATE,
    TYPE_DECIMAL,
    TYPE_EMPTY,
    TYPE_INTEGER,
    TYPE_TEXT,
    ColumnProfile,
    DatasetProfile,
    label_tokens,
)

MAPPING_VERSION = "rra003.mapping.v1"

SEMANTIC_TRANSACTION_DATE = "transaction_date"
SEMANTIC_REVENUE = "revenue"
SEMANTIC_UNITS = "units"
SEMANTIC_TRANSACTION_ID = "transaction_id"
SEMANTIC_PRODUCT = "product"
SEMANTIC_CATEGORY = "category"
SEMANTIC_STORE = "store"
SEMANTIC_CHANNEL = "channel"
SEMANTIC_COST = "cost"
SEMANTIC_DISCOUNT = "discount"
SEMANTIC_RETURNS = "returns"

CORE_MEASURES = (SEMANTIC_REVENUE, SEMANTIC_UNITS)

STATE_MAPPED = "mapped"
STATE_AMBIGUOUS = "ambiguous"
STATE_CONFLICTING = "conflicting"
STATE_UNAVAILABLE = "unavailable"

REQUIREMENT_REQUIRED = "required"
REQUIREMENT_CORE_MEASURE = "core_measure"
REQUIREMENT_OPTIONAL = "optional"

# A per-unit, average, or rate column is not a row-level measure. Matching is
# token-level, plus a leading prefix and an unambiguous compound, so a compact
# header like "unitcost" is caught without refusing "opportunity_cost" or
# "supermarket_sales" the way a bare substring test would.
_PER_UNIT_TOKENS = frozenset(
    {
        "unit",
        "per",
        "each",
        "average",
        "avg",
        "rate",
        "percent",
        "pct",
        "ratio",
        "share",
        # Normalized Arabic: per / the unit / unit / average / rate / ratio.
        "لكل",
        "الوحده",
        "وحده",
        "متوسط",
        "معدل",
        "نسبه",
        "مئويه",
    }
)
_PER_UNIT_PREFIXES = ("unit", "per", "average", "avg")
_PER_UNIT_COMPOUNDS = frozenset(
    {
        "perunit",
        "peritem",
        "perorder",
        "pertransaction",
        "unitprice",
        "unitcost",
        "unitvalue",
        "averageprice",
        "averagesales",
        "averagevalue",
    }
)
_PLURAL_REMAINDERS = frozenset({"", "s", "es"})
# A compact label cannot be tokenized, so a "per" sitting between two parts is
# read as a denominator. Any separator avoids this, which is the documented way
# to express a row-level measure whose name happens to contain the sequence.
_PER_INFIXES = ("per", "لكل")

_CONFIDENCE_EXACT = Decimal("0.95")
_CONFIDENCE_TOKEN = Decimal("0.80")
_CONFIDENCE_SUBSTRING = Decimal("0.60")
_CONFIDENCE_TYPE_ONLY = Decimal("0.55")
_CONFIDENCE_TYPE_BONUS = Decimal("0.05")
_CONFIDENCE_MAX = Decimal("1.00")


@dataclass(frozen=True, slots=True)
class SemanticRule:
    semantic: str
    requirement: str
    accepted_types: frozenset[str]
    vocabulary: frozenset[str]
    type_only: bool = False
    disqualifiers: frozenset[str] = frozenset()
    rejects_per_unit: bool = False


SEMANTIC_RULES: tuple[SemanticRule, ...] = (
    SemanticRule(
        semantic=SEMANTIC_TRANSACTION_DATE,
        requirement=REQUIREMENT_REQUIRED,
        accepted_types=frozenset({TYPE_DATE}),
        vocabulary=frozenset(
            {
                "date",
                "dates",
                "day",
                "datetime",
                "timestamp",
                "period",
                "month",
                "orderdate",
                "saledate",
                "salesdate",
                "invoicedate",
                "transactiondate",
                "تاريخ",
                "اليوم",
                "الشهر",
                "شهر",
                "يوم",
            }
        ),
        type_only=True,
    ),
    SemanticRule(
        semantic=SEMANTIC_REVENUE,
        requirement=REQUIREMENT_CORE_MEASURE,
        accepted_types=frozenset({TYPE_INTEGER, TYPE_DECIMAL}),
        vocabulary=frozenset(
            {
                "revenue",
                "revenues",
                "sales",
                "netsales",
                "grosssales",
                "salesamount",
                "amount",
                "total",
                "turnover",
                "salesvalue",
                "ايرادات",
                "الايرادات",
                "مبيعات",
                "المبيعات",
                "اجمالي",
                "الاجمالي",
                "قيمه",
                "القيمه",
            }
        ),
        rejects_per_unit=True,
    ),
    SemanticRule(
        semantic=SEMANTIC_UNITS,
        requirement=REQUIREMENT_CORE_MEASURE,
        accepted_types=frozenset({TYPE_INTEGER}),
        vocabulary=frozenset(
            {
                "units",
                "unit",
                "quantity",
                "quantities",
                "qty",
                "pieces",
                "items",
                "unitssold",
                "الكميه",
                "كميه",
                "عدد",
                "وحدات",
                "وحده",
            }
        ),
        disqualifiers=frozenset({"price", "cost", "value", "amount", "قيمه", "تكلفه"}),
        rejects_per_unit=True,
    ),
    SemanticRule(
        semantic=SEMANTIC_TRANSACTION_ID,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_TEXT, TYPE_INTEGER}),
        vocabulary=frozenset(
            {
                "transactionid",
                "orderid",
                "invoice",
                "invoiceno",
                "invoicenumber",
                "receipt",
                "receiptno",
                "bill",
                "billno",
                "ticket",
                "فاتوره",
                "الفاتوره",
                "طلب",
                "الطلب",
            }
        ),
    ),
    SemanticRule(
        semantic=SEMANTIC_PRODUCT,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_TEXT, TYPE_INTEGER}),
        vocabulary=frozenset(
            {
                "product",
                "products",
                "productname",
                "sku",
                "item",
                "itemname",
                "barcode",
                "منتج",
                "المنتج",
                "صنف",
                "الصنف",
                "باركود",
            }
        ),
    ),
    SemanticRule(
        semantic=SEMANTIC_CATEGORY,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_TEXT}),
        vocabulary=frozenset(
            {
                "category",
                "categories",
                "department",
                "family",
                "group",
                "subcategory",
                "فئه",
                "الفئه",
                "تصنيف",
                "التصنيف",
                "قسم",
                "القسم",
            }
        ),
    ),
    SemanticRule(
        semantic=SEMANTIC_STORE,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_TEXT, TYPE_INTEGER}),
        vocabulary=frozenset(
            {
                "store",
                "stores",
                "storename",
                "branch",
                "branches",
                "outlet",
                "shop",
                "location",
                "site",
                "فرع",
                "الفرع",
                "متجر",
                "المتجر",
                "موقع",
            }
        ),
    ),
    SemanticRule(
        semantic=SEMANTIC_CHANNEL,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_TEXT}),
        vocabulary=frozenset(
            {
                "channel",
                "channels",
                "platform",
                "medium",
                "saleschannel",
                "قناه",
                "القناه",
                "منصه",
            }
        ),
    ),
    SemanticRule(
        semantic=SEMANTIC_COST,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_INTEGER, TYPE_DECIMAL}),
        vocabulary=frozenset(
            {
                "cost",
                "costs",
                "cogs",
                "costofgoods",
                "totalcost",
                "تكلفه",
                "التكلفه",
            }
        ),
        rejects_per_unit=True,
    ),
    SemanticRule(
        semantic=SEMANTIC_DISCOUNT,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_INTEGER, TYPE_DECIMAL}),
        vocabulary=frozenset(
            {
                "discount",
                "discounts",
                "promo",
                "promotion",
                "markdown",
                "rebate",
                "خصم",
                "الخصم",
                "تخفيض",
            }
        ),
        rejects_per_unit=True,
    ),
    SemanticRule(
        semantic=SEMANTIC_RETURNS,
        requirement=REQUIREMENT_OPTIONAL,
        accepted_types=frozenset({TYPE_INTEGER, TYPE_DECIMAL}),
        vocabulary=frozenset(
            {
                "return",
                "returns",
                "returned",
                "refund",
                "refunds",
                "refunded",
                "creditnote",
                "مرتجع",
                "مرتجعات",
                "استرداد",
            }
        ),
        rejects_per_unit=True,
    ),
)

_RULES_BY_SEMANTIC = {rule.semantic: rule for rule in SEMANTIC_RULES}

KNOWN_SEMANTICS = frozenset(_RULES_BY_SEMANTIC)


@dataclass(frozen=True, slots=True)
class MappingCandidate:
    position: int
    safe_label: str
    confidence: str
    evidence: tuple[str, ...]
    type_compatible: bool


@dataclass(frozen=True, slots=True)
class SemanticMapping:
    semantic: str
    requirement: str
    state: str
    candidates: tuple[MappingCandidate, ...]

    @property
    def column(self) -> MappingCandidate | None:
        if self.state != STATE_MAPPED:
            return None
        return self.candidates[0]

    @property
    def confidence(self) -> str | None:
        return self.candidates[0].confidence if self.candidates else None

    @property
    def evidence(self) -> tuple[str, ...]:
        return self.candidates[0].evidence if self.candidates else ()

    def as_document(self) -> dict[str, object]:
        return {
            "semantic": self.semantic,
            "requirement": self.requirement,
            "state": self.state,
            "candidates": [
                {
                    "position": candidate.position,
                    "safe_label": candidate.safe_label,
                    "confidence": candidate.confidence,
                    "evidence": list(candidate.evidence),
                    "type_compatible": candidate.type_compatible,
                }
                for candidate in self.candidates
            ],
        }


@dataclass(frozen=True, slots=True)
class RetailMapping:
    mapping_version: str
    mappings: tuple[SemanticMapping, ...]
    excluded_positions: tuple[int, ...]

    def for_semantic(self, semantic: str) -> SemanticMapping:
        for mapping in self.mappings:
            if mapping.semantic == semantic:
                return mapping
        raise KeyError(semantic)

    def state_of(self, semantic: str) -> str:
        return self.for_semantic(semantic).state

    @property
    def mapped_semantics(self) -> tuple[str, ...]:
        return tuple(
            mapping.semantic for mapping in self.mappings if mapping.state == STATE_MAPPED
        )

    def as_document(self) -> dict[str, object]:
        return {
            "mapping_version": self.mapping_version,
            "mappings": [mapping.as_document() for mapping in self.mappings],
            "excluded_positions": list(self.excluded_positions),
        }


def build_mapping(profile: DatasetProfile) -> RetailMapping:
    excluded = tuple(
        column.position for column in profile.columns if column.personal_data_risk
    )
    admissible_columns = [
        column
        for column in profile.columns
        if not column.personal_data_risk and column.inferred_type != TYPE_EMPTY
    ]
    mappings = _refuse_shared_columns(
        tuple(_resolve(rule, admissible_columns) for rule in SEMANTIC_RULES)
    )
    return RetailMapping(
        mapping_version=MAPPING_VERSION,
        mappings=mappings,
        excluded_positions=excluded,
    )


def _refuse_shared_columns(
    mappings: tuple[SemanticMapping, ...],
) -> tuple[SemanticMapping, ...]:
    """Refuse a column that answers more than one governed semantic.

    A header carrying vocabulary for two measures, such as `sales quantity`,
    would otherwise let one set of values stand as both money and a count.
    """
    owners: dict[int, int] = {}
    for mapping in mappings:
        column = mapping.column
        if column is not None:
            owners[column.position] = owners.get(column.position, 0) + 1
    shared = {position for position, count in owners.items() if count > 1}
    if not shared:
        return mappings
    return tuple(
        replace(mapping, state=STATE_CONFLICTING)
        if mapping.column is not None and mapping.column.position in shared
        else mapping
        for mapping in mappings
    )


def requirement_of(semantic: str) -> str:
    return _RULES_BY_SEMANTIC[semantic].requirement


def _resolve(rule: SemanticRule, columns: list[ColumnProfile]) -> SemanticMapping:
    candidates = [
        candidate
        for candidate in (_candidate(rule, column) for column in columns)
        if candidate is not None
    ]
    if not candidates and rule.type_only:
        candidates = [
            MappingCandidate(
                position=column.position,
                safe_label=column.safe_label,
                confidence=str(_CONFIDENCE_TYPE_ONLY),
                evidence=("type_only",),
                type_compatible=True,
            )
            for column in columns
            if column.inferred_type in rule.accepted_types
        ]

    compatible = sorted(
        (candidate for candidate in candidates if candidate.type_compatible),
        key=lambda candidate: (-Decimal(candidate.confidence), candidate.position),
    )
    if compatible:
        best = compatible[0]
        tied = tuple(
            candidate
            for candidate in compatible
            if Decimal(candidate.confidence) == Decimal(best.confidence)
        )
        if len(tied) == 1:
            return SemanticMapping(
                semantic=rule.semantic,
                requirement=rule.requirement,
                state=STATE_MAPPED,
                candidates=(best,),
            )
        return SemanticMapping(
            semantic=rule.semantic,
            requirement=rule.requirement,
            state=STATE_AMBIGUOUS,
            candidates=tied,
        )

    if candidates:
        return SemanticMapping(
            semantic=rule.semantic,
            requirement=rule.requirement,
            state=STATE_CONFLICTING,
            candidates=tuple(
                sorted(candidates, key=lambda candidate: candidate.position)
            ),
        )
    return SemanticMapping(
        semantic=rule.semantic,
        requirement=rule.requirement,
        state=STATE_UNAVAILABLE,
        candidates=(),
    )


def _disqualified(rule: SemanticRule, tokens: tuple[str, ...], collapsed: str) -> bool:
    """Whether a label describes something other than this row-level measure.

    A disqualifier never overrides an exact vocabulary term, so a column named
    `unit` still answers `units` while `unit_cost` and `unitcost` answer neither
    `cost` nor `units`.
    """
    unclaimed = [token for token in tokens if token not in rule.vocabulary]
    if rule.disqualifiers.intersection(unclaimed):
        return True
    if not rule.rejects_per_unit or collapsed in rule.vocabulary:
        return False
    if _PER_UNIT_TOKENS.intersection(unclaimed):
        return True
    if any(compound in collapsed for compound in _PER_UNIT_COMPOUNDS):
        return True
    if len(tokens) == 1 and _has_per_infix(collapsed):
        return True
    return any(
        collapsed.startswith(prefix)
        and collapsed[len(prefix) :] not in _PLURAL_REMAINDERS
        for prefix in _PER_UNIT_PREFIXES
    )


def _has_per_infix(collapsed: str) -> bool:
    return any(
        0 < position < len(collapsed) - len(infix)
        for infix in _PER_INFIXES
        for position in [collapsed.find(infix)]
        if position != -1
    )


def _candidate(rule: SemanticRule, column: ColumnProfile) -> MappingCandidate | None:
    tokens = label_tokens(column.safe_label)
    if not tokens:
        return None
    collapsed = "".join(tokens)
    if _disqualified(rule, tokens, collapsed):
        return None

    confidence: Decimal | None = None
    evidence: list[str] = []
    if collapsed in rule.vocabulary:
        confidence = _CONFIDENCE_EXACT
        evidence.append("label_exact")
    elif rule.vocabulary & set(tokens):
        confidence = _CONFIDENCE_TOKEN
        evidence.append("label_token")
    else:
        matched = sorted(term for term in rule.vocabulary if len(term) > 3 and term in collapsed)
        if matched:
            confidence = _CONFIDENCE_SUBSTRING
            evidence.append("label_substring")
    if confidence is None:
        return None

    type_compatible = column.inferred_type in rule.accepted_types
    if type_compatible:
        confidence = min(confidence + _CONFIDENCE_TYPE_BONUS, _CONFIDENCE_MAX)
        evidence.append("type_confirmed")
    else:
        evidence.append("type_conflict")

    return MappingCandidate(
        position=column.position,
        safe_label=column.safe_label,
        confidence=str(confidence),
        evidence=tuple(evidence),
        type_compatible=type_compatible,
    )
