# #434 private-beta hardening: plan

**Issue.** `#434`, re-verified at `3a50710`. One PR. Commit 1 holds this plan and the RED tests.
Later commits hold the implementation. Nothing here edits a specification, a decision, the
validator, or a governance file.

## Disposition per item

| § | Item | Disposition | Authority |
|---|---|---|---|
| 1 | XLSX actual-inflate cap | **Fix** | `RRA-002` §Requirements ("validate archive expansion ... to prevent decompression and resource-exhaustion") |
| 2 | Same-origin check fails open when both browser signals are absent | **Fix** | Approved journey design, `docs/superpowers/specs/2026-08-13-client-journey-ui-design.md` §Browser security |
| 3 | No request-rate limit | **Deferred: needs owner/spec** | None found |
| 4 | Database TLS is `sslmode=require` | **Deferred: needs owner decision** | `KHEPRI-DEC-028` requires only "TLS required" |
| 5 | Worker workbook directory | **Already fixed** by `#463` (`own_private_directory`) | none needed |
| 6 | Purge race | **Code already fixed by `#565`** (`0e7d776`). This PR adds the PostgreSQL proof. | `KHEPRI-DEC-015` §2b |
| 7 | Redemption skips the scrypt on refused lookups | **Fix** | `RCA-001` FR-017, `RRA-001` §Requirements ("without revealing which check failed") |

## §1: refuse a member whose recorded size is false

Today intake stream-reads only the parts it parses. It checks every other member against its
*declared* `file_size` alone. `profiling.materialize` later hands the whole archive to calamine,
and that includes `xl/sharedStrings.xml`, the styles, and any other member. Python's
`ZipExtFile` stops at the declared size, but it only checks the CRC. A CRC forged to match the
truncated prefix therefore passes.

The fix inflates every member's raw stream once and counts the output itself, without trusting
`ZipInfo.file_size`. Each member's inflate stops one step past its declared size. A member is
refused when its inflated length differs from its declared size, or when its deflate stream does
not end. Every member must match its declared size, so the declared sum, which is still checked
against `max_expanded_bytes`, bounds the actual total. The inflater replaces the
declared-sum clause in the existing conditional, with the declared-sum fast path kept inside it,
so `_validate_xlsx` does not grow.

The RED tests add an `xl/sharedStrings.xml` member whose central directory and local header state
a small size. One variant states only the size. The other also forges the CRC of the prefix. Both
go through `UploadAccumulator.finish`, and both are accepted on `main`.

## §2: a cookie-bearing mutation must carry a browser signal

The design says that "mutating browser requests must carry an allowed `Origin` and same-origin
Fetch Metadata". The rule refuses a mutation that carries a `Cookie` header when both
`Sec-Fetch-Site` and `Origin` are absent. The cookie is the only ambient credential a forged
request can ride on. Cookieless callers, which are bearer or non-browser clients, stay admitted.
Safe methods are untouched. A browser that sends only one of the two signals is still admitted,
which covers older Fetch Metadata support.

No CSRF token is added. The documented stance in `shell_pins.py` and `session_end_api.py` stands.
Test clients that post with a cookie send `Origin: https://testserver`, which is what a browser
sends.

**Residual.** A cookieless `redeem` from a client that sends neither signal is still admitted
(login CSRF).

## §6: prove the row lock under PostgreSQL

This is a `concurrency`-marked test in `test_concurrent_persistence_postgres.py`. The purge
checks eligibility and then waits. A concurrent `enable_account` runs in that window. Under the
lock, the enable blocks, and after the purge commits it is refused by `_apply_account`'s
`email IS NOT NULL` predicate. Without the lock, the enable commits and the purge then tombstones
an enabled row. The invariant is checked `ATTEMPTS` times. The test is a proof rather than a RED
test, so its mutation check replaces `account_for_update` with `database.get`.

## §7: always pay one hash

RRA `InvitationService.redeem` and RCA `InvitationService.redeem` each pay exactly one scrypt on
every well-formed token. That covers an unknown identifier, a destroyed verifier, a redeemed
invitation, and an expired one, using a fixed dummy salt at the invitation work factor. A
malformed token is given a well-formed identifier that is never issued and takes the ordinary
lookup and hash, as the R4-01 design note §5 requires. The RED
tests count calls to the hash seam. RRA's test drives `POST /api/v1/beta/sessions/redeem`. RCA
has no HTTP redemption route, so its test drives the service verb.

## Deferred

- **§3.** No active specification or decision authorizes a request-rate limit. `KHEPRI-DEC-015`
  and the `RRA-010` exclusions constrain how one could be built, because it could not use
  behavioural telemetry. A limit on redeem and on comparison rendering needs an owner-approved
  artifact that names the bound and the refusal.
- **§4.** A loopback/non-loopback split breaks the staging compose stack. There the database host
  is the service name `postgres`, the certificate is self-signed, and no CA is mounted. The
  comments in `docker-compose.staging.yml`, `ops/staging/generate-certs.sh`, and
  `ops/staging/postgres-tls.Dockerfile` all state `require`. The issue itself makes the split an
  owner record.
