"""The closed view-contract refusal set and its wording (`SV1-03`; `RRA-014` `FR-141`).

`FR-141` enumerates the causes: "Unknown view/version/metric/dimension/filter,
incompatible source shape, or missing required evidence returns a stable
view-contract refusal with bilingual wording and no partial result." That
sentence is a *closed set*, and this module is it.

**A condition that seems to need an eighth cause is an `RRA-014` amendment.**
`#408` is the worked example on the `RRA-008` side: `C1-02` emitted `filter
mismatch`, a cause §Refusals does not contain, and the correction folded it into
the frozen `incomparable basis` rather than widening the set. A cause invented in
a slice is a refusal no specification authorized and no customer wording governs.

**Both languages in one table, keyed by cause.** `LABEL_WORDING` and
`CROSSVERSION_REFUSALS` are the same shape for the same reason: wording added to
one language cannot be silently missing from the other, and a test can assert
that every cause carries both. `REFUSAL_CAUSES` is *derived* from the table
rather than listed beside it -- a second list is a second truth, and it would go
stale exactly when a cause is added.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH

__all__ = [
    "CAUSE_INCOMPATIBLE_SOURCE_SHAPE",
    "CAUSE_MISSING_REQUIRED_EVIDENCE",
    "CAUSE_UNKNOWN_DIMENSION",
    "CAUSE_UNKNOWN_FILTER",
    "CAUSE_UNKNOWN_METRIC",
    "CAUSE_UNKNOWN_VERSION",
    "CAUSE_UNKNOWN_VIEW",
    "REFUSAL_CAUSES",
    "VIEW_REFUSALS",
    "ViewRefusal",
    "refusal_wording",
]

#: The request named a view the closed registry does not publish (`FR-135`).
CAUSE_UNKNOWN_VIEW = "unknown view"

#: The view exists; the named version is not the published one (`FR-143`). A
#: distinct cause from `CAUSE_UNKNOWN_VIEW` because the advice differs: one asks
#: for a view that exists, the other for a version that does.
CAUSE_UNKNOWN_VERSION = "unknown version"

#: A requested metric is outside this version's `metric_allowlist`.
CAUSE_UNKNOWN_METRIC = "unknown metric"

#: A requested dimension is outside this version's `dimension_allowlist`.
CAUSE_UNKNOWN_DIMENSION = "unknown dimension"

#: A requested filter parameter is outside `request_filter_allowlist`. `FR-137`
#: makes this a refusal rather than a silent drop: a filter quietly ignored
#: returns a wider population than the reader asked for and says nothing.
CAUSE_UNKNOWN_FILTER = "unknown filter"

#: The source is not a shape this definition admits (`FR-136`).
CAUSE_INCOMPATIBLE_SOURCE_SHAPE = "incompatible source shape"

#: The definition requires evidence the source does not carry (`FR-141`).
#: Distinct from a governed evidence *absence*, which `FR-140` keeps intact
#: through projection: that is an answer the source gave, and this is a
#: requirement it cannot meet at all.
CAUSE_MISSING_REQUIRED_EVIDENCE = "missing required evidence"

#: Every cause `FR-141` names, in both governed languages.
#:
#: The wording says what happened and what the reader can do, and never names a
#: value the request did not already carry: a refusal that echoed a published
#: metric code back at a caller who guessed it would confirm the guess.
VIEW_REFUSALS: dict[str, dict[str, str]] = {
    CAUSE_UNKNOWN_VIEW: {
        LANGUAGE_ENGLISH: (
            "That view is not one Khepri publishes. The set of views is fixed, so "
            "no view will be created on request. Choose one of the published views."
        ),
        LANGUAGE_ARABIC: (
            "هذا العرض ليس من العروض التي تنشرها خِبري. مجموعة العروض ثابتة، ولا "
            "يُنشأ أي عرض عند الطلب. اختر أحد العروض المنشورة."
        ),
    },
    CAUSE_UNKNOWN_VERSION: {
        LANGUAGE_ENGLISH: (
            "That version of the view is not published. Khepri answers the exact "
            "version you name and never substitutes a newer one. Name a published "
            "version of this view."
        ),
        LANGUAGE_ARABIC: (
            "هذه النسخة من العرض غير منشورة. تجيب خِبري على النسخة التي تحددها "
            "بالضبط ولا تستبدل بها نسخة أحدث. حدد نسخة منشورة من هذا العرض."
        ),
    },
    CAUSE_UNKNOWN_METRIC: {
        LANGUAGE_ENGLISH: (
            "This view does not carry one of the measures you asked for. A view "
            "selects from measures that already exist and calculates nothing new. "
            "Ask for a measure this view carries, or choose a view that carries it."
        ),
        LANGUAGE_ARABIC: (
            "لا يحمل هذا العرض أحد المقاييس التي طلبتها. يختار العرض من مقاييس "
            "موجودة مسبقًا ولا يحسب أي شيء جديد. اطلب مقياسًا يحمله هذا العرض، أو "
            "اختر عرضًا يحمله."
        ),
    },
    CAUSE_UNKNOWN_DIMENSION: {
        LANGUAGE_ENGLISH: (
            "This view cannot break the figures down by one of the groupings you "
            "asked for. Ask for a grouping this view supports, or choose a view "
            "that supports it."
        ),
        LANGUAGE_ARABIC: (
            "لا يستطيع هذا العرض تفصيل الأرقام حسب أحد التجميعات التي طلبتها. اطلب "
            "تجميعًا يدعمه هذا العرض، أو اختر عرضًا يدعمه."
        ),
    },
    CAUSE_UNKNOWN_FILTER: {
        LANGUAGE_ENGLISH: (
            "This view does not accept one of the filters you applied. Khepri "
            "refuses rather than ignoring it, because a filter that was quietly "
            "dropped would return more data than you asked for without saying so."
        ),
        LANGUAGE_ARABIC: (
            "لا يقبل هذا العرض أحد عوامل التصفية التي طبقتها. ترفض خِبري بدل "
            "تجاهله، لأن عامل تصفية يُهمل بصمت سيعيد بيانات أكثر مما طلبت دون أن "
            "يذكر ذلك."
        ),
    },
    CAUSE_INCOMPATIBLE_SOURCE_SHAPE: {
        LANGUAGE_ENGLISH: (
            "This view does not read the kind of result you pointed it at. A view "
            "that reads one population cannot read a two-population comparison, "
            "and the reverse. Point this view at a result of the kind it reads."
        ),
        LANGUAGE_ARABIC: (
            "لا يقرأ هذا العرض نوع النتيجة التي وجّهته إليها. العرض الذي يقرأ "
            "مجتمعًا واحدًا لا يستطيع قراءة مقارنة بين مجتمعين، والعكس. وجّه هذا "
            "العرض إلى نتيجة من النوع الذي يقرأه."
        ),
    },
    CAUSE_MISSING_REQUIRED_EVIDENCE: {
        LANGUAGE_ENGLISH: (
            "This view requires supporting evidence that the result does not "
            "carry. Khepri will not show the figures without it, because a figure "
            "shown without its evidence cannot be checked."
        ),
        LANGUAGE_ARABIC: (
            "يتطلب هذا العرض أدلة داعمة لا تحملها النتيجة. لن تعرض خِبري الأرقام "
            "بدونها، لأن الرقم المعروض دون دليله لا يمكن التحقق منه."
        ),
    },
}

#: The closed cause set, read from the wording table. Derived, never retyped:
#: a cause worded above is a cause admitted here, and a list beside the table
#: would be the second truth `FR-135` names elsewhere for the same reason.
REFUSAL_CAUSES: frozenset[str] = frozenset(VIEW_REFUSALS)


def refusal_wording(cause: str) -> dict[str, str]:
    """Both governed languages for one cause.

    Raises `KeyError` for anything else, deliberately, following
    `comparison_narrative.refusal_wording`: `FR-141` closes the cause set, so an
    unworded cause is a programming error rather than a customer-facing state.
    """
    return dict(VIEW_REFUSALS[cause])


@dataclass(frozen=True, slots=True)
class ViewRefusal:
    """A stable view-contract refusal (`FR-141`): one cause, both languages.

    The record carries no field a partial result could travel in -- no figure,
    no row, no bundle. `FR-141` admits "no partial result", and a refusal type
    with somewhere to put one is a refusal that can carry one.

    **`wording` is read from `cause`, never stored and never passed in.**
    `FR-141` requires *bilingual* wording, and while it was an ordinary field the
    type could be built two ways that break it: `ViewRefusal(cause)` alone
    produced a governed cause carrying no wording at all, and a caller could pass
    wording of its own -- text no governed vocabulary authorized, which `FR-139`
    bars elsewhere as "relabelling outside governed vocabulary".

    A property rather than a field set in `__post_init__`: assigning to a frozen
    record needs `object.__setattr__`, which `RCA-001`'s forgery scan bars from
    every production module -- "neither has an ordinary use, so a hit anywhere is
    worth a review" (`#200`). Reading the table on access needs no assignment at
    all, and leaves `cause` as the record's only state, so there is one truth
    about what this refusal says rather than a stored copy that could disagree
    with the table it came from.
    """

    cause: str

    def __post_init__(self) -> None:
        """Refuse a cause `FR-141` does not name."""
        if self.cause not in REFUSAL_CAUSES:
            raise ValueError(f"{self.cause!r} is not one of {sorted(REFUSAL_CAUSES)}")

    @property
    def wording(self) -> dict[str, str]:
        """Both governed languages for this refusal's cause."""
        return refusal_wording(self.cause)
