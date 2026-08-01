# RRA Production Runtime Launch Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give the approved RRA image real, distinct web and bounded-worker commands backed by fail-closed AWS runtime configuration, without creating ECS services, an ALB, a deployment, or beta capacity.

**Architecture:** Promote the deterministic narrative and session-scoped report adapters from the excluded local package into the production wheel without changing their behavior. Add a small queue-publication decorator for the web boundary, a one-message SQS worker driver for the worker boundary, and one composition root that builds approved SQLAlchemy, S3, rendering, and report services from validated environment values. CDK task definitions supply exact commands and resource coordinates; SQS redrive remains responsible for DLQ movement.

**Tech Stack:** Python 3.13, FastAPI/Uvicorn, SQLAlchemy/Psycopg, boto3 S3/SQS, Playwright Chromium, AWS CDK v2, pytest, Ruff.

**Governance boundary:** This implements the two process roles, opaque queue messages, bounded retries, deterministic no-provider narrative, and approved AWS resource choices in RRA-005 through RRA-007 and KHEPRI-DEC-005/007. It does not add ECS services, load balancing, desired counts, autoscaling, provisioning, deployment, scheduling, provider access, or beta authorization.

**Existing work to preserve:** `alembic.ini`, `docker-compose.local.yml`, and `tests/test_local_config.py` contain the already-verified local-contract correction and remain part of the working tree.

---

### Task 1: Promote production-neutral report adapters

**Files:**

- Move: `src/khepri/local/narrator.py` to `src/khepri/rra/deterministic_narrative.py`
- Move: `src/khepri/local/reports.py` to `src/khepri/rra/report_services.py`
- Modify: `src/khepri/local/wiring.py`
- Modify: `tests/test_local_narrator.py`
- Modify: `tests/test_local_journey.py`

**Step 1: Write the failing import tests**

Change the narrator test to import `DeterministicNarrator` from `khepri.rra`; the local journey will exercise the report adapters after local wiring imports them from `khepri.rra`. Keep all existing behavioral assertions.

**Step 2: Run the focused tests and verify RED**

Run: `uv run pytest tests/test_local_narrator.py -q`

Expected: FAIL because the production modules do not exist.

**Step 3: Move and rename without changing behavior**

- Move the deterministic adapter into `khepri.rra` and change its version identity from local-only to `rra005.deterministic.v1`.
- Move the report adapters into `khepri.rra`, dropping `Local` from class names.
- Update local wiring to consume the promoted implementations.
- Keep the provider-disabled deterministic behavior and narrative refusal semantics unchanged.

**Step 4: Run the focused tests and verify GREEN**

Run: `uv run pytest tests/test_local_narrator.py tests/test_local_journey.py -q -m "not local_stack"`

Expected: PASS.

### Task 2: Close the web-to-queue publication boundary

**Files:**

- Modify: `src/khepri/rra/sqs_queue.py`
- Add: `src/khepri/rra/report_publication.py`
- Add: `tests/test_rra007_report_publication.py`
- Modify: `tests/test_rra007_sqs_queue.py`

**Step 1: Write failing publication tests**

Prove that:

- `SqsReportPublisher` sends only `{"job_id":"..."}` to the source queue.
- `QueuedReportRequestService` delegates reads unchanged.
- Every successful report request publishes the returned opaque job ID, including an idempotent repeat, so retrying a request repairs a publication failure.
- A queue send failure escapes; the web boundary never reports success for an unpublished request.

**Step 2: Run the focused tests and verify RED**

Run: `uv run pytest tests/test_rra007_sqs_queue.py tests/test_rra007_report_publication.py -q`

Expected: FAIL because the publisher and decorator do not exist.

**Step 3: Implement the minimum boundary**

- Extract a source-queue-only publisher with a two-argument constructor.
- Reuse the existing canonical message encoder.
- Decorate the report request service; publish after the durable PostgreSQL enqueue and on every repeat.
- Do not add an outbox, scheduler, routing metadata, or worker permission to send messages.

**Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 3: Add fail-closed runtime configuration

**Files:**

- Add: `src/khepri/runtime/__init__.py`
- Add: `src/khepri/runtime/config.py`
- Add: `tests/test_runtime_config.py`

**Step 1: Write failing configuration tests**

Prove that configuration:

- requires every database-secret field and never embeds or prints the password accidentally;
- accepts only PostgreSQL, TLS-required database settings;
- accepts only `me-central-1`, a 12-digit account ID, a KMS key ARN in that region, non-empty bucket and queue URLs, and distinct source/DLQ URLs;
- rejects missing, malformed, blank, or cross-region values rather than defaulting them;
- produces a SQLAlchemy URL that safely quotes credentials.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_runtime_config.py -q`

Expected: FAIL because `khepri.runtime.config` does not exist.

**Step 3: Implement immutable settings**

Parse `KHEPRI_DATABASE_SECRET`, `KHEPRI_AWS_REGION`, `KHEPRI_BUCKET`, `KHEPRI_KMS_KEY_ARN`, `KHEPRI_EXPECTED_BUCKET_OWNER`, `KHEPRI_QUEUE_URL`, and `KHEPRI_DLQ_URL`. Build the database URL with `sqlalchemy.URL.create` and `sslmode=require`; never interpolate or log the secret.

**Step 4: Run and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 4: Compose the production web and bounded worker roles

**Files:**

- Add: `src/khepri/runtime/wiring.py`
- Add: `src/khepri/runtime/web.py`
- Add: `src/khepri/runtime/worker.py`
- Modify: `src/khepri/rra/worker.py`
- Add: `tests/test_runtime_wiring.py`
- Add: `tests/test_runtime_worker.py`
- Modify: `tests/test_rra007_worker.py`

**Step 1: Write failing role tests**

Prove that:

- web wiring uses the production S3 store, SQL repositories, full FastAPI route set, and queued report request decorator;
- worker wiring uses the same PostgreSQL job state, deterministic narrative adapter, all three renderers, one persistent Chromium context, a 300-second database/SQS lease, and a 60-second retry delay;
- the queue driver receives at most one message, acknowledges only successful or already-succeeded jobs, leaves retryable/running/dead-lettered/unknown deliveries for SQS redrive, and continues after recorded execution failure;
- a pipeline heartbeat extends both PostgreSQL lease and SQS visibility;
- the command modules obtain settings at process start and expose only their role.

Use fakes for AWS and process-loop decisions. Do not contact AWS in unit tests.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_rra007_worker.py tests/test_runtime_wiring.py tests/test_runtime_worker.py -q`

Expected: FAIL because runtime composition and queue heartbeat integration do not exist.

**Step 3: Implement the composition root and driver**

- Build role-specific service graphs from validated settings.
- Keep constructors grouped to two or three arguments where practical.
- Extend `ReportWorker.process` with a per-delivery heartbeat callback; invoke it only after the database heartbeat succeeds.
- Process synchronously and one message at a time.
- Let SQS redrive move exhausted deliveries; never call `SendMessage` from the worker.
- Keep maintenance sweeping and deployment cadence outside this slice.

**Step 4: Run and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 5: Declare exact ECS task launch contracts

**Files:**

- Modify: `src/khepri/infra/compute.py`
- Modify: `tests/test_infra_compute.py`
- Modify: `Dockerfile`
- Modify: `.github/workflows/image.yml`

**Step 1: Write failing synthesized-template tests**

Prove that:

- web command is Uvicorn over `khepri.runtime.web:app`, binds `0.0.0.0:8080`, and exposes only TCP 8080;
- worker command is `python -m khepri.runtime.worker` and exposes no port;
- both roles receive explicit region/database/storage/queue coordinates, while credentials remain secret references;
- no ECS service, load balancer, desired count, or autoscaling resource appears.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_infra_compute.py -q`

Expected: FAIL because task definitions have no commands, ports, or runtime coordinates.

**Step 3: Implement the CDK launch contract**

- Add exact command arrays and web port mapping.
- Add CloudFormation token references for the approved bucket, key, account, region, source queue, and DLQ.
- Preserve the distinct task roles and existing least-privilege grants.
- Update stale Dockerfile comments and add non-networked image import/command smoke checks.

**Step 4: Run and verify GREEN**

Run: `uv run pytest tests/test_infra_compute.py -q`

Expected: PASS.

### Task 6: Verify the independently testable slice

**Files:**

- Review all files changed above

**Step 1: Run the focused runtime suite**

Run: `uv run pytest tests/test_runtime_config.py tests/test_runtime_wiring.py tests/test_runtime_worker.py tests/test_rra007_report_publication.py tests/test_rra007_sqs_queue.py tests/test_rra007_worker.py tests/test_infra_compute.py -q`

Expected: PASS.

**Step 2: Run required repository gates**

Run:

- `uv run khepri-gov validate`
- `uv run ruff check .`
- `uv run pytest`

Expected: all PASS. If the CDK/jsii process is sandbox-blocked, rerun the same command outside the sandbox rather than changing tests.

**Step 3: Inspect the final diff**

Run:

- `git -c safe.directory=C:/Users/user/Documents/GitHub/Khepri diff --check`
- `git -c safe.directory=C:/Users/user/Documents/GitHub/Khepri status --short`

Expected: no whitespace errors; only the local-contract correction, this plan, and the runtime-launch slice are modified.

**Step 4: Report the CI-only gate honestly**

State that CodeScene Code Health remains CI-authoritative. Do not claim its 10.00 new-file score locally.
