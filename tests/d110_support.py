"""Shared harness for `D1-10`'s two test files (active `RCA-008`).

`D1-10`'s subject is the **extent** of parity and isolation evidence, so the one
thing this module must get right is that the surface roster is *derived* from the
product rather than hand-listed here. A roster typed into the test reproduces the
drift it exists to catch, which is how the print surface reached `main` with no
parity coverage.

Kept out of `d105_support.py` and `d109_support.py` for the reason both were kept
apart: each scored against Lines of Code and Low Cohesion, and a third subject
folded into either re-scores it. The scripted port and governed outcomes are
imported rather than redefined.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from khepri.runtime import shell_decisions
from khepri.runtime.shell_api import SHELL_PREFIX
from tests import test_d108_print as print_support
from tests.d105_support import LANGUAGES

__all__ = [
    "LANGUAGES",
    "MODES",
    "SURFACES",
    "Ask",
    "Surface",
    "expected_roster",
    "page",
]

# `LANGUAGES` is re-exported from `d105_support` rather than redefined: two
# definitions of the governed language set is the second truth `FR-135` refuses
# in its own domain, and the same reasoning applies to a test fixture.

#: The render modes the route serves, from the branch in `render_decisions`.
MODES = ("screen", "print")


@dataclasses.dataclass(frozen=True, slots=True)
class Surface:
    """One surface the parity and isolation extents must cover.

    `renders_prose` is declared rather than inferred: a read-count or latency
    surface is language-invariant and correctly carries no parity case, and that
    must be a visible choice so a new prose surface defaulting to "no" is caught
    in review rather than silently skipped.
    """

    key: str
    renders_prose: bool


def _section_keys() -> tuple[str, ...]:
    """The breakdown sections, from the product's own constants."""
    return (
        shell_decisions.SECTION_BRANCHES,
        shell_decisions.SECTION_PRODUCTS,
        shell_decisions.SECTION_BASKET,
        shell_decisions.SECTION_CONCENTRATION,
    )


def _reading_keys() -> tuple[str, ...]:
    """The page's reads, from `DecisionReadings`' own fields.

    `dataclasses.fields` rather than a list: a read added to the page appears
    here without an edit, which is the whole point of deriving the roster.
    """
    return tuple(
        field.name for field in dataclasses.fields(shell_decisions.DecisionReadings)
    )


def _copy_keys(language: str) -> tuple[str, ...]:
    """The sections the *template copy* names, for one language.

    **The independent source, and the reason this function exists.** If
    `expected_roster` derived the sections from `_section_keys()` -- the same
    constants `SURFACES` is built from -- the two would move in lockstep and the
    comparison would be a restatement against itself: dropping a whole section
    from the derivation would still pass. `SECTION_COPY` is maintained separately
    because it carries governed prose in both languages, so it disagrees when one
    side drifts. Verified: removing `SECTION_CONCENTRATION` from `_section_keys()`
    passed every test before this was added, and fails after.
    """
    return tuple(shell_decisions.SECTION_COPY[language].keys())


def expected_roster() -> set[str]:
    """Every surface key the product exposes, pinned to an independent source.

    Sections come from the template's own bilingual copy rather than from the
    constants `SURFACES` uses, so the two cannot drift together.
    """
    return set(_reading_keys()) | set(_copy_keys("en")) | set(MODES)


SURFACES: tuple[Surface, ...] = tuple(
    Surface(key=key, renders_prose=True) for key in sorted(expected_roster())
)


@dataclasses.dataclass(frozen=True, slots=True)
class Ask:
    """One request for one surface, grouped rather than passed flat.

    A value object because CodeScene's gate admits four arguments and the flat
    form carried six; `DecisionRead` in `decision/seam.py` made the same trade
    for the same reason. It also collapses what were two near-duplicate helpers:
    asking as the owner and asking across organizations differ only in
    `organization_id`, so one call with a defaulted field expresses both.
    """

    world: Any
    who: Any
    run_id: str
    organization_id: str | None = None
    language: str = "en"
    printable: bool = False

    @property
    def address(self) -> str:
        """Where this ask is addressed. The owner's organization unless named."""
        organization = self.organization_id or self.who.organization_id
        tail = "?print=1" if self.printable else ""
        return (
            f"{SHELL_PREFIX}/{self.language}/{organization}"
            f"/decisions/{self.run_id}{tail}"
        )


def page(ask: Ask) -> Any:
    """One whole surface over the real route, as `ask` describes it.

    **Driven over HTTP and not through `render_decisions`**, which takes four
    positional arguments and hardcodes `decision.html.j2` -- it cannot reach the
    print surface at all. `?print=1` on the language-parameterised prefix
    (`FR-047`) is the only path that renders `decision_print.html.j2`, so it is
    the only seam a parity extent over *every* surface can use.

    `tests/test_d108_print.py::_shell` builds the authenticated client with the
    production decision collaborator; reusing it rather than rebuilding one keeps
    a single definition of what the shell is wired to.
    """
    return print_support._shell(ask.world, ask.who).get(ask.address)
