"""RRA-017 plan §1.5.1: the shell and commercial paths act in their RCA-resolved scope (`#595`).

These three paths reach RRA rows with an owner already resolved by RCA, so each enters that owner's
unit before its RRA reads. Inside the unit a read by `session_id` must agree with the owner, or
raise `ScopeConflict`, and a read by job alone (`find_delivery`) has a scope at all. Each test
records the unit bound at the moment the RRA port is called, so removing the `acting_for` fails it
on SQLite too, where no policy would otherwise notice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rra.scope import bound_unit
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
from khepri.runtime.comparison_operands import OperandRequest, derive_operand
from khepri.runtime.workspace_recording import ReportLocator, WorkspaceRecording, WorkspaceRefused

NOW = datetime(2026, 10, 3, tzinfo=UTC)
OWNER = "own_boundary"


def _bound_owner() -> str | None:
    unit = bound_unit()
    return None if unit is None else unit.owner_id


class _Seen:
    """The owner bound at each recorded call, in order."""

    def __init__(self) -> None:
        self.owners: list[str | None] = []

    def note(self) -> None:
        self.owners.append(_bound_owner())


# -- commercial consent --------------------------------------------------------------------------


@dataclass
class _Context:
    account_id: str = "acct-1"
    organization_id: str | None = "org-1"


class _Resolver:
    def for_request(self, _token: str, *, organization_id: str | None, now: object) -> _Context:
        return _Context()


class _Bridge:
    def resume(self, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(session_id="ses_1", owner_id=OWNER)


class _Consent:
    def __init__(self, seen: _Seen) -> None:
        self._seen = seen

    def record_consent(self, _session_id: str, *, consent_version: str, now: object) -> None:
        self._seen.note()


def test_commercial_consent_is_recorded_in_the_resumed_sessions_scope() -> None:
    seen = _Seen()
    app = FastAPI()
    add_commercial_routes(
        app,
        services=CommercialServices(
            resolver=_Resolver(),  # type: ignore[arg-type]
            bridge=_Bridge(),  # type: ignore[arg-type]
            consent=_Consent(seen),  # type: ignore[arg-type]
        ),
        clock=lambda: NOW,
    )
    response = TestClient(app).post(
        "/api/v1/commercial/analyses/ses_1/consent",
        json={"consent_version": "v1"},
        cookies={"khepri_session": "tok"},
    )
    assert response.status_code == 204, response.text
    assert seen.owners == [OWNER]
    assert _bound_owner() is None


# -- comparison operand --------------------------------------------------------------------------


class _Reports:
    def __init__(self, seen: _Seen) -> None:
        self._seen = seen

    def job_id_for_run(self, _run_id: str, _owner_id: str) -> str | None:
        self._seen.note()
        return None


def test_an_operand_is_derived_in_the_callers_scope() -> None:
    seen = _Seen()
    ports = SimpleNamespace(reports=_Reports(seen))
    run = SimpleNamespace(run_id="run_1", package_digest="d" * 64)
    request = OperandRequest(ports=ports, owner_id=OWNER, run=run, now=NOW)  # type: ignore[arg-type]
    load = derive_operand(request)
    assert load.operand is None
    assert seen.owners == [OWNER]
    assert _bound_owner() is None


# -- workspace recording -------------------------------------------------------------------------


class _Packages:
    def __init__(self, seen: _Seen) -> None:
        self._seen = seen

    def get_session_package(self, *, session_id: str, now: datetime) -> object:
        self._seen.note()
        return object()


class _Deliveries:
    def __init__(self, seen: _Seen) -> None:
        self._seen = seen

    def find_delivery(self, _job_id: str) -> None:
        self._seen.note()


class _Uploads:
    def __init__(self, seen: _Seen) -> None:
        self._seen = seen

    def get_upload_for_scope(self, _scope: object) -> None:
        self._seen.note()


def _recording(seen: _Seen) -> WorkspaceRecording:
    """A recording whose RRA ports note the unit; built without `__init__`, which needs both
    stores, because only the three RRA-reading helpers are under test."""
    recording = WorkspaceRecording.__new__(WorkspaceRecording)
    recording._rra = SimpleNamespace(  # noqa: SLF001
        packages=_Packages(seen),
        deliveries=_Deliveries(seen),
        uploads=_Uploads(seen),
        sessions=SimpleNamespace(get_session_for_owner=lambda *_: seen.note() or object()),
        profiling=SimpleNamespace(get_session_profile=lambda **_: seen.note()),
    )
    return recording


def test_the_admission_is_read_in_the_callers_scope() -> None:
    seen = _Seen()
    with pytest.raises(WorkspaceRefused):  # the stubs hold no upload, so it refuses
        _recording(seen)._admission(OWNER, "ses_1", NOW)  # noqa: SLF001
    assert seen.owners == [OWNER, OWNER, OWNER]
    assert _bound_owner() is None


def test_the_derivation_is_read_in_the_callers_scope() -> None:
    seen = _Seen()
    _recording(seen)._derivation(OWNER, "ses_1", NOW)  # noqa: SLF001
    assert seen.owners == [OWNER, OWNER]
    assert _bound_owner() is None


def test_the_delivery_read_by_job_alone_has_the_callers_scope() -> None:
    seen = _Seen()
    report = ReportLocator(session_id="ses_1", job_id="job_1")
    with pytest.raises(WorkspaceRefused):  # no delivery, so it refuses
        _recording(seen)._published_artifacts(OWNER, report, NOW)  # noqa: SLF001
    assert seen.owners == [OWNER]
    assert _bound_owner() is None
