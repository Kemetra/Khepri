from __future__ import annotations

import pytest

from tests.test_rra_journey_api import client

CONSENT = {"consent_version": "rra001.beta-consent.v1"}
REFUSAL = {"detail": "Cross-site mutation is not allowed."}


def test_cross_site_mutation_is_refused_before_the_api_handles_it() -> None:
    response = client().post(
        "/api/v1/beta/consent",
        json=CONSENT,
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert response.json() == REFUSAL


def test_same_origin_mutation_reaches_the_normal_api_contract() -> None:
    response = client().post(
        "/api/v1/beta/consent",
        json=CONSENT,
        headers={"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"},
    )
    assert response.status_code != 403


# --- #434 §2: a cookie-bearing mutation must carry at least one browser signal ---------------


def test_a_cookie_bearing_mutation_with_neither_browser_signal_is_refused() -> None:
    """The approved journey design: mutating browser requests must carry `Origin` and Fetch
    Metadata. A request that carries the session cookie and neither signal is what an old
    client, a WebView, or a replayed cookie sends, and it must fail closed rather than pass.
    """
    response = client().post("/api/v1/beta/consent", json=CONSENT)

    assert response.status_code == 403
    assert response.json() == REFUSAL


@pytest.mark.parametrize(
    "signal",
    [
        pytest.param({"Origin": "https://testserver"}, id="origin_only"),
        pytest.param({"Sec-Fetch-Site": "same-origin"}, id="fetch_metadata_only"),
    ],
)
def test_one_same_origin_signal_is_enough(signal: dict[str, str]) -> None:
    """A browser without Fetch Metadata still sends `Origin` on a mutation."""
    response = client().post("/api/v1/beta/consent", json=CONSENT, headers=signal)

    assert response.status_code != 403


def test_a_cookieless_mutation_without_browser_signals_reaches_the_api() -> None:
    """A non-browser caller carries no ambient credential, so there is nothing to forge."""
    test = client()
    test.cookies.clear()

    response = test.post("/api/v1/beta/sessions/redeem", json={"token": "malformed"})

    assert response.status_code == 400


def test_a_safe_method_with_a_cookie_and_no_signal_is_untouched() -> None:
    response = client().get("/api/v1/beta/journey")

    assert response.status_code == 200
