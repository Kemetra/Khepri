"""The ordered pair `rra008.crossversion.v1` compares, and whether its periods are comparable.

`RRA-008` §Two-population comparison is the only family that reads more than one
`RRA-004` population, and `G4-04` §Frozen contracts froze its Input and
Compatibility halves. This module holds the period half of that contract: which
two dataset versions may be named as a pair, in which order, and whether the two
periods are comparable *as stated*. It states no delta and reads no fact.

**The order is an input, not a derivation.** §Operand order: "the requesting
slice states which, and this specification does not infer it from sealing time,
identifier, or period." So `VersionPair` stores what it is given and sorts
nothing. Sorting would be the more helpful-looking design and would silently flip
the sign of every delta built on it -- `subject - baseline` reversed is a
different fact, not the same fact negated, which is why §Composite provenance
makes the order part of fact identity.

**Length is not compared.** §Period rule inherits §Period comparison's rule that
"natural calendar length differences, including 28-, 29-, 30-, and 31-day months,
do not make otherwise complete full periods incompatible." February against March
is the ordinary case of this family. `DatasetPeriod.days` exists so a caller can
*report* a length; nothing here refuses on one.

**Nothing aligns.** §Period rule introduces "no truncation, no rescaling, and no
per-day normalization." The prefix concession that §Period comparison allows
*within* one population is declined across versions, because it "would require
reconciling two coverage manifests, which no active artifact authorizes" -- so
`D-6` requires both periods complete and this module exposes no helper that could
shorten one to fit the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra.aggregates import GRANULARITY_DAY, GRANULARITY_MONTH

__all__ = [
    "GRANULARITY_DAY",
    "GRANULARITY_MONTH",
    "CAUSE_GRANULARITY",
    "CAUSE_INCOMPLETE",
    "CAUSE_RETAIL_DAY",
    "CAUSE_UNORDERED_PAIR",
    "DatasetPeriod",
    "UnorderedPairRefused",
    "VersionPair",
    "periods_comparable",
]

#: `RRA-008` §Operand order's refusal cause, worded as that section words it.
CAUSE_UNORDERED_PAIR = "unordered pair"

#: §Period rule's three causes. Each is one stated cause, never a combination:
#: a refusal that named two would leave a caller unable to say which to fix.
CAUSE_GRANULARITY = "granularity mismatch"
CAUSE_RETAIL_DAY = "retail day boundary mismatch"
CAUSE_INCOMPLETE = "incomplete coverage"


class UnorderedPairRefused(Exception):
    """A pair that does not name two distinct versions in a stated order.

    Raised at construction rather than returned as a cause, because an unordered
    pair is not a comparison whose periods might still be checked -- there is no
    second population to check against.
    """

    def __init__(self, cause: str = CAUSE_UNORDERED_PAIR) -> None:
        super().__init__(cause)
        self.cause = cause


@dataclass(frozen=True, slots=True)
class DatasetPeriod:
    """One dataset version's period, as stated by its coverage manifest.

    `complete` is the manifest's answer, not this module's inference: §Period rule
    defers completeness to "the authoritative `RRA-003` coverage manifest", and a
    period's date bounds cannot prove it -- an export beginning on 15 January has
    bounds that look like a whole month's prefix.
    """

    dataset_version_id: str
    start: object
    end: object
    granularity: str
    retail_day_start_hour: int
    complete: bool

    @property
    def days(self) -> int:
        """How many dates this period covers, inclusive of both bounds."""
        return (self.end - self.start).days + 1


@dataclass(frozen=True, slots=True)
class VersionPair:
    """Two distinct dataset versions in the order the caller stated.

    Equality is order-sensitive by construction: the reversed pair is a different
    `VersionPair`, which is what keeps §Composite provenance's "order is part of
    fact identity" true of anything built from this type.
    """

    subject: DatasetPeriod
    baseline: DatasetPeriod

    def __post_init__(self) -> None:
        if self.subject.dataset_version_id == self.baseline.dataset_version_id:
            raise UnorderedPairRefused


def periods_comparable(pair: VersionPair) -> str | None:
    """The refusal cause for this pair's periods, or `None` when comparable.

    Structural causes are reported before completeness: granularity and the retail
    day boundary say the two periods are not the same *kind* of window, which a
    caller must fix before completeness is even a meaningful question.
    """
    if pair.subject.granularity != pair.baseline.granularity:
        return CAUSE_GRANULARITY
    if pair.subject.retail_day_start_hour != pair.baseline.retail_day_start_hour:
        return CAUSE_RETAIL_DAY
    if not (pair.subject.complete and pair.baseline.complete):
        return CAUSE_INCOMPLETE
    return None
