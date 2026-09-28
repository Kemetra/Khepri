"""#535: stored `v1` report artifacts are rewritten as envelope `v2`.

`KHEPRI-DEC-028`, amended in #613, keeps `v1` readable "until a migration slice rewrites every `v1`
object as `v2` and verifies that none remains". The owner split that slice on 2026-09-28. This file
covers the report-artifact half. Uploads wait for a stable upload identity, because their ciphertext
digest is a recorded identity in `DatasetVersion`.

The store under test is the real `S3EncryptedObjectStore` over a dict-backed client, and the rows
come from a real publication. `v1` objects are forged from the `v1` layout, with no AAD on either
GCM call, so the test does not depend on the module being able to write the format it retires.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select, update

from khepri.rra import envelope as env
from khepri.rra.artifact_persistence import ReportArtifactRow, SqlArtifactRepository
from khepri.rra.artifact_publication import ArtifactUnavailable, ReportArtifactPublisher
from khepri.rra.envelope_migration import ArtifactEnvelopeMigration, EnvelopeMigrationReport
from khepri.rra.intake import StoragePolicyViolation
from khepri.rra.persistence import BetaSessionRow, UploadRow
from khepri.rra.storage import S3EncryptedObjectStore, StoredEnvelope
from khepri.runtime import envelope_migration as runtime_migration
from tests.test_rra006_artifact_persistence import _publication
from tests.test_rra006_delivery_persistence import NOW, Harness, harness

MASTER = env.MasterKey(material=bytes([9]) * 32)
BUCKET = "khepri-content"
PLAINTEXT = b"report bytes that must survive the rewrite"
PLAINTEXT_SHA = hashlib.sha256(PLAINTEXT).hexdigest()
KEY = "owners/own_alpha/sessions/ses_alpha/reports/b/attempts/a/excel"
OTHER_KEY = "owners/own_bravo/sessions/ses_bravo/reports/b/attempts/a/excel"
MEDIA = "application/octet-stream"


def forge_v1(plaintext: bytes, master: env.MasterKey = MASTER) -> bytes:
    """A `v1` envelope: version byte 1, both nonces, the wrapped key, no AAD anywhere."""
    data_key = os.urandom(32)
    wrap_nonce, content_nonce = os.urandom(12), os.urandom(12)
    wrapped = AESGCM(master.material).encrypt(wrap_nonce, data_key, None)
    ciphertext = AESGCM(data_key).encrypt(content_nonce, plaintext, None)
    return bytes([1]) + wrap_nonce + content_nonce + wrapped + ciphertext


def _precondition_failed() -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "PreconditionFailed"},
            "ResponseMetadata": {"HTTPStatusCode": 412},
        },
        "PutObject",
    )


@dataclass
class DictS3:
    """The S3 calls the store makes, over a dict, honouring `IfNoneMatch`."""

    objects: dict[str, bytes] = field(default_factory=dict)
    puts: list[str] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    confirm: bool = True
    failing: set[str] = field(default_factory=set)

    def put_object(self, *, Key: str, Body: bytes, ChecksumSHA256: str, **kwargs: object) -> dict:
        if Key in self.failing:
            raise ClientError({"Error": {"Code": "InternalError"}}, "PutObject")
        if kwargs.get("IfNoneMatch") == "*" and Key in self.objects:
            raise _precondition_failed()
        self.puts.append(Key)
        self.objects[Key] = bytes(Body)
        return {"ChecksumSHA256": ChecksumSHA256} if self.confirm else {}

    def get_object(self, *, Key: str, **_: object) -> dict:
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Key: str, **_: object) -> dict:
        self.deletes.append(Key)
        self.objects.pop(Key, None)
        return {}


def _store(client: DictS3) -> S3EncryptedObjectStore:
    return S3EncryptedObjectStore(client=client, bucket=BUCKET, master_key=MASTER)


def _v1_record(body: bytes, plaintext_sha: str = PLAINTEXT_SHA) -> StoredEnvelope:
    return StoredEnvelope(
        ciphertext_sha256_hex=hashlib.sha256(body).hexdigest(),
        sha256_hex=plaintext_sha,
        encryption_algorithm=env.ALGORITHM_AES_256_GCM,
        envelope_version=1,
    )


def _opens_as_v2(body: bytes, key: str) -> bytes:
    return env.open_envelope(
        envelope=body,
        master_key=MASTER,
        expected=env.ExpectedObject(
            object_key=key,
            ciphertext_sha256_hex=hashlib.sha256(body).hexdigest(),
            plaintext_sha256_hex=PLAINTEXT_SHA,
            envelope_version=2,
        ),
    )


# --- the store verb --------------------------------------------------------------------------


def test_reseal_rewrites_a_v1_object_as_v2_bound_to_its_key() -> None:
    client = DictS3(objects={KEY: forge_v1(PLAINTEXT)})
    record = _v1_record(client.objects[KEY])

    resealed = _store(client).reseal(KEY, envelope=record, media_type=MEDIA)

    body = client.objects[KEY]
    assert (resealed.envelope_version, resealed.rewritten) == (2, True)
    assert body[0] == 2
    assert resealed.ciphertext_sha256_hex == hashlib.sha256(body).hexdigest()
    assert _opens_as_v2(body, KEY) == PLAINTEXT
    with pytest.raises(env.EnvelopeError):
        _opens_as_v2(body, OTHER_KEY)


def test_reseal_adopts_a_v2_object_a_previous_run_wrote_without_writing_again() -> None:
    sealed = env.seal(plaintext=PLAINTEXT, master_key=MASTER, object_key=KEY)
    client = DictS3(objects={KEY: sealed.envelope})
    # The row still describes the `v1` object the crashed run replaced.
    record = _v1_record(forge_v1(PLAINTEXT))

    resealed = _store(client).reseal(KEY, envelope=record, media_type=MEDIA)

    assert (resealed.envelope_version, resealed.rewritten) == (2, False)
    assert resealed.ciphertext_sha256_hex == sealed.ciphertext_sha256_hex
    assert client.puts == []


def test_reseal_refuses_a_v1_object_that_is_not_the_rows_content_and_writes_nothing() -> None:
    original = forge_v1(b"other content")
    client = DictS3(objects={KEY: original})

    with pytest.raises(StoragePolicyViolation):
        _store(client).reseal(KEY, envelope=_v1_record(original), media_type=MEDIA)

    assert client.objects[KEY] == original
    assert client.puts == []


def test_reseal_refuses_a_row_that_does_not_record_v1() -> None:
    sealed = env.seal(plaintext=PLAINTEXT, master_key=MASTER, object_key=KEY)
    client = DictS3(objects={KEY: sealed.envelope})
    record = StoredEnvelope(
        ciphertext_sha256_hex=sealed.ciphertext_sha256_hex,
        sha256_hex=PLAINTEXT_SHA,
        encryption_algorithm=env.ALGORITHM_AES_256_GCM,
        envelope_version=2,
    )

    with pytest.raises(StoragePolicyViolation):
        _store(client).reseal(KEY, envelope=record, media_type=MEDIA)
    assert client.puts == []


def test_reseal_refuses_to_adopt_a_v2_object_sealed_for_another_key() -> None:
    moved = env.seal(plaintext=PLAINTEXT, master_key=MASTER, object_key=OTHER_KEY).envelope
    client = DictS3(objects={KEY: moved})

    with pytest.raises(StoragePolicyViolation):
        _store(client).reseal(KEY, envelope=_v1_record(forge_v1(PLAINTEXT)), media_type=MEDIA)
    assert client.objects[KEY] == moved


def test_an_unconfirmed_overwrite_raises_and_deletes_nothing() -> None:
    """`put` deletes an object it could not confirm; an overwrite has no other copy to fall back on."""
    client = DictS3(objects={KEY: forge_v1(PLAINTEXT)}, confirm=False)
    record = _v1_record(client.objects[KEY])

    with pytest.raises(StoragePolicyViolation):
        _store(client).reseal(KEY, envelope=record, media_type=MEDIA)

    assert client.deletes == []
    assert KEY in client.objects


# --- the migration over a real publication ---------------------------------------------------


@dataclass
class World:
    test: Harness
    client: DictS3
    store: S3EncryptedObjectStore
    publisher: ReportArtifactPublisher
    publication: object

    def rows(self) -> list[ReportArtifactRow]:
        with self.test.factory() as database:
            return list(
                database.scalars(select(ReportArtifactRow).order_by(ReportArtifactRow.artifact_kind))
            )

    def versions(self) -> list[int]:
        return [row.envelope_version for row in self.rows()]

    def migration(self) -> ArtifactEnvelopeMigration:
        return ArtifactEnvelopeMigration(factory=self.test.factory, objects=self.store)

    def read(self, kind: str) -> bytes:
        document = self.publisher.read(
            session_id=self.test.session.session_id,
            job_id=self.publication.delivery.record.job_id,
            artifact_kind=kind,
            now=NOW,
        )
        assert document is not None
        return document.content


def _downgrade_to_v1(world: World, row: ReportArtifactRow) -> None:
    """Replace one published object with a `v1` envelope of the same content, row included."""
    plaintext = world.store.get(
        row.object_key,
        envelope=StoredEnvelope(
            ciphertext_sha256_hex=row.ciphertext_sha256_hex,
            sha256_hex=row.sha256_hex,
            encryption_algorithm=row.encryption_algorithm,
            envelope_version=row.envelope_version,
        ),
    )
    legacy = forge_v1(plaintext)
    world.client.objects[row.object_key] = legacy
    with world.test.factory.begin() as database:
        database.execute(
            update(ReportArtifactRow)
            .where(
                ReportArtifactRow.job_id == row.job_id,
                ReportArtifactRow.artifact_kind == row.artifact_kind,
            )
            .values(envelope_version=1, ciphertext_sha256_hex=hashlib.sha256(legacy).hexdigest())
        )


def _world(*, legacy: bool = True, test: Harness | None = None) -> World:
    test = test or harness()
    client = DictS3()
    store = _store(client)
    publisher = ReportArtifactPublisher(
        repository=SqlArtifactRepository(test.factory),
        deliveries=test.store,
        objects=store,
        now=lambda: NOW,
    )
    publication = _publication(test)
    publisher.publish(publication)
    world = World(test, client, store, publisher, publication)
    if legacy:
        for row in world.rows():
            _downgrade_to_v1(world, row)
    # Only what the migration writes is under test, not the publication that set the world up.
    client.puts.clear()
    return world


def _contents(world: World) -> dict[str, bytes]:
    return {row.artifact_kind: world.read(row.artifact_kind) for row in world.rows()}


def test_every_v1_artifact_becomes_v2_and_still_reads_as_its_content() -> None:
    world = _world()
    before = _contents(world)
    assert set(world.versions()) == {1}

    report = world.migration().migrate()

    assert report == EnvelopeMigrationReport(resealed=7, artifacts_remaining=0)
    assert report.verified
    assert world.versions() == [2] * 7
    for row in world.rows():
        body = world.client.objects[row.object_key]
        assert body[0] == 2
        assert row.ciphertext_sha256_hex == hashlib.sha256(body).hexdigest()
    assert _contents(world) == before


def test_a_second_run_changes_nothing_and_writes_nothing() -> None:
    world = _world()
    world.migration().migrate()
    rows = [(row.artifact_kind, row.ciphertext_sha256_hex) for row in world.rows()]
    world.client.puts.clear()

    report = world.migration().migrate()

    assert report == EnvelopeMigrationReport()
    assert report.verified
    assert world.client.puts == []
    assert [(row.artifact_kind, row.ciphertext_sha256_hex) for row in world.rows()] == rows


def test_a_rewrite_whose_row_never_committed_is_adopted_on_the_next_run() -> None:
    world = _world()
    crashed = world.rows()[0]
    # The first run overwrote this object and died before its row committed.
    world.store.reseal(
        crashed.object_key,
        envelope=StoredEnvelope(
            ciphertext_sha256_hex=crashed.ciphertext_sha256_hex,
            sha256_hex=crashed.sha256_hex,
            encryption_algorithm=crashed.encryption_algorithm,
            envelope_version=1,
        ),
        media_type=crashed.media_type,
    )
    written = world.client.objects[crashed.object_key]
    # Until the row catches up, a read of that one artifact fails closed.
    with pytest.raises(ArtifactUnavailable):
        world.read(crashed.artifact_kind)
    world.client.puts.clear()

    report = world.migration().migrate()

    assert report == EnvelopeMigrationReport(resealed=6, adopted=1, artifacts_remaining=0)
    assert world.client.objects[crashed.object_key] == written
    assert crashed.object_key not in world.client.puts
    assert world.read(crashed.artifact_kind)


def test_a_session_whose_deletion_was_requested_is_deferred_and_left_alone() -> None:
    world = _world()
    with world.test.factory.begin() as database:
        database.execute(
            update(BetaSessionRow)
            .where(BetaSessionRow.session_id == world.test.session.session_id)
            .values(deletion_requested_at=NOW)
        )
    objects = dict(world.client.objects)

    report = world.migration().migrate()

    assert report == EnvelopeMigrationReport(deferred=7, artifacts_remaining=7)
    assert not report.verified
    assert world.client.objects == objects
    assert set(world.versions()) == {1}


def test_a_row_whose_key_lies_outside_its_session_is_refused_and_left_alone() -> None:
    world = _world()
    stray = world.rows()[0]
    foreign = stray.object_key.replace(world.test.session.session_id, "ses_elsewhere")
    world.client.objects[foreign] = world.client.objects.pop(stray.object_key)
    with world.test.factory.begin() as database:
        database.execute(
            update(ReportArtifactRow)
            .where(
                ReportArtifactRow.job_id == stray.job_id,
                ReportArtifactRow.artifact_kind == stray.artifact_kind,
            )
            .values(object_key=foreign)
        )
    body = world.client.objects[foreign]

    report = world.migration().migrate()

    assert report == EnvelopeMigrationReport(resealed=6, refused=1, artifacts_remaining=1)
    assert world.client.objects[foreign] == body


def test_one_failing_object_does_not_stop_the_others() -> None:
    world = _world()
    broken = world.rows()[3]
    world.client.failing.add(broken.object_key)

    report = world.migration().migrate()

    assert report == EnvelopeMigrationReport(resealed=6, failed=1, artifacts_remaining=1)
    assert not report.verified
    assert sorted(world.versions()) == [1] + [2] * 6


def test_rows_already_at_v2_are_not_selected() -> None:
    world = _world(legacy=False)

    report = world.migration().migrate()

    assert report == EnvelopeMigrationReport()
    assert world.client.puts == []


def test_v1_uploads_are_counted_and_not_touched() -> None:
    world = _world(legacy=False)
    with world.test.factory.begin() as database:
        database.add(
            UploadRow(
                upload_id="upl_legacy",
                owner_id=world.test.session.owner_id,
                session_id=world.test.session.session_id,
                object_key=(
                    f"owners/{world.test.session.owner_id}/sessions/"
                    f"{world.test.session.session_id}/inputs/upl_legacy"
                ),
                size_bytes=10,
                sha256_hex="d" * 64,
                media_type="text/csv",
                created_at=NOW,
                expires_at=world.test.session.content_expires_at,
                encryption_algorithm=env.ALGORITHM_AES_256_GCM,
                envelope_version=1,
                ciphertext_sha256_hex="e" * 64,
            )
        )

    report = world.migration().migrate()

    # The upload half is its own slice, so it does not decide this command's verdict.
    assert report == EnvelopeMigrationReport(uploads_not_migrated=1)
    assert report.verified
    assert world.client.puts == []


# --- the entry point -------------------------------------------------------------------------


def _run(world: World) -> tuple[int, dict]:
    lines: list[str] = []
    stack = SimpleNamespace(factory=world.test.factory, objects=world.store, clock=lambda: NOW)
    status = runtime_migration.run(stack, out=lines.append)
    assert len(lines) == 1
    return status, json.loads(lines[0])


def test_the_entry_point_prints_counts_and_fails_while_v1_artifacts_remain() -> None:
    world = _world()
    world.client.failing.add(world.rows()[0].object_key)

    status, line = _run(world)

    assert status == 1
    assert line == {
        "adopted": 0,
        "artifacts_remaining": 1,
        "deferred": 0,
        "event": "envelope_migration",
        "failed": 1,
        "occurred_at": NOW.isoformat(),
        "refused": 0,
        "resealed": 6,
        "uploads_not_migrated": 0,
    }


def test_the_entry_point_succeeds_once_no_v1_artifact_remains() -> None:
    world = _world()

    status, line = _run(world)

    assert status == 0
    assert (line["resealed"], line["artifacts_remaining"]) == (7, 0)
    assert _run(world) == (0, line | {"resealed": 0})


def test_the_entry_point_line_names_no_identifier() -> None:
    """`KHEPRI-DEC-015` §7: counts only. No key, session, owner or job reaches the line."""
    world = _world()
    rows = world.rows()

    _status, line = _run(world)

    rendered = json.dumps(line)
    for row in rows:
        for identifier in (row.object_key, row.session_id, row.owner_id, row.job_id):
            assert identifier not in rendered
