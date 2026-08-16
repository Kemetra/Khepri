"""R6-08: static evidence that the resolver is not bypassed, and where it still can be.

**What this file claims, stated precisely, because the task title overstates it.** `R6-08` is named
"static or architectural tests making bypassing the resolver unreachable". Unreachable is not
achievable and this file does not claim it. The three membership verbs are ordinary methods that
take no authorization context; any module may call `promote_to_owner` directly and it will succeed,
because `R6-04` placed the authority check in the gate rather than in the verbs. Nothing static can
make that call impossible in Python.

`authorization.py` set the register this file follows: it says the boundary is **unmistakable**,
never unbypassable, and records why -- `IsolationScope` once carried a docstring claiming a
guarantee it did not have, and reviewers trusting it is part of why `#148` ran four review rounds.
The same discipline applies here, and it applies harder, because a chokepoint test is exactly the
kind of evidence a later reader will cite without re-deriving.

**What it does claim, which is worth having.** Two things, both falsifiable:

1. **A frozen inventory of who calls the verbs.** Today no module outside `organizations.py` calls
   any of the three. That is a fact about the codebase, and it is currently an *accident* -- no
   test records it, so the first handler to call one arrives silently. `test_the_membership_verbs_
   have_no_callers_outside_their_own_module` turns the accident into an asserted fact that breaks
   when it changes. The allowlist is deliberately empty and deliberately explicit: adding a caller
   means editing this test, which is the review conversation that ought to happen.

2. **The context boundary holds statically.** `test_rca001_authorization_context.py` proves
   `dataclasses.replace` is refused *behaviorally* -- it calls it and catches the refusal. This
   file asserts the different, static claim: no module in `src/khepri/rca/` writes that call in the
   first place, nor constructs a context outside its one door, nor reaches for `object.__new__`.
   Those are the escapes `records.py` enumerates as open, and a scan is the only thing that sees
   them across a whole package.

**Why an empty allowlist is evidence rather than a tautology.** A scan matching nothing passes
forever, which is the failure mode this whole slice exists to avoid. So the checker is self-tested
against known-bad and known-good sources, following
`test_rca001_boundary.py::test_rca_import_checker_flags_and_clears_expected_cases`, and every scan
asserts it actually read files before concluding anything.

**The gap this file records rather than closes.** `R6-04`'s docstring enumerates four things
deliberately left out of the resolver and does not mention the fifth: that it leaves the verbs
themselves ungated. That is not a defect in `R6-04` -- the gate is a coherent place for the check --
but it is an undocumented design decision, and `R6-01` §7 explicitly listed "where that check lives"
as a decision to be made rather than assumed. Recorded here and in `STATUS.md`, in the idiom
`test_rca001_guard_evidence.py` established for `R2`: a recorded gap, not an endorsement.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RCA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rca"

#: The three actions `R6-01` §3.1 makes owner-only. Each takes `actor_account_id` for attribution
#: and checks no authority of its own, so a direct call is an unauthorized mutation.
OWNER_ONLY_VERBS = ("promote_to_owner", "demote_to_member", "revoke_membership")

#: Modules permitted to call those verbs, and why. Empty of consumers by design.
#:
#: `organizations.py` defines them, so its own internal references are not bypasses. Every other
#: entry would be a module reaching a protected action; there are none today, and adding one means
#: editing this list -- which is the point. A caller admitted here must go through the resolver,
#: and this test cannot check that it does; it can only make the addition visible.
VERB_CALLER_ALLOWLIST = frozenset({"organizations.py"})


def _rca_sources() -> list[Path]:
    return sorted(p for p in RCA_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def find_verb_calls(source: str) -> list[str]:
    """Every call to one of the owner-only verbs, as `line N: name`.

    Matches on the called attribute's name rather than on a resolved receiver type, which is the
    only thing an AST scan can know without running the code. That over-matches in principle --
    an unrelated object with a `revoke_membership` method would be flagged -- and over-matching is
    the correct direction for a tripwire: a false positive is a review conversation, a false
    negative is an unnoticed bypass.
    """
    calls: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = (
            function.attr
            if isinstance(function, ast.Attribute)
            else function.id
            if isinstance(function, ast.Name)
            else None
        )
        if name in OWNER_ONLY_VERBS:
            calls.append(f"line {node.lineno}: {name}")
    return calls


def find_context_escapes(source: str) -> list[str]:
    """Calls that would forge or mutate an `AuthorizationContext` outside its one door.

    `records.py` enumerates these as the escapes that cannot be closed: `dataclasses.replace`
    rebuilds a frozen instance with fields swapped, `object.__new__` allocates without running a
    constructor, and `object.__setattr__` mutates what `frozen=True` protects. None is stoppable
    at runtime -- a guard against `object.__setattr__` is removable by `object.__setattr__` -- so
    a scan asserting nobody writes them is the available evidence.
    """
    escapes: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute):
            if function.attr in ("__new__", "__setattr__") and _is_object(function.value):
                escapes.append(f"line {node.lineno}: object.{function.attr}")
            elif function.attr == "replace" and _is_dataclasses(function.value):
                escapes.append(f"line {node.lineno}: dataclasses.replace")
        elif isinstance(function, ast.Name) and function.id == "replace":
            escapes.append(f"line {node.lineno}: replace")
    return escapes


def _is_object(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "object"


def _is_dataclasses(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "dataclasses"


def find_direct_context_construction(source: str) -> list[str]:
    """Calls spelling `AuthorizationContext(...)` directly, bypassing `create`.

    The class is callable -- `@dataclass` guarantees it -- and `Sealed` refuses construction
    outside `through_door()`, so this would raise at runtime. The static claim is separate and
    weaker in one way and stronger in another: it cannot prove the refusal works, but it sees
    every module at once rather than the ones a test happens to exercise.
    """
    return [
        f"line {node.lineno}: AuthorizationContext(...)"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AuthorizationContext"
    ]


class TestTheVerbInventory:
    """Who calls the three owner-only verbs, frozen so a new caller is visible."""

    def test_the_scan_reads_the_package(self) -> None:
        """A scan over zero files passes every assertion below it.

        `test_rca001_boundary.py` guards its own scan the same way. The number is a floor, not a
        count -- it fails if the package moves or the glob breaks, not when a module is added.
        """
        sources = _rca_sources()
        assert len(sources) >= 15, f"expected the rca package, found {len(sources)} files"
        assert any(p.name == "organizations.py" for p in sources)

    def test_the_membership_verbs_have_no_callers_outside_their_own_module(self) -> None:
        """The tripwire. Currently an empty set, asserted rather than assumed.

        **What a failure here means.** Not "you did something wrong" -- it means a module now
        reaches a protected action directly, and someone must confirm it goes through
        `AuthorizationResolver.require_owner` first. That check is a human one; this test only
        guarantees it is *asked*.
        """
        offenders: list[str] = []
        for path in _rca_sources():
            if path.name in VERB_CALLER_ALLOWLIST:
                continue
            for call in find_verb_calls(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.name}:{call}")
        assert offenders == [], (
            "a module outside the allowlist calls an owner-only membership verb; confirm it "
            "resolves authority through AuthorizationResolver.require_owner first, then add it "
            "to VERB_CALLER_ALLOWLIST with the reason"
        )

    def test_the_allowlist_names_only_modules_that_exist(self) -> None:
        """A stale allowlist entry silently widens the tripwire.

        If `organizations.py` were renamed and the entry left behind, the exemption would apply
        to nothing while the new module went unexamined -- a hole that looks like a passing test.
        """
        present = {p.name for p in _rca_sources()}
        assert present >= VERB_CALLER_ALLOWLIST

    def test_the_verb_scanner_flags_and_clears_expected_cases(self) -> None:
        """The checker self-test: it must discriminate, not merely return empty.

        Follows `test_rca001_boundary.py::test_rca_import_checker_flags_and_clears_expected_cases`.
        Without this, a scanner broken into always returning `[]` passes every assertion above.
        """
        flagged = [
            "service.promote_to_owner(org, account, actor_account_id=a, now=n)",
            "self._organizations.demote_to_member(org, account)",
            "revoke_membership(org, account)",
            "x = 1\nservice.revoke_membership(org, account)",
        ]
        for source in flagged:
            assert find_verb_calls(source), f"scanner missed a call in: {source!r}"

        cleared = [
            "resolver.require_owner(token, organization_id=org, now=n)",
            "service.create_organization('Acme', account, now=n)",
            "promote_to_owner = 'a string, not a call'",
            "def promote_to_owner(self): ...",
            "store.get_membership(org, account)",
        ]
        for source in cleared:
            assert find_verb_calls(source) == [], f"scanner false-positived on: {source!r}"


class TestTheContextBoundaryHoldsStatically:
    """No module writes the escapes `records.py` enumerates as unclosable.

    Distinct from `test_rca001_authorization_context.py`, which calls `dataclasses.replace` and
    asserts it is refused. That proves the runtime guard works on one instance; this proves no
    module in the package attempts it at all. Either alone leaves the other's failure mode open:
    a working guard nobody trips is not evidence nobody writes the call, and vice versa.
    """

    def test_no_module_forges_or_mutates_a_sealed_record(self) -> None:
        offenders: list[str] = []
        for path in _rca_sources():
            for escape in find_context_escapes(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.name}:{escape}")
        assert offenders == [], (
            "a module reaches for an escape records.py documents as unclosable; these are "
            "deliberate and conspicuous by design, so one appearing means reviewing intent"
        )

    def test_no_module_constructs_a_context_outside_its_door(self) -> None:
        """`AuthorizationContext.create` is the only door, and nothing spells the class directly.

        `authorization.py` itself is not exempt: its `create` calls `cls(...)` inside
        `through_door()`, which this scan does not match, so the module needs no allowlist entry.
        That is a property worth keeping -- an exemption here would be an exemption for the one
        module most able to abuse it.
        """
        offenders: list[str] = []
        for path in _rca_sources():
            for call in find_direct_context_construction(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.name}:{call}")
        assert offenders == []

    def test_the_escape_scanner_flags_and_clears_expected_cases(self) -> None:
        flagged = [
            "dataclasses.replace(context, role=OWNER_ROLE)",
            "object.__new__(AuthorizationContext)",
            "object.__setattr__(context, 'role', 'owner')",
            "replace(context, role='owner')",
        ]
        for source in flagged:
            assert find_context_escapes(source), f"scanner missed an escape in: {source!r}"

        cleared = [
            "AuthorizationContext.create(account_id=a, organization_id=o, role=r)",
            "self._store.replace_nothing()",
            "text.replace('a', 'b')",
            "membership.promoted()",
        ]
        for source in cleared:
            assert find_context_escapes(source) == [], f"false positive on: {source!r}"

    def test_the_construction_scanner_flags_and_clears_expected_cases(self) -> None:
        assert find_direct_context_construction("AuthorizationContext(account_id='a')")
        assert find_direct_context_construction("ctx = AuthorizationContext('a', None, None)")
        assert find_direct_context_construction("AuthorizationContext.create(account_id='a')") == []
        assert find_direct_context_construction("x: AuthorizationContext = ctx") == []


class TestWhatRemainsOpen:
    """**Recorded gaps, not endorsements** -- the idiom `R2` set in `test_rca001_guard_evidence.py`.

    Each of these is a hole a reader might otherwise assume this slice closed. Asserting them
    means the assumption cannot survive contact with the test suite.
    """

    def test_the_membership_verbs_accept_no_authorization_context(self) -> None:
        """The reason "unreachable" is not claimed anywhere in this file.

        The verbs take `actor_account_id` for *attribution* and check nothing. Closing this means
        giving them a context parameter, which is an `R6-02` change and out of a test-only slice.
        This asserts the current shape so that when it changes, the docstrings above are known to
        need revisiting.
        """
        import inspect

        from khepri.rca.organizations import OrganizationService

        for verb in OWNER_ONLY_VERBS:
            parameters = inspect.signature(getattr(OrganizationService, verb)).parameters
            assert "context" not in parameters
            assert "authorization" not in parameters
            assert "actor_account_id" in parameters, (
                f"{verb} lost its attribution parameter; if it gained authority checking "
                "instead, this whole file's framing needs revisiting"
            )

    def test_the_resolver_has_no_production_consumer_yet(self) -> None:
        """The tripwire's honest caveat: it currently guards an empty room.

        No module outside `authorization_resolution.py` imports `AuthorizationResolver`, because
        the HTTP surface that would use it is `R7`/`R8`. The inventory above is therefore
        *preventative* rather than confirmatory -- it will catch the first bypass, and it has
        caught none because none has been possible. Stating that here stops a later reader from
        reading a green test as "every handler is gated".
        """
        importers = [
            path.name
            for path in _rca_sources()
            if path.name != "authorization_resolution.py"
            and "AuthorizationResolver" in path.read_text(encoding="utf-8")
        ]
        assert importers == [], (
            "AuthorizationResolver now has a consumer; the chokepoint claim becomes checkable "
            "for real, and this test should be replaced by one asserting that consumer's path"
        )


@pytest.mark.parametrize("verb", OWNER_ONLY_VERBS)
def test_each_owner_only_verb_still_exists(verb: str) -> None:
    """The inventory is meaningless if it names verbs that were renamed away.

    A scan for `promote_to_owner` after a rename to `grant_ownership` finds nothing and passes,
    which is the silent-hole failure this whole file is built to avoid.
    """
    from khepri.rca.organizations import OrganizationService

    assert callable(getattr(OrganizationService, verb))
