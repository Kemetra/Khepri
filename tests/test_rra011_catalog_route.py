"""The catalog read route: definitions over HTTP, session-scoped and tier-clean.

`RRA-011` authorizes a read route exposing the registry, and bounds it: scoped to
its session through the same helper its siblings use, Business- and Audit-tier
fields only, and no Internal-tier field on any catalog surface.

**Why the catalog and not a per-fact evidence JSON.** The evidence surfaces are
pre-rendered artifacts served by `artifact_response` from a closed set of
`artifact_kind` values with a database check constraint behind it. A JSON
evidence artifact would mean a migration and a second projection of the same
bundle — `RRA-011` requires exactly one evidence projection per fact, and the
HTML surface already is it. The catalog needs no package, so it needs no
artifact.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from khepri.rra import definitions
from khepri.rra.api import create_app
from tests.test_rra006_report_api import (
    NOW,
    harness,
    invitation_service,
    redeem_and_consent,
)

CATALOG = "/api/v1/beta/catalog/{language}"


def test_the_catalog_requires_a_beta_session() -> None:
    """Same boundary as every sibling route, and asserted the same way."""
    test = harness()

    response = test.client.get(CATALOG.format(language="en"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}


def test_the_catalog_states_every_governed_metric_in_the_asked_language() -> None:
    test = harness()
    redeem_and_consent(test)

    body = test.client.get(CATALOG.format(language="en")).json()

    assert {entry["code"] for entry in body["metrics"]} == set(definitions.METRIC_CODES)
    for entry in body["metrics"]:
        assert entry["description"]
        assert entry["not_meant"]

    # Every metric a reader is shown as a figure carries a name. The one that
    # does not is `concentration_curve`, which names the retained series a chart
    # reads: `RRA-008` keeps that curve label-free deliberately, so a name here
    # would title something no reader meets as a figure.
    unnamed = {e["code"] for e in body["metrics"] if e["name"] is None}
    assert unnamed == {"concentration_curve"}


def test_the_catalog_answers_in_arabic_when_arabic_is_asked() -> None:
    """Parity is the point: the same codes, different words, no fallback."""
    test = harness()
    redeem_and_consent(test)

    english = test.client.get(CATALOG.format(language="en")).json()
    arabic = test.client.get(CATALOG.format(language="ar")).json()

    codes = {entry["code"] for entry in english["metrics"]}
    assert codes == {entry["code"] for entry in arabic["metrics"]}

    by_code = {entry["code"]: entry for entry in arabic["metrics"]}
    assert by_code["revenue"]["description"] != "Money from sales, after returns are subtracted."


def test_an_unsupported_language_is_refused_by_the_path() -> None:
    """`ArtifactLanguage` bounds the segment, so an unknown language never routes."""
    test = harness()
    redeem_and_consent(test)

    assert test.client.get(CATALOG.format(language="fr")).status_code == 422


def test_the_catalog_carries_no_internal_tier_field() -> None:
    """`RRA-011`: Business and Audit tiers only, on every catalog surface."""
    test = harness()
    redeem_and_consent(test)

    body = test.client.get(CATALOG.format(language="en")).json()

    for entry in body["metrics"]:
        assert "state" not in entry
        assert "precision" not in entry
        assert "population" not in entry


def test_the_catalog_is_absent_without_its_collaborators() -> None:
    """An unconfigured deployment exposes no catalog at all."""
    client = TestClient(
        create_app(service=invitation_service(), clock=lambda: NOW),
        base_url="https://testserver",
    )

    assert client.get(CATALOG.format(language="en")).status_code == 404
