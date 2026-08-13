from __future__ import annotations

from tests.test_rra_journey_api import client


def test_cross_site_mutation_is_refused_before_the_api_handles_it() -> None:
    response = client().post(
        "/api/v1/beta/consent",
        json={"consent_version": "rra001.beta-consent.v1"},
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-site mutation is not allowed."}


def test_same_origin_mutation_reaches_the_normal_api_contract() -> None:
    response = client().post(
        "/api/v1/beta/consent",
        json={"consent_version": "rra001.beta-consent.v1"},
        headers={"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"},
    )
    assert response.status_code != 403
