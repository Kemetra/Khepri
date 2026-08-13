# Client Journey A UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the production Arabic/English private-beta browser journey from invitation through consent, upload, mapping review, processing, and complete report access.

**Architecture:** FastAPI serves addressable Jinja2 pages and local static assets from the existing web role. Focused vanilla JavaScript modules call same-origin beta APIs and derive resumable workflow state from a new content-minimized session journey resource; no SPA, Node runtime, local customer state, or prototype harness is introduced.

**Tech Stack:** Python 3.13, FastAPI, Jinja2, bundled CSS and ES modules, Playwright/Chromium, pytest.

## Global Constraints

- The approved design is `docs/superpowers/specs/2026-08-13-client-journey-ui-design.md`.
- Visual source is Client Journey A under `docs/ui/design_handoff_khepri/`; do not port `support.js`.
- Runtime remains FastAPI + Jinja2 + bundled CSS + minimal JavaScript; no SPA or Node.js runtime.
- Languages are closed to `en` LTR and `ar` RTL with equal state/action coverage.
- Never persist invitation secrets, filenames, customer content, mappings, report bytes, or job IDs in browser storage.
- Never show raw sample cell values, invented progress percentages/timings, or unreconciled report links.
- Consent version is the fixed constant `rra001.beta-consent.v1`.
- UI and API are same-origin; mutating browser calls require allowed Origin and Fetch Metadata.
- All assets are local; pages contain no external fonts, scripts, styles, images, analytics, or API calls.
- Desktop and narrow layouts, keyboard operation, reduced motion, and semantic accessibility are required.
- Report links appear only after the backend plan's complete artifact publication contract passes.

---

## File Structure

- Create package `src/khepri/rra/journey/` with focused `routes.py`, `state.py`, `copy.py`, `security.py`.
- Create `templates/base.html.j2`, `upload.html.j2`, `review.html.j2`, `processing.html.j2`, `report.html.j2`, and shared partials.
- Create local `assets/journey.css`, `common.js`, `upload.js`, `review.js`, `processing.js`, `report.js` plus audited fonts/icons.
- Modify `src/khepri/rra/api.py` only to register the journey API/page group through one function.
- Modify runtime/local wiring to inject `SqlJourneyReader`.
- Add focused route, template, browser, and visual tests rather than growing existing API test files.

---

### Task 1: Content-minimized resumable journey state

**Files:**
- Create: `src/khepri/rra/journey/__init__.py`
- Create: `src/khepri/rra/journey/state.py`
- Create: `src/khepri/rra/journey/routes.py`
- Modify: `src/khepri/rra/api.py`
- Test: `tests/test_rra_journey_state.py`
- Test: `tests/test_rra_journey_api.py`

**Interfaces:**
- Produces: `JourneySnapshot`, `JourneyReader`, `SqlJourneyReader.read(session_id, now)`.
- Produces: `add_journey_routes(app, reader, clock)` and `GET /api/v1/beta/journey`.

- [ ] **Step 1: Write failing state-precedence tests**

```python
@pytest.mark.parametrize((resources, expected), [
    ({}, "upload"),
    ({"upload": True, "profile": False}, "upload"),
    ({"profile": True, "package": False}, "review"),
    ({"package": True, "job": "queued"}, "processing"),
    ({"job": "succeeded", "complete_bundle": True}, "report"),
])
def test_snapshot_derives_one_resumable_step(resources, expected):
    assert snapshot(resources).step == expected
```

Add failure cases for missing, expired, deletion-requested, deleted, foreign, dead-lettered,
succeeded-without-delivery, and partial artifact rows.

- [ ] **Step 2: Verify state module is missing**

Run: `uv run pytest tests/test_rra_journey_state.py tests/test_rra_journey_api.py -q`
Expected: import/route failures.

- [ ] **Step 3: Implement closed snapshot model**

```python
@dataclass(frozen=True, slots=True)
class JourneySnapshot:
    step: str
    content_expires_at: datetime
    consent_recorded: bool
    upload_present: bool
    profile_present: bool
    profile_admissible: bool | None
    package_present: bool
    job_id: str | None
    job_state: str | None
    job_reason: str | None
    row_count: int | None
    generated_at: datetime | None
    bundle_complete: bool
```

Snapshot construction validates closed step/job/reason vocabularies and impossible combinations.

- [ ] **Step 4: Implement one scoped SQL read**

Read session, upload, profile, fact package, latest session job, delivery, and seven artifact rows
through joins/subqueries scoped by the cookie session. Return `None` for missing/expired/deleted
sessions. Never select profile JSON, object keys, digests, labels, or content.

- [ ] **Step 5: Add the journey JSON endpoint**

Return 401 with the existing indistinguishable session message for no usable session. Serialize only
the snapshot fields and set `Cache-Control: private, no-store`.

- [ ] **Step 6: Run focused tests**

Run: `uv run pytest tests/test_rra_journey_state.py tests/test_rra_journey_api.py tests/test_rra001_api.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/khepri/rra/journey src/khepri/rra/api.py tests/test_rra_journey_state.py tests/test_rra_journey_api.py
git -c commit.gpgsign=false commit -m "feat(ui): expose resumable beta journey state"
```

### Task 2: Bilingual page routes, copy, and secure base shell

**Files:**
- Create: `src/khepri/rra/journey/copy.py`
- Create: `src/khepri/rra/journey/security.py`
- Create: `src/khepri/rra/journey/templates/base.html.j2`
- Create: `src/khepri/rra/journey/templates/expired.html.j2`
- Create: `src/khepri/rra/journey/assets/journey.css`
- Create: `src/khepri/rra/journey/assets/common.js`
- Modify: `src/khepri/rra/journey/routes.py`
- Test: `tests/test_rra_journey_pages.py`
- Test: `tests/test_rra_journey_security.py`

**Interfaces:**
- Produces: `JOURNEY_COPY[language]`, `journey_environment()`, page/asset route registration.
- Produces: `require_same_origin(request)` for mutating journey/API calls.

- [ ] **Step 1: Write failing page/security tests**

For every page and language assert exact `lang`, `dir`, title, one `h1`, skip link, main landmark,
local stylesheet/module URLs, no inline handlers, no external subresources, CSP, no-store,
no-referrer, nosniff, frame denial, and permissions policy. Assert unknown language/step is 404.

- [ ] **Step 2: Verify routes/templates are missing**

Run: `uv run pytest tests/test_rra_journey_pages.py tests/test_rra_journey_security.py -q`
Expected: expected page routes return 404.

- [ ] **Step 3: Implement strict template environment and bilingual copy**

Use `PackageLoader`, unconditional autoescape, and `StrictUndefined`. Store copy as two complete
immutable dictionaries keyed by the same closed vocabulary; test equality of keys. All generated
URLs come from route names, never translated strings.

- [ ] **Step 4: Implement page and local asset responses**

Register `/beta/{language}`, `/upload`, `/review`, `/processing`, `/report`; the entry page uses the
upload template. Serve only allow-listed packaged files under `/beta/assets/{name}` with explicit
media types and immutable cache headers. Do not expose arbitrary filesystem paths.

- [ ] **Step 5: Implement security headers and mutation guard**

Allow configured same-origin `Origin` plus `Sec-Fetch-Site` in `same-origin|none`; reject cross-site
mutations with 403 before body parsing. The CSP permits only `'self'`, locally served fonts/images,
and same-origin connections; no `unsafe-inline` or CDN host.

- [ ] **Step 6: Implement tokenized responsive shell**

Translate the Client Journey A palette, spacing, typography, focus, disabled, status, table, and
button rules into CSS custom properties. Use logical properties, `:focus-visible`, 44px controls,
`prefers-reduced-motion`, LTR numeric islands, desktop max width, and narrow single-column flow.

- [ ] **Step 7: Run page/security tests and commit**

Run: `uv run pytest tests/test_rra_journey_pages.py tests/test_rra_journey_security.py -q`
Expected: all pass.

```powershell
git add src/khepri/rra/journey tests/test_rra_journey_pages.py tests/test_rra_journey_security.py
git -c commit.gpgsign=false commit -m "feat(ui): add secure bilingual journey shell"
```

### Task 3: Invitation bootstrap, consent, and upload

**Files:**
- Create: `src/khepri/rra/journey/templates/upload.html.j2`
- Create: `src/khepri/rra/journey/assets/upload.js`
- Modify: `src/khepri/rra/journey/assets/common.js`
- Modify: `src/khepri/rra/journey/routes.py`
- Modify: `src/khepri/rra/api.py`
- Test: `tests/test_rra_journey_upload.py`
- Test: `tests/test_rra_journey_browser.py`

**Interfaces:**
- Consumes: existing redeem, consent, upload, profile endpoints and journey snapshot.
- Produces: fragment bootstrap and measurable raw-body upload UI.

- [ ] **Step 1: Write failing DOM/API interaction tests**

Assert invitation token is read only from `#invite=`, POSTed once, removed with
`history.replaceState`, and never placed in query/local/session storage. Assert drop zone/file input
remain disabled before consent; only CSV/XLSX <= 50 MB proceed; consent POST precedes upload; upload
uses raw file bytes and declared length; XHR progress updates an ARIA progressbar; error focuses the
summary; success requests profile and moves to review.

- [ ] **Step 2: Verify upload template/module is absent**

Run: `uv run pytest tests/test_rra_journey_upload.py tests/test_rra_journey_browser.py -q`
Expected: missing controls/module failures.

- [ ] **Step 3: Implement semantic upload template**

Include consent checkbox/label, native file input, keyboard-operable drop target, supported-format
and 50 MB copy, seven-day deletion promise, progress element, error summary, primary submit, language
switch, and delete action. No filename is sent anywhere except the visible live DOM.

- [ ] **Step 4: Implement fragment redemption and state resume**

On load: clear fragment immediately after copying its value; redeem; fetch journey snapshot; route
to review/processing/report when server truth is ahead. Without token/session render the shared
expired state and advisor/new-invitation guidance.

- [ ] **Step 5: Implement consent and XHR upload**

POST `{"consent_version":"rra001.beta-consent.v1"}` with same-origin headers, then send the `File`
as XHR body. Map 400/403/409/413/503 to fixed bilingual copy. On successful upload POST profile with
the default governed semantic request, then navigate to review. Abort leaves the next snapshot to
decide state.

- [ ] **Step 6: Run upload/API/browser tests**

Run: `uv run pytest tests/test_rra_journey_upload.py tests/test_rra001_api.py tests/test_rra002_api.py tests/test_rra_journey_browser.py -q`
Expected: all pass; browser test skips only when pinned Chromium is unavailable.

- [ ] **Step 7: Commit**

```powershell
git add src/khepri/rra/journey src/khepri/rra/api.py tests
git -c commit.gpgsign=false commit -m "feat(ui): build consent-gated beta upload"
```

### Task 4: Deterministic mapping review and confirmation

**Files:**
- Create: `src/khepri/rra/journey/templates/review.html.j2`
- Create: `src/khepri/rra/journey/assets/review.js`
- Modify: `src/khepri/rra/journey/copy.py`
- Test: `tests/test_rra_journey_review.py`
- Test: `tests/test_rra_journey_browser.py`

**Interfaces:**
- Consumes: `GET/POST /api/v1/beta/profile`, `POST /facts`, `POST /reports`, journey snapshot.
- Produces: confirmed report job and navigation to processing.

- [ ] **Step 1: Write failing review tests**

Assert the table presents only safe labels, semantics, requirement/state, confidence/evidence,
inferred type, counts/rates/ranges, exclusions, and findings already in `ProfileResponse`. Assert no
raw sample values or editable semantic controls. Required ambiguous/conflicting/unavailable mapping
or inadmissibility disables analysis with fixed explanations.

- [ ] **Step 2: Verify review controls are missing**

Run: `uv run pytest tests/test_rra_journey_review.py tests/test_rra_journey_browser.py -q`
Expected: missing review DOM/module failures.

- [ ] **Step 3: Implement responsive semantic review page**

Use a captioned table with scoped headers inside a labelled horizontal-scroll region. Each state has
text plus icon, never color alone. Findings use an ordered alert/callout. Narrow layout preserves the
table and actions without card conversion.

- [ ] **Step 4: Implement server-truth loading and confirmation**

Fetch profile, render with text nodes (never HTML interpolation), and enable confirmation only when
`admissible` and every required mapping is resolved. On confirmation POST facts, POST `{}` to reports,
then navigate to processing. Idempotent 200/201 responses are both success.

- [ ] **Step 5: Implement restart action**

"Upload a different file" explains that the immutable session must be deleted, calls DELETE content,
clears visible state, and renders the new-invitation state; it never replaces an upload in place.

- [ ] **Step 6: Run review and relevant domain tests**

Run: `uv run pytest tests/test_rra_journey_review.py tests/test_rra003_api.py tests/test_rra004_packages.py tests/test_rra006_report_api.py tests/test_rra_journey_browser.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/khepri/rra/journey tests/test_rra_journey_review.py tests/test_rra_journey_browser.py
git -c commit.gpgsign=false commit -m "feat(ui): add governed mapping review"
```

### Task 5: Recoverable processing and complete report access

**Files:**
- Create: `src/khepri/rra/journey/templates/processing.html.j2`
- Create: `src/khepri/rra/journey/templates/report.html.j2`
- Create: `src/khepri/rra/journey/assets/processing.js`
- Create: `src/khepri/rra/journey/assets/report.js`
- Modify: `src/khepri/rra/journey/copy.py`
- Test: `tests/test_rra_journey_processing.py`
- Test: `tests/test_rra_journey_report.py`
- Test: `tests/test_rra_journey_browser.py`

**Interfaces:**
- Consumes: journey snapshot, report job/bundle endpoints, and seven artifact routes.
- Produces: bounded polling, stable failure state, and bilingual ready page.

- [ ] **Step 1: Write failing processing/report tests**

Assert polling starts at 1 second, backs off to max 10 seconds, pauses while hidden, resumes on
visibility, and stops on report/dead-letter/unavailable. Assert no percentages or invented timings.
Assert ready links are absent until `bundle_complete`, then exactly seven links appear with correct
language/direction. Assert row count, generated timestamp with timezone, deletion deadline, and
neutral "Uploaded dataset" label.

- [ ] **Step 2: Verify templates/modules are absent**

Run: `uv run pytest tests/test_rra_journey_processing.py tests/test_rra_journey_report.py tests/test_rra_journey_browser.py -q`
Expected: missing DOM/module failures.

- [ ] **Step 3: Implement processing UI**

Show four honest stages whose completed/current/pending state is derived only from durable workflow
resources: upload/profile, confirmed facts, report job, complete publication. Use an indeterminate
bar with reduced-motion fallback and a polite live region that announces only state changes.

- [ ] **Step 4: Implement bounded polling and failure vocabulary**

Fetch the journey snapshot; redirect on server state. Map only governed dead-letter/failure codes to
bilingual copy. Unknown codes render generic unavailable text. Retry calls the idempotent report
request only for retryable states; delete always remains available.

- [ ] **Step 5: Implement report page and links**

Fetch snapshot then bundle manifest. Build explicit same-origin URLs for EN/AR business HTML,
EN/AR evidence HTML, EN/AR PDF, and Excel. Use safe fixed download labels and do not insert storage
locations. Language cards preserve their own `dir` islands.

- [ ] **Step 6: Run processing/report/API tests**

Run: `uv run pytest tests/test_rra_journey_processing.py tests/test_rra_journey_report.py tests/test_rra006_report_artifact_api.py tests/test_rra_journey_browser.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/khepri/rra/journey tests
git -c commit.gpgsign=false commit -m "feat(ui): deliver recoverable report journey"
```

### Task 6: Production/local wiring and package assets

**Files:**
- Modify: `src/khepri/runtime/wiring.py`
- Modify: `src/khepri/local/wiring.py`
- Modify: `pyproject.toml` only if hatch package-data verification proves assets absent
- Test: `tests/test_runtime_wiring.py`
- Test: `tests/test_local_journey.py`
- Test: `tests/test_build_image.py`

**Interfaces:**
- Both web compositions pass `SqlJourneyReader(factory)` to route registration.
- Built wheel and OCI image contain all journey templates/assets/fonts/icons.

- [ ] **Step 1: Write failing wheel/wiring tests**

Build a wheel, inspect it as ZIP, and assert every allow-listed template/asset exists. Instantiate
runtime/local apps and assert journey/page/state/artifact routes register only when their complete
service bundle is supplied.

- [ ] **Step 2: Wire the journey reader into both web roots**

Pass one `JourneyServices` dataclass into `create_app`; avoid adding more optional keyword parameters
to the existing large function. Production and local compositions use the same route module.

- [ ] **Step 3: Verify packaged assets**

Run: `uv build`; inspect the wheel. Add a narrow Hatch `artifacts`/include rule only if automatic
package-data inclusion does not contain `.j2`, `.css`, `.js`, `.woff2`, and licence files.

- [ ] **Step 4: Run wiring/build tests and commit**

Run: `uv run pytest tests/test_runtime_wiring.py tests/test_local_journey.py tests/test_build_image.py -q`
Expected: all pass; local-stack cases may skip only for declared missing prerequisites.

```powershell
git add src/khepri/runtime/wiring.py src/khepri/local/wiring.py pyproject.toml tests
git -c commit.gpgsign=false commit -m "feat(ui): wire packaged client journey"
```

### Task 7: Visual, accessibility, and end-to-end completion gate

**Files:**
- Create: `tests/test_rra_journey_accessibility.py`
- Create: `tests/test_rra_journey_visual.py`
- Create: `tests/test_rra_journey_e2e.py`
- Create: `tests/golden/journey/*.png`
- Modify: `docs/ui/design_handoff_khepri/README.md` only to link production baselines, without altering handoff instructions

**Interfaces:**
- Uses pinned Chromium already in project.
- Proves EN/AR desktop/narrow behavior, keyboard flow, resume, deletion, and artifact access.

- [ ] **Step 1: Add semantic accessibility tests**

For every page/language assert unique IDs, accessible names, valid heading order, one main landmark,
associated labels/errors, table headers/captions, progress semantics, live-region restraint, keyboard
focus order, visible focus, 44px hit targets, reduced-motion rule, contrast token values, and no
horizontal page overflow at 390px.

- [ ] **Step 2: Add controlled visual tests**

Render each step with fixed snapshots at 1180x900 EN, 1180x900 AR, and 390x844 narrow. Disable
animation, wait for local fonts, capture PNG, and compare SHA-256 to committed baselines generated
with pinned Chromium. The review/report governance differences are documented beside baselines.

- [ ] **Step 3: Add complete real browser journey**

Against the local stack: redeem invitation fragment, consent, upload a golden CSV, confirm safe
mappings, request report, run worker, poll across reload, open all seven artifacts, delete content,
then prove every former artifact route and journey state fails closed. Repeat the presentation path
in Arabic and the upload/report pages at narrow width.

- [ ] **Step 4: Run focused browser gates**

Run:

```powershell
uv run pytest tests/test_rra_journey_accessibility.py -q
uv run pytest -m browser tests/test_rra_journey_visual.py -q
uv run pytest -m "browser and local_stack" tests/test_rra_journey_e2e.py -q
```

Expected: accessibility and visual tests pass; complete E2E passes when the declared local stack is
running and otherwise skips with the existing marker contract.

- [ ] **Step 5: Run Impeccable only as a constrained final audit**

If installed at this point, run its audit/detect commands against `src/khepri/rra/journey/`. Accept
only findings consistent with the approved handoff, screenshot baselines, accessibility rules, and
governed behavior. Do not let it redesign copy/tokens/layout.

- [ ] **Step 6: Run full repository gates**

```powershell
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

Expected: all pass, with only declared external-prerequisite skips. Inspect `git diff --check` and
confirm no external URL, prototype runtime import, local storage use, raw sample value, or
unfinished marker.

- [ ] **Step 7: Commit**

```powershell
git add tests docs/ui/design_handoff_khepri/README.md
git -c commit.gpgsign=false commit -m "test(ui): verify complete client journey"
```
