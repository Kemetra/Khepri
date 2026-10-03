"""#535 on PostgreSQL: the re-keyed joins across a re-seal, and creation arbitrated by the identity.

`RCA-005` Verification: re-sealing an upload leaves every workspace join correct
(`FR-259`-`FR-261`) on PostgreSQL, where the purge also clears the version's `upload_id` through
`fk_rca_workspace_version_upload`. Each case builds its own upload and version, and first asserts
the pre-amendment digest join finds nothing on it (`test_i535_upload_identity.py` holds the cases).

Two concurrent `create_dataset_version` calls for one upload record exactly one version, and the
loser answers `already_recorded` through `existing_version` (`FR-257`, `FR-261`). The overlap is
forced: the first call is held just before its insert, after its lookup found nothing, and the
second is started only then.

Under the `concurrency` marker, so a skip in CI fails the build. **Not a `test_rra*` file**.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from sqlalchemy import Engine, text

from tests.rra017_support import POSTGRES
from tests.test_i535_upload_identity import (
    check_creation_stays_idempotent_across_a_reseal,
    check_deletion_finds_the_session_of_a_resealed_upload,
    check_the_purge_finds_a_resealed_upload,
)
from tests.w104_support import NOW as ADMITTED_AT
from tests.w104_support import admitted_session, member
from tests.w110_postgres_support import WAIT_SECONDS, HarnessError, postgres_journey

pytestmark = list(POSTGRES)


def test_the_purge_finds_a_resealed_upload_and_clears_the_identity() -> None:
    with postgres_journey() as j:
        version, _upload = check_the_purge_finds_a_resealed_upload(j)

        (kept,) = j.w.store.dataset_versions_for_scope(version.owner_id)

    assert kept.version_id == version.version_id
    assert kept.upload_id is None, "FR-256: the key clears the identity with the upload row"


def test_deletion_finds_the_session_of_a_resealed_upload() -> None:
    with postgres_journey() as j:
        check_deletion_finds_the_session_of_a_resealed_upload(j)


def test_creation_stays_idempotent_across_a_reseal() -> None:
    with postgres_journey() as j:
        check_creation_stays_idempotent_across_a_reseal(j)


class _HeldInsert:
    """Holds the first `add_dataset_version` call, after its caller's lookup found nothing."""

    def __init__(self, store: Any) -> None:
        self._original = store.add_dataset_version
        self._held = False
        self.reached = threading.Event()
        self.release = threading.Event()
        store.add_dataset_version = self

    def __call__(self, version: Any) -> Any:
        if not self._held:
            self._held = True
            self.reached.set()
            self.release.wait(WAIT_SECONDS * 3)
        return self._original(version)


def _a_backend_waits_on_a_lock(engine: Engine) -> bool:
    with engine.connect() as connection:
        waiting = connection.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE wait_event_type = 'Lock' AND datname = current_database()"
            )
        ).scalar_one()
    return waiting > 0


def _await_second(engine: Engine, second: threading.Thread) -> None:
    """Until the second call is blocked behind the first, or has finished on its own."""
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if not second.is_alive() or _a_backend_waits_on_a_lock(engine):
            return
        time.sleep(0.05)
    raise HarnessError("the second creation neither blocked nor finished")


def test_two_concurrent_creations_for_one_upload_record_one_version() -> None:
    with postgres_journey() as j:
        who = member(j.w)
        session_id = admitted_session(j.w, who.owner_id)
        held = _HeldInsert(j.w.store)
        results: dict[str, Any] = {}

        def create(name: str) -> None:
            try:
                results[name] = j.w.services.create_dataset_version(
                    who.caller, session_id=session_id, now=ADMITTED_AT
                )
            except Exception as error:  # noqa: BLE001 -- reported by the assertion below
                results[name] = error

        first = threading.Thread(target=create, args=("first",))
        second = threading.Thread(target=create, args=("second",))
        first.start()
        if not held.reached.wait(WAIT_SECONDS):
            raise HarnessError("the first creation never reached its insert")
        second.start()
        _await_second(j.w.factory.kw["bind"], second)
        held.release.set()
        first.join(WAIT_SECONDS * 3)
        second.join(WAIT_SECONDS * 3)

        versions = j.w.store.dataset_versions_for_scope(who.owner_id)
        outcomes = sorted(event.outcome for event in j.w.audit.events_for_scope(who.owner_id))

    assert not any(isinstance(result, Exception) for result in results.values()), results
    assert len(versions) == 1
    assert {results["first"].version_id, results["second"].version_id} == {versions[0].version_id}
    assert outcomes == ["already_recorded", "completed"]
