# #576: a deletion attempt overtaken by a failed attempt

**Issue:** `#576`. The defect was pinned by `#573` as a strict `xfail(raises=ValueError)`.

**Specification (registry `active`):** `RRA-002`. §Requirements asks for "immediate idempotent
deletion" and evidence that records "retry state". §Verification covers "retry safety". `RRA-002`
has no numbered FRs, so this plan cites sections. `RRA-007` does not own the deletion job.

## Defect

Two `delete_session_content` requests both hold the pending job at attempt 0. The inner request's
object delete fails, and its `fail()` commits attempt 1. The outer request then calls `complete()`
if its deletes succeeded, or `fail()` if they failed. Either way it passes attempt-1 evidence.
`_validate_attempt` refuses that evidence with `ValueError`, and the route maps only
`SessionExpired` and `DeletionRetryRequired`, so the customer gets a 500. The system fails closed:
no duplicate evidence is written and the job stays `retryable`. But a 500 is not the governed answer.

## Fix

1. **`SqlDeletionRepository.complete` / `fail`.** Under the job's row lock, and before any write,
   a job whose `attempt_count` no longer matches the caller's snapshot has been overtaken. It is
   returned unchanged: no evidence, no derived-content delete, no attempt increment. A job already
   `complete` still wins first, so an attempt overtaken by a *successful* attempt still answers
   complete. The check is inlined into the existing `state == "complete"` condition. A shared helper
   would push `persistence.py` past CodeScene's 600-line module threshold, since the file sits at
   exactly 600. Each method gains one `or` and no lines.
2. **`DeletionService`.** Both `complete` calls go through one `_complete` helper, which raises
   `DeletionRetryRequired` when the repository did not complete the job. Without that raise, the
   route would answer 204 and clear the cookie on a job that is still `retryable`. That is a false
   completion, which is worse than the 500. `_retry_or_complete` already raises for a result that
   is not complete.
3. `_validate_attempt` keeps its `ValueError`. The fix never reaches it, and it remains the invariant.

## Tests (RED first)

The `xfail` becomes
`test_a_request_overtaken_by_a_failed_attempt_answers_retry[outer_deletes|outer_fails]`. It drives
the real `DELETE /api/v1/beta/content` route. The inner request runs at the `get_targets` seam
(`WINDOW_AFTER_TARGETS`). The test asserts the following:

- the response is 503, `"Content deletion is pending retry."`
- the response has no `set-cookie`
- the store holds one job, `attempt_count == 1`, only `((1, "upl_alpha", "failed"),)`, and content
  that is not deleted

## Mutation checks

- Remove the repository guard in `complete`: `outer_deletes` fails with `ValueError`.
- Remove the repository guard in `fail`: `outer_fails` fails with `ValueError`.
- Remove the service raise in `_complete`: `outer_deletes` fails with a 204.
