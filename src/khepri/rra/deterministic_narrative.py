"""A deterministic Arabic and English narrator that needs no provider.

**What this is for.** `ReportPipeline.compose_narrative` raises when the narrative
is refused, so no report bundle can be produced without a `NarrativeAdapter` whose
draft survives `narrative.validate`. No concrete adapter exists in this repository
— only a test stub — and `KHEPRI-DEC-005` reserves provider selection to its own
architecture decision. This composes prose from the fact package itself instead, so
a report reaches a bundle without pre-empting that decision.

**It is not a stand-in for a provider.** It writes flat, mechanical sentences and
makes no interpretive claim whatsoever. Its `adapter_version` says so, so any
`NarrativeAttempt` recording a run made here is identifiable as such forever.

**How parity is guaranteed rather than checked.** `validate` compares five things
across languages: the stated figures, which facts were cited, which caveats were
covered, which labels were declared, and which directions were declared. Both
languages are rendered here from one `SectionPlan` list, so all five are equal by
construction — the same relationship `khepri.infra.app` relies on when it hands one
`EnvironmentProps` to both stacks rather than building two that happen to agree.
Only the surrounding words differ.

**Why the figures are written in Western digits in both languages.**
`_normalize_digits` maps Arabic-Indic digits onto ASCII before comparing, so
`٥٠٠٫٠٠` and `500.00` ground identically — but the *stated figure set* is compared
after normalization too, so either choice would pass. Western digits are used in
both because they are what the package supplies and what the workbook surface
renders; converting them would be a rendering decision this module has no mandate
to make.

**Why a proportion is quoted as a percentage.** `RRA-006`'s surfaces render a
ratio fact as `55.89%`, and prose quoting the bare `0.5589` beside that table
states the same fact in a second unit. The percentage form is *supplied* --
`narrative._stated` attaches `value_percent` to every ratio fact so that a
narrative saying `66.67%` is quoting rather than converting -- so choosing it
costs this module none of its "never computed" rule.

Which ratios are proportions is read from `bundle.PERCENTAGE_METRICS`, because
`unit_kind` cannot tell one from a rate: `basket_items_per_transaction` is
`ratio`-kind too, and quoting its supplied `value_percent` would say a basket
holds `382500.0000%` items. That import points from `RRA-005` at an `RRA-006`
module, which is the wrong direction; the set describes what a metric *is*
rather than how it is drawn, so `facts` is its likelier home. Moving it is a
separate change and is deliberately not made here, where the defect to fix is
the unit a customer reads.

**What is deliberately never declared.** `direction` and `labels` are left unset.
`_assert_declared_direction` requires the cited facts to exhibit exactly one
movement, and movement is derived only from series `points`; a section citing a
plain fact has none, so declaring a direction would refuse. Labels are available
only from points and buckets for the same reason. Both fields are optional and
declaring them here would buy nothing but refusal classes.

**What is never written.** No currency code, no percent word, and no numeral word
run may sit in the prose: `_assert_grounded_numbers` refuses a figure adjacent to a
currency code or a percent word, and `_assert_no_worded_quantity` refuses two or
more numeral words in a row. Sentences here therefore quote bare figures and let
the metric name carry the meaning.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    REASON_EMPTY_NARRATIVE,
    LanguageNarrative,
    NarrativeDraft,
    NarrativeRefused,
    NarrativeRequest,
    NarrativeSection,
)
from khepri.rra.presentation import PERCENTAGE_METRICS
from khepri.rra.rendering.wording import business_metric_name

# v2 quotes a proportion in the percentage form the request supplies, where v1
# quoted the bare ratio and read `0.5589` beside a table stating `55.89%`. The
# version is recorded on every `NarrativeAttempt`, so a stored run says which of
# the two unit conventions its prose was written in.
#
# v3 states whole-file facts only, each by the name the report gives it. v2 also
# quoted a breakdown's last bucket under the breakdown's name, so "revenue by
# category is 6584.93" was one category read as a total (SCRUM-21 A9), and its
# Arabic named every measure by its English code.
ADAPTER_VERSION = "rra005.deterministic.v3"

# Kept well inside the section budget a fact package can produce. A narrative is
# a summary; quoting every fact would be a transcript.
MAX_SECTIONS = 12


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """One section's claims, before either language has been written.

    Language-neutral on purpose. Everything `validate` compares across languages
    is decided here, once, so the two renderings cannot disagree about it.
    """

    section_id: str
    metric: str
    citation: str
    figure: str | None
    caveats: tuple[str, ...]


class DeterministicNarrator:
    """Compose grounded Arabic and English prose directly from the request.

    Satisfies `NarrativeAdapter` structurally: an `adapter_version` property and
    a `draft` method. A composition root must select it explicitly.
    """

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    def draft(self, request: NarrativeRequest, *, timeout_seconds: Decimal) -> NarrativeDraft:
        """Build both languages from one plan.

        `timeout_seconds` is accepted and ignored: composing takes no measurable
        time and there is no provider to bound. Accepting it keeps the signature
        the Protocol specifies rather than a convenient subset of it.
        """
        plans = _plan(request)
        if not plans:
            # No whole-file fact can be cited by a governed name (every metric
            # was refused, or none is named), so there is nothing to say.
            # Raising the governed refusal is the honest answer; inventing a
            # sentence about an empty package is exactly what a narrator must
            # not do.
            raise NarrativeRefused(REASON_EMPTY_NARRATIVE)
        return NarrativeDraft(
            adapter_version=ADAPTER_VERSION,
            request_digest=request.digest,
            languages=(
                LanguageNarrative(
                    language=LANGUAGE_ARABIC,
                    sections=tuple(_section(plan, _arabic) for plan in plans),
                ),
                LanguageNarrative(
                    language=LANGUAGE_ENGLISH,
                    sections=tuple(_section(plan, _english) for plan in plans),
                ),
            ),
        )


def _plan(request: NarrativeRequest) -> tuple[SectionPlan, ...]:
    """Decide what both languages will say, from the request alone.

    **Whole-file facts only.** A series or comparison is one figure per bucket,
    and a sentence has room for one. Quoting the last bucket under the
    breakdown's name read "revenue by category is 6584.93" for one category, a
    change of meaning `RRA-005` does not allow. Every breakdown is stated in full
    in the report's own tables, so the commentary loses nothing a reader needs.

    The request's order is kept, so it is a property of the request rather than
    of dictionary iteration.
    """
    plans = (_plan_entry(entry) for entry in request.document.get("facts", []))
    return tuple(plan for plan in plans if plan is not None)[:MAX_SECTIONS]


def _plan_entry(entry: dict[str, object]) -> SectionPlan | None:
    """One fact's plan, or nothing when it cannot be cited or named.

    A metric the report has no name for is left out rather than quoted by its
    code: the code is an internal identifier, never customer text.
    """
    citation = entry.get("citation_id") or entry.get("fact_id")
    metric = entry.get("metric")
    if not isinstance(citation, str) or not isinstance(metric, str):
        return None
    if any(business_metric_name(metric, language) is None for language in _LANGUAGES):
        return None
    caveats = tuple(str(caveat) for caveat in entry.get("caveats", ()) or ())
    return SectionPlan(
        section_id=f"facts.{citation}",
        metric=metric,
        citation=citation,
        figure=_fact_figure(entry),
        caveats=caveats,
    )


_LANGUAGES = (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)


def _fact_figure(entry: dict[str, object]) -> str | None:
    """A fact's quotable figure: its percentage form when it has one.

    Never computed and never reformatted. A supplied string is quoted verbatim
    or nothing is quoted at all, because deriving a rendering is how a narrative
    states a number the package did not carry. Choosing *which* supplied string
    to quote is not deriving one.

    **A proportion quoted as a bare ratio contradicted the table beside it.**
    `RRA-006`\'s surfaces render `gross_margin` as `55.89%`; this module quoted
    the package value and the same report read "The recorded gross margin is
    0.5589" in its commentary. Both numbers are correct and they are not in the
    same unit, so a reader comparing prose against table sees two figures.

    Nothing is converted here. `narrative._stated` attaches `value_percent` to
    the request precisely so a narrative can say `66.67%` without calculating,
    and this quotes that string with the sign appended -- which
    `_assert_grounded_numbers` grounds against `percents` rather than `numbers`,
    so a percentage claim is checked as a percentage.

    The digits are the request\'s, not the table\'s: `value_percent` carries the
    fact\'s own precision, so a margin reads `55.8900%` in prose where the table
    states `55.89%`. Same unit and same value; quantizing to match would be this
    module reformatting a supplied figure, which is the rule it does not break.
    """
    if entry.get("metric") in PERCENTAGE_METRICS:
        percent = entry.get("value_percent")
        if isinstance(percent, str):
            return f"{percent}%"
    value = entry.get("value")
    return value if isinstance(value, str) else None


def _section(plan: SectionPlan, render: object) -> NarrativeSection:
    """One plan, rendered into one language.

    `labels` and `direction` are omitted rather than declared. See the module
    docstring: both are only groundable from series points and bucket labels, and
    declaring either from a plain fact is an automatic refusal.
    """
    text = render(plan)  # type: ignore[operator]
    return NarrativeSection(
        section_id=plan.section_id,
        text=text,
        cited_fact_ids=(plan.citation,),
        caveats=plan.caveats,
    )


def _english(plan: SectionPlan) -> str:
    """A flat English sentence quoting at most one supplied figure.

    Name first, then the figure, so no verb has to agree with a plural name
    ("The recorded units is 836" did).
    """
    name = business_metric_name(plan.metric, LANGUAGE_ENGLISH)
    if plan.figure is None:
        return f"The report covers {name} as recorded in the file."
    return f"{name}: {plan.figure}, as recorded in the file."


def _arabic(plan: SectionPlan) -> str:
    """The Arabic counterpart, quoting the identical figure token.

    Different words, same claim. The figure is the same string, so the stated
    figure sets `validate` compares are equal without either language knowing
    about the other.
    """
    name = business_metric_name(plan.metric, LANGUAGE_ARABIC)
    if plan.figure is None:
        return f"يغطي التقرير {name} وفق ما سُجّل في الملف."
    return f"{name}: {plan.figure}، وفق ما سُجّل في الملف."


__all__ = ["ADAPTER_VERSION", "MAX_SECTIONS", "DeterministicNarrator", "SectionPlan"]
