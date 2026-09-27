"""#535: which envelope versions publication and intake accept, and from whom.

A write the store just made is the write version, always. Only an object that
already existed -- `put_or_verify`'s race loser -- may carry a pre-#535 `v1`.
Anything else is refused and leaves nothing behind.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, update

import khepri.rra.artifact_publication as artifact_publication
from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.artifact_publication import ArtifactUnavailable
from khepri.rra.intake import StoragePolicyViolation
from tests.test_rra002_service import MemoryEncryptedObjectStore, intake_service
from tests.test_rra006_artifact_publication import MemoryObjects, _publication, _publisher
from tests.test_rra006_delivery_persistence import NOW

ATTEMPT = "a" * 32


def _first_key(test, publication) -> str:
    return (
        f"owners/{test.session.owner_id}/sessions/{test.session.session_id}/reports/"
        f"{publication.delivery.record.bundle_id}/attempts/{ATTEMPT}/"
        f"{publication.artifacts[0].kind}"
    )


def _recorded_versions(test) -> list[int]:
    with test.factory() as database:
        return sorted(database.scalars(select(ReportArtifactRow.envelope_version)))


@pytest.mark.parametrize("version", [1, 3])
def test_a_fresh_upload_write_that_is_not_the_write_version_is_refused(version: int) -> None:
    objects = MemoryEncryptedObjectStore(envelope_version=version)
    service, _, uploads = intake_service(objects=objects)
    intake = service.begin(session_id="ses_alpha", declared_size=8, now=NOW)
    intake.append(b"a,b\n1,2\n")

    with pytest.raises(StoragePolicyViolation):
        intake.complete(now=NOW)

    assert objects.objects == {}
    assert objects.deleted_keys == ["owners/own_alpha/sessions/ses_alpha/inputs/upl_example"]
    assert uploads.uploads == {}


def test_publication_refuses_an_object_it_created_as_v1(monkeypatch) -> None:
    monkeypatch.setattr(artifact_publication, "_new_attempt_id", lambda: ATTEMPT)
    objects = MemoryObjects(created_version=1)
    test, publisher = _publisher(objects)

    with pytest.raises(ArtifactUnavailable):
        publisher.publish(_publication(test))

    assert _recorded_versions(test) == []


def test_publication_proves_an_existing_v1_object_and_records_it_as_v1(monkeypatch) -> None:
    monkeypatch.setattr(artifact_publication, "_new_attempt_id", lambda: ATTEMPT)
    objects = MemoryObjects(existing_version=1)
    test, publisher = _publisher(objects)
    publication = _publication(test)
    first = publication.artifacts[0]
    objects.values[_first_key(test, publication)] = (
        first.content,
        first.media_type,
        first.sha256_hex,
    )

    publisher.publish(publication)

    assert _recorded_versions(test) == [1, 2, 2, 2, 2, 2, 2]


def test_an_artifact_row_pointing_outside_its_session_is_not_served() -> None:
    """The artifact read carries only the caller's session, so the key is held to it."""
    objects = MemoryObjects()
    test, publisher = _publisher(objects)
    publication = _publication(test)
    publisher.publish(publication)
    excel = next(key for key in objects.values if key.endswith("/excel"))
    foreign = excel.replace(f"/sessions/{test.session.session_id}/", "/sessions/ses_foreign/")
    objects.values[foreign] = objects.values[excel]
    with test.factory() as database:
        database.execute(
            update(ReportArtifactRow)
            .where(ReportArtifactRow.object_key == excel)
            .values(object_key=foreign)
        )
        database.commit()

    with pytest.raises(ArtifactUnavailable):
        publisher.read(
            session_id=test.session.session_id,
            job_id=publication.delivery.record.job_id,
            artifact_kind="excel",
            now=NOW,
        )
