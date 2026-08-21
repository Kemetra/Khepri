"""Commercial end-to-end evidence and the consent route (`R7-06`).

Authorized by `KHEPRI-DEC-023` §2. This is the last task in `R7`.

Every refusal asserted here must be byte-identical, and the comparisons are response-to-response
rather than each against a literal: a suite checking `404` twice would pass even if one cause grew a
body. `FR-024` is asserted as an **absence** rather than a behaviour, because no commercial route
accepts an organization and a test named for it that passed on a missing parameter could not fail.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.switching import OrganizationSwitcher
from khepri.rra.sessions import ConsentRequired, InvitationService, require_upload_consent
from khepri.runtime.commercial_api import (
    COMMERCIAL_PREFIX,
    CommercialServices,
    add_commercial_routes,
)
from tests.rca_lifecycle_support import NOW, factory_fixture  # noqa: F401 -- fixture
from tests.test_r703_live_authorization_on_resume import (  # noqa: F401 -- fixture re-export
    Journey,
    _account,
    _rca_sessions,
    journey_fixture,
)
from tests.test_r703_live_authorization_on_resume import _resolver as _r703_resolver


def _client(journey: Journey) -> TestClient:
    """The real graph: `R7-03`'s journey wired through the production route group."""
    app = FastAPI()
    add_commercial_routes(
        app,
        services=CommercialServices(
            resolver=_r703_resolver(journey.factory),
            bridge=journey.bridge,
            consent=InvitationService(journey.rra_store),
        ),
        clock=lambda: NOW,
    )
    return TestClient(app)


def test_a_member_can_consent_to_their_own_analysis(journey: Journey) -> None:
    """The route exists, authorizes, and records through the existing service."""
    response = _client(journey).post(
        f"/api/v1/commercial/analyses/{journey.session_id}/consent",
        json={"consent_version": "v1"},
        cookies={"khepri_session": journey.member_token},
    )

    assert response.status_code == 204
    assert response.content == b""


def _outsider(journey: Journey) -> str:
    """An account in a different organization, with a live session switched into it."""
    account = _account(journey.factory, "outsider@example.test")
    other = OrganizationService(SqlOrganizationStore(journey.factory)).create_organization(
        "Other", account, now=NOW
    )
    token = _rca_sessions(journey.factory).create(account, now=NOW)
    OrganizationSwitcher(
        _rca_sessions(journey.factory), SqlOrganizationStore(journey.factory)
    ).switch(token, other.organization_id, now=NOW)
    return token


def test_a_foreign_analysis_is_indistinguishable_from_an_absent_one(journey: Journey) -> None:
    """Scenario 14, `FR-023`/`FR-034`. Compared response-to-response, not each against a literal."""
    client = _client(journey)
    token = _outsider(journey)

    foreign = client.get(
        f"/api/v1/commercial/analyses/{journey.session_id}",
        cookies={"khepri_session": token},
    )
    absent = client.get("/api/v1/commercial/analyses/ses_nope", cookies={"khepri_session": token})

    assert (foreign.status_code, foreign.content) == (absent.status_code, absent.content)
    assert journey.analysis_exists()


def test_a_foreign_consent_write_changes_nothing(journey: Journey) -> None:
    """Scenario 15: denied, and **no state changes in either organization**.

    The state assertion is the point. A refused write and a successful one can both return `404` if
    the scope check sits after the write, so asserting only the status would not distinguish them.
    """
    client = _client(journey)
    token = _outsider(journey)

    refused = client.post(
        f"/api/v1/commercial/analyses/{journey.session_id}/consent",
        json={"consent_version": "v-foreign"},
        cookies={"khepri_session": token},
    )

    assert refused.status_code == 404
    stored = journey.rra_store.get_session(journey.session_id)
    assert stored is not None
    assert stored.consent_version is None, "a foreign write must leave the analysis untouched"


def test_an_account_with_no_membership_authenticates_but_is_denied(journey: Journey) -> None:
    """Scenario 18, `FR-028`. Authentication must SUCCEED while every action is denied.

    The first assertion is what makes this an `FR-028` test rather than a login test: without it the
    case would pass against a system that rejected the account outright.
    """
    account = _account(journey.factory, "nomember@example.test")
    token = _rca_sessions(journey.factory).create(account, now=NOW)

    context = _r703_resolver(journey.factory).resolve(token, now=NOW)
    assert context.account_id == account, "authentication must succeed"
    assert context.organization_id is None, "with no active organization"

    client = _client(journey)
    opened = client.post("/api/v1/commercial/analyses", cookies={"khepri_session": token})
    resumed = client.get(
        f"/api/v1/commercial/analyses/{journey.session_id}",
        cookies={"khepri_session": token},
    )

    assert opened.status_code == 404
    assert (resumed.status_code, resumed.content) == (opened.status_code, opened.content)


def _commercial_handlers() -> dict[str, object]:
    """Every route handler the commercial group declares, by name.

    Read from what FastAPI actually registered rather than from a source scan, so a renamed handler
    is still inventoried instead of silently disappearing.
    """
    app = FastAPI()
    add_commercial_routes(
        app,
        services=CommercialServices(
            resolver=object(),  # type: ignore[arg-type]
            bridge=object(),  # type: ignore[arg-type]
            consent=object(),  # type: ignore[arg-type]
        ),
        clock=lambda: NOW,
    )
    return {
        route.endpoint.__name__: route.endpoint  # type: ignore[attr-defined]
        for route in app.routes
        if getattr(route, "path", "").startswith(COMMERCIAL_PREFIX)
    }


def test_every_commercial_handler_passes_the_canonical_checkpoint() -> None:
    """`FR-021`, `FR-026`. An action that does not pass the checkpoint must be unreachable.

    The emptiness assertion is not decoration: an inventory that found no handlers would satisfy
    every claim about the handlers it found.
    """
    handlers = _commercial_handlers()

    assert handlers, "no commercial handlers were registered; this test proves nothing"
    for name, handler in handlers.items():
        source = inspect.getsource(handler)
        assert "for_request(" in source, f"{name} does not pass the canonical checkpoint"
        assert "resolver.resolve(" not in source, f"{name} calls resolve, which §2 forbids"


def test_no_commercial_handler_accepts_an_organization() -> None:
    """`FR-024`, satisfied by ABSENCE and asserted as such.

    `FR-024` requires a request whose actor and named organization scope disagree to fail closed. No
    commercial route accepts an organization, so that request cannot be constructed here. A test
    named for `FR-024` that passed because the parameter does not exist would be a test that cannot
    fail; this asserts the absence itself, which is the property making it unreachable.
    """
    handlers = _commercial_handlers()

    assert handlers, "no commercial handlers were registered; this test proves nothing"
    for name, handler in handlers.items():
        parameters = set(inspect.signature(handler).parameters)
        assert "organization_id" not in parameters, f"{name} accepts an organization"
        assert "organization" not in parameters, f"{name} accepts an organization"


def test_two_analyses_of_one_organization_share_its_scope(journey: Journey) -> None:
    """`FR-031`: the isolation scope is the organization's, not the session's or the actor's."""
    client = _client(journey)
    first = client.post(
        "/api/v1/commercial/analyses", cookies={"khepri_session": journey.member_token}
    ).json()["session_id"]
    second = client.post(
        "/api/v1/commercial/analyses", cookies={"khepri_session": journey.member_token}
    ).json()["session_id"]

    assert first != second, "each analysis is its own session"

    expected = IsolationService(
        SqlOrganizationStore(journey.factory), SqlAccountStore(journey.factory)
    ).resolve_scope(journey.member, journey.organization_id)
    for session_id in (first, second):
        stored = journey.rra_store.get_session(session_id)
        assert stored is not None
        assert stored.owner_id == expected


def test_another_member_of_the_organization_resumes_the_same_analysis(journey: Journey) -> None:
    """`FR-009`: the organization is a durable scope distinct from the accounts acting in it."""
    client = _client(journey)
    opened = client.post(
        "/api/v1/commercial/analyses", cookies={"khepri_session": journey.member_token}
    ).json()["session_id"]

    resumed = client.get(
        f"/api/v1/commercial/analyses/{opened}",
        cookies={"khepri_session": journey.first_token},
    )

    assert resumed.status_code == 200, "the analysis belongs to the organization, not its opener"


def test_a_commercial_actor_cannot_upload_before_consenting(journey: Journey) -> None:
    """`FR-038` clause 1, both halves.

    The refusal alone would pass against a route that never records consent at all -- which is
    exactly the defect `KHEPRI-DEC-023` was written to fix -- so the accepted case after consenting
    is what makes this evidence rather than a restatement of the bug.
    """
    before = journey.rra_store.get_session(journey.session_id)
    assert before is not None
    with pytest.raises(ConsentRequired):
        require_upload_consent(before, now=NOW)

    consented = _client(journey).post(
        f"/api/v1/commercial/analyses/{journey.session_id}/consent",
        json={"consent_version": "v1"},
        cookies={"khepri_session": journey.member_token},
    )
    assert consented.status_code == 204

    after = journey.rra_store.get_session(journey.session_id)
    assert after is not None
    require_upload_consent(after, now=NOW)


def test_the_report_path_never_branches_on_actor_kind() -> None:
    """`FR-038` clauses 2-4, proved structurally rather than assumed.

    Disclosure, reconciliation/provenance and Arabic/English parity hold for a commercial actor
    because the pipeline keys on `SessionScope(owner_id, session_id)` and has no actor-kind concept.
    Re-asserting beta's rendering per actor kind would duplicate its suite; what needs proving is
    that the actor kind never enters.

    The report path is named explicitly rather than scanned with exclusions. `sessions.py` and
    `persistence.py` both name the commercial entry point by design (`KHEPRI-DEC-021` §2), so an
    all-of-`rra` scan would need an exclusion list, and an exclusion list is what drifts. The
    missing-module assertion keeps the explicit list honest: a renamed pipeline module fails loudly
    instead of being skipped.
    """
    report_path = [
        Path("src/khepri/rra/report_services.py"),
        Path("src/khepri/rra/report_publication.py"),
        Path("src/khepri/rra/report_artifacts.py"),
        Path("src/khepri/rra/pipeline.py"),
        Path("src/khepri/rra/bundle.py"),
        *sorted(Path("src/khepri/rra/analysis").rglob("*.py")),
        *sorted(Path("src/khepri/rra/rendering").rglob("*.py")),
    ]
    missing = [p.as_posix() for p in report_path if not p.exists()]

    assert not missing, f"a named report-path module is missing: {missing}; the scan would skip it"
    assert report_path, "the scan matched no report modules; it proves nothing"
    offenders = [p.as_posix() for p in report_path if "commercial" in p.read_text(encoding="utf-8")]
    assert offenders == [], (
        "a report-path module distinguishes a commercial actor; it must be actor-kind-free for "
        "FR-038's disclosure, provenance and language-parity clauses to hold by shared "
        "implementation rather than by assumption"
    )
