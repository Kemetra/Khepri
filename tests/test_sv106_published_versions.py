"""`SV1-06` — exact-version resolution, no `latest`, historical immutability.

Authority: active `RRA-014` `FR-143` (requests name an exact version; supported
historical readers return that immutable definition, unsupported versions
refuse, and no `latest` alias or silent upgrade exists) and `FR-134`'s
immutability.

**The immutability check uses an independent witness.** The plan names the trap:
a slice can "fix" a published definition in place and every test still passes,
because the tests read the same object the edit changed. Comparing
`resolve(...)` with `define_view(...)` would be exactly that tautology. So the
expected value is `PUBLISHED_DIGESTS` -- content digests written down when each
version was published -- and an edit to any published definition fails here.

**The unsupported-version case uses a `.v99` sentinel**, the plan's other named
risk: a test naming the next real version becomes a no-op the day that version
ships.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from khepri.rra.semantic_views import contracts, published, refusals, registry

#: A version no view will ever publish. Not `.v2`: the day a real `.v2` ships,
#: a test written against it stops testing the unsupported path and starts
#: testing the supported one, silently.
_NEVER = "v99"


def _sentinel(view_id: str) -> str:
    """An unpublished version string for this view, built from its own prefix."""
    published_version = registry.define_view(view_id).view_version
    return f"{published_version.rsplit('.', 1)[0]}.{_NEVER}"


def test_an_exact_published_version_resolves_to_its_definition() -> None:
    """`FR-143` -- a supported historical reader returns that immutable definition."""
    for view_id in sorted(registry.view_ids()):
        expected = registry.define_view(view_id)
        assert published.resolve(view_id, expected.view_version) == expected


def test_every_published_definition_still_matches_its_published_digest() -> None:
    """`FR-134` -- immutable after publication, checked against a written witness.

    `PUBLISHED_DIGESTS` is a literal recorded at publication. Comparing the
    registry against itself would pass no matter what changed; comparing it
    against the digest fails the moment any published field moves, which is what
    `FR-134` asks for.
    """
    assert published.PUBLISHED_DIGESTS, "the witness table must not be empty"
    for view_id in sorted(registry.view_ids()):
        definition = registry.define_view(view_id)
        recorded = published.PUBLISHED_DIGESTS.get(definition.view_version)
        assert recorded is not None, f"{definition.view_version} was published with no digest"
        assert published.definition_digest(definition) == recorded, (
            f"{definition.view_version} changed after publication; "
            "FR-134 makes that a new version, not an edit"
        )


def test_the_digest_covers_every_contract_field() -> None:
    """A digest over part of the record would let the rest be edited freely.

    Each field is changed in turn and the digest must move. Derived from the
    record's own fields, so a tenth contract field is covered without an edit
    here -- and a digest that forgot it would fail this test rather than pass
    quietly.
    """
    definition = registry.define_view("BranchPerformanceView")
    baseline = published.definition_digest(definition)
    changes: dict[str, object] = {
        "view_id": "OtherView",
        "view_version": "sv1.branch_performance.v2",
        "accepted_source_shape": contracts.SHAPE_TWO_POPULATION,
        "metric_allowlist": ("revenue",),
        "dimension_allowlist": ("period",),
        "request_filter_allowlist": (),
        "fixed_filters": (("channel", "web"),),
        "required_evidence": ("figure_provenance",),
        "output_field_order": ("metric",),
        "empty_result_rule": contracts.EMPTY_STATED_ABSENCE,
    }
    names = {field.name for field in dataclasses.fields(contracts.SemanticViewDefinition)}
    assert set(changes) == names, "a contract field is not exercised by this test"

    for name, value in changes.items():
        altered = dataclasses.replace(definition, **{name: value, "view_version": f"probe.{name}"})
        assert published.definition_digest(altered) != baseline, f"{name} is outside the digest"


def test_an_unpublished_version_refuses_with_the_governed_cause() -> None:
    """`FR-143` -- unsupported versions refuse, with `FR-141`'s wording."""
    for view_id in sorted(registry.view_ids()):
        outcome = published.resolve(view_id, _sentinel(view_id))
        assert isinstance(outcome, refusals.ViewRefusal)
        assert outcome.cause == refusals.CAUSE_UNKNOWN_VERSION
        assert set(outcome.wording) == {"en", "ar"}
        assert all(text.strip() for text in outcome.wording.values())


def test_an_unknown_view_refuses_before_any_version_is_considered() -> None:
    """A version of a view that does not exist is an unknown *view*."""
    outcome = published.resolve("NoSuchView", "sv1.executive_overview.v1")
    assert isinstance(outcome, refusals.ViewRefusal)
    assert outcome.cause == refusals.CAUSE_UNKNOWN_VIEW


@pytest.mark.parametrize("alias", ["latest", "LATEST", "Latest", "*", "current", "head"])
def test_no_alias_resolves_anything(alias: str) -> None:
    """`FR-143` -- "No `latest` alias ... exists", and none of its neighbours either.

    Asserted for every view, not one: an alias honoured by a single view would be
    a silent upgrade for that view's readers and invisible here otherwise.
    """
    for view_id in sorted(registry.view_ids()):
        outcome = published.resolve(view_id, alias)
        assert isinstance(outcome, refusals.ViewRefusal)
        assert outcome.cause == refusals.CAUSE_UNKNOWN_VERSION


def test_no_alias_is_a_key_anywhere_in_the_published_record() -> None:
    """Not merely unresolved -- absent. A key would be an alias waiting to be read."""
    keys = set(published.PUBLISHED_DIGESTS)
    for versions in published.published_history().values():
        keys.update(versions)
    for alias in ("latest", "LATEST", "current", "head", "*"):
        assert alias not in keys


def test_a_version_less_request_cannot_be_made_at_all() -> None:
    """`FR-143` -- there is nothing to default to, so there is no default.

    Structural rather than documented: `resolve` takes the version as a required
    positional argument, so a caller cannot omit it. An empty string is not a
    version and refuses.
    """
    with pytest.raises(TypeError):
        published.resolve("BasketView")  # type: ignore[call-arg]

    outcome = published.resolve("BasketView", "")
    assert isinstance(outcome, refusals.ViewRefusal)
    assert outcome.cause == refusals.CAUSE_UNKNOWN_VERSION


def test_the_published_history_covers_every_view_by_extent() -> None:
    """Append-only is an extent claim, so the extent is what is asserted.

    Equality against the registry's own key set, never `>=`: a view published
    without a history entry, or a history entry for a view no longer published,
    both fail.
    """
    history = published.published_history()
    assert set(history) == registry.view_ids()
    for view_id, versions in history.items():
        assert versions == (registry.define_view(view_id).view_version,)
        assert len(versions) == len(set(versions)), f"{view_id} repeats a version"


def test_every_history_entry_has_a_recorded_digest() -> None:
    """A published version with no witness is a version nothing can hold to."""
    recorded = set(published.PUBLISHED_DIGESTS)
    published_now = {
        version for versions in published.published_history().values() for version in versions
    }
    assert published_now == recorded


def test_published_versions_is_empty_for_a_view_that_does_not_exist() -> None:
    """An unpublished view has no history rather than raising."""
    assert published.published_versions("NoSuchView") == ()


def test_resolution_returns_the_registry_object_itself() -> None:
    """No copy, no rebuild: `FR-143` returns *that* immutable definition."""
    definition = registry.define_view("ConcentrationView")
    assert published.resolve("ConcentrationView", definition.view_version) is definition


def test_the_digest_table_is_written_down_and_not_derived() -> None:
    """The witness must be independent, and no behavioural test can prove that.

    If `PUBLISHED_DIGESTS` were computed from the registry, every immutability
    assertion above would still pass -- vacuously, because both sides would move
    together. That is the tautology the plan warns about, and it is invisible at
    runtime: the only way to see it is to look at how the table is written.

    So this reads the source. Every value must be a string literal; a call, a
    comprehension or a name would mean the expected value is derived from the
    thing it is meant to hold to.
    """
    tree = ast.parse(pathlib.Path(published.__file__).read_text(encoding="utf-8"))
    table = _assigned_value(tree, "PUBLISHED_DIGESTS")

    assert isinstance(table, ast.Dict), "PUBLISHED_DIGESTS must be a literal mapping"
    assert table.values, "the witness table must not be empty"
    for key, value in zip(table.keys, table.values, strict=True):
        assert isinstance(key, ast.Constant), "a computed key is not a written witness"
        assert isinstance(value, ast.Constant), f"{ast.unparse(key)} has a derived digest"
        assert isinstance(value.value, str)


def _assigned_value(tree: ast.Module, name: str) -> ast.expr:
    """The right-hand side of one module-level assignment, found by name.

    Split across two readers rather than one compound condition, for the reason
    CodeScene gave on `SV1-04`'s import scan: `isinstance(...) and ...` is two
    branches against a threshold of two.
    """
    for node in tree.body:
        found = _annotated(node, name) or _plain_assignment(node, name)
        if found is not None:
            return found
    raise AssertionError(f"{name} is not assigned at module level")


def _annotated(node: ast.stmt, name: str) -> ast.expr | None:
    """`NAME: type = value` at module level, if this node is that."""
    if not isinstance(node, ast.AnnAssign):
        return None
    if not isinstance(node.target, ast.Name):
        return None
    if node.target.id != name:
        return None
    return node.value


def _plain_assignment(node: ast.stmt, name: str) -> ast.expr | None:
    """`NAME = value` at module level, if this node is that."""
    if not isinstance(node, ast.Assign):
        return None
    if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
        return None
    return node.value
