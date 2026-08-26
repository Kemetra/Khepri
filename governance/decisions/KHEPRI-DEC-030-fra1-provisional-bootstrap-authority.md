# KHEPRI-DEC-030: DigitalOcean FRA1 provisional non-production bootstrap authority

> Active when merged to `main`. Supersedes `KHEPRI-DEC-027`.

## Context

`KHEPRI-DEC-027` selected DigitalOcean and FRA1 as the target direction and was deliberately
narrower than the target-selection artifact `KHEPRI-DEC-008` required. Because that artifact did
not exist, its consequences state in terms that "`OPS1-02` remains blocked until the final
target-selection/environment descriptor is complete and approved", and its §4 withholds authority
to create paid resources, provision infrastructure, deploy, open beta traffic, or commit spend.

That block is now the binding constraint rather than a safeguard, and it is circular in a way the
owner rulings identify precisely. The final descriptor requires benchmark-derived sizing; the
benchmark requires a hosted target to measure; the hosted target requires provisioning; and
provisioning is blocked until the final descriptor exists. Nothing in the sequence can move first.

`KHEPRI-DEC-028` now supplies the target-selection content `KHEPRI-DEC-027` deferred — provider,
region, residency, concrete products, recovery objectives — with final sizing explicitly left to
measurement. What remains missing is the authority to create the one environment that measurement
requires.

This decision supplies exactly that authority, bounded to a provisional non-production bootstrap,
and carries `KHEPRI-DEC-027`'s bar forward for everything beyond it.

### Why supersession rather than a narrow exception

Leaving `KHEPRI-DEC-027` active alongside a separate permission would put two active decisions in
disagreement about whether `OPS1-02` is blocked. Constitution I gives each governed fact one
authoritative representation, and `AGENTS.md` fails closed on ambiguous authority. Restating the
provider, region, and residency selection here with the provisioning bar re-scoped keeps exactly
one active decision governing that fact.

## Decision

This decision supersedes `KHEPRI-DEC-027`.

### 1. Provider, region, and residency

Confirmed and carried forward unchanged.

The primary Khepri private-beta target is **DigitalOcean**, region **FRA1 (Frankfurt)**. For the
current non-paying private-beta stage, Khepri has no Middle East data-residency requirement and no
client commitment that overrides FRA1. A later provider change requires a superseding owner
decision. If a future customer contract, legal determination, or product commitment requires
another jurisdiction, that is a trigger to revisit this decision before serving that customer.

AWS `eu-central-1` remains a fallback candidate and Hetzner a later cost-optimization candidate.
Neither is an active target.

### 2. The settled architecture is confirmed, not reopened

The architecture recorded in `KHEPRI-DEC-028` and settled by the owner rulings in `#289` and `#296`
is confirmed: App Platform for both web and worker, App Platform pre-deploy jobs running
expand → deploy → contract migrations, Managed PostgreSQL 17, VPC with private database
connectivity, DigitalOcean Container Registry, App Platform runtime secrets, GitHub Actions as the
deployment execution path rather than an approval authority, Terraform plus an App Platform
specification, DigitalOcean-native plus Better Stack observability, RTO of two hours and RPO of
fifteen minutes as objectives to prove, no initial Droplets, and no Kubernetes, Kafka, Redis, or
RabbitMQ tier.

No application or domain code may branch on provider or geography; the provider choice remains an
infrastructure concern under the capability contract in `KHEPRI-DEC-028`.

### 3. What this decision authorizes

**Only a provisional non-production bootstrap**, and only after this governance transition is
merged to `main`.

Authorized: creating the DigitalOcean resources listed in `KHEPRI-DEC-028`'s product table, in
FRA1, at the provisional measurement shape below, through continuous integration, for the purpose
of producing the measurement and compatibility evidence the remaining stop-gates require.

### 4. The provisional measurement shape

The bootstrap may claim this shape and no more:

| Role | Provisional measurement shape |
|---|---|
| Web | 1 shared vCPU, 1 GiB RAM |
| Worker | 2 vCPU, 4 GiB RAM |
| Worker replicas | 1 |
| PostgreSQL | a Managed PostgreSQL 17 tier supporting PITR and private networking, at the smallest size satisfying both |

The worker starts materially above the web role because report rendering launches pinned Chromium
alongside the analytical workload, and Chromium is the largest single memory consumer and does not
shrink with dataset size. The web role performs no rendering and holds no fact package.

**These values exist only to bootstrap hosted measurement.** They are neither final capacity values
nor a beta commitment. `OPS1-09` may move them up or down from evidence, and the final values are
approved separately as described below.

### 5. What this decision does not authorize

- **Not final capacity.** No value above is a sizing decision. Final web, worker, and database
  sizing remains evidence-driven and is `OPS1-09`'s to produce from measurement.
- **Not beta authorization.** External private-beta traffic, public signup, and the client count
  and observation period remain with the separate later beta-authorization artifact, which no task
  in this sequence produces.
- **Not spend or scale beyond the provisional bootstrap.** Expanding beyond the shape in §4,
  adding roles or environments, enabling high-availability topology, or increasing tiers requires
  approved evidence and a further owner decision. `KHEPRI-DEC-027`'s bar on paid resources is
  carried forward for everything this section excludes; it is re-scoped, not lifted.
- **Not certification.** A benchmark run against the provisional shape is an exploratory
  measurement. `KHEPRI-DEC-029` fixes why: approving a final descriptor changes
  `environment_digest` and invalidates evidence produced under the provisional shape.

### 6. Gates that remain before beta authorization

Each is a verification or activation task, not a reason to reopen the architecture. In dependency
order:

1. provision only the provisional non-production environment at the §4 shape;
2. capture and record the live PostgreSQL minor version, and empirically verify DigitalOcean Spaces
   against the exact Khepri storage, deletion, and multipart contract. Spaces remains a
   **conditional** product selection until that proof exists; an incompatibility fails closed and
   reopens the storage product choice;
3. run the `OPS1-09` benchmark on the provisional target as an **exploratory** measurement;
4. approve the final environment descriptor and sizing from that measurement, then **re-run the
   governed benchmark against the final descriptor** and issue certification from that run;
5. run `OPS1-04` recovery exercises — backup and restore, deletion after restore, encryption
   read-back, worker crash, retry, and redrive — and prove the selected RTO and RPO;
6. run `OPS1-05` capacity and soak evidence;
7. complete `OPS1-06` content-free observability, alerts, dashboards, and runbooks;
8. complete release, rollback, database-migration, and incident procedures;
9. only then pursue the separate private-beta authorization artifact.

Certification refuses if the live PostgreSQL minor version differs from the recorded value, per
`KHEPRI-DEC-028` and `KHEPRI-DEC-029`.

## Alternatives not selected

- Leaving `KHEPRI-DEC-027` active and adding a separate narrow permission was not selected because
  it would leave two active decisions disagreeing about whether `OPS1-02` is blocked.
- Waiting for the final descriptor before authorizing any provisioning was not selected because it
  is circular: the descriptor requires benchmark-derived sizing, the benchmark requires a hosted
  target, and the target requires provisioning.
- Authorizing the full beta environment at final capacity was not selected because no measurement
  exists to size it, so any value chosen now would be invented rather than evidenced.
- Treating the provisional run as governed certification was not selected because approving the
  final descriptor invalidates evidence measured under the provisional shape, which would leave
  every downstream exercise resting on evidence its own governance had already invalidated.

## Consequences

- `OPS1-02` is unblocked for the provisional non-production bootstrap only, and remains blocked for
  anything beyond the §4 shape.
- Exactly one active decision governs the provider, region, residency, and provisioning authority.
- The circular dependency between descriptor, benchmark, and environment is broken at the point the
  owner rulings identified, without conceding final capacity or beta authorization.
- Provisional resources incur cost from the moment they exist. That is accepted deliberately as the
  price of measurement, bounded by the §4 shape and by the requirement that anything larger needs a
  further decision.
- `KHEPRI-DEC-027` moves to `retired`, retaining its evidence unchanged.
- No external traffic is authorized by this decision, and none may be opened on the strength of it.

## Evidence

- `KHEPRI-DEC-028`: active runtime target and capability contract, and the DigitalOcean FRA1
  target-selection content.
- `KHEPRI-DEC-029`: active benchmark authority, the `environment_digest` discipline, and the
  exploratory-versus-certification rule.
- `#243`: OPS1 provider portability and target-selection analysis, recommending DigitalOcean FRA1.
- `#251`: provider-portable object storage with application-side envelope encryption.
- `#289` and `#296`: the owner rulings settling the environment direction and the transition
  sequence this decision implements.
- Owner approval of the DigitalOcean FRA1 direction recorded on `#243` on 2026-08-23.

Identity, lifecycle state, dependencies, and supersession are authoritative in
`governance/registry.yaml`. Git history retains the transition evidence.
