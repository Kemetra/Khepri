# Report Artifact Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist, reconcile, retrieve, and delete every artifact in one complete bilingual RRA report bundle.

**Architecture:** Renderers expose worker-local payloads beside their existing content-free `SurfaceContent` claims. A publication service writes seven content-addressed encrypted objects, then commits artifact metadata and existing delivery evidence in one PostgreSQL transaction; API readers resolve every byte through the caller's session and never expose storage locations.

**Tech Stack:** Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, boto3/S3-compatible storage, Jinja2, Playwright/Chromium, XlsxWriter, pytest.

## Global Constraints

- Link every product slice to active `RRA-002`, `RRA-006`, `RRA-007`, and `RRA-009` boundaries.
- Preserve `SurfaceContent` as content-free operational evidence; report bytes never enter telemetry, job-state, or bundle-manifest response models.
- Publish exactly seven artifacts: two business HTML, two evidence HTML, two PDF, and one bilingual Excel workbook.
- Expose no object key, storage URL, credential, or presigned URL.
- Require a complete reconciled bundle before any artifact becomes retrievable.
- Store artifacts under the owning session's seven-day expiry and immediate deletion boundary.
- Object keys contain only opaque identifiers and closed vocabulary.
- New migration revision is `20260813_0011` with `down_revision = "20260812_0010"`.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before handoff.

---

## File Structure

- Create `src/khepri/rra/report_artifacts.py`: closed artifact vocabulary and worker-local payload/publication value objects.
- Modify `src/khepri/rra/rendering/html.py`, `pdf.py`, `excel.py`: expose payloads without changing existing claim rendering.
- Modify `src/khepri/rra/pipeline.py`: assemble a complete `ReportPublication` while retaining `BundleAssembler` reconciliation.
- Create `src/khepri/rra/artifact_persistence.py`: artifact row, atomic delivery/artifact repository, and session-scoped metadata reader.
- Create `src/khepri/rra/artifact_publication.py`: encrypted object publication, idempotent verification, and artifact byte retrieval.
- Modify `src/khepri/rra/storage.py`: idempotent put-or-verify behavior for content-addressed report objects.
- Modify `src/khepri/rra/deletion.py` and `persistence.py`: delete upload plus every report artifact and record content-free evidence per target.
- Modify `src/khepri/rra/report_api.py`, `reports.py`, `report_services.py`: authenticated artifact routes and contracts.
- Modify runtime/local wiring so both web and worker use the same publication services.
- Create migration `migrations/versions/20260813_0011_rra_report_artifacts.py`.

---

### Task 1: Closed artifact model and renderer payloads

**Files:**
- Create: `src/khepri/rra/report_artifacts.py`
- Modify: `src/khepri/rra/rendering/html.py`
- Modify: `src/khepri/rra/rendering/pdf.py`
- Modify: `src/khepri/rra/rendering/excel.py`
- Test: `tests/test_rra006_artifact_rendering.py`

**Interfaces:**
- Produces: `ArtifactPayload`, `MaterializedSurface`, `MaterializedRenderer`, `REQUIRED_ARTIFACT_KINDS`.
- Produces: `HtmlReportRenderer.render_materialized`, `PdfReportRenderer.render_materialized`, `ExcelSurfaceRenderer.render_materialized`.

- [ ] **Step 1: Write failing closed-vocabulary tests**

```python
def test_required_artifact_matrix_is_exact() -> None:
    assert REQUIRED_ARTIFACT_KINDS == (
        "web_business_ar", "web_business_en",
        "web_evidence_ar", "web_evidence_en",
        "pdf_ar", "pdf_en", "excel",
    )

def test_payload_rejects_wrong_digest() -> None:
    with pytest.raises(ValueError, match="digest"):
        ArtifactPayload(kind="excel", media_type=XLSX_MEDIA_TYPE,
                        file_name="khepri-report.xlsx", content=b"xlsx", sha256_hex="0" * 64)
```

- [ ] **Step 2: Run the new test and verify missing imports fail**

Run: `uv run pytest tests/test_rra006_artifact_rendering.py -q`
Expected: collection failure because `khepri.rra.report_artifacts` does not exist.

- [ ] **Step 3: Implement immutable worker-local types**

```python
REQUIRED_ARTIFACT_KINDS = (
    "web_business_ar", "web_business_en",
    "web_evidence_ar", "web_evidence_en",
    "pdf_ar", "pdf_en", "excel",
)

@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    kind: str
    media_type: str
    file_name: str
    content: bytes
    sha256_hex: str

    @classmethod
    def of(cls, *, kind: str, media_type: str, file_name: str, content: bytes) -> "ArtifactPayload":
        return cls(kind, media_type, file_name, content, hashlib.sha256(content).hexdigest())

@dataclass(frozen=True, slots=True)
class MaterializedSurface:
    content: SurfaceContent
    artifacts: tuple[ArtifactPayload, ...]

class MaterializedRenderer(Protocol):
    @property
    def surface(self) -> str: ...
    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface: ...
```

Validate exact kind membership, non-empty bytes, fixed safe filename, known media type, 64-character digest, and digest/content equality. A `MaterializedSurface` validates the exact artifact subset for its surface.

- [ ] **Step 4: Add renderer materialization tests**

Assert HTML returns four UTF-8 payloads byte-equal to `render_html().documents/evidence`, PDF returns two byte-equal documents, and Excel returns one payload byte-equal to the closed workbook path. Assert each `SurfaceContent.output_size_bytes` equals its complete surface payload size.

- [ ] **Step 5: Implement `render_materialized` without changing existing `render` contracts**

`render()` delegates to `render_materialized().content`. HTML encodes each document as UTF-8; PDF uses the existing bytes; Excel reads the just-closed workbook and returns the bytes. Use fixed download names `khepri-report.html`, `khepri-evidence.html`, `khepri-report.pdf`, and `khepri-report.xlsx`.

- [ ] **Step 6: Run focused rendering tests**

Run: `uv run pytest tests/test_rra006_artifact_rendering.py tests/test_rra006_html_surface.py tests/test_rra006_pdf_surface.py tests/test_rra006_excel_surface.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/khepri/rra/report_artifacts.py src/khepri/rra/rendering tests/test_rra006_artifact_rendering.py
git -c commit.gpgsign=false commit -m "feat(rra): materialize governed report artifacts"
```

### Task 2: Pipeline publication boundary

**Files:**
- Modify: `src/khepri/rra/report_artifacts.py`
- Modify: `src/khepri/rra/pipeline.py`
- Test: `tests/test_rra006_pipeline.py`
- Test: `tests/test_rra006_bundle.py`

**Interfaces:**
- Consumes: `MaterializedRenderer.render_materialized(bundle)`.
- Produces: `ReportPublication(delivery: ReportDelivery, artifacts: tuple[ArtifactPayload, ...])`.
- Produces: `PublicationStore.find_delivery(job_id)` and `PublicationStore.publish(publication)`.

- [ ] **Step 1: Write a failing complete-publication pipeline test**

```python
def test_pipeline_publishes_one_reconciled_seven_artifact_set() -> None:
    outcome = pipeline(materialized_renderers()).run(execution())
    publication = publisher.published[0]
    assert publication.delivery.record == outcome.record
    assert tuple(item.kind for item in publication.artifacts) == REQUIRED_ARTIFACT_KINDS
```

Also assert one failed/missing/mismatched payload publishes neither delivery evidence nor artifact bytes.

- [ ] **Step 2: Verify the test fails because the pipeline accepts only claim renderers**

Run: `uv run pytest tests/test_rra006_pipeline.py -q`
Expected: failure showing `publish`/`ReportPublication` is absent.

- [ ] **Step 3: Implement `ReportPublication` and claim adapters**

```python
@dataclass(frozen=True, slots=True)
class ReportPublication:
    delivery: ReportDelivery
    artifacts: tuple[ArtifactPayload, ...]

class PublicationStore(Protocol):
    def find_delivery(self, job_id: str) -> DeliveryRecord | None: ...
    def publish(self, publication: ReportPublication) -> DeliveryRecord: ...
```

In `ReportPipeline.assemble`, materialize each renderer once, retain its payloads in worker memory,
and pass a tiny cached claim renderer into the existing `BundleAssembler`. Only after
`BundleAssembler` returns a complete reconciled result construct `ReportPublication`. Change
`deliver` to call `PublicationStore.publish`.

- [ ] **Step 4: Prove bytes cannot enter evidence models**

Add tests that `BundleAttempt.as_document`, `DeliveryRecord.as_document`, `ReportJobView`, and
operational events contain none of the artifact byte markers or filenames.

- [ ] **Step 5: Run pipeline/bundle tests**

Run: `uv run pytest tests/test_rra006_pipeline.py tests/test_rra006_bundle.py tests/test_rra007_stage_instrumentation.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/khepri/rra/report_artifacts.py src/khepri/rra/pipeline.py tests/test_rra006_pipeline.py tests/test_rra006_bundle.py
git -c commit.gpgsign=false commit -m "feat(rra): carry complete report publications"
```

### Task 3: Artifact schema and atomic metadata persistence

**Files:**
- Create: `migrations/versions/20260813_0011_rra_report_artifacts.py`
- Create: `src/khepri/rra/artifact_persistence.py`
- Modify: `src/khepri/rra/delivery_persistence.py`
- Test: `tests/test_rra006_artifact_persistence.py`
- Test: `tests/test_rca001_migration.py`

**Interfaces:**
- Produces: `StoredArtifact`, `ReportArtifactRow`, `SqlArtifactRepository.commit`, `find_in_session`, `list_for_job`.
- Consumes: a complete `ReportPublication` plus object-store results.

- [ ] **Step 1: Write migration and repository failure tests**

Test that the table rejects an unknown kind, wrong digest length, mixed bundle, duplicate kind,
wrong session scope, expiry not after generation, and fewer/more than the seven required rows at
repository commit. Test `down_revision == "20260812_0010"`.

- [ ] **Step 2: Run and observe missing table/model failures**

Run: `uv run pytest tests/test_rra006_artifact_persistence.py tests/test_rca001_migration.py -q`
Expected: failures for missing revision/model.

- [ ] **Step 3: Implement the `rra_report_artifacts` migration**

Columns: `job_id`, `artifact_kind`, `owner_id`, `session_id`, `bundle_id`, `object_key`,
`media_type`, `file_name`, `size_bytes`, `sha256_hex`, `created_at`, `expires_at`,
`encryption_algorithm`, `kms_key_id`. Primary key `(job_id, artifact_kind)`. Composite foreign keys
bind `(job_id,bundle_id)` to deliveries and `(owner_id,session_id)` to beta sessions. Add unique
`object_key`, closed artifact/media/filename checks, digest/size/encryption/expiry checks, and expiry
index.

- [ ] **Step 4: Implement atomic repository commit**

```python
@dataclass(frozen=True, slots=True)
class StoredArtifact:
    job_id: str
    artifact_kind: str
    owner_id: str
    session_id: str
    bundle_id: str
    object_key: str
    media_type: str
    file_name: str
    size_bytes: int
    sha256_hex: str
    created_at: datetime
    expires_at: datetime
    encryption_algorithm: str
    kms_key_id: str
```

Refactor delivery insertion into a transaction-local helper. `SqlArtifactRepository.commit`
locks the scoped live session/job, validates exactly seven stored artifacts against the publication,
inserts delivery, surface evidence, and artifact rows in one transaction, and returns the existing
delivery on an identical retry. Any mismatch raises `ArtifactConflict` without partial rows.

- [ ] **Step 5: Add session-scoped reads**

`find_in_session(session_id, job_id, artifact_kind, now)` returns `None` for missing, foreign,
expired, deletion-requested, or incomplete delivery; `list_for_job` returns required order and
fails closed on any incomplete/mixed row set.

- [ ] **Step 6: Run persistence and migration tests**

Run: `uv run pytest tests/test_rra006_artifact_persistence.py tests/test_rra006_delivery_persistence.py tests/test_rca001_migration.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add migrations/versions/20260813_0011_rra_report_artifacts.py src/khepri/rra/artifact_persistence.py src/khepri/rra/delivery_persistence.py tests
git -c commit.gpgsign=false commit -m "feat(rra): persist report artifact metadata"
```

### Task 4: Idempotent encrypted object publication

**Files:**
- Modify: `src/khepri/rra/storage.py`
- Create: `src/khepri/rra/artifact_publication.py`
- Test: `tests/test_rra006_artifact_publication.py`
- Test: `tests/test_rra002_s3_storage.py`

**Interfaces:**
- Produces: `S3EncryptedObjectStore.put_or_verify`.
- Produces: `ReportArtifactPublisher.find_delivery`, `publish`, and `read`.
- Consumes: `SqlArtifactRepository`, `SqlDeliveryStore`, `ReportPublication`.

- [ ] **Step 1: Write failing idempotency and rollback tests**

Cover first publication, identical retry after an object already exists, conflicting existing
bytes, policy/checksum failure, failure on artifact four, metadata transaction failure, and read
digest/size/media mismatch. Assert no delivery becomes readable on every failure.

- [ ] **Step 2: Verify tests fail on missing publisher**

Run: `uv run pytest tests/test_rra006_artifact_publication.py tests/test_rra002_s3_storage.py -q`
Expected: missing class/method failures.

- [ ] **Step 3: Add content-addressed `put_or_verify`**

Attempt existing `put` with `IfNoneMatch="*"`. Only when botocore reports HTTP 412/PreconditionFailed,
read the existing object through the audited `get`, compare SHA-256 and length, and return its proven
metadata. Re-raise every other client or policy error. Never overwrite conflicting bytes.

- [ ] **Step 4: Implement publication service**

Build keys from `owner_id/session_id/bundle_id/artifact_kind`, put all seven objects with encryption
context, and pass the seven proven `StoredArtifact` records to the atomic repository. If metadata
commit fails, delete only objects created by this attempt; pre-existing verified objects remain.
An identical committed retry returns the existing delivery without rewriting objects.

- [ ] **Step 5: Implement verified reads**

Resolve scoped metadata first, load through the encrypted store, then verify byte digest, size, and
known media type again. Return `ArtifactDocument(content, media_type, file_name)`; convert storage
policy failures to `ArtifactUnavailable` without leaking provider text.

- [ ] **Step 6: Run focused storage/publication tests**

Run: `uv run pytest tests/test_rra006_artifact_publication.py tests/test_rra002_s3_storage.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/khepri/rra/storage.py src/khepri/rra/artifact_publication.py tests/test_rra006_artifact_publication.py tests/test_rra002_s3_storage.py
git -c commit.gpgsign=false commit -m "feat(rra): publish encrypted report artifacts"
```

### Task 5: Session-wide artifact deletion and expiry

**Files:**
- Modify: `src/khepri/rra/deletion.py`
- Modify: `src/khepri/rra/persistence.py`
- Modify: `migrations/versions/20260813_0011_rra_report_artifacts.py`
- Test: `tests/test_rra002_deletion.py`
- Test: `tests/test_rra002_deletion_persistence.py`
- Test: `tests/test_rra006_artifact_deletion.py`

**Interfaces:**
- Replaces: `DeletionRepository.get_target` with `get_targets(job) -> tuple[DeletionTarget, ...]`.
- Replaces single evidence arguments with `tuple[DeletionEvidence, ...]` for one attempt.

- [ ] **Step 1: Write failing multi-target deletion tests**

Create one upload and seven artifact targets. Assert deletion aborts the session prefix, deletes all
eight keys, records eight content-free evidence rows with one attempt number, removes package/profile/
upload/artifact metadata, marks content deleted, and is idempotent. Inject failure on target four and
assert metadata remains retryable and the next attempt safely finishes remaining keys.

- [ ] **Step 2: Verify current single-input model fails**

Run: `uv run pytest tests/test_rra002_deletion.py tests/test_rra002_deletion_persistence.py tests/test_rra006_artifact_deletion.py -q`
Expected: failures because only one input target is returned/allowed.

- [ ] **Step 3: Generalize deletion targets and evidence**

```python
@dataclass(frozen=True, slots=True)
class DeletionTarget:
    target_kind: str  # input | report_artifact
    target_id: str
    object_key: str
    content_digest: str
```

Generate one evidence row per target per attempt. The migration changes the evidence target-kind
check to `IN ('input','report_artifact')`, drops the old `(deletion_id,attempt_number)` uniqueness,
and adds `(deletion_id,attempt_number,target_kind,target_id)` uniqueness.

- [ ] **Step 4: Delete all targets and commit metadata atomically**

Abort multipart uploads under the opaque session prefix once, delete each target idempotently,
collect success/failure evidence, and call repository `complete` only if every target succeeded.
On any failure, persist the whole attempt's evidence and schedule retry. Treat an already absent
object as deleted only through an explicit object-store not-found contract.

- [ ] **Step 5: Run deletion and sweeper tests**

Run: `uv run pytest tests/test_rra002_deletion.py tests/test_rra002_deletion_persistence.py tests/test_rra006_artifact_deletion.py tests/test_local_sweeper.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/khepri/rra/deletion.py src/khepri/rra/persistence.py migrations/versions/20260813_0011_rra_report_artifacts.py tests
git -c commit.gpgsign=false commit -m "feat(rra): delete every session report artifact"
```

### Task 6: Authenticated artifact retrieval API

**Files:**
- Modify: `src/khepri/rra/reports.py`
- Modify: `src/khepri/rra/report_services.py`
- Modify: `src/khepri/rra/report_api.py`
- Test: `tests/test_rra006_report_artifact_api.py`
- Test: `tests/test_rra006_report_api.py`

**Interfaces:**
- Adds: `ReportArtifactReader.get_session_artifact(session_id, job_id, artifact_kind, now)`.
- Adds: `ReportServices.artifacts`.
- Adds explicit web/evidence/PDF/Excel download routes.

- [ ] **Step 1: Write failing route contract tests**

Assert the seven URLs return exact bytes, media type, `Content-Disposition`, `Cache-Control: private,
no-store`, and `X-Content-Type-Options: nosniff`. Assert missing cookie is 401; foreign and unknown
job/kind are indistinguishable 404; incomplete bundle, digest failure, deleted/expired content, and
store failure are the same generic 503/absence contract without keys/provider text.

- [ ] **Step 2: Verify routes are unregistered**

Run: `uv run pytest tests/test_rra006_report_artifact_api.py -q`
Expected: 404 for every expected route.

- [ ] **Step 3: Extend report service contracts**

```python
class ReportArtifactReader(Protocol):
    def get_session_artifact(self, *, session_id: str, job_id: str,
                             artifact_kind: str, now: datetime) -> ArtifactDocument | None: ...

@dataclass(frozen=True, slots=True)
class ReportServices:
    jobs: ReportRequestService
    bundles: DeliveredBundleReader
    artifacts: ReportArtifactReader
```

- [ ] **Step 4: Register explicit closed routes**

Register `/surfaces/web/{language}`, `/surfaces/evidence/{language}`,
`/surfaces/pdf/{language}`, and `/surfaces/excel`. Close language to `ar|en`; map route to a closed
artifact kind; return a raw `Response` with safe fixed filename. Do not accept arbitrary object keys.

- [ ] **Step 5: Run report API tests**

Run: `uv run pytest tests/test_rra006_report_artifact_api.py tests/test_rra006_report_api.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/khepri/rra/reports.py src/khepri/rra/report_services.py src/khepri/rra/report_api.py tests
git -c commit.gpgsign=false commit -m "feat(rra): serve scoped report artifacts"
```

### Task 7: Runtime wiring and complete backend verification

**Files:**
- Modify: `src/khepri/runtime/wiring.py`
- Modify: `src/khepri/local/wiring.py`
- Modify: `src/khepri/runtime/worker.py`
- Modify: `src/khepri/local/worker.py`
- Test: `tests/test_runtime_wiring.py`
- Test: `tests/test_local_journey.py`
- Test: `tests/test_rra006_pipeline.py`

**Interfaces:**
- Production and local web roles receive the same scoped artifact reader.
- Production and local workers receive the artifact publisher, not the evidence-only delivery store.

- [ ] **Step 1: Write failing wiring tests**

Assert `build_pipeline` receives `HtmlReportRenderer`, `PdfReportRenderer`, and
`ExcelSurfaceRenderer` as materialized renderers and a `ReportArtifactPublisher`; assert
`build_report_services` exposes the publisher as artifact reader; assert no object-store client or
key appears in route responses.

- [ ] **Step 2: Wire repository and publisher once per stack**

Add artifact repository/publisher to `ReportStores` or a focused `ReportArtifacts` dataclass.
Worker and web compose from the same factory/object store/clock. Keep the existing one image and two
process roles unchanged.

- [ ] **Step 3: Run focused backend suite**

Run: `uv run pytest tests/test_rra006_* tests/test_rra002_* tests/test_runtime_wiring.py tests/test_local_journey.py -q`
Expected: all pass; local-stack marked tests may skip when prerequisites are absent.

- [ ] **Step 4: Run required repository gates**

Run:

```powershell
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

Expected: governance and Ruff pass; full suite passes with only declared external-prerequisite skips.

- [ ] **Step 5: Commit**

```powershell
git add src/khepri/runtime src/khepri/local tests
git -c commit.gpgsign=false commit -m "feat(rra): wire durable report publication"
```

