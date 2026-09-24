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
- **Loading** -- **none ships, by choice.** The surfaces are server-rendered whole and
  the shell carries no script at all. The invariant is asserted, not the state.
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
from importlib.resources import files

import pytest

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import card, seam
from khepri.rra.semantic_views import contracts
from khepri.runtime import shell_decisions
from tests import d105_support as support
from tests.test_r807_shell_quality import _selector_parts, _without_comments

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
            seam.BRANCH_PERFORMANCE,
            support.BRANCH_FIELDS,
            (("store-a", "revenue_by_store", "700.00", None),),
        ),
        seam.PRODUCT_CATEGORY.view_id: support.breakdown(
            seam.PRODUCT_CATEGORY,
            support.PRODUCT_FIELDS,
            (("category", "drinks", "revenue_by_category", "120.00", None),),
        ),
        seam.BASKET.view_id: support.breakdown(
            seam.BASKET,
            support.BASKET_FIELDS,
            (("basket_attach_rate", "0.25", None, ()),),
        ),
        seam.CONCENTRATION.view_id: support.breakdown(
            seam.CONCENTRATION,
            support.CONCENTRATION_FIELDS,
            (("product", "concentration_top_decile_share", "0.60", None),),
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


def _collisions_on(element: str, state: str) -> list[str]:
    """Every OTHER state class sharing this element, which `FR-202` forbids.

    Compared as a rendered element rather than by counting classes: two states merged
    onto one `<p>` keeps both counts at one, so a count-based check passes the very
    defect it exists to catch.
    """
    return [
        other
        for other in _STATE_CLASSES
        if other != state and re.search(r"\b" + other + r"\b", element)
    ]


def _error_tokens_on(element: str) -> list[str]:
    """Every class token on this element that would make it read as a failure."""
    classes = re.search(r'class="([^"]*)"', element)
    assert classes is not None, f"a state element carries no class attribute: {element}"
    return [token for token in classes.group(1).split() if _ERROR_TOKEN.search(token)]


@pytest.mark.parametrize("language", ("en", "ar"))
def test_the_shell_state_classes_are_mutually_exclusive(language: str) -> None:
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

    body = _rendered(_three_state_surface(), language)
    assert body.strip(), f"the decision surface rendered nothing in {language}"
    assert "decision-refusal" in body, f"no refusal reached the page in {language}"

    carriers = {state: _elements_carrying(body, state) for state in _STATE_CLASSES}
    for state, elements in carriers.items():
        assert elements, f"{state} did not render in {language}"
        assert all(element.startswith("<p") for element in elements), (
            f"{state} is not on a <p> element in {language}: {elements}"
        )

    shared = [
        f"{state} shares an element with {_collisions_on(element, state)}: {element}"
        for state, elements in carriers.items()
        for element in elements
        if _collisions_on(element, state)
    ]
    assert shared == [], f"state classes share an element in {language}:\n" + "\n".join(shared)

    mislabelled = [
        f"{_error_tokens_on(element)} on {element}"
        for element in carriers["decision-refusal"]
        if _error_tokens_on(element)
    ]
    assert mislabelled == [], (
        f"the refusal carries an error-shaped class in {language}: {mislabelled}"
    )


def _section_markup(body: str, section: str) -> str:
    """One `<section data-section="...">` subtree, so a sentence can be located in it."""
    match = re.search(
        r'<section[^>]*data-section="' + re.escape(section) + r'".*?</section>',
        body,
        flags=re.DOTALL,
    )
    assert match is not None, f"the {section} section did not render"
    return match.group(0)


def test_the_two_governed_empty_rules_reach_the_shell_from_an_independent_source() -> None:
    """`FR-163`: the shell's empty wording covers exactly the governed rules, no more.

    **The expectation is `contracts.EMPTY_RULES`** (`khepri/rra/semantic_views`), which
    is `SV1`/`RRA`'s and sits outside `RCA-010` §Scope, so this slice can read it and
    cannot edit it. A third rule invented there fails here; a rule renamed there is an
    import error rather than a silent pass.

    **Distinct from `test_d105_decision_sections.py:272`**, which derives the same
    extent from `seam.py`. This asserts that the `RRA` registry and the shell's wording
    agree -- which nothing checks today. Two modules deriving from two sources is the
    point; deriving both from one would be the tautology this repository keeps finding.

    Equality and non-empty, never a subset: a subset assertion "only ever weakens" and
    cannot see a rule **added**.
    """
    assert contracts.EMPTY_RULES, "an empty rule set would satisfy any subset claim"
    for language in ("en", "ar"):
        wording = shell_decisions.EMPTY_WORDING[language]
        assert set(wording) == set(contracts.EMPTY_RULES), (
            f"{language} wording covers {sorted(wording)}, "
            f"governed rules are {sorted(contracts.EMPTY_RULES)}"
        )
        assert all(sentence.strip() for sentence in wording.values()), (
            f"{language} carries a blank governed sentence"
        )


def test_the_two_empty_rules_render_as_two_sentences_on_the_breakdown_sections() -> None:
    """`FR-163` on the **sections** path, which is the half that is correct.

    Extends `test_d105_decision_sections.py:142` rather than duplicating it: that test
    asserts both sentences reach one English page. This adds **Arabic**, and adds the
    stronger claim that each sentence appears **only in the section whose rule it is** --
    a page rendering both sentences everywhere would satisfy the weaker check while
    telling every reader both things about every section.

    `BRANCH_PERFORMANCE` is `stated_no_rows` and `BASKET` is `stated_absence`
    (`seam.py`), and those rules are read from the views rather than written out here.
    """
    outcomes = _admitted_surface()
    outcomes[seam.BRANCH_PERFORMANCE.view_id] = support.breakdown(
        seam.BRANCH_PERFORMANCE, support.BRANCH_FIELDS, (), is_empty=True
    )
    outcomes[seam.BASKET.view_id] = support.breakdown(
        seam.BASKET, support.BASKET_FIELDS, (), is_empty=True
    )

    for language in ("en", "ar"):
        body = _rendered(outcomes, language)
        wording = shell_decisions.EMPTY_WORDING[language]
        no_rows = wording[seam.EMPTY_STATED_NO_ROWS]
        absence = wording[seam.EMPTY_STATED_ABSENCE]
        assert no_rows != absence, f"the two governed rules share a sentence in {language}"

        branches = _section_markup(body, shell_decisions.SECTION_BRANCHES)
        basket = _section_markup(body, shell_decisions.SECTION_BASKET)
        assert no_rows in branches, f"branches ({seam.BRANCH_PERFORMANCE.empty_rule}) in {language}"
        assert absence not in branches, f"branches states the other rule's sentence in {language}"
        assert absence in basket, f"basket ({seam.BASKET.empty_rule}) in {language}"
        assert no_rows not in basket, f"basket states the other rule's sentence in {language}"


def test_the_cards_path_states_its_governed_empty_rule() -> None:
    """`FR-163` renders the admitted cards path's own governed empty sentence."""
    outcomes = _admitted_surface()
    outcomes[seam.EXECUTIVE_OVERVIEW.view_id] = ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.EXECUTIVE_OVERVIEW.view_id,
            view_version=seam.EXECUTIVE_OVERVIEW.view_version,
            fields=support.OVERVIEW_FIELDS,
            rows=(),
            is_empty=True,
        ),
        effective=ports.EffectiveRequest(dimensions=("period",)),
    )

    for language in ("en", "ar"):
        body = _rendered(outcomes, language)
        expected = shell_decisions.EMPTY_WORDING[language][seam.EXECUTIVE_OVERVIEW.empty_rule]
        assert expected in body, (
            f"the cards path did not state its governed rule "
            f"({seam.EXECUTIVE_OVERVIEW.empty_rule}) in {language}"
        )


#: Every class the shell uses to mark a governed screen state, across both partials,
#: the decision and compare surfaces, and the four workspace surfaces. Wider than
#: `_STATE_CLASSES`, which is only the three that can share one page.
_ALL_STATE_CLASSES = (
    "decision-refusal",
    "decision-unsupported",
    "compare-refusal",
    "decision-empty",
    "decision-unavailable",
    "decision-absence",
    "decision-evidence-absent",
    "decision-evidence-unavailable",
    "empty-state",
)

#: The `--danger` family, which paints a destructive action and never a screen state.
_DANGER_TOKENS = ("--danger", "--danger-border", "--danger-surface", "--danger-ink")

#: `.invitation-warning` (`shell-components.css:158`, `color: var(--danger)`) is a
#: warning on a **destructive action**, not a screen state, so it is carved out by
#: name. Without the carve-out the scan reports a defect that is not one, and the next
#: slice narrows the scan until it proves nothing -- the guard-that-disarms-itself
#: failure this repository has already paid for once.
_DANGER_EXEMPT = ("invitation-warning",)

#: The shell's three stylesheets, as `(package, path parts)` -- the same set and the
#: same link order `test_r807_shell_quality.py:404-430` injects into the browser.
_SHELL_SHEETS = (
    ("khepri.rra.journey", ("assets", "shell.css")),
    ("khepri.rra.journey", ("assets", "shell-components.css")),
    ("khepri.runtime", ("shell_assets", "workspace.css")),
)

#: Both template directories `RCA-010` §Scope admits. `legal_templates/` is included
#: deliberately: `test_every_shell_template_is_measured` scans only `shell_templates/`,
#: so the legal pages are reached by no extent assertion -- slice 2b's recorded lesson.
_TEMPLATE_PACKAGES = (("khepri.runtime", "shell_templates"), ("khepri.runtime", "legal_templates"))


def _sheet_sources() -> list[tuple[str, str]]:
    """Each shell sheet as `(name, comment-stripped text)`, each proven non-empty."""
    sources = []
    for package, parts in _SHELL_SHEETS:
        name = parts[-1]
        text = files(package).joinpath(*parts).read_text(encoding="utf-8")
        assert text.strip(), f"{name} is empty, so this scan proves nothing"
        sources.append((name, _without_comments(text, name)))
    assert len(sources) == len(_SHELL_SHEETS)
    return sources


def _rules(css: str) -> list[tuple[str, str]]:
    """Every `(selector, declaration block)` pair in a comment-stripped sheet."""
    return [
        (match.group(1).strip(), match.group(2))
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)
    ]


def _templates() -> list[tuple[str, str]]:
    """Every template in both admitted directories, as `(name, source)`."""
    found = []
    for package, directory in _TEMPLATE_PACKAGES:
        for entry in files(package).joinpath(directory).iterdir():
            if entry.name.endswith(".html.j2"):
                text = entry.read_text(encoding="utf-8")
                assert text.strip(), f"{entry.name} is empty, so this scan proves nothing"
                found.append((f"{directory}/{entry.name}", text))
    assert found, "no templates found, so this scan proves nothing"
    return found


def _all_rules(sources: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """Every `(sheet, selector, block)` triple across the shell's three sheets."""
    return [
        (name, selector, block)
        for name, css in sources
        for selector, block in _rules(css)
    ]


def _rules_using_danger(all_rules: list[tuple[str, str, str]]) -> list[str]:
    """Every rule referencing the `--danger` family that is not a carved-out warning.

    **Checked over every rule, not only the rules naming a state class** -- and that is
    what makes the `.invitation-warning` carve-out load-bearing rather than decorative.
    Scoped to state-class selectors the exemption could never be reached, because
    `.invitation-warning` names no state: it would be a defined-but-never-attached
    shape inside a guard written to catch exactly that. Scoped to every rule, the
    exemption is the one thing standing between this scan and a false positive, and the
    invariant is stronger -- the family reaches ONE rule in the shell.

    Matched on `var(--danger...)` rather than the bare token, so `shell.css`'s `:root`
    block, which *defines* the family at `:68-71`, is not read as a usage of it.
    """
    return [
        f"{name}: {selector!r}"
        for name, selector, block in all_rules
        if re.search(r"var\(\s*--danger", block)
        and not any(exempt in selector for exempt in _DANGER_EXEMPT)
    ]


def _exempt_rules_naming_a_state(all_rules: list[tuple[str, str, str]]) -> list[str]:
    """The carve-out is not a blanket: an exempt rule may warn, never paint a state.

    A rule naming both `.invitation-warning` and a state class would be exempted by its
    own name, which is the one way the carve-out could be turned into a hole.
    """
    return [
        f"{name}: {selector!r} names {state}"
        for name, selector, _block in all_rules
        if any(exempt in selector for exempt in _DANGER_EXEMPT)
        for part in _selector_parts(selector + "{}")
        for state in _ALL_STATE_CLASSES
        if state in part
    ]


def _error_selectors(sources: list[tuple[str, str]]) -> list[str]:
    """Any selector naming an error, so an `.error-*` rule cannot arrive unnoticed."""
    return [
        f"{name}: {part}"
        for name, css in sources
        for part in _selector_parts(css)
        if "error" in part.lower()
    ]


def test_no_shell_state_rule_carries_error_paint() -> None:
    """`FR-202`: a governed state "never carries error paint".

    **Holds today by ABSENCE, and that is the fragile part.** No shell sheet carries a
    rule for `.decision-refusal`, `.decision-empty`, `.decision-unavailable` or
    `.compare-refusal` at all; the only state rule that exists is
    `.empty-state { color: var(--muted) }`. A refusal is unpainted body text. So this
    guard is what stops the first such rule arriving painted.

    Comments are stripped with the **shared** `_without_comments()` rather than a local
    stripper: slice 2b's evidence records that a second stripper without the
    string-literal guard reopens the hole where `content: "/*"` blinds the scan.
    """
    sources = _sheet_sources()
    all_rules = _all_rules(sources)
    assert all_rules, "no rules parsed from any shell sheet, so this test proves nothing"

    painted = _rules_using_danger(all_rules)
    assert painted == [], (
        f"the --danger family reached a rule that is not a destructive action: {painted}"
    )

    overreaching = _exempt_rules_naming_a_state(all_rules)
    assert overreaching == [], f"an exempt rule also names a governed state: {overreaching}"

    errors = _error_selectors(sources)
    assert errors == [], f"an error selector reached a shell sheet: {errors}"


def test_no_shell_template_gives_a_governed_state_an_error_role() -> None:
    """`FR-202` and master specification §13: a refusal is "Governed, not error".

    **This is the one assertion in the slice that is genuinely RED on arrival.**
    `role="alert"` -- an *assertive* live region, which is the journey's **transport
    error** role (`test_rra_journey_accessibility.py:64`) -- ships today on
    `_decision_cards.html.j2:13`, `_decision_sections.html.j2:11` and
    `decision.html.j2:30`. Task 8's build changes all three to `role="status"`, the
    polite role the journey already uses for its own refusal (`:67`).

    Scanned over **both** admitted template directories, so a state given an error role
    on a legal page would fail here too.
    """
    offenders = []
    for name, source in _templates():
        for element in re.finditer(r"<[a-z]+\b[^>]*>", source):
            markup = element.group(0)
            if 'role="alert"' not in markup:
                continue
            carried = [
                state
                for state in _ALL_STATE_CLASSES
                if re.search(r"\b" + state + r"\b", markup)
            ]
            if carried:
                offenders.append(f"{name}: {carried} carries role=alert")
    assert offenders == [], "a governed state carries an error role:\n" + "\n".join(offenders)


#: What a client-side loading affordance would need, none of which the shell has.
_LOADING_MARKERS = (
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"\baria-busy\b", re.IGNORECASE),
    re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE),
    re.compile(r'class="[^"]*\b(?:spinner|skeleton|loading|progress)\b', re.IGNORECASE),
)


def test_no_shell_surface_carries_a_loading_affordance() -> None:
    """`FR-202`'s loading state is not presented, because it **cannot occur**.

    The reason is **choice, not prohibition** -- and an earlier form of this docstring
    got that wrong. It claimed the shipped `default-src 'none'` CSP "forbids the script
    a client-side loading affordance would need". **It does not.** The policy is
    `default-src 'none'; script-src 'self'; style-src 'self'; ...`
    (`rra/journey/security.py`), which the shell imports rather than restates, and
    `script-src 'self'` explicitly **permits** same-origin script -- `default-src` is
    only the fallback for directives not otherwise named. The journey ships five `.js`
    files under that identical policy.

    What is true, and is what this guard holds: every shell surface is server-rendered
    whole and the commercial shell ships **no script at all**, by choice. A loading
    affordance would be the first, and it would have to be argued for rather than
    slipped in. `FR-206` forbids weakening the policy, which remains true and is simply
    not what makes this invariant hold.

    Stating it correctly matters because a guard resting on a false reason invites the
    next author to "fix" the CSP when the CSP was never the constraint.
    `test_r810_shell_responsive_rtl.py`'s
    `test_the_shell_ships_no_script_by_choice_not_by_policy` asserts the policy still
    permits script, so this correction cannot silently rot back.

    A later slice that ships a decorative spinner naming no stage fails here, which is
    what master specification §F.4 forbids even on the journey's own processing surface.

    **The CSP header itself is `test_r802_shell_unavailable_surface.py:290`'s**, which
    asserts `'unsafe-inline'` is absent, and `:281` asserts the shell policy *is* the
    journey policy, imported rather than restated. This asserts the **template** half
    only; a second policy assertion would be a second definition, and two definitions
    drift.
    """
    offenders = []
    for name, source in _templates():
        for marker in _LOADING_MARKERS:
            if marker.search(source):
                offenders.append(f"{name}: {marker.pattern}")
    assert offenders == [], "a loading affordance reached a shell surface:\n" + "\n".join(offenders)


#: `FR-203`'s motion properties, matched at a **declaration boundary** rather than at
#: the line start. A declaration follows either `{` or `;`, which occurs mid-line in a
#: packed one-liner, so `.x { transition: all 1s }` is caught while
#: `.change-transition {` is not -- there the word is *followed* by `{`, never preceded
#: by one. `journey.css:153` proves the packed idiom exists in this repository.
_MOTION_DECLARATION = re.compile(
    r"(?:[{;]\s*)(transition|animation|transform|will-change|scroll-behavior)[-a-z]*\s*:"
)

#: `@keyframes` carries no property-colon, so the declaration pattern cannot see it.
#: A second pattern, or a bare `@keyframes pulse { ... }` walks straight through.
_KEYFRAMES = re.compile(r"@keyframes\b")


def test_the_shell_stylesheets_declare_no_motion() -> None:
    """`FR-203`, asserted as the **superset** of its enumerated prohibitions.

    `FR-203` names bounce, elastic `cubic-bezier` outside `[0,1]`, parallax, infinite
    `animation-iteration-count` and counting numbers. Rather than scanning for those,
    this asserts that the shell sheets declare **no motion at all**, which subsumes
    every one of them and cannot be slipped past by a "tasteful" transition the
    enumeration happens to miss.

    **The allocation plan's premise for this task is false.** It records that
    `workspace.css` "contains three `transition`/`animation` declarations". It contains
    **zero**: the three matches for the *word* are the class name `.change-transition`
    and two prose comments. The plan counted the word, not declarations.

    **So no `prefers-reduced-motion` block is added, and none is needed.** Over zero
    motion declarations it would be dead CSS gating nothing -- the
    defined-but-never-attached defect. `journey.css:206` and `landing.css:232` carry
    such blocks because those sheets **have** motion; the shell does not, and this test
    is what keeps that true.

    `FR-203`'s "a positional transition on a drawer or dialog is short" is vacuous
    here: the drawer is a `<details>` that opens in place with no transition
    (`workspace.css:346-352`). Slice 8 measures one if it ever ships.

    Non-emptiness is asserted on **each file read** by `_sheet_sources()`, so a renamed
    or moved sheet cannot make the scan vacuously clean. It is deliberately **not**
    asserted on the match set: this scan defines motion patterns only, and a clean
    baseline yields zero matches, so requiring the matches to be non-empty would
    require the baseline to be both empty and non-empty. What rules out a scanner that
    finds nothing anywhere is the mutation record.
    """
    offenders = []
    for name, css in _sheet_sources():
        for match in _MOTION_DECLARATION.finditer(css):
            offenders.append(f"{name}: {match.group(1)} declared")
        if _KEYFRAMES.search(css):
            offenders.append(f"{name}: @keyframes")
    assert offenders == [], "the shell sheets declare motion:\n" + "\n".join(offenders)
