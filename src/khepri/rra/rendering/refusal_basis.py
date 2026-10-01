"""A refused section's headline, with each comparison basis named by its own cause (`RRA-009`).

SCRUM-26 A4(b), as `#637` amended `RRA-009` §Refusals. The Period comparison section printed
one cause as its headline when each basis had been refused for a different one, so a sentence
true of one basis read as true of both.

**Where the basis is read from.** A section's reason is the family's summary of the refusals it
recorded per basis, and those same records travel on the bundle as caveats scoped to the
section, each naming its basis in its own result (`revenue_delta_absolute.year_over_year`). So
the per-basis causes are the section's own records, read from the bundle rather than inferred
from another section's refusal. Growth records none: it decomposes one basis, and the causes it
takes from that basis's window are named here because `growth.derive` takes them from there.

**When a basis is named.** Only when the cause belongs to one basis. A section whose every
basis was refused for the same cause -- a file with no revenue, or a single day -- states that
cause once and names none, because it is true of both. Bases refused for different causes are
each named with their own cause, in governed mode order, and within each basis the family's
own order has already chosen one cause. A basis recorded alone names itself.

A module of its own for `refused_results`' reason: it reads bundle records, not wording tables,
and `wording.py` keeps only the composition (`with_basis`).
"""

from __future__ import annotations

from collections.abc import Iterable

from khepri.rra.analysis import comparison, growth
from khepri.rra.bundle import SECTION_GROWTH, StatedCaveat
from khepri.rra.rendering import wording

#: The causes growth takes from the previous-period window it decomposes (`window_refusal`),
#: rather than from its own inputs.
_GROWTH_WINDOW_REASONS = frozenset(
    {growth.REASON_PRIOR_WINDOW_ABSENT, comparison.REASON_COVERAGE_INCOMPATIBLE}
)


def section_refusal_prose(
    section_id: str,
    reason: str,
    caveats: Iterable[StatedCaveat],
    language: str,
) -> str:
    """A refused section's prose: one sentence, or one per basis refused for its own cause."""
    return " ".join(
        wording.with_basis(
            wording.section_refusal_message(section_id, cause, language), basis, language
        )
        for basis, cause in _causes(section_id, reason, caveats)
    )


def _causes(
    section_id: str, reason: str, caveats: Iterable[StatedCaveat]
) -> tuple[tuple[str | None, str], ...]:
    if section_id == SECTION_GROWTH:
        basis = comparison.MODE_PERIOD_OVER_PERIOD if reason in _GROWTH_WINDOW_REASONS else None
        return ((basis, reason),)
    per_basis = _per_basis(section_id, caveats)
    if not per_basis or _shared_by_every_basis(per_basis):
        return ((None, reason),)
    return tuple(per_basis.items())


def _shared_by_every_basis(per_basis: dict[str, str]) -> bool:
    """One cause recorded for every governed basis: it belongs to neither alone."""
    return len(per_basis) == len(comparison.GOVERNED_MODES) and len(set(per_basis.values())) == 1


def _per_basis(section_id: str, caveats: Iterable[StatedCaveat]) -> dict[str, str]:
    """Each basis's recorded cause, in governed mode order.

    A basis refused wholly refuses every metric for one cause (`comparison._refused`), so the
    first record found for a basis is its cause.
    """
    found: dict[str, str] = {}
    for caveat in caveats:
        if caveat.section != section_id or wording.RESULT_CAVEAT_SEPARATOR not in caveat.code:
            continue
        result, cause = caveat.code.rsplit(wording.RESULT_CAVEAT_SEPARATOR, 1)
        basis = wording.basis_of(result)
        if basis is not None:
            found.setdefault(basis, cause)
    return {mode: found[mode] for mode in comparison.GOVERNED_MODES if mode in found}
