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

ADAPTER_VERSION = "rra005.deterministic.v1"

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
            # Every metric was refused, so there is nothing to say. Raising the
            # governed refusal is the honest answer; inventing a sentence about
            # an empty package is exactly what a narrator must not do.
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

    Facts come first, then series, then comparisons, so the ordering is a
    property of the request rather than of dictionary iteration. Only entries
    carrying a citable identifier and a quotable value become sections.
    """
    document = request.document
    plans: list[SectionPlan] = []
    for kind in ("facts", "series", "comparisons"):
        for entry in document.get(kind, []):
            plan = _plan_entry(entry, kind)
            if plan is not None:
                plans.append(plan)
            if len(plans) >= MAX_SECTIONS:
                return tuple(plans)
    return tuple(plans)


def _plan_entry(entry: dict[str, object], kind: str) -> SectionPlan | None:
    """One entry's plan, or nothing when it carries no quotable figure."""
    citation = entry.get("citation_id") or entry.get("fact_id")
    metric = entry.get("metric")
    if not isinstance(citation, str) or not isinstance(metric, str):
        return None
    figure = _figure(entry, kind)
    caveats = tuple(str(caveat) for caveat in entry.get("caveats", ()) or ())
    return SectionPlan(
        section_id=f"{kind}.{citation}",
        metric=metric,
        citation=citation,
        figure=figure,
        caveats=caveats,
    )


def _figure(entry: dict[str, object], kind: str) -> str | None:
    """The one value this section quotes, exactly as the request supplied it.

    Never computed and never reformatted. A supplied string is quoted verbatim
    or nothing is quoted at all, because deriving a rendering is how a narrative
    states a number the package did not carry.
    """
    if kind == "facts":
        value = entry.get("value")
        return value if isinstance(value, str) else None
    buckets = entry.get("points") or entry.get("buckets") or ()
    if not isinstance(buckets, list) or not buckets:
        return None
    last = buckets[-1]
    value = last.get("value") if isinstance(last, dict) else None
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
    """A flat English sentence quoting at most one supplied figure."""
    label = _readable(plan.metric)
    if plan.figure is None:
        return f"The report covers {label} as recorded in the fact package."
    return f"The recorded {label} is {plan.figure}."


def _arabic(plan: SectionPlan) -> str:
    """The Arabic counterpart, quoting the identical figure token.

    Different words, same claim. The figure is the same string, so the stated
    figure sets `validate` compares are equal without either language knowing
    about the other.
    """
    label = _readable(plan.metric)
    if plan.figure is None:
        return f"يغطي التقرير {label} وفق حزمة الحقائق."
    return f"القيمة المسجلة لـ {label} هي {plan.figure}."


def _readable(metric: str) -> str:
    """A metric identifier as words, with no character a validator refuses.

    Underscores become spaces so the sentence reads. Nothing else changes: the
    metric name is a governed identifier, not customer text, and rewriting it
    further would be inventing a label.
    """
    return metric.replace("_", " ")


__all__ = ["ADAPTER_VERSION", "MAX_SECTIONS", "DeterministicNarrator", "SectionPlan"]
