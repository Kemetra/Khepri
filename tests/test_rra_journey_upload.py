from __future__ import annotations

from importlib.resources import files

from tests.test_rra_journey_api import client


def _script() -> str:
    return files("khepri.rra.journey").joinpath("assets", "upload.js").read_text(
        encoding="utf-8"
    )


def test_upload_page_is_consent_gated_and_has_measurable_progress() -> None:
    body = client().get("/beta/en/upload").text
    assert 'id="consent"' in body
    assert 'id="sales-file"' in body and " disabled" in body
    assert 'role="progressbar"' in body
    assert "CSV · XLSX · 50 MB" in body


def test_invitation_fragment_is_redeemed_cleared_and_never_persisted() -> None:
    script = _script()
    assert 'location.hash.slice(1)' in script
    assert 'history.replaceState' in script
    assert '/api/v1/beta/sessions/redeem' in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "resume()" in script


def test_bootstrap_profiles_an_upload_whose_response_was_interrupted() -> None:
    script = _script()
    assert "state?.upload_present && !state.profile_present" in script
    assert script.rindex('api("/api/v1/beta/profile"') < script.rindex(
        'routeFor("review")'
    )


def test_consent_precedes_raw_xhr_upload_and_profile_request() -> None:
    script = _script()
    assert script.index("/api/v1/beta/consent") < script.index("await upload()")
    assert 'xhr.send(file)' in script
    assert 'xhr.upload.addEventListener("progress"' in script
    assert script.index("await upload()") < script.index("/api/v1/beta/profile")
    assert "Content-Length" not in script


def test_profile_rejection_exposes_session_recovery_after_upload() -> None:
    body = client().get("/beta/en/upload").text
    script = _script()
    assert 'id="upload-recovery"' in body
    assert "deleteContent" in script
    assert "uploaded = true" in script
    assert "upload-recovery" in script
