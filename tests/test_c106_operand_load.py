"""How the C1-06 assembly binds each operand: which run, manifest, and retention scope.

Three legs review on `#409` found stated nowhere: the newest completed run is the one bound; a
stored manifest that no longer reads is a governed refusal, not an escape; and a workspace-bound
session remains readable with its run under DEC-033 rather than inheriting the beta timer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from khepri.rca.workspace.audit import ACTION_RUN_COMPLETED, ACTION_RUN_FAILED
from khepri.rca.workspace.contracts import RUN_COMPLETED, AnalysisRun, RunOutcome, RunSubject
from khepri.rra.analysis.dataset_period import CAUSE_INCOMPLETE
from khepri.runtime.comparison_assembly import _latest_completed
from tests.c106_support import comparison_actions, completed_pair
from tests.test_c106_comparison_orchestration import _request
from tests.w104_support import member
from tests.w104b_support import journey

OWNER = "org_owner"
NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


class _Runs:
    """A workspace store that answers the one read the selector makes."""

    def __init__(self, runs: tuple[AnalysisRun, ...]) -> None:
        self._runs = runs

    def analysis_runs_for_scope(self, owner_id: str) -> tuple[AnalysisRun, ...]:
        return self._runs


def _completed(run_id: str, version_id: str, completed_at: datetime) -> AnalysisRun:
    return AnalysisRun._from_storage(
        subject=RunSubject(run_id=run_id, owner_id=OWNER, version_id=version_id),
        outcome=RunOutcome(
            state=RUN_COMPLETED,
            package_digest="d" * 64,
            package_version="package-v-alpha",
            formula_version="formula-v-alpha",
            completed_at=completed_at,
        ),
        started_at=completed_at - timedelta(minutes=5),
    )


def test_the_newest_completed_run_is_the_one_bound() -> None:
    """Two completed runs on one version: the later completion is bound. The identifiers are
    ordered against the completion order, so a selector that fell back to identifier order, or
    took the earliest, picks the other run. The report door is idempotent per session, so the
    second run cannot be produced through the journey fixture; the selector is pinned directly."""
    older = _completed("run_z_older", "dsv_one", NOW)
    newer = _completed("run_a_newer", "dsv_one", NOW + timedelta(hours=1))
    elsewhere = _completed("run_zz_other", "dsv_two", NOW + timedelta(hours=2))

    chosen = _latest_completed(_Runs((older, newer, elsewhere)), OWNER, "dsv_one")

    assert chosen is not None
    assert chosen.run_id == "run_a_newer"


def test_an_unreadable_stored_manifest_refuses_as_incomplete_with_one_audit_event(
    tmp_path,
) -> None:
    """The stored profile's manifest section is read without re-admission; a document that no
    longer reads must be the governed incomplete refusal with its one event, as a corrupted
    package already is -- not an error escaping before the audit write."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j)
    j.clock.advance(timedelta(minutes=1))
    before = len(j.w.audit.events_for_scope(who.owner_id))

    with patch(
        "khepri.runtime.comparison_operands.stored_manifest", side_effect=KeyError("timezone")
    ):
        outcome = actions.request(
            _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
        )

    added = j.w.audit.events_for_scope(who.owner_id)[before:]
    assert outcome.refused and outcome.refusal is not None
    assert outcome.refusal.cause == CAUSE_INCOMPLETE
    assert [event.action for event in added] == [ACTION_RUN_FAILED]


def test_a_workspace_pair_remains_available_past_the_beta_horizon(tmp_path) -> None:
    """DEC-033 keeps each package with its run, so the session-shaped read path must not make a
    comparison disappear on day eight. The request still records its one content-free event."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j)
    j.clock.advance(timedelta(days=8))
    before = len(j.w.audit.events_for_scope(who.owner_id))

    outcome = actions.request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )

    added = j.w.audit.events_for_scope(who.owner_id)[before:]
    assert outcome.admitted
    assert [event.action for event in added] == [ACTION_RUN_COMPLETED]
