# #555 D-01: index review evidence

Collected against the scale and thresholds fixed in
`2026-10-02-555-d01-index-review.md` (committed as `1c1a2ec`, before any figure here existed).
That plan's threshold is applied unchanged. Nothing here is a production measurement: there is no
production, and every scale is an assumption stated in the plan.

## Verdict

| Candidate | Hosted scale, seq vs index (median) | Threshold | Verdict |
|---|---|---|---|
| 2. `rra_fact_packages (owner_id, package_digest)` | 32.94 ms -> 0.050 ms (99.8%, 5,241 + 2,744 buffers -> 4) | plan changes, >= 50%, >= 5 ms | **Lands** (`20261002_0035`) |
| 1. `rca_memberships (account_id)` | 1.69 / 1.94 / 2.16 ms -> 0.027 / 0.051 / 0.088 ms | plan changes, >= 50%, >= 5 ms | **Rejected**: 98% but only about 2 ms |
| 3. `rra_deletion_evidence (attempted_at)` | 97.2 ms -> 1.04 ms per pass | plan changes, >= 50%, >= 1 s per pass | **Rejected**: 96 ms saved, a tenth of the bar |

The hosted scale is the decision basis. The 10x column below is a sensitivity and decides nothing.

## Method as run

- PostgreSQL **18.4** (the only version installed; production and CI are 17). Throwaway cluster
  on port 55434, `alembic upgrade head` for the real schema, default server settings
  (`shared_buffers` 128 MB, so some reads in the packages scan came from the OS cache).
- Seeded with SQL `generate_series`, foreign-key parents skipped via
  `session_replication_role = replica` for the three tables the queries read alone;
  `rca_organizations` and `rca_accounts` seeded for real. `ANALYZE` after seeding and after every
  index create or drop.
- The SQL is what SQLAlchemy emits. A harness called the real store methods
  (`SqlOrganizationStore.memberships_for_account`, `.organizations_for_account`,
  `SqlFactPackageRepository.get_owned_package`, `SqlDeletionRepository.purge_evidence_before`) and
  the named statement `owner_memberships_for_update`, with an engine event that captured the
  statement and parameters and aborted before execution. The captured statements were then run
  under `EXPLAIN (ANALYZE, BUFFERS)` inside `BEGIN ... ROLLBACK`.
- Per arm: one first run (reported in the raw output, not used), then 11 warm runs; the median is
  reported. The candidate index was created, analysed, measured, then dropped.
- Test parameters hit seeded rows: the account owning the most organizations (`acct-0`, owning 4
  of them in the hosted seed, 6 memberships in all), the 18th-newest package, and a horizon 365
  days back (deleting the one day, about 1,500 rows, that the daily sweep would).

### Seeded sizes (hosted)

| Table | Rows | Heap |
|---|---|---|
| `rca_memberships` | 30,996 | 1.8 MB |
| `rca_organizations` / `rca_accounts` | 5,000 / 20,000 | |
| `rra_fact_packages` | 200,000 (2,000 owners x 100) | 62 MB heap; 1,693 MB with out-of-line documents of about 8 KB |
| `rra_deletion_evidence` | 549,000 (1,500 a day for 366 days) | 126 MB |

### PG 17 against PG 18 for candidate 1

PG 18's B-tree skip scan could let `account_id` lookups use the primary key
`(organization_id, account_id)`. The PG 18 planner **did not**: with about 5,000 distinct
organizations it chose a sequential scan (`Seq Scan on rca_memberships ... Rows Removed by
Filter: 30990`, and `Index Searches` absent on that node). A plan 17 cannot produce was therefore
never in the baseline, and the 18 figures stand for 17 without emulation. Whether 18 would flip to
a skip scan at other cardinalities was not tested; production runs 17, which has none.

## Captured statements

```
-- memberships_for_account
SELECT organization_id, account_id, role FROM rca_memberships WHERE account_id = $1

-- organizations_for_account
SELECT o.organization_id, o.name, o.created_at FROM rca_organizations o
JOIN rca_memberships m ON m.organization_id = o.organization_id
WHERE m.account_id = $1 ORDER BY o.name, o.organization_id

-- owner_memberships_for_update
SELECT organization_id, account_id, role FROM rca_memberships
WHERE organization_id IN (SELECT organization_id FROM rca_memberships
                          WHERE account_id = $1 AND role = 'owner')
  AND role = 'owner'
ORDER BY organization_id, account_id FOR UPDATE

-- get_owned_package (columns abbreviated)
SELECT ... FROM rra_fact_packages WHERE package_digest = $1 AND owner_id = $2

-- purge_evidence_before
DELETE FROM rra_deletion_evidence WHERE attempted_at < $1
```

## Results

Median of 11 warm runs, execution time in ms. "Index" is the candidate index.

| Statement | Beta seq | Beta idx | Hosted seq | Hosted idx | 10x seq | 10x idx |
|---|---|---|---|---|---|---|
| `memberships_for_account` | 0.019 | 0.021 | 1.694 | 0.027 | 32.825 | 0.022 |
| `organizations_for_account` | 0.040 | 0.046 | 1.939 | 0.051 | 34.145 | 0.051 |
| `owner_memberships_for_update` | 0.063 | 0.060 | 2.164 | 0.088 | 20.761 | 0.096 |
| `get_owned_package` | 0.098 | 0.014 | 32.938 | 0.050 | see note | 0.016 |
| `purge_evidence_before` | 0.854 | 0.030 | 97.239 | 1.041 | 739.194 | 8.852 |

Beta scale (147 memberships, 1,000 packages, 10,980 evidence rows): every candidate is below the
bar and candidate 1 is slightly slower with the index. Beta cannot land an index.

10x scale: 309,995 memberships, 5,490,000 evidence rows, 2,000,000 packages. **The 10x package
figure is not comparable and is not used**: to keep the seed tractable its documents were about 1
KB and stored inline, so the heap is 2.6 GB rather than 62 MB and the scan took 4.6 s. It only
shows the scan grows with the table.

### Candidate 2 (lands)

```
-- no index (hosted)                              median 32.938 ms
Gather (Workers Planned: 2, Workers Launched: 2)   Buffers: shared hit=2744 read=5241 written=94
  -> Parallel Seq Scan on rra_fact_packages        Rows Removed by Filter: 66666 (per worker)

-- with ix_cand_package_owner_digest               median 0.050 ms
Index Scan using ix_cand_package_owner_digest on rra_fact_packages
  Index Searches: 1   Buffers: shared hit=4
```

The scan above already had two parallel workers. A connection pool under load may not be granted
them, which would make the real cost higher. The index's costs: 20 MB at 200,000 rows (heap 68
MB), and inserting 20,000 rows took 375 ms without and 508 ms with it, about 6.6 microseconds a
row. Packages are written once per publication, so the write cost is negligible against a 33 ms
read saved on every historical-run read.

### Candidate 1 (rejected)

```
-- memberships_for_account, no index (hosted)     median 1.694 ms
Seq Scan on rca_memberships  Rows Removed by Filter: 30990   Buffers: shared hit=225

-- with ix_cand_membership_account                median 0.027 ms
Bitmap Heap Scan on rca_memberships -> Bitmap Index Scan on ix_cand_membership_account
  Index Searches: 1   Buffers: shared hit=8
```

The plan changes on all three statements (limb a) and the saving is 96-98% (limb b), but the
absolute saving is 1.67, 1.89 and 2.08 ms against the 5 ms bar (limb c). For
`owner_memberships_for_update` the figure is the statement's duration inside the transaction that
holds the row locks: 2.16 ms becomes 0.09 ms. The locked rows (the organizations' owner rows) are
the same with or without the index, so the lock footprint does not change; only the time the
statement spends before the locks are released does.

The sequential scan reads 225 buffers (1.8 MB) and is linear in the table. By that linearity it
would cross 5 ms at roughly 90,000 memberships; the 10x sensitivity (310,000 rows) measures
20.8 to 34.1 ms. This is recorded as the point at which to revisit candidate 1. It is not a
reason to land it at the assumed hosted scale, where the ruling is "material benefit to an actual
production query".

Not measured: the account-purge path, where `fk_rca_membership_account` (`ON DELETE RESTRICT`)
makes PostgreSQL look up memberships by `account_id` when an `rca_accounts` row is deleted. That
is a rare background path with the same scan cost per account, so it does not change the verdict
at the assumed scale.

### Candidate 3 (rejected)

```
-- no index (hosted)                              median 97.239 ms
Delete on rra_deletion_evidence
  -> Seq Scan  Rows Removed by Filter: 547500   Buffers: shared hit=9401 read=8186

-- with ix_cand_evidence_attempted                median 1.041 ms
  -> Index Scan using ix_cand_evidence_attempted  rows=1500   Buffers: shared hit=1552
```

The plan changes and the saving is 99%, but one daily sweep pass saves 96 ms against a 1 s bar,
and the sweep is background work no request waits on. At 10x (5.49 million rows, 15,000 deleted a
pass) it is 739 ms against 8.9 ms, still under the bar. The index would also add a write to every
evidence insert. Limb (d) was not measured because limb (c) already fails.

## Reproducing

The scripts were kept in the scratch directory rather than committed. They are a seed (SQL
`generate_series`, the sizes above) and a harness that captures the SQL from the real store
methods and runs the `EXPLAIN` sequence above. The numbers are not expected to repeat exactly on
other hardware; the plan shapes and the order of magnitude should.
