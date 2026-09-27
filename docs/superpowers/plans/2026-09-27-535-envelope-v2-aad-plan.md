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

## Status as of 2026-09-27, revision after two independent REVISE verdicts

Two judges returned REVISE with the same two HIGH findings. This block records the fix round; the
blocks above are left as written.

**Correction to "The identity: the object key" and to the Shape section.** Two claims above were
wrong or incomplete:

1. *Binding the key does not bind the scope at read.* `datasets.py`, `packages.py` and the artifact
   read compared the row's scope columns with `assert_same_scope` and then read `object_key`
   unchecked. Edit only a row's `owner_id`/`session_id` to scope B and the row still names scope
   A's object; `v2` binds that object to *its* key, so the tag verifies and B is served A's content.
   The fix is a reader-side check: `khepri.rra.sessions.object_prefix(scope)` is now the one
   spelling of a scope's namespace (intake, publication and deletion build keys with it), and
   `assert_object_in_scope(caller, key)` refuses a key outside the **caller's** namespace with the
   existing uniform `CrossSessionAccessDenied`. It runs in `ProfilingService`,
   `FactPackageService` and `ReportArtifactPublisher.read`. Deletion needed no check: it already
   deletes by the caller's prefix (`deletion.py`), never by a row's key.
   - The artifact read carries only the caller's `session_id`, not an owner. It holds the key to
     `owners/{row owner}/sessions/{caller session}/`. Session identifiers are unique, so the
     session segment is what a row-only edit cannot satisfy. Widening the read to carry the
     caller's owner would change the route contract, which is outside this slice.
2. *"The version byte is authenticated, so rewriting a `v2` header to `1` fails the tag"* gives the
   wrong reason. That rewrite fails because `v1` opens with no AAD while the object was sealed with
   some. The version inside the AAD separates `v2` from later formats. It is now pinned by a forge
   whose AAD names version `3` under a `v2` header, and the module docstring says so.

**Version rules tightened.** Publication now requires `created ⇒ WRITE_ENVELOPE_VERSION` and
`not created ⇒ READABLE_ENVELOPE_VERSIONS` (`_provable_versions`). `artifact_persistence` sees only
the recorded artifact and not whether the store created it, so it keeps the readable check, and a
comment says the publisher enforces the created rule. Intake's refusal of a non-write-version fresh
write was untested: a `put` returning `1` or `3` is now refused, the object removed and no row kept.

**RED evidence.** The RED commit's eleven xfails failed on the signature change (`seal` and
`open_envelope` did not yet take a key), not on the behaviour each names. They show the tests could
not pass against the old code, nothing more. The behavioural evidence is the GREEN-phase mutation
check.

**Tests added.** `tests/test_i535_read_scope.py` makes the row-only scope edit against the real
routes, for profiling and for packaging, and asserts the uniform 401. It also covers the helper's
boundaries, including `ses_alpha0` against `ses_alpha`. `tests/test_i535_publication_versions.py`
covers intake with `1` and `3`, publication refusing a created `v1`, proving an existing `v1` and
recording it as `v1`, and an artifact row pointing outside its session. The moved-object test in
`test_i535_envelope_aad.py` is now labelled as the narrower attack.

**Mutation check: 22 mutants, all killed, each restored byte-for-byte.** These are the 15 above,
with "publication requires write version" split into two directional mutants, plus seven more:

- intake admitting `v1` on a fresh write (`in (1, 2)`);
- the scope check removed from each of the three readers;
- the helper disabled;
- the prefix losing its trailing slash.

### Owner items (raised here, not decided in code)

(a) **New rows may attach to a pre-existing `v1` object and are recorded as `v1`.** This happens
when `put_or_verify` loses the `IfNoneMatch` race or a publication is retried onto an existing
attempt key. It proves the existing object by decryption and records the version that object
carries. So a `v1` row can be written after this slice ships, and it is not only one written
before. The alternative is to refuse or rewrite the existing object as `v2`, which is the
migration slice's territory. Accept, or require the race-loser path to rewrite?

(b) **`READABLE_ENVELOPE_VERSIONS = {1, 2}` has no end condition.** There are two options: retire
`v1` once every `v1` row has expired, or leave it to the migration slice. What I found on expiry:

- A sweep exists in the wheel. `khepri-retention-sweep` (`pyproject.toml:54`,
  `khepri.runtime.retention_sweep`) deletes sessions past `content_expires_at` and purges
  workspace raw uploads seven days after seal.
- Nothing schedules it. The module says so ("Nothing here is a scheduler"), and nothing in the
  repository invokes it on a cadence.
- A session bound to a workspace version moves to `KHEPRI-DEC-033`'s organization lifetime.
  `workspace_retention.py:92-98` sets its upload, delivery and report-artifact rows to
  `WORKSPACE_CONTENT_END`, so its report artifacts have no seven-day end.

So "all `v1` rows have expired" is not a condition the running system guarantees today. Which end
condition should govern?
