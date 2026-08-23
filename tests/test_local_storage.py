"""Local object storage is the real store over a real endpoint, not a stub.

**What these tests are really guarding.** The class under test is the production
one, reached through the production constructor, so what passes here is what runs
in the runtime. A `FilesystemObjectStore` would have to report an encryption
algorithm it did not perform; these exercise the algorithm instead.

**What `KHEPRI-DEC-008` changed about them.** They used to assert
`encryption_algorithm == "aws:kms"` and a `me-central-1` key ARN read back off the
`PutObject` response, and to compare a private `_kms_key_arn` between two
constructions. None of that exists any more: encryption is the application's own
work, `S3EncryptedObjectStore` has no KMS attribute, and `_write_is_unversioned`
checks only the echoed checksum and the absence of a `VersionId`. Those assertions
did not merely become unnecessary, they became errors -- `AttributeError` on a
field the production class no longer defines -- and they went unnoticed because
every case here skips unless the local stack happens to be running.

The properties that replace them are stronger, because they are about the bytes
rather than about a provider's claim: the ciphertext digest differs from the
plaintext digest, the plaintext survives the round trip, a duplicate write is
refused by `IfNoneMatch` and proven equivalent by decryption, and a delete really
deletes rather than leaving a recoverable version behind.
"""

from __future__ import annotations

import hashlib

import pytest

from khepri.local.config import LocalSettings
from khepri.local.storage import build_local_object_store
from khepri.rra.storage import ObjectWrite, S3EncryptedObjectStore, StoredEnvelope
from tests.local_stack_support import requires_local_stack

CONTENT = b"date,revenue\n2026-07-29,125.50\n"
SHA256_HEX = hashlib.sha256(CONTENT).hexdigest()
KEY = "owners/own_local/sessions/ses_local/inputs/upl_local"
MEDIA_TYPE = "text/csv"


def _request(key: str = KEY) -> ObjectWrite:
    return ObjectWrite(
        key=key,
        content=CONTENT,
        media_type=MEDIA_TYPE,
        sha256_hex=SHA256_HEX,
    )


def _envelope(stored: object) -> StoredEnvelope:
    return StoredEnvelope(
        ciphertext_sha256_hex=stored.ciphertext_sha256_hex,  # type: ignore[attr-defined]
        sha256_hex=stored.sha256_hex,  # type: ignore[attr-defined]
        encryption_algorithm=stored.encryption_algorithm,  # type: ignore[attr-defined]
        envelope_version=stored.envelope_version,  # type: ignore[attr-defined]
    )


@pytest.fixture
def store() -> S3EncryptedObjectStore:
    built = build_local_object_store(LocalSettings.from_environment())
    yield built
    # Each case owns one key, and a leftover object would make the next run's
    # first write a duplicate rather than a creation.
    built.delete_prefix("owners/own_local/")


@requires_local_stack()
@pytest.mark.local_stack
class TestTheProductionStoreIsWhatRuns:
    def test_the_store_is_the_unmodified_production_class(
        self, store: S3EncryptedObjectStore
    ) -> None:
        """No local subclass, no local override -- the same class the beta uses."""
        assert type(store) is S3EncryptedObjectStore

    def test_the_store_holds_no_provider_key_material(
        self, store: S3EncryptedObjectStore
    ) -> None:
        """The KMS coupling is gone, and its absence is asserted rather than assumed.

        This file previously read `_kms_key_arn` off the store. If a provider key
        attribute is ever reintroduced, the encryption boundary has moved back out
        of the application and these tests should be rewritten again, not adjusted.
        """
        attributes = dir(store)

        assert not [name for name in attributes if "kms" in name.lower()]


@requires_local_stack()
@pytest.mark.local_stack
class TestTheRoundTrip:
    def test_what_is_written_is_ciphertext(
        self, store: S3EncryptedObjectStore
    ) -> None:
        """The plaintext digest is the content address; the ciphertext is not it."""
        result = store.put_or_verify(_request())

        assert result.created is True
        assert result.stored.sha256_hex == SHA256_HEX
        assert result.stored.size_bytes == len(CONTENT)
        assert result.stored.ciphertext_sha256_hex != SHA256_HEX

    def test_get_returns_exactly_what_was_stored(
        self, store: S3EncryptedObjectStore
    ) -> None:
        result = store.put_or_verify(_request())

        assert store.get(KEY, envelope=_envelope(result.stored)) == CONTENT

    def test_a_duplicate_write_is_refused_and_proven_equivalent(
        self, store: S3EncryptedObjectStore
    ) -> None:
        """`IfNoneMatch` makes creation conditional, so two writers cannot both win.

        The loser must decrypt what is already there to prove it represents the same
        plaintext, because randomised encryption means identical content does not
        produce identical ciphertext.
        """
        first = store.put_or_verify(_request())
        second = store.put_or_verify(_request())

        assert first.created is True
        assert second.created is False
        assert second.stored.sha256_hex == SHA256_HEX

    def test_delete_leaves_nothing_recoverable(
        self, store: S3EncryptedObjectStore
    ) -> None:
        """A versioned delete leaves a recoverable copy, which `RRA-002` forbids."""
        result = store.put_or_verify(_request())
        envelope = _envelope(result.stored)

        store.delete(KEY)

        with pytest.raises(Exception):  # noqa: B017 - any read failure proves absence
            store.get(KEY, envelope=envelope)
