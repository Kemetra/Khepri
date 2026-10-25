# Atlassian Transition

Takes effect when merged to `main` with Constitution 3.0.0 and KHEPRI-DEC-036. Owner decision:
[Khepri - Atlassian-First Governance - Owner Decision - 2026-10-24](https://rahmaqanater.atlassian.net/wiki/spaces/KHEPRI/pages/55345155)
(page 55345155). Execution: Jira KH-43.

This document is a map and a set of conventions. It is not an approval ledger and not a registry
artifact; it grants no authority that the Constitution and registry do not.

## Where each authority lives

| Authority | Before | After | Effective boundary |
|---|---|---|---|
| Approve a product decision or specification | Owner merges it to `main`; listed in `registry.yaml` | Owner marks a Confluence page in space KHEPRI **Approved** | Records created after this change merges. Registry-listed artifacts keep their repository home. |
| Approve a repository change (code, contracts, tests, CI, governance text) | Owner merge | Owner merge (unchanged) | The merge approves the change only, never a Confluence-homed decision. |
| Index of legacy artifacts | `registry.yaml` | `registry.yaml` (unchanged), listing no Confluence record | Validator and schema unchanged, still fail closed. |
| Admit product code | Active registry specification | A primary Approved specification named in the pull request, plus any others it relies on | Registry specification governs where it applies; otherwise an Approved Confluence specification cited by page and version. |
| Execution scope, priority, Work Mode, status | Jira `SCRUM` | Jira `KH` | Jira is never proof of implementation. |
| Technical truth: code, tests, CI, security and privacy controls | GitHub | GitHub (unchanged) | Article V is unchanged; Article VII's substance is unchanged (only its approval pointer is generalized). |
| Roadmap | `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` | Confluence KHEPRI, then Atlassian Projects and Goals | From KH-22's merge: the repository file is frozen at its path as a historical record, and the Confluence Roadmap (page 7405569) is canonical. Task IDs, section 15 and section 16 keep their numbers. |

## Confluence record conventions

The minimum a Confluence record needs to carry authority:

- **Home.** A page in space KHEPRI, titled `<identifier> - <title>`.
- **Status.** Exactly one of `Draft`, `Proposed`, `Approved`, `Superseded`, shown at the top of the
  page. Only `Approved` has authority.
- **Approval.** The owner sets `Approved` with their name, the date, and the page version number
  on the page itself. An edit by an agent, or any later edit, is not approval. The cited version
  governs; a changed page needs a fresh approval.
- **Citation.** The pull request that implements a record names its page ID and version.
  Automation cannot read Confluence, so the owner checks the citation at merge. A pull request
  that cites a Confluence specification is merged only by the owner, or under a grant whose chat
  message names that page ID and version; an agent never merges on a page's own status.
- **Supersession.** The superseding page names the page it replaces and the replaced page names its
  successor. Both links are required.
- **Identifiers.** Legacy identifiers are never reused, renumbered, or deleted. A new
  Confluence record takes the `KHC-` prefix with its series (`KHC-DEC-001`, `KHC-RRA-001`, and
  onward) and states that identifier on the page. Registry identifiers never use the prefix, so
  the two homes cannot allocate the same identifier.

## Open items

- **Retiring a legacy artifact to a Confluence record.** `superseded_by` must name an active
  registry artifact of the same type, so this cannot be expressed yet. Until a later validator
  change, a legacy artifact is retired, narrowed, or corrected only by an owner-merged repository change.
- **No Confluence record exists yet for any legacy identifier.** Every row below has no
  Confluence counterpart: its current guard is retained. Nothing is converted until the owner approves a replacement.
- **Status is not machine-checked.** Whether a cited page is Approved is verified by the owner at
  merge. A slice with no citable Approved specification is not admitted (Constitution IV).
- **KHEPRI-DEC-017 and FND-001.** DEC-017's approval bullet and FND-001's registry-authority
  bullet are read as scoped by KHEPRI-DEC-036 to repository changes and the artifacts the registry
  lists. Both stay active and their bodies are unchanged.
- **This table.** It is a snapshot of `registry.yaml` at this change and is not machine-checked;
  on any conflict the registry prevails.
- **Reconciliation after merge.** Khepri Operating System, the Decisions index, space guidance, and
  the repository roadmap are updated only once this change has merged, under KH-22.

## Legacy identifier map

Every identifier in `governance/registry.yaml` at this change, with its current state and the home
of its authority after the change.

| Identifier | Type | State | Successor | Title | Home after change |
|---|---|---|---|---|---|
| `FND` | family | active |  | Platform Foundation | Repository registry (legacy, governing) |
| `RRA` | family | active |  | Retail Reporting Automation | Repository registry (legacy, governing) |
| `RCA` | family | active |  | Retail Commercial Analysis | Repository registry (legacy, governing) |
| `KHEPRI-DEC-001` | decision | active |  | Khepri authority and predecessor reference policy | Repository registry (legacy, governing) |
| `KHEPRI-DEC-002` | decision | retired | `KHEPRI-DEC-017` | Selective predecessor assessment and re-specification protocol | Repository registry (context only, not governing) |
| `KHEPRI-DEC-003` | decision | retired | `KHEPRI-DEC-014` | Retail Reporting Automation private beta boundary | Repository registry (context only, not governing) |
| `KHEPRI-DEC-004` | decision | retired | `KHEPRI-DEC-017` | Atomic approval packages and bounded implementation authority | Repository registry (context only, not governing) |
| `KHEPRI-DEC-005` | decision | retired | `KHEPRI-DEC-028` | RRA private-beta runtime and provider architecture | Repository registry (context only, not governing) |
| `KHEPRI-DEC-006` | decision | retired | `KHEPRI-DEC-029` | RRA beta benchmark workload and environment | Repository registry (context only, not governing) |
| `KHEPRI-DEC-007` | decision | retired | `KHEPRI-DEC-028` | RRA private-beta and benchmark infrastructure sizing | Repository registry (context only, not governing) |
| `KHEPRI-DEC-008` | decision | retired | `KHEPRI-DEC-028` | RRA private-beta portable runtime and target selection | Repository registry (context only, not governing) |
| `KHEPRI-DEC-009` | decision | retired |  | Standing authorization for specification milestone transitions | Repository registry (context only, not governing) |
| `KHEPRI-DEC-010` | decision | retired | `KHEPRI-DEC-017` | Spoken delegation to a named non-human authority | Repository registry (context only, not governing) |
| `KHEPRI-DEC-011` | decision | retired | `KHEPRI-DEC-017` | Constitution 1.1.0, delegation articles | Repository registry (context only, not governing) |
| `KHEPRI-DEC-012` | decision | active |  | Transformation and orchestration tooling boundary | Repository registry (legacy, governing) |
| `KHEPRI-DEC-013` | decision | retired |  | Seshat-BI analytical dependency and ownership boundary | Repository registry (context only, not governing) |
| `KHEPRI-DEC-014` | decision | active |  | Commercial boundary superseding the private-beta scope | Repository registry (legacy, governing) |
| `KHEPRI-DEC-015` | decision | active |  | Commercial identity retention under Constitution VII | Repository registry (legacy, governing) |
| `KHEPRI-DEC-016` | decision | retired | `KHEPRI-DEC-017` | Reserved set by consequence | Repository registry (context only, not governing) |
| `KHEPRI-DEC-017` | decision | active |  | Minimal Single-Owner Governance | Repository registry (legacy, governing) |
| `KHEPRI-DEC-018` | decision | retired | `KHEPRI-DEC-025` | External identity provider boundary | Repository registry (context only, not governing) |
| `KHEPRI-DEC-019` | decision | retired | `KHEPRI-DEC-023` | Commercial attachment to the opaque analysis scope | Repository registry (context only, not governing) |
| `KHEPRI-DEC-020` | decision | retired | `KHEPRI-DEC-023` | Commercial attachment to the opaque analysis scope, with the schema change it requires | Repository registry (context only, not governing) |
| `KHEPRI-DEC-021` | decision | retired | `KHEPRI-DEC-023` | Authorization to implement the commercial bridge and the RRA scoped-session entry point | Repository registry (context only, not governing) |
| `KHEPRI-DEC-022` | decision | retired | `KHEPRI-DEC-023` | Authorization to implement the commercial HTTP surface | Repository registry (context only, not governing) |
| `KHEPRI-DEC-023` | decision | active |  | Authorization for the commercial consent route | Repository registry (legacy, governing) |
| `KHEPRI-DEC-024` | decision | retired | `KHEPRI-DEC-025` | Staged external identity provider admission | Repository registry (context only, not governing) |
| `KHEPRI-DEC-025` | decision | active |  | Authorization for the merged Clerk private-beta implementation | Repository registry (legacy, governing) |
| `KHEPRI-DEC-026` | decision | active |  | Narrative model-provider selection and enabling gates | Repository registry (legacy, governing) |
| `KHEPRI-DEC-027` | decision | retired | `KHEPRI-DEC-030` | DigitalOcean FRA1 target direction | Repository registry (context only, not governing) |
| `KHEPRI-DEC-028` | decision | active |  | RRA private-beta portable runtime and DigitalOcean FRA1 target | Repository registry (legacy, governing) |
| `KHEPRI-DEC-029` | decision | active |  | RRA beta benchmark workload and environment | Repository registry (legacy, governing) |
| `KHEPRI-DEC-030` | decision | active |  | DigitalOcean FRA1 provisional non-production bootstrap authority | Repository registry (legacy, governing) |
| `KHEPRI-DEC-031` | decision | active |  | Local-only M2 rehearsal, and the two clauses it leaves unmet | Repository registry (legacy, governing) |
| `KHEPRI-DEC-032` | decision | active |  | A catalog route may construct a `ReportBundle` | Repository registry (legacy, governing) |
| `KHEPRI-DEC-033` | decision | active |  | Durable retail-content retention for the organization workspace | Repository registry (legacy, governing) |
| `KHEPRI-DEC-034` | decision | active |  | Workspace navigation convenience — pins and recent activity | Repository registry (legacy, governing) |
| `KHEPRI-DEC-035` | decision | active |  | Anchoring the RRA scope in the database — the admissible shape, and the interim acceptance | Repository registry (legacy, governing) |
| `KHEPRI-DEC-036` | decision | active |  | Atlassian-First Approval Home | Repository registry (legacy, governing) |
| `FND-001` | specification | active |  | Minimal Governance Kernel | Repository registry (legacy, governing) |
| `FND-002` | specification | retired |  | Governed Lifecycle Transitions | Repository registry (context only, not governing) |
| `FND-003` | specification | retired |  | Delegated Approval Records | Repository registry (context only, not governing) |
| `FND-004` | specification | active |  | Mechanical UI Contract Reference Index | Repository registry (legacy, governing) |
| `FND-005` | specification | active |  | CI Test-Completeness for Dependency-Gated Markers | Repository registry (legacy, governing) |
| `RRA-001` | specification | active |  | Beta Invitations and Isolated Sessions | Repository registry (legacy, governing) |
| `RRA-002` | specification | active |  | Governed File Intake and Deletion Lifecycle | Repository registry (legacy, governing) |
| `RRA-003` | specification | active |  | Retail Data Profiling and Admissibility | Repository registry (legacy, governing) |
| `RRA-004` | specification | active |  | Deterministic Retail Fact Package | Repository registry (legacy, governing) |
| `RRA-005` | specification | active |  | Grounded Arabic and English Narrative | Repository registry (legacy, governing) |
| `RRA-006` | specification | active |  | Unified Web PDF and Excel Report Bundle | Repository registry (legacy, governing) |
| `RRA-007` | specification | active |  | Reliable Report Operations and Performance Evidence | Repository registry (legacy, governing) |
| `RRA-008` | specification | active |  | Comparative and Concentration Retail Analysis | Repository registry (legacy, governing) |
| `RRA-009` | specification | active |  | Business-First Report Presentation with Separated Audit Evidence | Repository registry (legacy, governing) |
| `RRA-010` | specification | active |  | Beta Journey Presentation Maintenance | Repository registry (legacy, governing) |
| `RRA-011` | specification | active |  | Metric, Population, and Reason Catalog | Repository registry (legacy, governing) |
| `RRA-012` | specification | active |  | Governed Data-Display Component Layer | Repository registry (legacy, governing) |
| `RRA-013` | specification | active |  | Catalog Evidence Supply to the Report Surfaces | Repository registry (legacy, governing) |
| `RRA-014` | specification | active |  | Versioned No-Calculation Semantic Views | Repository registry (legacy, governing) |
| `RRA-015` | specification | active |  | Governed Chart Grammar and Report-Surface Presentation Evidence | Repository registry (legacy, governing) |
| `RRA-016` | specification | active |  | Beta Journey Visual Language Implementation Authority | Repository registry (legacy, governing) |
| `RRA-017` | specification | active |  | Row-Level Security Beneath the RRA Scope | Repository registry (legacy, governing) |
| `RRA-018` | specification | active |  | Reading the Governed Report in Place | Repository registry (legacy, governing) |
| `RCA-001` | specification | active |  | Commercial Identity, Organizations, and Authorization | Repository registry (legacy, governing) |
| `RCA-002` | specification | active |  | Commercial Application Shell and Surface Boundary | Repository registry (legacy, governing) |
| `RCA-003` | specification | active |  | Public Legal and Trust Surfaces | Repository registry (legacy, governing) |
| `RCA-004` | specification | active |  | Public Product Landing Surface | Repository registry (legacy, governing) |
| `RCA-005` | specification | active |  | Organization Workspace, Dataset Versions, Analysis History, and Deletion | Repository registry (legacy, governing) |
| `RCA-006` | specification | active |  | Organization Semantic-Query Orchestration | Repository registry (legacy, governing) |
| `RCA-007` | specification | active |  | Semantic-View Runtime Composition | Repository registry (legacy, governing) |
| `RCA-008` | specification | active |  | Executive Decision Workspace Surfaces | Repository registry (legacy, governing) |
| `RCA-009` | specification | active |  | Period Comparison Runtime Composition | Repository registry (legacy, governing) |
| `RCA-010` | specification | active |  | Commercial Shell Presentation, Navigation and Filter Implementation Authority | Repository registry (legacy, governing) |
| `RCA-011` | specification | active |  | The shell serves its own typeface | Repository registry (legacy, governing) |
| `RCA-012` | specification | active |  | The shell serves its own hero artwork | Repository registry (legacy, governing) |
