# Database migrations

**Status: operator reference, not a governed artifact.** Authorizes nothing.

Source of truth: `alembic.ini`, `migrations/env.py`, and `migrations/versions/`.

## Apply

```sh
uv run alembic upgrade head
```

Against the **local** stack this needs no configuration: `alembic.ini` pins
`postgresql+psycopg://khepri:khepri@127.0.0.1:15432/khepri`, which is the local compose
stack's published port.

Against anything else, set `KHEPRI_DATABASE_URL` — `migrations/env.py` prefers it over
`alembic.ini`. That is exactly what the staging `migrate` service does, adding
`?sslmode=require`, because the pinned URL in `alembic.ini` points at the local stack.

```sh
KHEPRI_DATABASE_URL='postgresql+psycopg://user:pw@host:5432/db?sslmode=require' \
  uv run alembic upgrade head
```

`migrations/env.py` escapes `%` as `%%` when it hands the value to Alembic, so a
percent-encoded password in that URL survives ConfigParser interpolation. Quote the value
in the shell regardless.

In the staging stack this runs as a one-shot `migrate` service with `restart: "no"`; `web`
and `worker` wait on it completing successfully, so they never start against an unmigrated
schema.

## Inspect

```sh
uv run alembic current
uv run alembic heads
uv run alembic history
```

`heads` returning more than one line means the chain has forked — see below. There should
always be exactly one; `alembic heads` reads the script directory offline and needs no
database, so it is safe to run anywhere.

## Revision naming

Files are `YYYYMMDD_NNNN_slug.py` and the `revision` identifier is the `YYYYMMDD_NNNN`
prefix, not a hash. The chain is linear:

```
20260821_0019  ->  20260822_0020   (head)
```

## Parallel slices: the second to merge re-points `down_revision`

This is a standing rule in `AGENTS.md`, and it is the failure mode most likely to bite.

Two slices developed in parallel each write a migration whose `down_revision` is the head
they branched from. Both merge cleanly — git sees two new files, no textual conflict — and
Alembic then has **two heads**, so `upgrade head` fails or applies only one branch.

**The second slice to merge re-points its own `down_revision`** at the first one's
revision, restoring a single chain. Do not merge the heads with a merge revision, and do
not renumber the first slice's migration.

Related rule from the same file: if squash-merging detaches a stacked branch, replay it
with `git rebase --onto origin/main <old-base>` rather than merging.

## Downgrade

`alembic downgrade` exists, but treat it as a development-only tool here. No approved
RTO/RPO targets or recovery evidence exist yet — they are open `KHEPRI-DEC-027` §3
stop-gates — so there is no rollback procedure for a provisioned environment to document,
and none is implied by this file.
