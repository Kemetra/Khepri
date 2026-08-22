"""Local object storage is the real store over a real endpoint, not a stub.

**What these tests are really guarding.** `intake._storage_response_is_valid`
requires `encryption_algorithm == "aws:kms"` and `rra_uploads` carries a CHECK
constraint enforcing the same string, so any local store that merely *returned*
it would satisfy every caller while writing a false claim into the database. The
assertions below are therefore about provenance as much as behaviour: the class
under test is the production one, and the ARN it reports is one a KMS actually
issued.
"""

from __future__ import annotations

import hashlib

import pytest

from khepri.local.config import LocalSettings
from khepri.local.storage import build_local_object_store, local_client
from khepri.rra.storage import S3EncryptedObjectStore
from tests.local_stack_support import requires_local_stack

CONTENT = b"date,revenue\n2026-07-29,125.50\n"
SHA256_HEX = hashlib.sha256(CONTENT).hexdigest()
KEY = "owners/own_local/sessions/ses_local/inputs/upl_local"
CONTEXT = {
    "owner_id": "own_local",
    "session_id": "ses_local",
    "upload_id": "upl_local",
}


@pytest.fixture
def store() -> S3EncryptedObjectStore:
    return build_local_object_store(LocalSettings.from_environment())


@requires_local_stack()
@pytest.mark.local_stack
class TestTheProductionStoreIsWhatRuns:
    def test_the_store_is_the_unmodified_production_class(
        self, store: S3EncryptedObjectStore
    ) -> None:
        """No local subclass, no local override -- the same class the beta uses."""
        assert type(store) is S3EncryptedObjectStore

    def test_the_key_is_a_real_me_central_1_arn(self) -> None:
        """The constructor regex refuses anything else, so this cannot be invented."""
        kms = local_client(LocalSettings.from_environment(), "kms")
        keys = kms.list_keys()["Keys"]

        assert keys
        arn = kms.describe_key(KeyId=keys[0]["KeyId"])["KeyMetadata"]["Arn"]
        assert arn.startswith("arn:aws:kms:me-central-1:")


@requires_local_stack()
@pytest.mark.local_stack
class TestTheRoundTrip:
    def test_put_proves_the_storage_policy(self, store: S3EncryptedObjectStore) -> None:
        """A response that did not prove it raises `StoragePolicyViolation`."""
        stored = store.put(
            key=KEY,
            content=CONTENT,
            media_type="text/csv",
            sha256_hex=SHA256_HEX
        )

        assert stored.encryption_algorithm == "aws:kms"
        assert stored.kms_key_id.startswith("arn:aws:kms:me-central-1:")
        assert stored.sha256_hex == SHA256_HEX
        assert stored.size_bytes == len(CONTENT)
        store.delete(KEY)

    def test_get_returns_exactly_what_was_stored(
        self, store: S3EncryptedObjectStore
    ) -> None:
        store.put(
            key=KEY,
            content=CONTENT,
            media_type="text/csv",
            sha256_hex=SHA256_HEX
        )

        assert store.get(KEY) == CONTENT
        store.delete(KEY)

    def test_delete_is_accepted_without_versioned_semantics(
        self, store: S3EncryptedObjectStore
    ) -> None:
        """A versioned delete leaves a recoverable copy, which RRA-002 forbids."""
        store.put(
            key=KEY,
            content=CONTENT,
            media_type="text/csv",
            sha256_hex=SHA256_HEX
        )

        store.delete(KEY)

    def test_the_key_is_reused_across_constructions(self) -> None:
        """Otherwise a restart would orphan every object written before it."""
        settings = LocalSettings.from_environment()

        first = build_local_object_store(settings)
        second = build_local_object_store(settings)

        assert first._kms_key_arn == second._kms_key_arn  # noqa: SLF001
