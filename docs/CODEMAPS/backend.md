<!-- Generated: 2026-09-27 | Files scanned: 310 | Token estimate: ~950 -->
# Backend (FastAPI)

App assembled in `runtime/wiring.py:build_web_app` — `rra.api.create_app` then `add_*_routes` in order:
commercial → beta_membership_guard (middleware) → external_auth → session_end → legal → landing → shell.

## Beta API — /api/v1/beta (invite-bound beta session cookie)
```
POST   /sessions/redeem              rra/api.py        → invitations.redeem → rra.sessions
POST   /consent                      rra/api.py
POST   /uploads                      rra/api.py        → intake → storage (S3, envelope)
POST|GET /profile                    rra/api.py        → profiling (profile_request)
POST|GET /facts                      rra/api.py        → packages / facts
DELETE /content                      rra/api.py        → deletion
GET    /coverage/completeness        rra/coverage_api.py
POST   /reports                      rra/report_api.py → report_services → jobs (queued)
GET    /reports/{job_id}[/bundle]    rra/report_api.py
GET    /reports/{job_id}/surfaces/{web|evidence|pdf}/{lang} | /excel
GET    /catalog/{metrics|populations|reasons|caveats|quality|citations…}   rra/report_api.py
```
Journey pages: `GET /beta/{lang}`, `/beta/{lang}/{step}`, `/beta/assets/{name}` + JSON `/api/v1/beta/journey` (rra/journey/routes.py).

## Commercial API — /api/v1/commercial (rca session cookie `cse_…`)
```
POST /analyses | GET /analyses/{sid} | POST /analyses/{sid}/consent   runtime/commercial_api.py
POST /auth/session  | /auth/recovery                                   runtime/external_auth_api.py (Clerk)
POST /auth/logout                                                      runtime/session_end_api.py
```

## Shell — /app (server-rendered Jinja)
```
GET  /app/{path:path}      shell_api.py dispatcher → surfaces overview|data|analyses|team (_WORKSPACE_SURFACES)
GET  /app/{lang}/{org}/decisions/{source}                    shell_decisions.py → rca.workspace.decision.*
GET  /app/{lang}/{org}/analyses/compare/{subject}/{baseline} shell_comparison.py → comparison_assembly/operands
POST /app/{lang}/{org}/analyses                         shell_journey_entry.py
POST …/analyses/compare                                 shell_comparison.py
POST …/analyses/{run_id}/artifacts/{kind}               shell_artifact_handoff.py
POST …/data/{version_id}/delete                         shell_deletion.py → workspace_deletion
POST …/{surface}/{id}/pin|unpin                         shell_pins.py
POST …/switch                                           shell_switching.py (active org)
POST …/team/invitations[/…]                             shell_invitations.py → rca.invitation_service
```
Public: `GET /landing/{lang}`, `/legal/{lang}/{page}` (+ `/assets/{name}` each).

## Worker
```
runtime/worker.py ClaimWorkerLoop ─► rra/claim_queue.ClaimingReportQueue (lease, attempts, dead-letter)
  ─► rra/worker.ReportWorker ─► rra/pipeline.ReportPipeline
       ports: SessionFactPackageSource, DeterministicNarrator, [Html, Pdf, Excel] renderers, publisher
  ─► runtime/pipeline_recording + workspace_recording (write rca_workspace_* rows)
Retention: runtime/retention_sweep.py (khepri-retention-sweep) → *_retention modules in rra/rca
```

## Service → persistence
```
rca.session_service     → rca.session_persistence      (rca_sessions)
rca.invitation_service  → rca.invitation_persistence   (rca_invitations)
rca.organizations/accounts → rca.persistence           (rca_accounts, orgs, memberships, scopes)
rca.workspace.store     → rca.workspace.schema/persistence (rca_workspace_*)
rra.jobs/claim_queue    → rra.job_persistence          (rra_report_jobs, attempts)
rra.packages/facts      → rra.persistence              (rra_fact_packages, profiles, uploads)
rra.artifact_publication→ rra.artifact_persistence     (rra_report_artifacts)
rra.deletion            → rra.deletion_persistence     (rra_deletion_jobs/evidence)
rra.telemetry_service   → rra.telemetry_persistence    (rra_operational_events, content-free)
```

## Largest files (hotspots)
rra/facts.py 2657 · rra/bundle.py 2400 · rra/rendering/wording.py 1972 · rra/narrative.py 1563 ·
rca/persistence.py 1427 · runtime/shell_decisions.py 1200 · rra/report_api.py 1095 · rra/rendering/html.py 1062
