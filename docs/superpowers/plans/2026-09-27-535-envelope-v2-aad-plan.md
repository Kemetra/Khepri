# #535: envelope format v2 binds its version and object key as AAD

Closes the implementation half of #535. The migration of stored `v1` objects is **not** in this
slice (owner decision, 2026-09-26: "any migration of stored `v1` data is named in its own slice,
never implied"), so the issue stays open for it.

## Authority

- `RRA-002` (active): stored input and derived content are encrypted at rest in isolated object
  namespaces. This slice hardens that requirement. It adds no data, field, column or use.
- `KHEPRI-DEC-028` fixes the construction: a per-object AES-256-GCM data key wrapped by a master
  key, with the ciphertext digest verified on read-back. AAD is an input of that same primitive, so
  no second algorithm, library or key is introduced.
- Owner decisions on #535, 2026-09-24 and 2026-09-26: a versioned `v2` whose AAD authenticates the
  format version and the object/scope identity; `v1` stays readable; new writes use `v2`.

**No boundary widens and no migration is needed.** `envelope_version` already exists on
`rra_uploads` and `rra_report_artifacts` under `CHECK (envelope_version > 0)` (`persistence.py:119`,
`artifact_persistence.py:89`), which admits `2`. The identity bound is the object key, which every
caller already holds; nothing new is stored.

## The identity: the object key

Every object key is built under its scope:
`owners/{owner_id}/sessions/{session_id}/inputs/{upload_id}` (`intake.py:227`) and
`owners/{owner_id}/sessions/{session_id}/reports/{bundle}/attempts/{attempt}/{kind}`
(`artifact_publication.py:263`). Nothing copies an object between keys (no `copy_object` in `src`).
So the key names both the object and its scope, and one key names one object: binding it cannot
break a second writer, because a second writer of the same key is `put_or_verify`'s race loser
proving the *same* object.

The key is supplied by the caller at open time, from the row it read (`S3EncryptedObjectStore.get`
is called with the row's `object_key`). It is never read from the envelope, which would let the
bytes vouch for themselves.

## Shape (`khepri.rra.envelope`)

- `WRITE_ENVELOPE_VERSION = 2`; `READABLE_ENVELOPE_VERSIONS = frozenset({1, 2})`. `ENVELOPE_VERSION`
  is removed rather than aliased, so every pin has to choose which of the two it means.
- `seal(*, plaintext, master_key, object_key)` and `open_envelope(..., object_key, ...)`: the key is
  a required argument, so no caller can seal an unbound object.
- `v2` AAD, on **both** GCM calls, domain-separated per call:
  `b"khepri.envelope\x00" + purpose + b"\x00" + version byte + object_key (UTF-8)`, with purpose
  `wrap` or `content`. The version byte is authenticated, so rewriting a `v2` header to `1` makes
  the reader choose the AAD-free path and fail the tag.
- `v1` opens with `None` AAD, exactly as before. `envelope_version_of(envelope)` reports the version
  of stored bytes.

## Version pins moved

| Pin | Before | After | Why |
|---|---|---|---|
| `envelope.assert_supported` | `== 1` | `in READABLE` | rows written as `v1` stay readable |
| `envelope._parse` | `== 1` | `in READABLE` | same |
| `storage._read_and_verify_existing` | reports `1` | reports the body's version | an existing `v1` object is what it is |
| `storage.get` | — | body version must equal the row's | row and object must describe each other |
| `artifact_publication._require_proven` | `== 1` | `in READABLE` | `put_or_verify` may prove an existing `v1` object |
| `artifact_persistence._validate_storage_metadata` | `== 1` | `in READABLE` | same row, recorded |
| `intake._storage_response_is_valid` | `== 1` | `== WRITE` | `put` only ever writes new objects |

The existing publication suite (`MemoryObjects` reports `envelope_version=1`) is the regression for
the two `in READABLE` pins: it fails if either tightens to `WRITE`.

## Tests: `tests/test_i535_envelope_aad.py`

- A golden `v1` envelope, committed as bytes sealed by the pre-change code with no AAD, still opens.
- New seals are `v2`, header byte included.
- A `v2` envelope opened under another object key refuses, and so does one moved to another key
  through the storage adapter with both digests intact: the splice the digests alone do not stop.
- A `v2` envelope whose version byte is rewritten to `1` refuses.
- An envelope forged in the test with the documented AAD opens; one missing the wrap AAD, and one
  missing the content AAD, each refuse. This pins the stored format independently of the module.
- `put_or_verify` over an existing `v1` object proves it and reports `v1`; `get` refuses a row whose
  version differs from the body's.
- An empty object key refuses to seal.

Mutation check after GREEN: drop the AAD from the wrap call, then from the content call, then make
`_aad` return `None` for `v2`; each must turn a test red. Restored by diff.

## Status as of 2026-09-27, `main` @ `4276814`

RED: 11 of the tests above are committed under `xfail(strict=True)`. Three carry no marker because
they hold before and after: a `v1` object reads through the adapter, `put_or_verify` proves an
existing `v1` object as `v1`, and a row naming another version than its object carries is refused
(today by `assert_supported`, after this slice by the explicit comparison). Nothing is implemented.

## Status as of 2026-09-27, branch `fix/535-envelope-v2-aad` @ implementation commit

GREEN. Built as planned, with one change of shape: `open_envelope` takes an `ExpectedObject`
(`object_key`, both digests, `envelope_version`) rather than a fifth keyword. A fifth argument was a
new CodeScene finding on `envelope.py` (10.00 → 9.68), and the bundle also moved the row-versus-object
version comparison into the envelope module, so `storage.get` gained no branch. `envelope_version`
is `None` only on `put_or_verify`'s race-loser path, where no record exists yet; the caller writes
the `None` out.

The fake object stores in `test_rra002_service.py` now report `WRITE_ENVELOPE_VERSION` from `put`,
because a real `put` can no longer return `v1`. Persisted-row fixtures elsewhere keep
`envelope_version=1`: a `v1` row is still a legal row.

Mutation check (15 mutants, each restored byte-for-byte): dropping the AAD from each of the four
GCM calls, `_aad` returning `None` for `v2`, the version or the purpose left out of the AAD, an
empty key admitted, the recorded-version comparison disabled, `v1` made unreadable, writes left at
`v1`, `get` binding a constant key, the race loser reporting the write version, and publication or
persistence tightened to the write version. All 15 killed.

Still open under #535: rewriting stored `v1` objects as `v2`, its own slice by the owner's decision.
