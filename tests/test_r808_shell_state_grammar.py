"""`U1` slice 5 -- the shell's screen-state grammar: `RCA-010` `FR-202`, `FR-203`.

`FR-202` names **four** states -- refusal, empty, loading, error -- and the commercial
shell authors **two and a half**. Stating the count before asserting anything about it
is the point of this docstring, because a test "proving four states differ" over a
surface carrying two is proving something else.

- **Refusal** -- four elements: `.decision-refusal` on the cards and sections
  partials, `.decision-unsupported`, and `.compare-refusal`. Asserted for mutual
  exclusivity, for carrying no error paint, and for carrying no error role.
- **Empty** -- two idioms: `.decision-empty` and `.empty-state`. Asserted as the two
  governed rules of `FR-163`, on **both** render paths.
- **Unavailable** (`FR-165`, content-free) -- `.decision-unavailable` and
  `.decision-evidence-unavailable`. Asserted for mutual exclusivity.
- **Loading** -- **none, and none can occur.** The invariant is asserted, not the state.
- **Error** -- **none; no error class exists anywhere on the shell.** The absence is
  asserted, not the state.

**`FR-202` was found ALREADY SATISFIED, and by *absence of paint*.** No shell sheet
carries a rule for `.decision-refusal`, `.decision-empty`, `.decision-unavailable` or
`.compare-refusal`; the only state rule that exists is `.empty-state { color:
var(--muted) }`. So the work here is the instrument, not the change: these guards fail
when a later slice paints a refusal, merges a state class with an error class, drops a
motion declaration into a shell sheet, or ships a loading affordance.

**Separate from `test_r807_shell_quality.py`, which is 788 lines against CodeScene's
600-line gate.** Adding a fifth subject to a module already over the gate makes a
failing metric worse. Task 6's per-surface §F contracts live in
`test_r809_shell_state_contracts.py` for the same reason: what the grammar *is* and
what each surface *contracts to show* are different subjects.
"""

from __future__ import annotations

import re

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import card, seam
from tests import d105_support as support

#: `FR-202`'s four states, as a **reviewed literal**, because no constant enumerates
#: them: `FR-202` names them in prose and the repository holds no enum, table or
#: frozenset for the set. A derived-looking expectation here would be a fabrication,
#: which is worse than a literal a reviewer can check against `RCA-010` `FR-202` and
#: master specification §13. Two of the four are asserted as **absences** -- see
#: `test_no_shell_surface_carries_a_loading_affordance` and
#: `test_no_shell_state_rule_carries_error_paint`.
_FR202_STATES = ("refusal", "empty", "loading", "error")

#: The state classes the shell authors, which is the other two-and-a-half.
_STATE_CLASSES = ("decision-refusal", "decision-empty", "decision-unavailable")

#: A class token that would make a governed state read as a failure. `FR-202`: a
#: refusal "never shares an element or a class with an error".
_ERROR_TOKEN = re.compile(r"error|danger|alert|fail")


class _Decisions:
    """Every view scripted independently; an unscripted view is content-free unavailable.

    The same shape as `test_d105_decision_sections.py`'s collaborator, defined here
    rather than imported: that module is `RCA-008`'s Verification and this slice
    neither edits nor depends on its private names. The **fixtures** are shared --
    `tests/d105_support` is the support module both use -- so this is one scripted
    port, not a second definition of the outcomes.
    """

    def __init__(self, outcomes: dict[str, ports.ViewOutcome]) -> None:
        """Hold the scripted answers for one page."""
        self.outcomes = outcomes

    def request(self, asked: object) -> ports.ViewOutcome:
        """Answer as scripted, defaulting to `FR-146`'s uniform miss."""
        view_id = asked.view.view_id  # type: ignore[attr-defined]
        return self.outcomes.get(view_id, support.UNAVAILABLE)


def _admitted_surface() -> dict[str, ports.ViewOutcome]:
    """Every view this surface reads, each admitted with figures on it."""
    return {
        seam.EXECUTIVE_OVERVIEW.view_id: support.overview(),
        seam.METRIC_AVAILABILITY.view_id: support.availability(
            (("revenue", card.AVAILABILITY_AVAILABLE, None, ()),)
        ),
        seam.REPORT_EVIDENCE.view_id: support.evidence_outcome(
            (support.STATED, support.UNSTATED), support.UNSTATED_ABSENCES
        ),
        seam.BRANCH_PERFORMANCE.view_id: support.breakdown(
            seam.BRANCH_PERFORMANCE, support.BRANCH_FIELDS, (("branch", "revenue", "1", "done"),)
        ),
        seam.PRODUCT_CATEGORY.view_id: support.breakdown(
            seam.PRODUCT_CATEGORY, support.PRODUCT_FIELDS, (("cat", "revenue", "1", "done"),)
        ),
        seam.BASKET.view_id: support.breakdown(
            seam.BASKET, support.BASKET_FIELDS, (("basket_attach_rate", "0.25", "done", ()),)
        ),
        seam.CONCENTRATION.view_id: support.breakdown(
            seam.CONCENTRATION,
            support.CONCENTRATION_FIELDS,
            (("product", "concentration_top_decile_share", "0.60", "done"),),
        ),
    }


def _refused(wording_en: str, wording_ar: str) -> ports.ViewOutcome:
    """A governed view refusal carrying its own wording (`FR-141`, `FR-164`)."""
    return ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=ports.ViewRefusal(
            cause="unsupported_filter",
            wording_pairs=(("en", wording_en), ("ar", wording_ar)),
        ),
    )


def _three_state_surface() -> dict[str, ports.ViewOutcome]:
    """One page carrying a refusal, an unavailable and both governed empty rules.

    The decision surface is the only one that reaches all three -- see the
    reachability table in `test_r809_shell_state_contracts.py`. The two empty
    sections are chosen to carry **different** governed rules:
    `BRANCH_PERFORMANCE` is `stated_no_rows` and `BASKET` is `stated_absence`
    (`seam.py`), so this one page also exercises `FR-163`.
    """
    outcomes = _admitted_surface()
    outcomes[seam.PRODUCT_CATEGORY.view_id] = _refused(
        "This measure was refused.", "رُفض هذا المقياس."
    )
    outcomes[seam.CONCENTRATION.view_id] = support.UNAVAILABLE
    outcomes[seam.BRANCH_PERFORMANCE.view_id] = support.breakdown(
        seam.BRANCH_PERFORMANCE, support.BRANCH_FIELDS, (), is_empty=True
    )
    outcomes[seam.BASKET.view_id] = support.breakdown(
        seam.BASKET, support.BASKET_FIELDS, (), is_empty=True
    )
    return outcomes


def _rendered(outcomes: dict[str, ports.ViewOutcome], language: str) -> str:
    """That page, rendered through the real route in one language."""
    return support.client(_Decisions(outcomes)).get(support.address(language)).text


def _elements_carrying(body: str, state_class: str) -> list[str]:
    """Every element whose class attribute carries `state_class` as a whole token."""
    return [
        match.group(0)
        for match in re.finditer(r"<[a-z]+\b[^>]*>", body)
        if re.search(r'class="[^"]*\b' + re.escape(state_class) + r'\b[^"]*"', match.group(0))
    ]


def test_the_shell_state_classes_are_mutually_exclusive() -> None:
    """`FR-202`: a governed state "never shares an element or a class with an error".

    Driven through the real render path on the decision surface, in both languages,
    because that is the only surface reaching refusal, empty and unavailable together.

    **This passes on arrival** -- the three classes already sit on three `<p>` elements
    in three independent `{% if %}` branches -- so it is a forward-looking guard and a
    bare run proves nothing about it. Its value is the mutation record: merging two
    state classes onto one element, or renaming the refusal class to `decision-error`,
    must fail here.
    """
    assert len(_FR202_STATES) == 4, "FR-202 names four states"

    for language in ("en", "ar"):
        body = _rendered(_three_state_surface(), language)
        assert body.strip(), f"the decision surface rendered nothing in {language}"
        assert "decision-refusal" in body, f"no refusal reached the page in {language}"

        carriers = {state: _elements_carrying(body, state) for state in _STATE_CLASSES}
        for state, elements in carriers.items():
            assert elements, f"{state} did not render in {language}"
            assert all(element.startswith("<p") for element in elements), (
                f"{state} is not on a <p> element in {language}: {elements}"
            )

        # No element carries two of them. Compared as rendered elements rather than by
        # counting classes: two states merged onto one `<p>` keeps both counts at one.
        for state, elements in carriers.items():
            others = [other for other in _STATE_CLASSES if other != state]
            for element in elements:
                collisions = [
                    other for other in others if re.search(r"\b" + other + r"\b", element)
                ]
                assert collisions == [], (
                    f"{state} shares an element with {collisions} in {language}: {element}"
                )

        # The refusal carries no token that would read as a failure.
        for element in carriers["decision-refusal"]:
            classes = re.search(r'class="([^"]*)"', element)
            assert classes is not None
            found = [token for token in classes.group(1).split() if _ERROR_TOKEN.search(token)]
            assert found == [], f"the refusal carries an error-shaped class {found} in {language}"
