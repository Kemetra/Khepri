from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from functools import cache

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
from khepri.rra.source_contract import SourceContract

# v2 publishes the measure-kind disqualifiers and the shared-column refusal. The
# same profiled input can map differently under v1, so a recorded mapping
# version has to distinguish them for replay to mean anything.
MAPPING_VERSION = "rra003.mapping.v2"

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

# A governed measure must be an actual, row-level figure. A per-unit, average,
# or rate column is not row-level, and a forecast, target, budget, or plan is
# not actual — RRA-004 excludes forecasting outright. Matching is token-level,
# plus a leading prefix and an unambiguous compound, so a compact header like
# "unitcost" is caught without refusing "opportunity_cost" or
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
        # A running total is not additive: summing successive snapshots of
        # year-to-date sales publishes a figure no row ever held.
        "cumulative",
        "cumul",
        "ytd",
        "mtd",
        "qtd",
        "wtd",
        "todate",
        "yeartodate",
        "monthtodate",
        "rolling",
        "تراكمي",
        "تراكميه",
        "التراكمي",
        # Not an actual figure.
        "forecast",
        "forecasted",
        "target",
        "targeted",
        "budget",
        "budgeted",
        "plan",
        "planned",
        "projected",
        "projection",
        "estimate",
        "estimated",
        "expect",
        "expected",
        "project",
        # Normalized Arabic: forecast / expected / target / budget / plan.
        "توقع",
        "توقعات",
        "متوقع",
        "متوقعه",
        "مستهدف",
        "مستهدفه",
        "هدف",
        "ميزانيه",
        "موازنه",
        "خطه",
        "مخطط",
        "مخططه",
        "تقدير",
        "مقدر",
        "مقدره",
    }
)
_PER_UNIT_PREFIXES = (
    "unit",
    "per",
    "average",
    "avg",
    "forecast",
    "target",
    "budget",
    "planned",
    "projected",
    "estimated",
    "expected",
)
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
# A qualifier is also recognized structurally, in two ways that enumeration kept
# failing at. Strip a vocabulary term off either end of a compact label and what
# remains must not be a qualifier -- which refuses "plansales" while keeping
# "plantsales" and "projectorsales" answerable, as a prefix test could not. And
# a stem stands for its ordinary inflections, so refusing "percent" refuses
# "percentage" without anyone having to have listed it.
_QUALIFIER_SUFFIXES = ("", "s", "es", "age", "ages")
# A word that qualifies a measure in one reading and names a product in another
# is only read as a qualifier when it accounts for the whole of the rest of the
# label: "running_sales" is a running total, "running_shoe_sales" is footwear.
_AFFIX_ONLY_QUALIFIERS = frozenset({"running", "cumulated", "accumulated"})
# A compact label cannot be tokenized, so a "per" sitting between two parts is
# read as a denominator. Any separator avoids this, which is the documented way
# to express a row-level measure whose name happens to contain the sequence.
_PER_INFIXES = ("per", "لكل")
# A tax, fee, commission, or tip sits beside a sale without being one. Summing a
# "sales_tax" column as revenue publishes somebody else's money as the seller's.
_NON_REVENUE_COMPONENTS = frozenset(
    {
        "tax",
        "taxes",
        "vat",
        "gst",
        "duty",
        "duties",
        "levy",
        "excise",
        "commission",
        "commissions",
        "fee",
        "fees",
        "surcharge",
        "tip",
        "tips",
        "gratuity",
        "freight",
        "shipping",
        "ضريبه",
        "الضريبه",
        "ضرايب",
        "عموله",
        "العموله",
        "رسوم",
        "الرسوم",
        "شحن",
        "الشحن",
    }
)
# A bare "discount" or "returns" column of plain integers is indistinguishable
# between an amount, a percentage, and a count, and summing it as currency
# publishes an authoritative figure from a guess. Such a semantic is answered
# only where the label itself declares the measure to be an amount.
_AMOUNT_TOKENS = frozenset(
    {
        "amount",
        "amounts",
        "value",
        "values",
        "total",
        "totals",
        "money",
        "currency",
        "قيمه",
        "القيمه",
        "مبلغ",
        "المبلغ",
        "اجمالي",
        "الاجمالي",
    }
)

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
    requires_amount_evidence: bool = False


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
        disqualifiers=_NON_REVENUE_COMPONENTS,
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
        requires_amount_evidence=True,
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
        requires_amount_evidence=True,
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


def build_mapping(
    profile: DatasetProfile,
    *,
    contract: SourceContract,
) -> RetailMapping:
    """The admitted reading of one file: its profile, plus what was declared.

    **Deterministic from profile plus contract, and from nothing else.** Under
    `rra003.mapping.v2` this function read headers alone, which made the mapping
    a function of the file's spelling. `RRA-003` refuses that for the governed
    semantics -- event kind, status, currency, basis, identity -- because none
    of them is visible in a header or a value. Those now come from the contract,
    which is recorded, attributable, and digested; header resolution continues
    to place the *measure* columns it can legitimately infer.

    The contract is a required keyword rather than an optional one so that no
    call site can quietly fall back to the v2 behaviour: a mapping built without
    a declaration is exactly what this version exists to stop.
    """
    excluded = tuple(
        column.position for column in profile.columns if column.personal_data_risk
    )
    admissible_columns = [
        column
        for column in profile.columns
        if not column.personal_data_risk and column.inferred_type != TYPE_EMPTY
    ]
    mappings = _refuse_shared_columns(_award_shared_columns(admissible_columns))
    return RetailMapping(
        mapping_version=MAPPING_VERSION,
        mappings=_declared_over_inferred(mappings, contract),
        excluded_positions=excluded,
    )


def _declared_over_inferred(
    mappings: tuple[SemanticMapping, ...],
    contract: SourceContract,
) -> tuple[SemanticMapping, ...]:
    """Let an explicit declaration settle a semantic header resolution guessed.

    `RRA-003`: a declaration is evidence and a header is not, so where the
    operator named the column the contract wins outright -- including over a
    confident inference, and including where inference found nothing.

    Only the identity semantics are re-pointed here. `transaction_id` is the one
    the contract names directly and the one canonical transaction keys are built
    from, so a wrong column there mis-counts every transaction-denominated
    figure. The measure semantics keep their inferred resolution: `RRA-003` does
    not ask the operator to name the revenue column, and re-pointing one on no
    declaration would be inference wearing a contract's clothes.
    """
    declared = contract.identity.transaction_id_column
    if declared is None:
        return mappings
    return tuple(
        _pointed_at(mapping, declared)
        if mapping.semantic == SEMANTIC_TRANSACTION_ID
        else mapping
        for mapping in mappings
    )


def _pointed_at(mapping: SemanticMapping, label: str) -> SemanticMapping:
    """The same semantic, resolved to the declared column, or left unresolved.

    **A declared column the file does not carry leaves the semantic
    unavailable** -- it does not fall back to what inference found. `RRA-003`
    refuses to establish identity from headers, so publishing transaction facts
    from an inferred `invoice_no` after the operator declared `external_id`
    would do exactly that, under a contract that says otherwise. The declaration
    is evidence; the inference it displaced is not evidence for a different
    column.

    `STATE_UNAVAILABLE` rather than a fabricated candidate, because there is no
    column to point at and inventing one would publish a figure computed from
    nothing the contract named.
    """
    for candidate in mapping.candidates:
        if candidate.safe_label == label:
            return SemanticMapping(
                semantic=mapping.semantic,
                requirement=mapping.requirement,
                state=STATE_MAPPED,
                candidates=(
                    MappingCandidate(
                        position=candidate.position,
                        safe_label=candidate.safe_label,
                        confidence=candidate.confidence,
                        evidence=(*candidate.evidence, "declared_in_source_contract"),
                        type_compatible=candidate.type_compatible,
                    ),
                ),
            )
    return SemanticMapping(
        semantic=mapping.semantic,
        requirement=mapping.requirement,
        state=STATE_UNAVAILABLE,
        candidates=(),
    )


def _award_shared_columns(columns: list[ColumnProfile]) -> tuple[SemanticMapping, ...]:
    """Give a contested column to the semantic that claims it most strongly.

    Two semantics can reach the same column with very different evidence: a
    numeric `items` column is exact, type-confirmed units vocabulary, and only
    incidentally a product through the weaker `item` substring. Refusing both
    would cost the dataset its core measure. The strongest claim wins outright
    and every other semantic re-resolves without that column, which may find it
    a second-best one. Only a genuine tie is left for refusal.
    """
    surrendered: dict[str, set[int]] = {}
    while True:
        mappings = tuple(
            _resolve(rule, columns, frozenset(surrendered.get(rule.semantic, ())))
            for rule in SEMANTIC_RULES
        )
        awarded = False
        for claims in _shared_claims(mappings):
            strongest = max(Decimal(mapping.confidence) for mapping in claims)
            winners = [
                mapping
                for mapping in claims
                if Decimal(mapping.confidence) == strongest
            ]
            if len(winners) != 1:
                continue
            position = winners[0].column.position
            for loser in claims:
                if loser.semantic != winners[0].semantic:
                    surrendered.setdefault(loser.semantic, set()).add(position)
                    awarded = True
        if not awarded:
            return mappings


def _shared_claims(
    mappings: tuple[SemanticMapping, ...],
) -> list[list[SemanticMapping]]:
    owners: dict[int, list[SemanticMapping]] = {}
    for mapping in mappings:
        if mapping.column is not None:
            owners.setdefault(mapping.column.position, []).append(mapping)
    return [claims for claims in owners.values() if len(claims) > 1]


def _refuse_shared_columns(
    mappings: tuple[SemanticMapping, ...],
) -> tuple[SemanticMapping, ...]:
    """Refuse a column that answers more than one governed semantic.

    A header carrying vocabulary for two measures, such as `sales quantity`,
    would otherwise let one set of values stand as both money and a count. By
    this point the claims are equally strong, so there is nothing to arbitrate.
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


def _resolve(
    rule: SemanticRule,
    columns: list[ColumnProfile],
    surrendered: frozenset[int] = frozenset(),
) -> SemanticMapping:
    available = [column for column in columns if column.position not in surrendered]
    candidates = [
        candidate
        for candidate in (_candidate(rule, column) for column in available)
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
            for column in available
            if column.inferred_type in rule.accepted_types
        ]

    if rule.requires_amount_evidence:
        undeclared = [
            candidate for candidate in candidates if not _declares_amount(candidate.safe_label)
        ]
        if undeclared:
            # The column is found and named, but its measure kind is not stated,
            # so it is reported unresolved rather than summed as currency.
            return SemanticMapping(
                semantic=rule.semantic,
                requirement=rule.requirement,
                state=STATE_AMBIGUOUS,
                candidates=tuple(
                    sorted(candidates, key=lambda candidate: candidate.position)
                ),
            )

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


def _declares_amount(safe_label: str) -> bool:
    """Whether a label states that its measure is money rather than a rate or count."""
    tokens = label_tokens(safe_label)
    if _AMOUNT_TOKENS & set(tokens):
        return True
    collapsed = "".join(tokens)
    return any(term in collapsed for term in _AMOUNT_TOKENS)


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
    if any(_is_qualifier(token) for token in unclaimed):
        return True
    if any(compound in collapsed for compound in _PER_UNIT_COMPOUNDS):
        return True
    if len(tokens) == 1 and _has_per_infix(collapsed):
        return True
    if _qualified_by_affix(rule, collapsed):
        return True
    return any(
        collapsed.startswith(prefix)
        and collapsed[len(prefix) :] not in _PLURAL_REMAINDERS
        for prefix in _PER_UNIT_PREFIXES
    )


def _qualified_by_affix(rule: SemanticRule, collapsed: str) -> bool:
    """Whether a compact label reads as governed vocabulary carrying a qualifier.

    Stripping one vocabulary term off one end only ever saw two pieces, so
    "runningtotalsales" -- a qualifier followed by two vocabulary terms -- read
    as ordinary revenue. The label is decomposed into governed pieces instead,
    and refused when some complete decomposition contains a qualifier. Requiring
    the decomposition to be complete is what keeps "plantsales" and
    "runningshoesales" answerable: neither leaves a governed remainder.
    """
    return _decomposes(collapsed, rule.vocabulary, carries_qualifier=False)


@cache
def _decomposes(text: str, vocabulary: frozenset[str], *, carries_qualifier: bool) -> bool:
    if not text:
        return carries_qualifier
    for end in range(1, len(text) + 1):
        piece = text[:end]
        if piece in vocabulary:
            if _decomposes(text[end:], vocabulary, carries_qualifier=carries_qualifier):
                return True
        elif _is_affix_qualifier(piece) and _decomposes(
            text[end:], vocabulary, carries_qualifier=True
        ):
            return True
    return False


def _is_qualifier(token: str) -> bool:
    """Whether a word is a qualifier, in any of its ordinary inflections.

    Enumerating written forms is what let "percentage" through after "percent"
    was already refused, and "plansales" through after "planned" was. The
    inflection is derived from the stem instead.
    """
    return any(
        stem in _PER_UNIT_TOKENS
        for suffix in _QUALIFIER_SUFFIXES
        for stem in [token[: len(token) - len(suffix)] if suffix else token]
        if token.endswith(suffix) and stem
    )


def _is_affix_qualifier(remainder: str) -> bool:
    return remainder in _AFFIX_ONLY_QUALIFIERS or _is_qualifier(remainder)


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
