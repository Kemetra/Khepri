# #560 residuals, items 2–7

**Issue:** `#560`, items 2 onward. Item 1 (a real decision card qualified by every bundle caveat,
`RCA-008`) is another PR and is not touched here. Neither is `src/khepri/rra/facts.py`.

**Specifications (registry `active`):** `RRA-002` (intake and deletion lifecycle), `RRA-009`
(§Refusals), `RCA-001` (`FR-025`), `RRA-001` (consent).

## Disposition

| Item | What | Disposition |
|---|---|---|
| 2 | `caveat_prose` fills `{column}`/`{field}` with the metric name | **Deferred, pinned.** Strict `xfail` test |
| 3 | stale docstring, `rca/workspace/decision/evidence.py` | **Already fixed** by `#565` (`0e7d776`) |
| 4 | `revoke_invitation` broad `except Exception` | **Already fixed** by `#565` (`0e7d776`); mutant re-checked |
| 5 | `record_consent` succeeds on a session being deleted | **Deferred:** no active spec requires the refusal |
| 6 | two simultaneous `delete_session_content` calls untested | **Implemented:** SQLite interleaving plus PostgreSQL `concurrency` test |
| 7 | cross-version refusal wording gaps | **Deferred:** needs customer prose no decision gives |

### Item 2: why deferred

`RRA-009` §Refusals part 4 names "which missing field or evidence caused it, named as a column
the customer would recognise". The joined caveat code `<result>:<reason>` carries no refusing
input. `_reason_for` in `facts.py` knows the first unmapped input but drops it. A renderer that
guessed the input would be recomputing (§Preservation). A fix needs three things:

1. `RefusedResult` carries the refusing semantic, in `facts.py`, which another PR owns.
2. The package document is versioned for the new field (a lenient reader when the field is absent).
3. The owner names the part-4 column vocabulary. The journey's `semantic_*` labels are one
   candidate, but they are journey copy.

**Second finding (live, outside `#560`).** Three codes are shared between section and result
refusals: `required_input_unavailable`, `incomplete_transaction_identifiers`, and
`family_version_pairing_unadmitted`. `caveat_prose` routes every section reason to its section
sentence, so a refused *result* with a shared code renders the section text, and that text does not
name the metric. For example, `units_by_channel:required_input_unavailable` reads "This analysis —
not available", and `units_by_channel:incomplete_transaction_identifiers` reads "Basket size — not
available". Either way RRA-009 part 1 fails, and the governed result-context sentences never reach a
customer. This PR records the finding and does not fix it.

The strict `xfail` pins all three column reasons. For `required_input_unavailable` it pins the
combined fix: routing and column together are needed to reach exactly one mention of the metric.

### Item 5: why deferred

`RRA-002` says nothing about consent. `RRA-001` requires only "Record explicit consent version and
timestamp before enabling upload". Neither requires that a consent save refuse on a session being
deleted. Refusing would change the `SessionStore.update_session`/`record_consent` contract. Uploads
are already refused, because `update_session` never clears a recorded deletion (`#547`) and
`require_upload_consent` refuses a deleted session.

### Item 7: why deferred

`#550` wrote the decided text for parts 3 and 4. The remedy sentences for `CAUSE_STORE_SET` and
`CAUSE_GRANULARITY`, the part-1 openings, and a concrete field for `CAUSE_SCOPE` are new customer
prose. No specification or decision gives that prose, so this PR adds none. Candidate text goes to
the owner in the PR body, not in code.

## Item 6: the test

`RRA-002` requires "immediate idempotent deletion". There are two windows a second request can be
caught in, and each is hooked at a seam the service still calls:

- **`after_read`**, after `get_session` (the unlocked read) and before `begin`. Settled by the
  session row's `FOR UPDATE` and `begin`'s existing-job check against `uq_deletion_session`.
- **`after_targets`**, after `begin` and `get_targets` and before any object is touched. Settled
  by `complete` returning a job that is already `complete` under the job's row lock.

The assertions: both requests answer `complete` with one `deletion_id`, and the store holds one job
with `attempt_count == 1` and one attempt-1 `deleted` evidence row. The session's content deletion
is recorded.

- `tests/test_rra002_concurrent_session_deletion.py`: deterministic on SQLite. The whole first
  request runs inside the second's window.
- `tests/test_concurrency_postgres.py`: two threads with a barrier in the window, repeated 10× per
  window, marked `concurrency`.
- `tests/rra002_deletion_race_support.py`: the shared hooks and assertions.

**No RED.** The race is settled correctly at `main`, and both new tests pass there. The mutants
below stand in for a RED step.

| Mutant | Killed by |
|---|---|
| `begin` skips the existing-job check | SQLite (both windows), PostgreSQL |
| `session_scope_for_update_statement` drops `FOR UPDATE` | PostgreSQL `after_read` (10/10) |
| `complete` drops its `state == "complete"` early return | SQLite `after_targets`, PostgreSQL |

**Observed and not fixed.** In `after_targets`, suppose request B's object delete fails and B's
`fail()` commits before A's `complete()`. A's attempt-1 evidence then no longer matches the job's
attempt 2, so A raises `ValueError`, even though the content is gone. The route maps only
`SessionExpired` and `DeletionRetryRequired`, so the caller gets a 500. The outcome fails closed: no
duplicate evidence is written and the job stays retryable. A strict `xfail` (`raises=ValueError`)
pins it. The expected outcome is a later slice's call.

## Gates

Run `khepri-gov validate`, `ruff check .`, the touched tests with PostgreSQL, and the full suite.
