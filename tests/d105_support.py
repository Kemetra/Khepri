"""Shared harness for `D1-05`'s two test files (active `RCA-008`).

`D1-05` has two subjects and they need one set of fixtures. The read model --
`decision/evidence.py`, `MetricCard.evidence` and the drawer on S-1 -- is
`test_d105_evidence_drawer.py`; the four breakdown surfaces the drawer has to
hang from are `test_d105_decision_sections.py`. Both drive the same scripted
port, the same governed outcomes and the same shell stubs, and a second copy of
those would be a second definition of what the port answers.

**Split because CodeScene said so, and it was right.** One file carrying both
scored 8.03 on Lines of Code in a Single File and, critically, on Low Cohesion.
The seam it pointed at is a real one: what a read model selects and what a page
renders are different subjects with different failure modes, and the fixtures
they share are exactly the ones collected here.

The port is a fake for the reason `D1-02`'s, `D1-03`'s and `D1-04`'s were: what
is under test is the *selection*, and a real projection would put a pipeline
between the inputs and the choice. The two cases that must see `RRA-014`'s own
projector stay in the drawer file, with the bundle they need.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.organizations import Organization
from khepri.rca.semantic_queries import ports
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.decision import seam
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes

__all__ = [
    "AVAILABILITY_FIELDS",
    "BASKET_FIELDS",
    "BRANCH_FIELDS",
    "CONCENTRATION_FIELDS",
    "EVIDENCE_FIELDS",
    "LANGUAGES",
    "NOW",
    "OVERVIEW_FIELDS",
    "PRODUCT_FIELDS",
    "STATED",
    "UNAVAILABLE",
    "UNSTATED",
    "UNSTATED_ABSENCES",
    "VIEW_FIELDS",
    "EchoPort",
    "Record",
    "ScriptedPort",
    "StubIsolation",
    "StubOrganizations",
    "StubRecords",
    "StubResolver",
    "StubRun",
    "actions",
    "address",
    "availability",
    "breakdown",
    "client",
    "evidence_outcome",
    "overview",
    "services",
]

LANGUAGES = ("en", "ar")
NOW = datetime(2026, 9, 12, tzinfo=UTC)

EVIDENCE_FIELDS = ("figure", "evidence", "provenance", "absence")
OVERVIEW_FIELDS = ("metric", "value", "population", "versions")
AVAILABILITY_FIELDS = ("metric", "availability", "reason", "versions")
BRANCH_FIELDS = ("store", "metric", "value", "population")
PRODUCT_FIELDS = ("dimension", "member", "metric", "value", "population")
BASKET_FIELDS = ("metric", "value", "population", "versions")
CONCENTRATION_FIELDS = ("dimension", "metric", "value", "population")

#: `FR-165`'s content-free miss, as the collaborator answers an unscripted view.
UNAVAILABLE = ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE)


class ScriptedPort:
    """Answers per `view_id`, so one read can miss while the others admit.

    `FR-165` makes each read independently authorized and independently able to
    answer unavailable; a port that answered uniformly could not express that.
    """

    def __init__(self, outcomes: dict[str, ports.ViewOutcome | None]) -> None:
        """Answer each view with what it was scripted to answer."""
        self.outcomes = outcomes
        self.requests: list[ports.SemanticViewRequest] = []

    def project(
        self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
    ) -> ports.ViewOutcome | None:
        """Record the request verbatim, and answer as scripted."""
        self.requests.append(request)
        return self.outcomes.get(request.view_id)


class _FakeIsolation:
    """One owner id for any pair; scoping is not what these cases test."""

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        """One owner id, so the port decides every answer."""
        return f"owner-of-{organization_id}"


class _FakeSources:
    """A source reader that always finds the run."""

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object:
        """A source the fake port never inspects."""
        return object()


def actions(port: ScriptedPort) -> SemanticQueryActions:
    """The real orchestration over a fake door and a scripted port."""
    return SemanticQueryActions(_FakeIsolation(), _FakeSources(), port)


@dataclasses.dataclass(frozen=True, slots=True)
class Record:
    """One cited evidence record as the port publishes it.

    A local shape rather than `CitedEvidence` because the read model is
    `khepri.rca`'s and may not import `khepri.rra`: a test that handed it the
    real record would assert an import the module is forbidden to make.
    """

    citation_id: str
    metric: str
    unit_kind: object = "monetary"
    formula_version: object = "rra004.formula.v1"
    precision: object | None = 2
    inputs: object | None = ("fct_a",)
    provenance: object | None = (("subject", "v1"),)


#: A complete record and one stating all three governed absences.
STATED = Record(citation_id="cit_revenue", metric="revenue")
UNSTATED = Record(
    citation_id="cit_gross_profit",
    metric="gross_profit",
    precision=None,
    inputs=None,
    provenance=None,
)

#: The absences `UNSTATED` states, in the order `RRA-014` states them.
UNSTATED_ABSENCES = (
    ("cit_gross_profit", "precision"),
    ("cit_gross_profit", "inputs"),
    ("cit_gross_profit", "provenance"),
)


def evidence_outcome(
    records: tuple[Record, ...] = (STATED,),
    absences: tuple[tuple[str, str], ...] = (),
) -> ports.ViewOutcome:
    """An admitted S-9 outcome carrying rows, records and stated absences."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.REPORT_EVIDENCE.view_id,
            view_version=seam.REPORT_EVIDENCE.view_version,
            fields=EVIDENCE_FIELDS,
            rows=tuple(
                (f"fig_{record.metric}", record.citation_id, None, None)
                for record in records
            ),
            evidence=records,
            evidence_absences=absences,  # type: ignore[arg-type]
        ),
        effective=ports.EffectiveRequest(dimensions=("period",)),
    )


def availability(rows: tuple[tuple[object, ...], ...]) -> ports.ViewOutcome:
    """S-6's governed four-state for the metrics a case names."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.METRIC_AVAILABILITY.view_id,
            view_version=seam.METRIC_AVAILABILITY.view_version,
            fields=AVAILABILITY_FIELDS,
            rows=rows,
        ),
    )


def overview(caveats: tuple[object, ...] = ()) -> ports.ViewOutcome:
    """S-1 publishing two figures, qualified by whatever caveats a case supplies."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.EXECUTIVE_OVERVIEW.view_id,
            view_version=seam.EXECUTIVE_OVERVIEW.view_version,
            fields=OVERVIEW_FIELDS,
            rows=(
                ("revenue", "700.00", None, ()),
                ("gross_profit", "120.00", None, ()),
            ),
            caveats=caveats,
        ),
        effective=ports.EffectiveRequest(dimensions=("period",)),
    )


def breakdown(
    view: seam.ViewIdentity,
    fields: tuple[str, ...],
    rows: tuple[tuple[object, ...], ...],
    is_empty: bool = False,
) -> ports.ViewOutcome:
    """An admitted breakdown outcome in its own view's published field order.

    `effective` is absent here and supplied by `filtered_breakdown` where a case
    needs it, so the cases that do not care about `D1-07`'s routing read exactly
    as they did before it.
    """
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=view.view_id,
            view_version=view.view_version,
            fields=fields,
            rows=rows,
            is_empty=is_empty,
        ),
    )


def _echo_cell(field: str) -> str:
    """One cell, governed where the field names something the catalog knows.

    `metric` carries a real code because the drawer resolves a business name
    through `RRA-011`, and an invented code raises `UnknownCode` rather than
    rendering. Every other field is filler: this port exists to show which
    filters reached which view, not to publish figures.
    """
    return "revenue" if field == "metric" else "1"


class EchoPort:
    """Answers every view admitted, echoing the request's own filters back.

    `D1-07` routes a filter to the views whose definitions admit it, so what a
    case must see is **which pairs reached which view**. A port that answered a
    fixed outcome could not show that; this one builds each outcome's
    `EffectiveRequest` from the request it was handed, which is what
    `projection.project` does for a real read.
    """

    def __init__(self, fields: dict[str, tuple[str, ...]]) -> None:
        """Answer each view with rows shaped to its own published fields."""
        self.fields = fields
        self.requests: list[ports.SemanticViewRequest] = []

    def project(
        self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
    ) -> ports.ViewOutcome:
        """Record the request verbatim, and admit it carrying its own filters."""
        self.requests.append(request)
        fields = self.fields.get(request.view_id, OVERVIEW_FIELDS)
        return ports.ViewOutcome(
            kind=ports.KIND_ADMITTED,
            projection=ports.ViewProjection(
                view_id=request.view_id,
                view_version=request.view_version,
                fields=fields,
                rows=(tuple(_echo_cell(name) for name in fields),),
            ),
            effective=ports.EffectiveRequest(requested_filters=request.filters),
        )

    def filters_for(self, view_id: str) -> tuple[tuple[str, str], ...]:
        """What reached one view, from the requests this port recorded."""
        for request in self.requests:
            if request.view_id == view_id:
                return request.filters
        raise AssertionError(f"{view_id} was not read")


#: The published field order of every view a decision page reads, so `EchoPort`
#: shapes each row to the view that published it.
VIEW_FIELDS = {
    seam.EXECUTIVE_OVERVIEW.view_id: OVERVIEW_FIELDS,
    seam.METRIC_AVAILABILITY.view_id: AVAILABILITY_FIELDS,
    seam.REPORT_EVIDENCE.view_id: EVIDENCE_FIELDS,
    seam.BRANCH_PERFORMANCE.view_id: BRANCH_FIELDS,
    seam.PRODUCT_CATEGORY.view_id: PRODUCT_FIELDS,
    seam.BASKET.view_id: BASKET_FIELDS,
    seam.CONCENTRATION.view_id: CONCENTRATION_FIELDS,
}


class StubRun:
    """One analysis run as `analysis_runs_for_scope` answers it."""

    def __init__(self, run_id: str, state: str = "completed") -> None:
        """A run in the state a case names, completed at a fixed instant."""
        self.run_id = run_id
        self.state = state
        self.completed_at = NOW if state == "completed" else None


class StubRecords:
    """The record reader the source selector reads, over a fixed run list."""

    def __init__(self, runs: tuple[StubRun, ...]) -> None:
        """The runs this scope holds."""
        self.runs = runs
        self.scopes: list[str] = []

    def analysis_runs_for_scope(self, owner_id: str) -> tuple[StubRun, ...]:
        """Every run of this scope, newest first as the real store orders them."""
        self.scopes.append(owner_id)
        return self.runs


class StubIsolation:
    """`RCA-001`'s bridge, answering one opaque owner id per organization."""

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        """The opaque key, which no commercial identifier may be derivable from."""
        return f"owner-of-{organization_id}"


class _Context:
    """A resolved actor in one organization, as `ActorResolver` answers one."""

    def __init__(self) -> None:
        """One owner of `org-acme`, which every case in these files acts in."""
        self.account_id = "acct-1"
        self.organization_id = "org-acme"
        self.role = "owner"

    @property
    def is_owner(self) -> bool:
        """Owner everywhere; the decision surface is a read and never asks."""
        return True


class StubResolver:
    """The scope door, answering one context."""

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        """The session's context."""
        return _Context()

    def require_owner(
        self, token: str, *, organization_id: str, now: object = None
    ) -> _Context:  # pragma: no cover
        """Never reached: nothing on this surface is owner-gated."""
        raise AssertionError("the decision surface is a read")


class StubOrganizations:
    """One membership, so the frame resolves rather than the chooser rendering."""

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        """The one organization every case in these files acts in."""
        return [
            Organization._from_storage(
                organization_id="org-acme", name="Acme", created_at=NOW
            )
        ]


def services(decisions: object, records: object | None = None) -> ShellServices:
    """A shell wired with the decision collaborator a case supplies.

    `records` and `isolation` are wired together or not at all: `D1-07`'s source
    selector needs both, and `FR-165` makes a deployment without them render the
    page with the selector absent rather than failing.
    """
    return ShellServices(
        resolver=StubResolver(),
        organizations=StubOrganizations(),
        decisions=decisions,
        records=records,
        isolation=StubIsolation() if records is not None else None,
    )


def client(decisions: object, records: object | None = None) -> TestClient:
    """That shell, behind a session cookie."""
    app = FastAPI()
    add_shell_routes(app, services=services(decisions, records), clock=lambda: NOW)
    started = TestClient(app, base_url="https://testserver")
    started.cookies.set(SESSION_COOKIE, "a-session-token")
    return started


def address(language: str = "en") -> str:
    """The decision surface's address for one completed run."""
    return f"{SHELL_PREFIX}/{language}/org-acme/decisions/run-a"
