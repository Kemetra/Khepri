# Clerk private-beta hard stop

This is the operator procedure required by `KHEPRI-DEC-024` sections 5.1 and 9. Use it before the
first paying customer, before commercial production, or immediately upon expiration, withdrawal,
suspension, or loss of the educational Clerk access.

1. Deploy configuration with `KHEPRI_CLERK_MODE=disabled`.
2. Drain and terminate every web instance built with enabled Clerk configuration. Configuration is
   immutable inside a running `RuntimeStack`; leaving an old instance alive leaves a minting path.
3. Verify `POST /api/v1/commercial/auth/session` is absent and returns `404` on the replacement
   deployment.
4. With the replacement deployment's database environment, run
   `uv run python -m khepri.runtime.clerk_hard_stop` exactly once.
5. Retain the command's content-free JSON output (time and revoked-session count) in the deployment
   log. Re-run the command and require `revoked_sessions` to be `0`; this proves idempotent closure.

The command refuses to run unless Clerk configuration is disabled. It revokes every Khepri session
belonging to an account with a local `clerk` identity link, including dual-capability accounts. It
does not unlink identities, disable or delete accounts, alter organizations, memberships, roles or
isolation, or touch RRA and analytical data. If any step fails, keep Clerk disabled and do not
restore the external-session route.
