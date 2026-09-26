"""#596: the RRA store reads a session's children by the `(owner_id, session_id)` pair.

The pipeline used to read a session's upload, profile and package by `session_id` alone and
check the scope afterwards. Each read is now a scoped verb whose statement carries the owner
predicate, so a caller holding the right `session_id` under the wrong owner gets `None`, as
`get_session_for_owner` already answers for the session itself.

**Additive, by owner decision (2026-09-26).** `RCA-001` `FR-037` keeps RRA's existing tests
unmodified, and two of them implement the repository Protocols with only the session-only
verb. So the Protocols gain the scoped verb with a default body that fails closed on a scope
mismatch, and the session-only verbs stay for those tests. The guard below keeps production
code off them.

`get_session(session_id)` is deliberately not narrowed. The beta session id is the bearer
credential: no owner exists until it resolves.

**Not a `test_rra*` file**, for the same `FR-037` reason.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select

from khepri.rra.intake import UploadMetadata, UploadRepository
from khepri.rra.packages import PackageVersions
from khepri.rra.persistence import FactPackageRow, SqlFactPackageRepository
from khepri.rra.sessions import SessionScope
from tests.test_rra003_persistence import record, repositories, session_and_upload
from tests.w104_support import member
from tests.w107_support import journey, sealed_version

_SRC = Path(__file__).resolve().parents[1] / "src" / "khepri"
_UNSCOPED = ("get_upload_for_session", "get_profile_for_session", "get_package_for_session")

#: The only production calls of a session-only verb allowed to remain: each Protocol's default
#: scoped body, which filters the session-only result by the whole scope.
_ALLOWED_CALLS = {
    ("rra/intake.py", "get_upload_for_session"),
    ("rra/datasets.py", "get_profile_for_session"),
    ("rra/packages.py", "get_package_for_session"),
}


def _foreign(scope: SessionScope) -> SessionScope:
    return SessionScope(owner_id="own_other", session_id=scope.session_id)


class TestTheStoreCarriesTheOwnerPredicate:
    def test_an_upload_is_read_only_under_its_own_owner(self) -> None:
        _, sessions, uploads, _, _ = repositories()
        scope, upload = session_and_upload(sessions, uploads)

        assert uploads.get_upload_for_scope(scope) == upload
        assert uploads.get_upload_for_scope(_foreign(scope)) is None

    def test_a_profile_is_read_only_under_its_own_owner(self) -> None:
        _, sessions, uploads, profiles, _ = repositories()
        scope, upload = session_and_upload(sessions, uploads)
        stored = profiles.add_profile(record(upload))

        assert profiles.get_profile_for_scope(scope) == stored
        assert profiles.get_profile_for_scope(_foreign(scope)) is None

    def test_a_package_is_read_only_under_its_own_owner(self) -> None:
        j = journey()
        who = member(j.w)
        sealed_version(j, who, with_run=True)
        with j.w.factory() as database:
            row = database.scalars(
                select(FactPackageRow).where(FactPackageRow.owner_id == who.owner_id)
            ).first()
        assert row is not None, "the fixture published no package, so this proves nothing"
        scope = SessionScope(owner_id=row.owner_id, session_id=row.session_id)
        packages = SqlFactPackageRepository(j.w.factory)
        versions = PackageVersions.current()

        found = packages.get_package_for_scope(scope, versions)
        assert found is not None and found.package_id == row.package_id
        assert packages.get_package_for_scope(_foreign(scope), versions) is None


class _SessionOnlyUploads(UploadRepository):
    """A store implementing only the session-only verb, as RRA's existing test doubles do."""

    def __init__(self, upload: UploadMetadata) -> None:
        self._upload = upload

    def add_upload(self, upload: UploadMetadata) -> bool:
        return False

    def get_upload_for_session(self, session_id: str) -> UploadMetadata | None:
        return self._upload if session_id == self._upload.session_id else None

    def get_upload_in_scope(self, upload_id: str, scope: SessionScope) -> UploadMetadata | None:
        return None


def test_the_protocol_default_refuses_a_foreign_owner() -> None:
    """A double that knows only `session_id` still answers the scoped question fail-closed."""
    _, sessions, uploads, _, _ = repositories()
    scope, upload = session_and_upload(sessions, uploads)
    double = _SessionOnlyUploads(upload)

    assert double.get_upload_for_scope(scope) == upload
    assert double.get_upload_for_scope(_foreign(scope)) is None


def _unscoped_calls(source: str) -> list[str]:
    return re.findall(r"\.(" + "|".join(_UNSCOPED) + r")\(", source)


def test_the_call_scanner_finds_a_call() -> None:
    assert _unscoped_calls("x = store.get_upload_for_session(sid)") == ["get_upload_for_session"]
    assert _unscoped_calls("def get_upload_for_session(self, sid): ...") == []


def test_no_production_code_reads_a_session_child_by_session_id_alone() -> None:
    """Every production read goes through a scoped verb; the defaults are the only exception."""
    modules = sorted(_SRC.rglob("*.py"))
    assert len(modules) > 50, f"scanned {len(modules)} modules under {_SRC}, so this proves nothing"

    found = {
        (path.relative_to(_SRC).as_posix(), verb)
        for path in modules
        for verb in _unscoped_calls(path.read_text(encoding="utf-8"))
    }

    assert found == _ALLOWED_CALLS, (
        f"session-only reads outside the Protocol defaults: {sorted(found - _ALLOWED_CALLS)}; "
        f"defaults no longer present: {sorted(_ALLOWED_CALLS - found)}"
    )
