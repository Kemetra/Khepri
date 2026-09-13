"""The decision surface's visible controls (`D1-07`; active `RCA-008` `FR-166`).

`shell_decisions.py` renders the figures; this renders what chose them. A module
of its own rather than more of that one: it is already the largest surface module
in the shell, and CodeScene scores the file rather than the addition.

**What the three controls actually are** is `controls.py`'s subject and is not
restated here. What this module adds is the rendering, the address, and the one
rule the address must keep.

**Applied state lives in the address and nowhere else.** `FR-169` bars "no
retained preference, layout, or filter state", so there is no session store, no
cookie and no remembered selection: a filter is in the query string or it does
not exist. That makes the address the whole of the applied state, which is what
lets it survive navigation -- and what makes the language switch a real risk.

**The language switch would drop every filter, left alone.** `shell.html.j2`
builds the alternate-language address as `{prefix}/{alternate}{surface_path}`,
and `decision_tail` returns a path with no query string. A reader who filtered to
one store and switched to Arabic would land on an unfiltered page with the
controls reset -- applied state lost on the most ordinary action. So the query
string is part of `surface_path` here, and `test_d107_controls` asserts it
through the rendered switch link rather than through this function.

**The source options are completed runs, and the list is not a second Analyses
surface.** Each option re-addresses *this* surface at a different `source_id`;
none links elsewhere. `FR-165` applies to the list as it does to a view read: a
scope whose runs cannot be read renders the surface with the selector absent
rather than failing the page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from khepri.rca.workspace.contracts import RUN_COMPLETED
from khepri.rca.workspace.decision.controls import (
    ControlSelection,
    SourceOption,
    offered_filters,
)
from khepri.rca.workspace.decision.seam import (
    BASKET,
    BRANCH_PERFORMANCE,
    CONCENTRATION,
    EXECUTIVE_OVERVIEW,
    METRIC_AVAILABILITY,
    PRODUCT_CATEGORY,
    REPORT_EVIDENCE,
)

__all__ = [
    "CONTROL_COPY",
    "SURFACE_VIEWS",
    "ControlsView",
    "FilterControl",
    "controls_view",
    "selection_query",
    "inbound_parameters",
    "PRINT_PARAMETER",
    "partition_print",
    "source_options",
]

#: Every view the decision surface reads, which is what decides the filters it
#: may offer. Seven and not eight: `PeriodComparisonView` is published and not
#: reachable (`FR-170`), no read model calls it, and offering a control for a
#: surface held open would be rendering it as partial.
SURFACE_VIEWS = (
    EXECUTIVE_OVERVIEW,
    METRIC_AVAILABILITY,
    REPORT_EVIDENCE,
    BRANCH_PERFORMANCE,
    PRODUCT_CATEGORY,
    BASKET,
    CONCENTRATION,
)

#: The controls' own wording, in both governed languages. `FR-171` requires
#: equivalent content, so every key appears under both and the test asserts the
#: key sets are equal rather than spot-checking one label.
CONTROL_COPY = {
    "en": {
        "controls_label": "Controls",
        "period_label": "Analysis",
        "period_hint": "Figures come from one completed analysis.",
        "no_sources": "No completed analysis is available.",
        "filters_label": "Filters",
        "apply_label": "Apply",
        "clear_label": "Clear filters",
        "any_label": "Any",
        "store": "Store",
        "product": "Product",
        "category": "Category",
    },
    "ar": {
        "controls_label": "عناصر التحكم",
        "period_label": "التحليل",
        "period_hint": "تأتي الأرقام من تحليل مكتمل واحد.",
        "no_sources": "لا يوجد تحليل مكتمل متاح.",
        "filters_label": "المرشحات",
        "apply_label": "تطبيق",
        "clear_label": "مسح المرشحات",
        "any_label": "الكل",
        "store": "الفرع",
        "product": "المنتج",
        "category": "الفئة",
    },
}


@dataclass(frozen=True, slots=True)
class FilterControl:
    """One offered filter: its dimension, its label, and what was asked for.

    `value` is what this request asked for and not what applied. What applied is
    `FR-137`'s effective request, which the drawer already renders from the
    outcome -- `_effective_filters` in `shell_decisions.py`. Two different
    statements, and a control that showed the effective value would claim the
    view accepted something it may have refused.
    """

    dimension: str
    label: str
    value: str | None


@dataclass(frozen=True, slots=True)
class ControlsView:
    """The controls as one page renders them, in one language."""

    copy: dict[str, str]
    sources: tuple[SourceOption, ...]
    filters: tuple[FilterControl, ...]
    applied: bool


def source_options(runs: tuple[Any, ...], selected: str) -> tuple[SourceOption, ...]:
    """The completed runs of this scope, newest first, with the chosen one marked.

    **Completed only**, because `FR-166` makes the period "a source selector --
    choosing a **completed** run". A started or failed run has no package for a
    view to read, so offering one would offer a selection that can only refuse.

    The order is the store's own (`analysis_runs_for_scope` orders by
    `started_at` descending); nothing here re-sorts, which would be this module
    holding a second opinion about recency.
    """
    return tuple(
        SourceOption(
            source_id=run.run_id,
            completed_at=run.completed_at,
            selected=run.run_id == selected,
        )
        for run in runs
        if getattr(run, "state", None) == RUN_COMPLETED
    )


def controls_view(
    selection: ControlSelection, sources: tuple[SourceOption, ...], language: str
) -> ControlsView:
    """The controls this surface offers, for one request in one language.

    The offered filters are `offered_filters`' -- the union of what the views
    this surface reads admit -- so a dimension no view admits has no control and
    a reader cannot compose a request that must refuse. An inbound parameter that
    bypasses the controls is a different matter, and `FR-137` answers it.
    """
    copy = CONTROL_COPY[language]
    return ControlsView(
        copy=copy,
        sources=sources,
        filters=tuple(
            FilterControl(
                dimension=dimension,
                label=copy[dimension],
                value=selection.value_for(dimension),
            )
            for dimension in offered_filters(SURFACE_VIEWS)
        ),
        applied=bool(selection.filters),
    )


def selection_query(selection: ControlSelection) -> str:
    """This selection as a query string, or `""` when nothing was asked for.

    **Every asked-for parameter, including one no view admits.** A selection
    carrying `period=2026-08` keeps it here, so the address a reader shares or
    switches language on asks the same question and gets the same governed
    refusal. Dropping it would make the refusal disappear on a language switch,
    which is the silent discard `FR-166` forbids arriving by another route.

    Ordered as the selection carries it, and `urlencode` with a sequence rather
    than a mapping so a dimension stated twice stays stated twice.
    """
    if not selection.filters:
        return ""
    return "?" + urlencode(list(selection.filters))


def inbound_parameters(raw: Any) -> tuple[tuple[str, str], ...]:
    """Every inbound query parameter, in the order the address spelled it.

    **Nothing is reordered and nothing is removed.** An earlier draft sorted
    offered dimensions first, which fabricated an address different from the one
    the reader sent: `selection_query` would then rebuild a reordered query
    string, and the address a reader shares would stop matching the address the
    controls rebuild -- breaking the "identical across navigation" property the
    sort was added to serve.

    `multi_items()` and not a mapping, because a dimension stated twice is two
    statements -- the reading `_effective_filters` already takes of `FR-137`.
    """
    return tuple((name, value) for name, value in raw.multi_items())


#: The rendering-mode parameter. Not a filter, and partitioned out before the
#: selection is built -- `selection_from` passes every parameter it is given to
#: the seam, where a name no view admits is *refused* (`FR-166`). Leaving `print`
#: in that stream would refuse the very request that asked to print.
PRINT_PARAMETER = "print"


def partition_print(
    parameters: tuple[tuple[str, str], ...],
) -> tuple[bool, tuple[tuple[str, str], ...]]:
    """Split the rendering mode from the filter statements.

    Returns whether print was asked for, and the parameters with it removed.

    **This is not a silent drop.** `FR-137` forbids reading a filter statement
    and discarding it; `print` is not a filter statement. It names how the page
    renders, the way the language segment does, and the surface it selects is
    visible in the response. Every remaining parameter still travels to the seam
    untouched, so an unadmitted dimension is still refused rather than ignored.

    A `print` carrying no value is not a request to print: an absent control and
    one left blank are the same statement, which is the reading `selection_from`
    already takes of an empty member.
    """
    asked = any(
        name == PRINT_PARAMETER and value for name, value in parameters
    )
    remaining = tuple(
        (name, value) for name, value in parameters if name != PRINT_PARAMETER
    )
    return asked, remaining
