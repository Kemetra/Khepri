<!-- Generated: 2026-09-27 | Files scanned: 310 | Token estimate: ~750 -->
# Data

PostgreSQL 17 (SQLAlchemy 2 Core + psycopg3), Alembic migrations in `migrations/versions/`.
Object store: S3 (MinIO locally), objects envelope-encrypted (AES-GCM, `rra/envelope.py`, v2 binds AAD).
Tests default to SQLite; concurrency contracts need PostgreSQL (`-m concurrency`).

## RCA tables (identity & workspace)
```
rca_accounts ─┬─< rca_memberships >── rca_organizations
              ├─< rca_external_identities (Clerk)
              ├─< rca_sessions (cse_…, active_organization)
              └─< rca_membership_events
rca_isolation_scopes (owner_id)  ◄── every rca_workspace_* row keys on owner_id
rca_invitations (inv_…, token kci1) · rca_recovery_security_events
rca_workspace_dataset_versions ─< rca_workspace_source_profiles
rca_workspace_analysis_runs ─┬─< rca_workspace_run_reports
                             ├─< rca_workspace_run_provenance
                             └─< rca_workspace_artifact_bindings
rca_workspace_pins · rca_workspace_revocations · rca_workspace_tombstones · rca_workspace_audit_events
```
Schema DDL: `rca/workspace/schema.py` (1005 LOC); stores: `rca/persistence.py`, `rca/workspace/store.py`.

## RRA tables (analysis pipeline)
```
rra_beta_sessions (session_id, owner_id) ─┬─< rra_uploads
                                          ├─< rra_dataset_profiles
                                          ├─< rra_fact_packages
                                          └─< rra_report_jobs ─┬─< rra_report_job_attempts
                                                               └─< rra_report_deliveries ─< rra_report_delivery_surfaces
rra_report_artifacts (→ deliveries/bundle) · rra_deletion_jobs ─< rra_deletion_evidence
rra_invitations (beta) · rra_operational_events (content-free telemetry)
```

## Migration history
```
0001-0009  2026-07-29/30  rra: sessions, uploads, deletion, profiles, fact packages, jobs, events, dead letter, deliveries
0010-0019  2026-08-12/21  rca: identity spine, lifecycle, artifacts, memberships, sessions+external ids, invitations, recovery
0020       2026-08-22     portable object encryption
0021-0029  2026-09-04/06  rca workspace: runs, audit, reports, provenance, family versions, deletion audit, revocations, sweep, pins
0030       2026-09-15     workspace content retention
0031-0034  2026-09-25/26  package profile scope, session active org, profile upload SET NULL + scope
```
Naming: `YYYYMMDD_NNNN_<family>_<topic>.py`. Local memory: new derived tables need a transition rule for pre-migration rows.
