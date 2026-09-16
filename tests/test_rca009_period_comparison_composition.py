"""`RCA-009`: the Period Comparison composition branch.

Authority: active `RCA-009` `FR-172`--`FR-180`.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.semantic_queries import ports as query_ports
from khepri.rca.semantic_queries import queries as semantic_queries
from khepri.rca.workspace.contracts import AnalysisRun
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rca.workspace.provenance import SqlRunProvenanceStore
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.rra.persistence import SqlFactPackageRepository
from khepri.rra.semantic_views import projection
from khepri.rra.semantic_views.contracts import SHAPE_TWO_POPULATION
from khepri.rra.semantic_views.registry import define_view, view_ids
from khepri.runtime import wiring
from khepri.runtime.comparison_assembly import ComparisonAssemblyPorts
from khepri.runtime.job_sessions import SqlJobSessions
from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
from tests.c106_support import CompletedPair, completed_pair
from tests.w104_support import member
from tests.w104b_support import Journey, journey

#: The one published view this branch exists to reach (`FR-172`).
_VIEW_ID = "PeriodComparisonView"


@dataclass(frozen=True, slots=True)
class _Scene:
    """One journey, its completed pair, and the wired adapter over both."""

    journey: Journey
    pair: CompletedPair
    adapter: SemanticViewAdapter


def _ports(j: Journey) -> ComparisonAssemblyPorts:
    """The real collaborators the seam needs, over the journey's live stores."""
    return ComparisonAssemblyPorts(
        packages=j.w.packages,
        profiling=j.w.profiling,
        jobs=SqlJobSessions(j.w.factory),
        reports=SqlRunReportStore(j.w.factory),
        provenance=SqlRunProvenanceStore(j.w.factory),
        workspace=j.w.store,
    )


def _scene() -> _Scene:
    """A journey with one substantive completed pair and the wired adapter."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    adapter = SemanticViewAdapter(
        SqlFactPackageRepository(j.w.factory), operands=_ports(j), now=j.clock
    )
    return _Scene(journey=j, pair=pair, adapter=adapter)


def _request(view_id: str = _VIEW_ID) -> query_ports.SemanticViewRequest:
    """One exact published version of `view_id`, named as `FR-143` requires."""
    definition = define_view(view_id)
    return query_ports.SemanticViewRequest(
        view_id=definition.view_id, view_version=definition.view_version
    )


def _composed(
    scene: _Scene, *, subject: AnalysisRun, baseline: AnalysisRun
) -> projection.ViewOutcome | None:
    """The composed outcome for the caller-ordered pair `(subject, baseline)`."""
    return scene.adapter.project(_request(), (subject, baseline))


def _provenance(outcome: projection.ViewOutcome | None) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Every cited figure's provenance pairs, in projection order.

    `output_field_order` for `PeriodComparisonView` is `("metric", "subject",
    "baseline", "delta", "versions")`, and none of `subject`, `baseline` or
    `delta` has a reader in `_FIELD_READERS` -- each projects as an unstated
    absence, so `rows` alone cannot show which run was subject and which was
    baseline. `CitedEvidence.provenance` does: `crossversion_assembly.py`
    stamps `subject_version_id`/`baseline_version_id`/`operand_order` on every
    cited figure, and those pairs invert when the caller's order inverts.
    """
    assert outcome is not None and outcome.projection is not None
    return tuple(figure.provenance for figure in outcome.projection.evidence)


def test_an_authorized_ordered_pair_reaches_a_real_projection() -> None:
    """`FR-179` -- an admitted projection with compared figures, not an empty one.

    The distinction this asserts is `FR-179`'s own: an admitted empty projection
    is not proof of reachability, and neither is the absence of a refusal.
    """
    scene = _scene()

    outcome = _composed(scene, subject=scene.pair.subject_run, baseline=scene.pair.baseline_run)

    assert outcome is not None
    assert outcome.kind == projection.KIND_ADMITTED
    assert outcome.projection.rows, "an empty projection does not prove reachability"
    assert outcome.refusal is None


def test_the_view_no_longer_refuses_for_an_incompatible_shape() -> None:
    """`FR-179` -- the refusal this slice exists to remove."""
    scene = _scene()

    outcome = _composed(scene, subject=scene.pair.subject_run, baseline=scene.pair.baseline_run)

    assert outcome.refusal is None


def test_the_caller_supplied_order_survives_composition() -> None:
    """`FR-174`, `FR-176` -- subject and baseline are the caller's, in their order.

    Every cited figure's provenance stamps `subject_version_id` and
    `baseline_version_id` (`crossversion_assembly.py`). Swapping which run the
    caller names as subject and which as baseline must invert those two version
    identifiers in the admitted evidence -- identical provenance here would mean
    the adapter lost the caller's order rather than merely that it does not
    matter to the figures.
    """
    scene = _scene()
    subject_version = scene.pair.subject_run.version_id
    baseline_version = scene.pair.baseline_run.version_id

    forward = _composed(scene, subject=scene.pair.subject_run, baseline=scene.pair.baseline_run)
    swapped = _composed(scene, subject=scene.pair.baseline_run, baseline=scene.pair.subject_run)

    forward_pairs = dict(_provenance(forward)[0])
    swapped_pairs = dict(_provenance(swapped)[0])
    assert forward_pairs["subject_version_id"] == subject_version
    assert forward_pairs["baseline_version_id"] == baseline_version
    assert swapped_pairs["subject_version_id"] == baseline_version
    assert swapped_pairs["baseline_version_id"] == subject_version


def test_every_other_view_still_routes_single_population() -> None:
    """`FR-172` -- derived from the registry, asserting equality and non-emptiness.

    A subset assertion here would not see a view added to the branch.

    `SHAPE_EITHER_BUNDLE` is deliberately excluded from this predicate, contrary
    to an earlier draft that included it on the premise "no published view
    declares it today". The registry disproves that premise:
    `MetricAvailabilityView` and `ReportEvidenceView` both declare
    `either_bundle` and project today over exactly one source through the
    unmodified `RCA-007` path. Routing either of them into the two-population
    branch would break `FR-172`'s own second sentence -- "every other view
    continues through `RCA-007` unchanged" -- for a one-source request. The
    adapter's predicate matches this test: `accepted_source_shape ==
    SHAPE_TWO_POPULATION`, not membership in a set that includes
    `SHAPE_EITHER_BUNDLE`.
    """
    admits_two = {
        view_id
        for view_id in view_ids()
        if define_view(view_id).accepted_source_shape == SHAPE_TWO_POPULATION
    }
    assert admits_two == {"PeriodComparisonView"}
    assert admits_two


def test_an_either_bundle_view_still_projects_over_one_source() -> None:
    """`FR-172` -- the narrowing above is load-bearing, not merely asserted.

    `MetricAvailabilityView` declares `SHAPE_EITHER_BUNDLE`. Composed through
    the wired adapter with a single source (its existing, unmodified shape), it
    must still be admitted -- if the branch predicate widened back to include
    `SHAPE_EITHER_BUNDLE`, a one-source request here would hit the two-population
    branch, fail its `len(sources) != 2` guard, and come back `None` instead of
    admitted. This is the regression that scenario would produce.
    """
    scene = _scene()

    outcome = scene.adapter.project(_request("MetricAvailabilityView"), (scene.pair.subject_run,))

    assert outcome is not None
    assert outcome.kind == projection.KIND_ADMITTED


def test_an_unwired_adapter_fails_closed_rather_than_crashing() -> None:
    """`FR-175` -- an unwired deployment (no operands/clock) is the uniform miss."""
    scene = _scene()
    unwired = SemanticViewAdapter(scene.journey.w.packages)

    outcome = unwired.project(
        _request(), (scene.pair.subject_run, scene.pair.baseline_run)
    )

    assert outcome is None


def test_a_cross_scope_pair_is_the_uniform_miss() -> None:
    """`FR-173` -- two runs read under different scopes yield no partial result."""
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    owner_pair = completed_pair(j, owner)
    foreign_pair = completed_pair(j, stranger)
    adapter = SemanticViewAdapter(
        SqlFactPackageRepository(j.w.factory), operands=_ports(j), now=j.clock
    )

    outcome = adapter.project(
        _request(), (owner_pair.subject_run, foreign_pair.baseline_run)
    )

    assert outcome is None


def _minimal_stack(j: Journey) -> wiring.RuntimeStack:
    """A `RuntimeStack` real enough for `_shell_decisions`, and no more.

    `_shell_decisions` reads exactly three attributes off the stack:
    `stack.factory`, `stack.services.packages`, and `stack.services.profiling`
    (see `wiring.py`'s `_shell_decisions`, and `build_comparison_actions`'s
    identical read of the same three). Every other `RuntimeStack` field --
    `settings`, `clients`, `reports`, `objects`, `clock`, `identity_provider`,
    and the other four `SessionServices` members -- is untouched by that
    function, so this stack supplies the journey's own factory and package/
    profiling services (the same objects `completed_pair` populated) and
    leaves the rest `None`. A dataclass carries no runtime type check, so this
    does not weaken what the test proves: `_shell_decisions` is called for
    real, unmodified, exactly as the composition root calls it.
    """
    services = wiring.SessionServices(
        invitations=None,  # type: ignore[arg-type]
        intake=None,  # type: ignore[arg-type]
        profiling=j.w.profiling,
        packages=j.w.packages,
        deletion=None,  # type: ignore[arg-type]
    )
    return wiring.RuntimeStack(
        settings=None,  # type: ignore[arg-type]
        clients=None,  # type: ignore[arg-type]
        services=services,
        reports=None,  # type: ignore[arg-type]
        factory=j.w.factory,
        objects=None,  # type: ignore[arg-type]
        clock=j.clock,
        identity_provider=None,
    )


def test_the_composition_root_wires_the_branch_not_a_hand_built_fixture() -> None:
    """`FR-172`-`FR-176` reach the deployed image, not just a hand-wired test double.

    Every other test in this module builds `SemanticViewAdapter` directly with
    `operands=`/`now=` supplied by hand. That is necessary to isolate the
    branch's own logic, but by itself it cannot show that `wiring.py`'s
    `_shell_decisions` -- the one production call site this task edits -- ever
    supplies those same collaborators. A hand-wired fixture passing every test
    while the deployed wiring silently drops a constructor argument is exactly
    the shape memory's `W1-07a` finding records: "a route absent from the
    image while every route test passes over a hand-built `ShellServices`".

    This drives `wiring._shell_decisions` itself -- the real function, called
    the way `build_shell_services` calls it -- over a real completed pair, and
    asserts the returned `SemanticQueryActions` admits a real
    `PeriodComparisonView` request. If `_shell_decisions` regressed to
    constructing `SemanticViewAdapter` with no `operands`/`now` (the pre-Task-2
    call), this would fail with `KIND_UNAVAILABLE` instead of `KIND_ADMITTED`.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    stack = _minimal_stack(j)
    isolation = IsolationService(SqlOrganizationStore(j.w.factory), SqlAccountStore(j.w.factory))
    sources = SqlWorkspaceRecordStore(j.w.factory)

    actions = wiring._shell_decisions(stack, isolation, sources)
    outcome = actions.request(
        semantic_queries.SemanticQueryRequest(
            actor=semantic_queries.SemanticQueryActor(account_id=who.account_id),
            organization_id=who.organization_id,
            view=_request(),
            source_ids=(pair.subject_run.run_id, pair.baseline_run.run_id),
        )
    )

    assert outcome.kind == query_ports.KIND_ADMITTED
    assert outcome.projection is not None
    assert outcome.projection.rows
