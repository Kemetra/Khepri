# KHEPRI-DEC-027: DigitalOcean FRA1 target direction

> Active when merged to `main`. This decision records the owner's provider, region, and current-stage residency selection for OPS1. It does not by itself satisfy every field `KHEPRI-DEC-008` requires of the final target-selection artifact and therefore does not authorize provisioning, deployment, beta launch, or spend.

## Context

`KHEPRI-DEC-008` makes the private-beta runtime provider-portable and deliberately leaves provider, region, residency, sizing, and environment details to a separate owner-approved target-selection artifact. The OPS1 analysis merged in `#243` evaluated the available targets and recommended DigitalOcean in FRA1 (Frankfurt), with AWS `eu-central-1` second and Hetzner deferred as a later cost optimization.

Since that analysis, `#251` implemented the application-side envelope-encryption and storage-portability work that had been the main technical blocker to running outside AWS. The storage boundary is therefore no longer a reason to postpone the provider choice.

The repository owner explicitly approved the DigitalOcean / FRA1 direction on 2026-08-23 and recorded that approval on `#243`.

## Decision

### 1. Provider and region

The primary Khepri private-beta target is **DigitalOcean**, region **FRA1 (Frankfurt)**.

This is the default target against which the remaining OPS1 environment descriptor, sizing, recovery evidence, and deployment work are prepared. A later provider change requires a superseding owner decision.

### 2. Residency

For the current non-paying private-beta stage, Khepri has **no Middle East data-residency requirement** and no current client commitment that overrides FRA1. The selected target therefore places the private-beta runtime and provider-managed data in the EU / Frankfurt region, subject to the concrete service-level storage locations recorded in the final environment descriptor.

If a future customer contract, legal determination, or product commitment requires another jurisdiction, that is a trigger to revisit this decision before serving that customer.

### 3. This decision is intentionally narrower than the final target-selection artifact

`KHEPRI-DEC-008` requires the final target-selection artifact to record more than provider and region, including concrete products and exact versions, object-storage semantics, RTO and RPO, and sizing values. Those values are not invented here.

The following remain unresolved and therefore remain stop-gates before provisioning:

- concrete DigitalOcean product selections and exact versions where applicable;
- acceptance and mitigation of provider-managed PostgreSQL minor upgrades;
- the envelope-master-key secret source;
- the egress/VPC posture and whether any dependency requires IP allowlisting;
- owner-approved RTO and RPO targets;
- worker/web/database sizing derived from the governed benchmark rules;
- any remaining operational defects identified by the OPS1 analysis that would make a provisioned environment unsafe or non-recoverable.

### 4. No deployment or spend authority

This decision authorizes planning and preparation against DigitalOcean / FRA1. It does **not** authorize creating paid resources, provisioning infrastructure, deploying Khepri, opening beta traffic, or committing spend.

Those actions require the complete target-selection/environment descriptor required by `KHEPRI-DEC-008`, with the remaining stop-gates resolved and separately approved by the owner.

## Consequences

- OPS1 no longer treats provider, primary region, or current-stage residency as open owner questions.
- DigitalOcean / FRA1 becomes the reference target for remaining portability verification, environment design, benchmark sizing, recovery targets, and deployment planning.
- AWS `eu-central-1` remains a fallback candidate, not an active target.
- Hetzner remains a later cost-optimization candidate, not an active target.
- No application or domain code may branch on provider or geography; the provider choice remains an infrastructure concern under the capability contract in `KHEPRI-DEC-008`.
- `OPS1-02` remains blocked until the final target-selection/environment descriptor is complete and approved.

## Evidence

- `KHEPRI-DEC-008`: active portable runtime capability contract and target-selection requirement.
- `#243`: OPS1 provider portability and target-selection analysis, recommending DigitalOcean / FRA1.
- `#251`: provider-portable object storage with application-side envelope encryption.
- Owner approval recorded on `#243` on 2026-08-23.
