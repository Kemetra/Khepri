# #379 and #434 §4: runtime corrections plan

**Issues.** `#379` (the Notice's predecessor) and `#434` §4 (database TLS). One PR. Commit 1 holds
this plan and the RED tests. Later commits hold the implementation. Each correction implements an
owner decision recorded on its issue. The `RCA-005` `FR-116` wording amendment is a proposal and
governs only once the owner merges it (Constitution II). Nothing here edits the validator.

## 1. `#379`: the Notice compares only runs over the same dataset version

**Decision (owner, 2026-09-24, on `#379`).** "Any dataset version in the same organization" is not
automatically related. Until a lineage relationship is governed, only the same dataset version
counts. Remove the broad fallback so the Notice fails closed. Amend the governing wording so that
cross-version behaviour is explicitly deferred to future lineage work (`T1-06` or a lineage
program).

**Change.** `previous_completed` (`src/khepri/runtime/shell_change_notice.py`) returns the most
recent completed run that started earlier *over the same `version_id`*, or `None`. The
`same or earlier` fallback is deleted. `FR-116` keeps its obligation and names the same dataset
version. One added sentence says a cross-version relationship is not governed, and that `T1-06`
or a lineage program may reopen it. No registry ID is invented for that work. The `RCA-005`
registry row carries no digest, so it does not change.

**Consequences, stated rather than discovered.**

- **The mapping row becomes unreachable.** A `DatasetVersion` carries exactly one
  `mapping_version`, so two runs over one version cannot differ in `rra003.mapping.*`. The
  `notice_mapping` entry in `_GOVERNED` stays, because it is what lineage work reopens. The
  positive-Notice test no longer expects a mapping row.
- **The Notice will rarely fire in the ordinary workflow.** `#379` measured this: uploads are
  deduplicated by content digest, so a new period's data mints a new `version_id`. The Notice
  therefore fires only when the same file is re-run under a moved package, formula or family.
  The owner accepted this ("correctness takes priority over making the currently undefined branch
  reachable").

**Tests (`tests/test_w108_methodology_change_notice.py`, driven through the detail route).**

- The shared builders `_two_runs` and `_same_methodology` put both runs on one version. Every
  positive case already pairs a run with its same-version predecessor, so they stay green.
- RED: `test_an_earlier_run_over_another_dataset_version_raises_no_notice`. The scope holds only an
  earlier completed run on another version, differing in mapping, package and formula. The detail
  page shows no Notice and no link to that run. On `main` the fallback pairs them.
- `test_the_same_version_is_preferred_over_a_more_recent_run_on_other_data` is kept, with its
  docstring corrected. It still kills a "most recent completed, any version" mutant.
- Mutants: restore `same or earlier`; drop the `version_id` filter; drop the `RUN_COMPLETED`
  check.

## 2. `#434` §4: `verify-full` off loopback

**Decision (owner, 2026-09-26, on `#434`).** Use `sslmode=verify-full` whenever the database host
is not loopback. `require` stays only for local loopback / compose. Fail closed on a hosted target
that provides no CA. `KHEPRI-DEC-028` requires "TLS required" and does not name a mode, so this
decision edits no governance artifact.

**Loopback** is `localhost` (case-insensitive) or any address `ipaddress` reports as loopback:
`127.0.0.0/8` and `::1`. Everything else is `verify-full`, including a name that merely starts
with `127.` or `localhost`.

**Compose service names are treated as non-loopback.** The gate sees only a hostname. It cannot
tell a compose network's `postgres` or `db` from a hosted private network with the same name, so
an allowlist of service names would be a guess, and one that fails open. The staging stack
(`docker-compose.staging.yml`, whose secret names `"host":"postgres"`) is therefore moved onto
`verify-full` instead. This also fits that file's own purpose, which is to exercise the TLS paths
a provisioned environment uses:

- `ops/staging/generate-certs.sh` issues the PostgreSQL leaf from the existing local CA with
  `subjectAltName=DNS:postgres`, the way MinIO's is issued. Today it is self-signed with a CN only.
  The leaf moves to new file names (`postgres/server.crt`, `postgres/server.key`), so an existing
  checkout's self-signed pair fails the completeness check and is reissued rather than reported as
  `[OK]`. `postgres-tls.Dockerfile` copies from the new paths.
- `web` and `worker` already mount the CA at `/opt/khepri/tls/ca.crt`. They gain
  `PGSSLROOTCERT` pointing at it. `migrate` gains the same mount, and its URL moves to
  `sslmode=verify-full&sslrootcert=/opt/khepri/tls/ca.crt`.
- The owner is asked in the PR body to confirm this reading of "loopback / compose". The
  alternative, which keeps the compose stack on `require`, needs a service-name allowlist.

**The CA arrives through `PGSSLROOTCERT`.** libpq reads it natively, as botocore reads
`AWS_CA_BUNDLE`, which is the precedent `docker-compose.staging.yml` already set. No `KHEPRI_`
variable exists for it, and inventing one would make two names for one file. `config.py` reads it
with the existing `_optional` helper. Off loopback, an absent value raises
`RuntimeConfigurationError` naming the variable, and a present-but-empty value is refused by
`_required`. The value is written into the URL query as `sslrootcert`, so the URL stays the one
asserted source. The runtime never falls back to `require`.

**Tests (`tests/test_runtime_config.py`, `tests/test_local_config.py`,
`tests/test_runtime_wiring.py`).**

- Loopback gives `{"sslmode": "require"}`, with no CA needed: `localhost`, `LOCALHOST`,
  `127.0.0.1`, `127.8.9.10`, `::1`.
- Non-loopback gives `verify-full` plus `sslrootcert`: `khepri.cluster.internal`, `postgres`,
  `127.0.0.1.evil.example`, `localhost.example`, `0.0.0.0`, `10.0.0.5`, `::2`.
- Non-loopback without a CA fails closed and names `PGSSLROOTCERT`.
- Staging: the migrate URL and the web and worker environment name one CA path, that path is
  mounted in all three, and the PostgreSQL leaf is issued by the CA with `DNS:postgres`.
- Fixtures gain `PGSSLROOTCERT`. That passes on `main`, so it sits in the RED commit.
- Mutants: always `require`; always `verify-full`; fall back to `require` when the CA is absent;
  omit `sslrootcert`; drop IPv6 handling (`ip_address`); `startswith("127.")`.

**Left alone, and named in the PR.**

- `migrations/env.py` reads `KHEPRI_DATABASE_URL` raw and gates nothing. The owner's §4 wording
  carves out no connection path, so this is **raised as an owner question** in the PR rather than
  settled here: gate it in this PR or in a follow-up.
- `src/khepri/infra/compute.py` is the frozen AWS reference. Its task definition supplies no CA, so
  it would now fail closed at boot. It is not the deployment path.
- `docs/platform/proposed-governance/` still describes `sslmode=require`. Those files are proposals.

**CodeScene.** `_database_url` gains the environment as an argument and one call to a small
`_tls_query(host, environment)` helper, so no existing function grows beyond a line.
