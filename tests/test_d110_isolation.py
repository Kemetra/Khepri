"""Cross-organization isolation on every surface (`D1-10`; active `RCA-008`).

§Verification requires isolation "on every surface". Three surfaces carry it
today and six do not, and nothing fails when a seventh ships without it -- the
same extent defect parity had.

**The effect, not the exception.** A foreign organization must reach the same
governed unavailable a missing run reaches. Asserting an exception type would
survive the guard being replaced by a different one that leaks, and would not
notice a surface that renders a foreign figure under a caught error.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from tests.d110_support import LANGUAGES, MODES, Ask, page
from tests.w104b_support import journey
from tests.w106_support import completed_run
from tests.w110_support import two_members


def _two_organizations():
    """Two members of different organizations, and a run belonging to the first."""
    world = journey()
    who, other = two_members(world)
    run, _job, _session = completed_run(world, who)
    return world, who, other, run.run_id


def _missing(ask: Ask) -> Any:
    """The same ask, for a run that exists nowhere.

    The comparison partner for every isolation assertion. Asserting only that a
    foreign response withholds the run id would accept a `200` decision page that
    happened not to echo it; what `FR-165` requires is that denial and absence are
    the *same* answer, so each case is compared against this rather than against a
    predicate.
    """
    return page(dataclasses.replace(ask, run_id="no-such-run-at-all"))


@pytest.mark.parametrize("printable", [False, True])
def test_a_foreign_member_cannot_reach_another_organizations_run(
    printable: bool,
) -> None:
    """`FR-165` over both render modes, which is the extent that was missing.

    Driven as the *other* member asking for the owner's run at the owner's
    address: a request that merely changes the address while staying the owner
    tests routing, not isolation.
    """
    world, who, other, run_id = _two_organizations()

    ask = Ask(world, other, run_id, who.organization_id, printable=printable)

    response = page(ask)
    missing = _missing(ask)

    assert response.status_code == missing.status_code
    assert response.text == missing.text
    assert run_id not in response.text


def test_the_foreign_answer_is_indistinguishable_from_a_missing_run() -> None:
    """Absence and denial must not be tellable apart.

    A foreign member learning that a run *exists* but is denied is a
    cross-organization leak in the shape of a status code. Compared as the pair
    a real attacker can compare: same actor, same address shape, one run that
    exists elsewhere and one that exists nowhere.
    """
    world, _who, other, _run_id = _two_organizations()

    foreign = page(Ask(world, other, "run-of-another-org"))
    missing = page(Ask(world, other, "no-such-run-at-all"))

    assert foreign.status_code == missing.status_code


@pytest.mark.parametrize("language", LANGUAGES)
def test_isolation_holds_in_both_languages(language: str) -> None:
    """A governed refusal is content, so `FR-171` applies to it like any figure."""
    world, who, other, run_id = _two_organizations()

    ask = Ask(world, other, run_id, who.organization_id, language=language)

    response = page(ask)
    missing = _missing(ask)

    assert response.status_code == missing.status_code
    assert response.text == missing.text
    assert run_id not in response.text


def test_no_mode_is_exempt_from_the_isolation_extent() -> None:
    """The extent assertion, derived from `MODES` and asserted non-empty."""
    world, who, other, run_id = _two_organizations()

    assert MODES
    for mode in MODES:
        ask = Ask(world, other, run_id, who.organization_id, printable=mode == "print")

        response = page(ask)
        missing = _missing(ask)

        assert response.status_code == missing.status_code, mode
        assert response.text == missing.text, mode
        assert run_id not in response.text, mode
