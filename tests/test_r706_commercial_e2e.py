"""Commercial end-to-end evidence and the consent route (`R7-06`).

Authorized by `KHEPRI-DEC-023` §2. This is the last task in `R7`.

Every refusal asserted here must be byte-identical, and the comparisons are response-to-response
rather than each against a literal: a suite checking `404` twice would pass even if one cause grew a
body. `FR-024` is asserted as an **absence** rather than a behaviour, because no commercial route
accepts an organization and a test named for it that passed on a missing parameter could not fail.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rra.sessions import InvitationService
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
from tests.rca_lifecycle_support import NOW, factory_fixture  # noqa: F401 -- fixture
from tests.test_r703_live_authorization_on_resume import (  # noqa: F401 -- fixture re-export
    Journey,
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
