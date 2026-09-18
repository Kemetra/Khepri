"""`U1` slice 5 -- the §F per-surface state contracts: which surface may show which state.

A companion to `test_r808_shell_state_grammar.py`, split from it deliberately. What the
state grammar *is* -- classes that never merge, paint that never arrives, motion that
never ships -- and what each surface *contracts to show* are different subjects with
different failure modes, and CodeScene scores test modules on cohesion too.

**A surface that cannot reach a state is NOT EXERCISED, not PASS.** The reachability
table below is the whole point of the module: without it, a per-surface state test
either asserts nothing on the surfaces that carry no state, or asserts the presence of
something that cannot occur there. The table is derived from the templates on disk and
is the expectation a later slice's drift is measured against.

**Three of this slice's plan's claims about §F were falsified by the tree and are
corrected here**, each recorded rather than quietly dropped:

1. The plan's table lists `team` under "No state region". `team.html.j2` carries **two**
   `.empty-state` regions (`:30` an empty member list, `:96` an empty invitation list),
   both legitimate. The table below says so, and the plan's prescribed mutant -- adding
   an `.empty-state` to `team.html.j2` -- is a no-op that would have passed.
2. The plan asserts an exit anchor inside "a refused `decision`"'s own document-card. A
   refused section's card carries **zero** anchors, and needs none: the decision surface
   renders the **full** frame navigation, so the reader has many exits. The plan's
   premise for including it -- that its frame "drops or narrows the navigation" -- is
   not true of `decision`.
3. The plan asserts an exit anchor on `no_membership`. That surface carries **no anchor
   at all** beyond the skip-link and language switch, and correctly so: an authenticated
   account in no organization has nowhere in the product to go, and inventing a
   destination is exactly what `FR-193` forbids. Its next step is stated in words
   (`no_membership_action`, "Ask an organization owner to invite you.").

So the exit invariant is asserted where it has teeth -- see
`test_no_frameless_surface_traps_the_reader`.
"""

from __future__ import annotations

import re
from importlib.resources import files

import pytest

from tests.test_r807_shell_quality import SHELL_SURFACES
from tests.test_r808_shell_state_grammar import _ALL_STATE_CLASSES

#: Which state classes each surface's markup may carry, established against the tree.
#: A surface absent from a row's value carries **none**, which is what stops a later
#: slice dropping an `.empty-state` onto a surface whose read cannot be empty.
#:
#: `decision` inherits the two shared partials' classes because it includes them; the
#: resolution is transitive rather than hand-copied, so a partial gaining a state is
#: seen here without editing this table.
_DECISION_STATES = (
    "decision-refusal",
    "decision-unsupported",
    "decision-empty",
    "decision-unavailable",
    "decision-absence",
    "decision-evidence-absent",
    "decision-evidence-unavailable",
)
_REACHABLE: dict[str, tuple[str, ...]] = {
    # The only surface reaching refusal, empty and unavailable together.
    "decision": _DECISION_STATES,
    # §F.11: `KIND_REFUSED` and `KIND_UNAVAILABLE` stay distinct on the comparison.
    "compare": ("compare-refusal",),
    # §F.7-§F.10: a read that can publish nothing states so in one region.
    "overview": ("empty-state",),
    "data": ("empty-state",),
    "analyses": ("empty-state",),
    "analysis": ("empty-state",),
    # CORRECTED against the plan: two empty regions, members and invitations.
    "team": ("empty-state",),
    # §F.15: the surface **is** the state, so it carries no state region of its own.
    "unavailable": (),
    "no_membership": (),
    # A chooser, not a state.
    "switcher": (),
}

#: Surfaces whose frame renders no destination navigation, because there is no resolved
#: organization to navigate within. These are the only ones where "does the reader have
#: a way onward" is a real question: everywhere else the frame answers it.
_FRAMELESS = ("unavailable", "no_membership", "switcher")

#: Frame chrome that is present on every page and is therefore not an answer to it.
_CHROME_ANCHOR = re.compile(r'class="(?:skip-link|frame-language|frame-organization)')


def _template_source(name: str) -> str:
    """One template's text, proven non-empty."""
    text = files("khepri.runtime").joinpath("shell_templates", name).read_text(encoding="utf-8")
    assert text.strip(), f"{name} is empty, so this test proves nothing"
    return text


def _with_includes(name: str, seen: set[str] | None = None) -> str:
    """A template's source with every `{% include %}` resolved, transitively.

    Resolved rather than hand-listed: `decision.html.j2` reaches its states through
    `_decision_cards.html.j2` and `_decision_sections.html.j2`, and a partial gaining a
    state must be visible here without anyone remembering to update a table.
    """
    seen = seen if seen is not None else set()
    if name in seen:
        return ""
    seen.add(name)
    source = _template_source(name)
    for included in re.findall(r'include\s+"([^"]+)"', source):
        source += _with_includes(included, seen)
    return source


def _states_in(markup: str) -> set[str]:
    """Every state class the markup carries, as whole class tokens."""
    return {
        state
        for state in _ALL_STATE_CLASSES
        if re.search(r'class="[^"]*\b' + re.escape(state) + r'\b', markup)
    }


def test_the_reachability_table_covers_every_measured_surface() -> None:
    """The table's extent, so a surface cannot slip past the per-surface test.

    `SHELL_SURFACES` is `test_r807_shell_quality.py`'s and is cross-checked there
    against the template directory itself, so a template added without a browser case
    already fails. This adds the second half: a surface added to that map without a
    decision about which states it may show fails **here**, rather than being measured
    against an empty expectation.
    """
    assert SHELL_SURFACES, "no shell surfaces known, so this test proves nothing"
    assert set(_REACHABLE) == set(SHELL_SURFACES), (
        f"the table and the measured surfaces disagree: "
        f"table-only={sorted(set(_REACHABLE) - set(SHELL_SURFACES))}, "
        f"unmeasured={sorted(set(SHELL_SURFACES) - set(_REACHABLE))}"
    )


@pytest.mark.parametrize("surface", sorted(_REACHABLE))
def test_each_surface_reaches_only_the_states_its_contract_admits(surface: str) -> None:
    """§F.7-§F.15: a surface shows the states its read can produce, and no others.

    Asserted over the **template** rather than a rendered page, because the subject is
    what the surface *can* reach, not what one fixture happened to produce. A surface
    whose read cannot be empty must not carry an empty region at all, and a rendered
    page would simply not show one either way.
    """
    markup = _with_includes(f"{surface}.html.j2")
    found = _states_in(markup)
    admitted = set(_REACHABLE[surface])
    assert found <= admitted, (
        f"{surface} carries a state its contract does not admit: {sorted(found - admitted)}"
    )
    # And the table is not stale in the other direction either: a state it promises
    # must actually be there, or the table is documentation rather than a measurement.
    assert admitted <= found, (
        f"{surface}'s table promises states its markup does not carry: {sorted(admitted - found)}"
    )


def test_every_shell_empty_state_offers_prose_and_no_illustration() -> None:
    """§F.7: an empty state is "one instruction and one action, **not an illustration**".

    The **template** half only. `FR-206`'s stylesheet half -- that the component layer
    draws no artwork -- is `test_r807_shell_quality.py:651`'s instrument from slice 2b,
    and is cited rather than duplicated: a second scanner over the same sheet is a
    second definition, and two definitions drift.

    So this asserts what that one cannot see: no `<img>` or `<svg>` element inside an
    empty region, and governed text rather than a hard-coded sentence.
    """
    regions = []
    for surface, states in _REACHABLE.items():
        if "empty-state" not in states:
            continue
        markup = _with_includes(f"{surface}.html.j2")
        for match in re.finditer(r'<p class="empty-state"[^>]*>(.*?)</p>', markup, flags=re.DOTALL):
            regions.append((surface, match.group(1)))

    assert regions, "no empty-state region found, so this test proves nothing"
    for surface, body in regions:
        assert "<img" not in body and "<svg" not in body, (
            f"{surface} illustrates an empty state instead of stating it: {body!r}"
        )
        assert re.search(r"\{\{.*\}\}", body), (
            f"{surface} hard-codes its empty sentence instead of taking governed copy: {body!r}"
        )


def test_no_frameless_surface_traps_the_reader() -> None:
    """§Higher-order invariants: "No surface traps a reader ... carries at least one exit".

    **Scoped to the surfaces whose frame renders no destination navigation**, because
    everywhere else the frame answers the question and the assertion would pass on
    chrome without proving anything about the state. That is `unavailable`,
    `no_membership` and `switcher` -- not a refused `decision`, which renders the full
    navigation and whose refused section's card correctly carries no anchor of its own.

    A "way onward" is an anchor that is **not** frame chrome, or -- where the product
    genuinely offers no destination -- a stated next step. `no_membership` is the second
    case and is the reason this is not a bare anchor count: an authenticated account in
    no organization has nowhere in the product to go, and inventing a destination is
    what `FR-193` forbids. Its next step is a sentence, and that sentence is what stops
    the surface being a dead end.
    """
    for surface in _FRAMELESS:
        markup = _with_includes(f"{surface}.html.j2")
        anchors = [
            anchor
            for anchor in re.findall(r"<a\b[^>]*>", markup)
            if not _CHROME_ANCHOR.search(anchor)
        ]
        next_step = re.findall(r'<p class="next-step"[^>]*>(.*?)</p>', markup, flags=re.DOTALL)
        assert anchors or next_step, (
            f"{surface} offers the reader neither a destination nor a stated next step"
        )
        for step in next_step:
            assert re.search(r"\{\{.*\}\}", step), (
                f"{surface} hard-codes its next step instead of taking governed copy: {step!r}"
            )
