# #596: owner-scoped reads of a session's upload, profile and package

S1 hardening (roadmap `S1-05`), routed here from `#432` via `#152`. `KHEPRI-DEC-035` §3 names these
lookups as open, and §5 leaves them to this work. The owner decision on `#152` (2026-09-24) needs
no further planning round.

## Shape: additive, by owner decision (2026-09-26)

`RCA-001` `FR-037` keeps RRA's existing tests unmodified. Two of them (`test_rra002_service`,
`test_rra004_packages`) implement the repository Protocols with only the session-only verb, so
narrowing the verbs in place would force edits to them. Instead:

1. Each Protocol gains a scoped verb whose default body delegates to the session-only verb and
   returns `None` unless the result's scope equals the requested one:
   - `UploadRepository.get_upload_for_scope(scope)`
   - `ProfileRepository.get_profile_for_scope(scope)`
   - `FactPackageRepository.get_package_for_scope(scope, versions)`

   A double that subclasses the Protocol inherits a fail-closed answer.
2. Each SQL store overrides the scoped verb with `owner_id` **and** `session_id` in the statement.
3. Every production caller moves to the scoped verb: `IntakeService.begin`, `ProfilingService`
   (both reads), `FactPackageService` (four reads), `SqlUploadRepository.add_upload`'s conflict
   path, and `WorkspaceRecording._admission`.
4. The session-only verbs stay, for the unmodified tests. A guard pins the Protocol defaults as
   the only production callers.

**`get_session(session_id)` is not narrowed.** The beta session id is the bearer credential, so no
owner exists before it resolves. Callers that already hold an owner use `get_session_for_owner`.

## Tests: `tests/test_i596_owner_scoped_store_lookups.py`

- Store: each scoped verb returns the row under its own owner and `None` under another owner with
  the same `session_id`. For packages the fixture is a real published package, not a raw insert.
- The Protocol default refuses a foreign owner for a session-only double.
- The guard sweeps `src/khepri` (anchored to `__file__`, with a non-empty assertion) and requires
  the session-only calls to be exactly the three Protocol defaults, with a positive control.

Mutants to kill: drop the owner predicate from each statement; point one caller back at a
session-only verb; make a Protocol default skip its scope check.
