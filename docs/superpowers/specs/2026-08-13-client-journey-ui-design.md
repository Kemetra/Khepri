# Client Journey A production UI — design

## Objective

Turn the imported Client Journey A handoff into Khepri's first production browser journey:

`invitation → consent and upload → mapping review → report generation → bilingual report access`

The result is a self-serve, Arabic/English, responsive private-beta experience that uses the
existing RRA domain services and preserves their isolation, expiry, deletion, reconciliation, and
content-free telemetry guarantees. This design does not introduce the separate operator console,
commercial workspaces, report history, sharing, comments, public signup, or customer-authored
configuration shown elsewhere in the handoff.

The imported files under `docs/ui/design_handoff_khepri/` remain non-authoritative visual reference.
Production code recreates the design; it does not port the prototype runtime in `support.js`.

## Governing boundary

`governance/registry.yaml` is authoritative and marks the relevant RRA specifications active:

- `RRA-001`: invitation redemption, consent, isolated session, and seven-day boundary;
- `RRA-002`: bounded CSV/XLSX intake and immediate/expiry deletion;
- `RRA-003`: content-minimized profiling, deterministic mapping, and admissibility;
- `RRA-004`, `RRA-005`, and `RRA-008`: facts and grounded narrative shown by the report;
- `RRA-006` and `RRA-009`: complete bilingual web/PDF/Excel delivery and presentation;
- `RRA-007`: bounded job states, recovery, and content-free operational evidence.

`KHEPRI-DEC-008` fixes the runtime: FastAPI, Jinja2, bundled CSS, and minimal bundled JavaScript.
It explicitly excludes a separate SPA and Node.js runtime for the private beta. The UI therefore
fits the existing modular monolith and adds no third process role or frontend deployment.

## Approaches considered

### Selected: server-rendered journey with progressive enhancement

FastAPI serves one Jinja2 page per journey step. Small same-origin JavaScript modules perform raw
streaming upload, API transitions, polling, language switching, and focus/status updates. Pages
remain addressable and reloadable; the API remains the source of workflow truth.

This is the only approach that both matches the handoff's interaction needs and stays inside the
active runtime decision.

### Not selected: HTMX or Alpine enhancement

Either could implement the journey without a build tool, but both add a new client dependency and
interaction vocabulary to four bounded pages. Native browser APIs are sufficient and easier to
audit, package, and keep offline.

### Not selected: React/Vite SPA

A component SPA would improve client-side composition at the cost of a second toolchain, a build
artifact boundary, and substantially more client state. More importantly, `KHEPRI-DEC-008`
explicitly prohibits it for this beta.

## Application structure

The UI is a bounded `khepri.rra.journey` package rather than more branches inside the existing
large API module. Its public boundary is one route-registration function receiving explicit
services. Templates, styles, scripts, locally licensed fonts, and icons ship as package data.

The browser-facing routes are:

| Route | Purpose |
| --- | --- |
| `/beta/{language}` | Entry and invitation bootstrap; redirects to the applicable step |
| `/beta/{language}/upload` | Consent, supported-file guidance, upload, and deletion promise |
| `/beta/{language}/review` | Content-minimized profile and deterministic mapping confirmation |
| `/beta/{language}/processing` | Current governed job state and polling recovery |
| `/beta/{language}/report` | Complete-bundle status and links to the delivered language surfaces |

`language` is closed to `en` and `ar`. Every response declares matching `lang` and `dir`; Arabic is
RTL and English LTR. A language change alters presentation only and cannot change workflow state.

Existing JSON API paths remain stable. New output retrieval routes live under
`/api/v1/beta/reports/{job_id}/surfaces/...`, inside the current HttpOnly cookie path. Static UI
assets use content-versioned URLs and immutable cache headers; HTML and report responses are
private and non-cacheable.

## Invitation and resumability

An invitation link carries its secret in the URL fragment, for example
`/beta/en#invite=<secret>`. Fragments are not sent in HTTP requests and therefore do not enter
access logs. The entry module posts the secret once to the existing redemption endpoint, removes
the fragment with `history.replaceState`, and relies on the existing Secure, HttpOnly,
SameSite=Strict session cookie thereafter.

Opening a step URL without a usable session renders the handoff's expired/unavailable state. The
page never confirms whether an arbitrary invitation, session, job, or bundle belonging to another
scope exists.

The workflow state is derived from server resources rather than local storage:

- no profile: upload step;
- profile present, no fact package: review step;
- fact package present, job unfinished: processing step;
- succeeded job with a reconciled complete bundle: report step;
- deleted or expired session: unavailable state.

The browser may remember the chosen language. It does not persist invitation secrets, opaque
identifiers, customer content, mapping data, report content, or filenames.

## Data flow

### 1. Consent and upload

The consent checkbox is inert until explicitly selected. Starting an assessment first records the
fixed consent version, then streams the chosen file as the request body to the existing upload
endpoint. Client checks for CSV/XLSX and the 50 MB limit improve feedback but never replace server
validation.

The upload module uses `XMLHttpRequest` because its upload progress event is a native, measurable
byte signal; `fetch` currently provides no equivalent upload progress contract. Cancellation
leaves no UI claim that an upload succeeded; the next server read decides whether the session
contains an upload.
Only one upload is accepted per beta session, so "upload another file" deletes the current session
content and requires a new invitation rather than silently replacing provenance.

The source filename remains ephemeral browser text. It is not added to persistence or telemetry,
because filenames may contain personal data and the governed API currently stores only opaque IDs,
digests, media type, size, and timestamps.

### 2. Profile and mapping review

After upload, the browser requests the governed profile. The review page shows safe labels,
inferred types, mapping semantics, confidence/evidence, row and column counts, exclusions, and
findings already present in `ProfileResponse`. It does not invent sample raw values shown in the
mockup, because the existing content-minimized contract does not expose them.

An admissible, fully resolved profile enables "Looks right — analyse". Confirmation creates the
fact package and report job in order. An unavailable, ambiguous, conflicting, or inadmissible
required mapping is displayed with its governed state and cannot proceed. The user may delete the
session and start from a new invitation; free-form remapping is not introduced.

### 3. Processing

The processing page polls the existing job resource with bounded backoff and pauses while the tab
is hidden. It presents only states and reasons the API already governs. It never manufactures
per-stage percentages or durations from content-free evidence that the caller cannot access.

Queued/retrying work remains recoverable after refresh or tab close. Success is announced only
after the bundle endpoint proves one complete reconciled delivery. Dead-letter and unavailable
states show the governed customer-safe reason and a route to delete the session or retry the same
idempotent request where allowed.

### 4. Report access

The ready page shows links for English and Arabic web reports, their separate technical-evidence
pages, English and Arabic PDFs, and the single bilingual Excel workbook. It reports row count,
completion timestamp with timezone, and deletion deadline from governed server data. Because the
source filename is not persisted, a resumed page uses the neutral label "Uploaded dataset" rather
than reconstructing or guessing a filename.

The existing report HTML remains the authoritative web report. The journey does not recalculate,
reshape, or re-chart report facts.

## Durable report surfaces

The current pipeline proves content and stores delivery digests, but it discards HTML/PDF payloads
and leaves the workbook only in ephemeral worker storage. That is insufficient for `RRA-006`'s
published-output storage requirement and for the ready page. Output persistence is therefore a
prerequisite slice, not a UI workaround.

The worker will publish every rendered artifact to the existing encrypted object store beneath:

`owners/{owner_id}/sessions/{session_id}/reports/{bundle_id}/{surface}/{language-or-region}`

Object keys contain only opaque identifiers and closed vocabulary. Each write supplies the same
owner/session encryption context as intake plus bundle, surface, and language identifiers. Stored
metadata records media type, byte size, digest, bundle binding, generation time, and session
expiry—never content or an externally usable object location.

One bundle contains exactly seven retrievable artifacts:

- English and Arabic business HTML documents;
- English and Arabic technical-evidence HTML documents;
- English and Arabic PDFs, each already containing its evidence appendix;
- one bilingual Excel workbook, already containing its audit worksheets.

Renderer payloads stay inside the worker. A worker-local materialized-artifact type may carry bytes
or a temporary path alongside `SurfaceContent`, but it is never accepted by telemetry, job-state,
or delivery-response contracts. `SurfaceContent` remains the content-free claim reconciled by the
domain. The publication boundary accepts the complete reconciled artifact set and emits only
stored artifact metadata to persistence.

Publication follows a staged whole-bundle rule:

1. render all required Arabic and English web/PDF artifacts and the Excel workbook;
2. validate each artifact and reconcile every `SurfaceContent` claim;
3. put artifacts under their final content-addressed keys;
4. atomically commit delivery evidence and artifact metadata in PostgreSQL;
5. expose artifacts only when the complete delivery and every required artifact reconcile.

A retry writes identical bytes to identical bundle keys. Orphaned staged/final objects without a
committed delivery remain unservable and are removed by deletion/expiry cleanup. A partial write
never produces a partial customer response.

Retrieval resolves the caller's HttpOnly session, job, bundle, surface, and language through stored
metadata before reading object bytes. Cross-session and nonexistent objects return the same
customer-safe absence. Responses stream bytes from the application; no object key, storage URL,
credential, or presigned URL reaches the browser.

Immediate and expiry deletion remove the entire opaque session prefix, including uploads,
rendered artifacts, and incomplete multipart uploads, before content metadata is finalized as
deleted. Evidence retains only target kind, opaque ID, location digest, content digest, attempt,
outcome, and governed error code.

## Visual system

Client Journey A is the visual source. Production preserves its light document direction,
Nocturne-derived spacing and colors, restrained typography, content hierarchy, and recommended
four-step flow. The implementation uses design tokens rather than per-element inline styles.

Fonts and icons are local package assets. No page calls Google Fonts, a CDN, an analytics service,
or any runtime asset host. Existing audited Noto Sans Arabic subsets may be reused where their
coverage and weights meet the design; any additional IBM Plex or icon assets must ship with their
licence and audited digest.

The production UI intentionally differs from static mockup data where governance requires it:

- no raw sample cell values on mapping review;
- no invented progress percentage or internal stage timing;
- no durable source filename;
- no share, comment, workspace, history, or report-configuration controls;
- no surface link until the whole delivered bundle reconciles.

## Responsive and accessible behavior

All four journey pages support desktop and narrow widths. Tables retain semantic headers and gain a
labelled horizontal scroll container rather than being converted into ambiguous cards. Numeric
and time-series content stays LTR inside Arabic pages. Logical CSS properties avoid separate
mirrored layouts.

Baseline requirements:

- one visible `h1`, landmarks, skip link, and meaningful page title per route;
- native form controls and buttons with at least 44px touch targets;
- visible `:focus-visible` treatment and deterministic focus after navigation/errors;
- status changes announced through appropriately scoped live regions without repeated polling
  noise;
- reduced-motion variants for progress animation;
- sufficient contrast in normal, hover, focus, disabled, error, and success states;
- no color-only mapping, progress, or error meaning;
- Arabic/English copy tables have equal state and action coverage;
- delivered report charts retain accessible tables and do not become journey-owned charts.

## Failure behavior

The UI maps HTTP outcomes to a small bilingual customer vocabulary while preserving server detail
only when that detail is already governed:

| Condition | Customer behavior |
| --- | --- |
| Missing, expired, deleted, or foreign session | Same unavailable/expired state |
| Consent not recorded | Upload remains disabled; server refusal returns to consent |
| Unsupported, malformed, encrypted, multi-sheet, or oversized file | Focused upload error; no progression |
| Existing upload | Resume its profile state rather than claiming a second upload |
| Inadmissible or unresolved profile | Explain governed findings; analysis action disabled |
| Fact-package refusal | Remain on review with governed reason |
| Queued or retrying report | Remain on processing and continue bounded polling |
| Dead-lettered report | Stable failure state with governed reason and deletion action |
| Missing, partial, mixed, or corrupt delivery | No links; generic bundle-unavailable state |
| Output storage/read failure | Generic unavailable state; no location or provider detail |
| Deletion retry required | Confirm request accepted but deletion is pending retry |

Unknown states and unknown reason codes fail closed to a generic unavailable response and are not
rendered verbatim.

## Browser security

UI and API remain same-origin. Mutating browser requests must carry an allowed `Origin` and
same-origin Fetch Metadata; the existing Secure, HttpOnly, SameSite=Strict cookie remains the only
session credential. Invitation fragments are cleared before any navigation. No secret or customer
content is placed in query strings, route parameters, local storage, analytics, or logs.

Journey pages set a restrictive Content Security Policy with only local styles, scripts, fonts,
images, and API connections; deny framing and object embedding; use `Referrer-Policy: no-referrer`,
`X-Content-Type-Options: nosniff`, and a restrictive permissions policy. Production templates use
autoescaping and external scripts rather than inline event handlers. Download responses set an
explicit governed media type, safe fixed filename, `Content-Disposition`, and `nosniff`.

## Verification strategy

Implementation remains a sequence of independently verifiable slices:

1. browser route and language contracts with no workflow mutation;
2. local design assets and accessible Upload page;
3. invitation bootstrap, consent, upload, and resume behavior;
4. profile/mapping Review page and confirmation boundary;
5. artifact persistence, metadata, whole-bundle publication, retrieval, and deletion;
6. Processing and Report pages against real job/output contracts;
7. end-to-end browser journeys and visual hardening.

Every slice is test-first and names its active specification links. Verification includes:

- unit tests for route registration, closed language/state vocabularies, and error mapping;
- API tests for cookie scope, cross-session indistinguishability, object metadata, byte streaming,
  whole-bundle refusal, retry idempotency, and deletion/expiry;
- template tests for escaping, copy parity, `lang`/`dir`, landmarks, labels, focus targets, and no
  external subresources;
- Playwright journeys for invitation, consent gate, upload, reload/resume, review confirmation,
  polling, ready links, deletion, expiry, keyboard use, and narrow layouts;
- screenshot comparisons against the imported EN/AR desktop and narrow references at controlled
  viewports, fonts, data, and animation state;
- the repository gates: governance validation, Ruff, full pytest, and server-side CodeScene.

Impeccable may be installed only after real components exist and then used as a constrained audit
and polish tool. It may not override the handoff, governing contracts, accessibility requirements,
or screenshot baselines.

## Completion criteria

The Client Journey A mission is complete when a valid invitation can drive both English and Arabic
users through consent, supported upload, deterministic mapping review, confirmed analysis,
recoverable processing, and access to every complete report surface; refresh and tab close resume
from server state; expired/deleted/cross-session access fails closed; immediate and expiry deletion
remove all customer content; desktop/narrow visual and accessibility tests pass; and every required
repository/PR gate is green.
