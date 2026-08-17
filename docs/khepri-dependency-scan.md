# Khepri dependency scan: unbuilt obligations and what closes them

- Drafted at: 2026-08-17
- Base commit: `086b960` on `main`. Drafted against `9bfae82` and rebased twice; the intervening
  commits (`#204` superseding `KHEPRI-DEC-019`, `#205` adding migration `0017`, `#207` adding
  tests only) were checked against the counts below and change none of them — `0017` introduces
  no raw SQL, so the three-of-seventeen figure in the SQL-linting section still holds.
- Inputs: `governance/decisions/KHEPRI-DEC-008-rra-portable-runtime-target.md`,
  `governance/decisions/KHEPRI-DEC-012-transformation-and-orchestration-boundary.md`,
  `pyproject.toml`, `src/khepri/rra/storage.py`, `src/khepri_gov/validator.py`,
  `migrations/versions/`, `.github/workflows/`
- Status: **advisory research, not a governed artifact.** It approves nothing, records no
  approval, creates no authority, and authorizes no implementation. Identity, lifecycle state,
  dependencies, and supersession are authoritative in `governance/registry.yaml`.

## Why this scan is shaped the way it is

The question asked was which external projects would benefit Khepri. Answered literally that
produces noise here, for a structural reason rather than a matter of taste.

`KHEPRI-DEC-008` does not describe an application stack loosely; it enumerates one, closing with
a clause carried verbatim from `KHEPRI-DEC-005:36`:

> No separate SPA, Node.js runtime, Redis, data warehouse, notebook runtime, or microservice
> boundary is introduced for the private beta.

`KHEPRI-DEC-012` then records how additions are actually treated. The owner asked directly about
dbt and Dagster; both were refused with a written cost-benefit, and a standing refused list was
recorded that a later boundary decision does not reopen.

So candidates were filtered against gaps the governance itself names, and each gap was verified
against `src/` before research was commissioned. The finding is that **the beneficial results are
obligations Khepri already owns and has not built** — not new territory. No recommendation below
requires superseding an accepted decision.

One early false positive is recorded so it is not rediscovered: a search for `envelope` matches
`src/khepri/rca/credentials.py:52`, where the string is OpenSSL's error text in a comment
explaining why `hashlib.scrypt` needs an explicit `maxmem`. That is a sound standard-library
choice, not a gap.

## Gap register

| Gap | Source | Verified status | Recommendation | New dependency |
|---|---|---|---|---|
| Envelope encryption | `KHEPRI-DEC-008` follow-on | Unbuilt; five provider proofs still asserted | Add `cryptography` | Yes |
| Fact and formula catalog | `KHEPRI-DEC-012`, named gap | Absent | Build with Jinja2 | No |
| OpenTelemetry / OTLP | `KHEPRI-DEC-008` observability | Unbuilt; no references in `src/` | Core only, no auto-instrumentation | Core only |
| Migration-safety linting | `infra` group precedent | No lock analysis in CI | Squawk, once blocked path is resolved | No |
| Pre-merge dependency scan | `infra` group precedent | `image.yml` scan skips pull requests | `osv-scanner` | No |
| SBOM generation | — | Produced during the scan | Already solved by `uv` | No |
| Dependency licence checking | — | No lockfile-native tool exists | **Uncovered** | — |
| SQL style linting | — | 3 of 17 migrations use raw SQL | Skip | No |
| YAML registry validation | — | `validator.py` read in full | Keep what exists | No |

## Envelope encryption

`KHEPRI-DEC-008` requires a per-object AES-256-GCM data key, wrapped by a master key drawn from
the secret store, with the ciphertext digest verified on read-back. The decision states why: no
S3-compatible store outside AWS can satisfy the five provider proofs the code demands.

Those proofs are still in place. `src/khepri/rra/storage.py` is 259 lines built around them —
`ServerSideEncryption="aws:kms"` at line 96, `SSEKMSKeyId` at line 97, `BucketKeyEnabled=True` at
line 99, and their verification at lines 164 and 255-257.

**A sequencing observation.** Line 15 pins `r"^arn:aws:kms:me-central-1:\d{12}:"`, hardcoding
region and account. Unlocking that is a *separate* `KHEPRI-DEC-008` follow-on. Both obligations
touch the same module, so sequencing them together avoids two passes over the same code.

### A dependency is unavoidable

Python 3.13's complete cryptographic surface is `hashlib`, `hmac`, and `secrets`. There is no
cipher module and no AEAD. An empirical probe against the pinned 3.13.12 interpreter found no AES
attributes on `ssl` or `_hashlib`; `ssl` encrypts TLS sessions, never a caller-supplied key.
Hand-rolling AES-GCM in pure Python is not a real option for a product whose value is
defensibility.

### Candidates

| | `cryptography` | `pycryptodome` | `tink` |
|---|---|---|---|
| Licence | `Apache-2.0 OR BSD-3-Clause` | `"BSD, Public Domain"`, not valid SPDX | `Apache-2.0` |
| Last release | 2026-07-31 | 2025-05-17 | 2026-08-13 |
| AES-256-GCM | `aead.AESGCM` | `AES.MODE_GCM` | yes |
| RFC 3394 key wrap | `keywrap.aes_key_wrap` | `MODE_KW` | none documented |
| Dependency closure | 3 packages | 1 package | 4, including protobuf |

`cryptography` carries both primitives the decision names in one library. A 32-byte data key is a
multiple of 8, so plain RFC 3394 applies with no padding variant.

`tink` is refused on architecture rather than quality: its envelope path is KMS-bound, which is
the coupling `KHEPRI-DEC-008` exists to sever, and it documents no RFC 3394 primitive.

`pycryptodome` wins the dependency-closure criterion outright, one package against three. It
ranks second only because closure was weighted below security track record and maintenance, and a
fifteen-month release gap loses both. The weighting is recorded here because reversing it
reverses the answer.

### Consequence to record

The `cryptography` wheel statically links its own OpenSSL, adding roughly 4-5 MB. A CVE in that
copy is patched by bumping a Python package rather than by rebuilding from a newer base image
(precedent: GHSA-h4gh-qq45-vh27, affecting wheels 37.0.0 through 43.0.0).

That matters here specifically. `src/khepri/infra/image.py:5` records that `environment_digest`
covers the image record, and `src/khepri/infra/database.py:12` states the same principle for the
database engine — an upgrade must not change what runs underneath an approved digest. A
dependency whose security patches arrive through the Python manifest is a second patching path,
and is better written down now than discovered during an incident.

Build impact is small: the base image is Debian noble and glibc, so the `abi3-manylinux_2_28`
wheel installs directly. Rust and C toolchains are build-phase only and are not invoked when
installing from a wheel, so `uv sync --frozen` needs no compiler.

No published third-party security audit of `cryptography` was located. Recorded as unverified.

## Fact and formula catalog

`KHEPRI-DEC-012` names this as the one dbt discipline Khepri lacks, frames it as a catalog gap
rather than a discipline gap, states it is achievable without dbt, and scopes it as an internal
asset. Versioned transformations, tests-as-contracts, and lineage are all present under other
names.

**Recommendation: build it with Jinja2 and add nothing.** This was tested rather than argued. A
spike against the real `khepri.rra.facts` module rendered a fact table from `dataclasses.fields()`
and a citation-lineage graph as inline static SVG, using rank-by-depth layout in roughly forty
lines of standard library. Output was 3280 bytes with no `<script>` element and no external
references. Jinja2 and MarkupSafe are already pinned runtime dependencies.

Three findings support this over the alternatives.

**`pdoc` does not close the gap.** It is an API-reference generator. In testing it surfaced
`citation_id` only because that is a field name in a class signature; it has no concept of facts,
formulas, or citations, and renders no lineage graph. Reaching the artifact means `pdoc` for
schema plus `erdantic` for graph plus glue — fourteen added packages — against glue alone.

**A packaging trap.** `khepri_gov` ships in the wheel (`pyproject.toml:55`). Adding a catalog
subcommand to the `khepri-gov` CLI drags the generator's imports into the OCI image unless the
import is lazy or the generator lives outside the wheel. That runs against the discipline the
manifest documents at lines 56-64, where `src/khepri/local` is excluded deliberately. The Jinja2
approach sidesteps it, since Jinja2 is already a runtime dependency and a CI-invoked generator
need not be a CLI subcommand.

**Data-catalog frameworks are disqualified as a category.** DataHub, OpenMetadata, Amundsen, and
Marquez are server applications — JVM services, search indexes, message queues, and in DataHub's
case a React SPA. Each is the microservice boundary `KHEPRI-DEC-005:36` excludes. dbt-docs, the
analogy `KHEPRI-DEC-012` itself draws, is a JS SPA requiring dbt and a warehouse.

If the library is wanted later, `erdantic` (MIT, dataclass-native, eleven packages, development
group) rendered `Fact` and `FactPackage` correctly and needed no system Graphviz, since the cp313
`pygraphviz` wheel bundles the binaries. The trigger is specific: reach for it when the citation
graph is dense enough that naive rank-by-depth layout produces edge crossings.

**The gate is governance, not packages.** The dependency verdict is that none is required, which
is not the same as unblocked. `KHEPRI-DEC-012` places this gap outside its own boundary, and
`README.md` states that active product work must link to an active specification. Closing it
requires either a specification linkage or an explicit determination that a continuous-integration
documentation job is tooling rather than product work. That is the gate, and this document does
not settle it.

## OpenTelemetry

`KHEPRI-DEC-008` requires OTLP traces and metrics and enumerates what telemetry may carry —
opaque correlation identifiers, stage names, state transitions, durations, queue time, retries,
provider latency, dataset-size bands, output sizes — and what it excludes: filenames, labels,
source values, narrative, facts, invitations, tokens, object locations. `RRA-007` requires
evidence to be content-free.

**Recommendation: `opentelemetry-api`, `opentelemetry-sdk`, and one OTLP exporter. No
`opentelemetry-instrumentation-*` package.**

Auto-instrumentation violates the guarantee by default:

- `opentelemetry-instrumentation-dbapi`, used by both the psycopg and SQLAlchemy instrumentation,
  calls `_set_db_statement(...)` unconditionally on every query with no gating flag, placing raw
  SQL text on spans. The adjacent `capture_parameters` flag, default `False`, governs only bound
  parameter values and is not a master switch.
- `opentelemetry-instrumentation-asgi`'s `collect_request_attributes()` explicitly appends the
  decoded query string to the captured URL.
- `enable_commenter` is frequently mistaken for a redaction control. It is the opposite: it
  injects trace context into outgoing SQL.

### The asymmetry that decides it

| Signal | Allow-list primitive |
|---|---|
| Metrics | Yes — `View(attribute_keys={...})`, deny-by-default, in the stable 1.x SDK |
| Traces | None — `SpanProcessor.on_end` receives a read-only `ReadableSpan` by specification design |

The content-bearing attributes live on traces, which is exactly where no allow-list exists. Every
trace-side mitigation is bespoke: a custom `on_start` processor keyed to whatever attribute names
each instrumentation version emits, an exporter wrapper filtering after the fact, or
environment-variable deny-lists. On the last, upstream issue
`open-telemetry/opentelemetry-python-contrib#3906` records an end user calling them "inherently
insecure," since one missed pattern leaks silently.

This compounds with the dependency-pinning policy. Core packages are stable at 1.44.0 with an API
commitment; every instrumentation package is `0.65b0`, pre-1.0, and the set of captured span
attributes is explicitly outside any stability contract. A deny-list correct today can be
silently defeated by a patch bump — converting a structural guarantee into a filtering
obligation. `KHEPRI-DEC-012` refused Dagster partly on this reasoning, observing that adding a
component which requires a redaction layer "converts a structural guarantee into a filtering
obligation." The precedent is Khepri's own.

### Exporter selection

Use the specific package; the `opentelemetry-exporter-otlp` meta-package depends on both
transports. The HTTP/protobuf exporter closes over fourteen packages, all pure Python, but pulls
`requests`, which is not currently in the stack. The gRPC exporter closes over ten but includes
`grpcio`, a compiled binary wheel. HTTP is the leaning choice, and one open question favours it:
gRPC fork-safety alongside the separate worker process role is unverified.

Manual instrumentation costs the free FastAPI, SQLAlchemy, and Psycopg spans. It buys the
property the decision describes: every attribute reaching a span is one the code wrote, so
nothing can silently begin emitting SQL text on an upgrade.

## Migration-safety linting

Squawk is a strong match — `Apache-2.0 OR MIT`, v2.62.0 released 2026-08-06, built on
`libpg_query`, with roughly thirty-five DDL-hazard rules including
`require-concurrent-index-creation`, `adding-field-with-default`, `ban-drop-column`,
`renaming-column`, and `constraint-missing-not-valid`. Nothing in continuous integration performs
semantic migration-lock analysis today.

It installs from PyPI as `squawk-cli`, a prebuilt wheel, so despite being written in Rust it needs
no Rust toolchain and can sit in a dependency group. The correct home is `dev`, beside `ruff` and
`pytest`; `infra` is scoped explicitly to AWS CDK at `pyproject.toml:44-49`. Note that
`default-groups = ["dev", "infra"]` means anything added to `dev` installs on every plain
`uv sync`.

**It is blocked today.** Squawk lints SQL, which Alembic must render through offline `--sql` mode.
This repository cannot render it:

```
$ uv run alembic upgrade head --sql
AttributeError: 'NoneType' object has no attribute 'fetchall'
  File "migrations/versions/20260814_0013_rca_membership_events.py",
    line 86, in _backfill_creation_events
```

Offline mode never opens a connection, so `op.get_bind()` yields a bind whose `execute(...)`
returns `None`. The migration is doing something legitimate — reading existing memberships to
reconstruct events for them, with identifiers derived from membership identity so that a
downgrade-and-replay cannot double-write. This is Alembic declining to render any migration that
reads results back, not a tool limitation and not a defect in the migration.

Migrations `0001` through `0012` render cleanly; `0013` is the first failure. Whether `0014` and
`0015` also fail is unverified, because the render aborts before reaching them.

Adoption therefore requires two decisions before any configuration change:

1. Lint the pull-request delta rather than `head` from scratch —
   `alembic upgrade <prev_head>:<new_head> --sql`. History needs linting once, and cannot be
   rendered in any case.
2. Agree an escape hatch for migrations that read results back. Without one, the first backfill
   migration after adoption breaks continuous integration.

Rule tuning is also likely, since rendered output carries Alembic's own `BEGIN`, `COMMIT`, and
`UPDATE alembic_version` statements. That is unverified; it requires installing and running the
tool.

Alternatives: `migration-lint` (PandaDoc) is pure Python, MIT, and the only Alembic-aware
candidate, but was last pushed 2025-09-11, has one contributor, and pulls SQLFluff transitively.
`django-migration-linter` is ruled out on framework mismatch. `strong_migrations` is Ruby and
Rails-only.

## Supply chain, SBOM, and licences

**`osv-scanner` closes a real gap.** Google, Go, `Apache-2.0`, v2.5.0, with native `uv.lock`
parsing. It is additive rather than duplicative for a specific reason: `.github/workflows/image.yml`
gates its ECR scan `if: github.event_name != 'pull_request'`, so it never runs on a pull request.
A lockfile scan in the governance workflow supplies pre-merge dependency coverage that does not
exist today. Trivy has native support since v0.59.0 and would work technically, but overlaps the
existing scanner's role.

**`uv audit` is real and absent from this toolchain.** PyPA now defers to it: `pip-audit` issue
#1077 was closed `NOT_PLANNED` on 2026-07-13, its maintainer stating uv support is out of scope
and pointing at `uv audit`. But the installed toolchain is `uv 0.10.7 (2026-02-27)`, and
`uv audit --help` returns `error: unrecognized subcommand 'audit'`. Continuous integration pins
`astral-sh/setup-uv` by commit SHA across all four jobs in `governance.yml`. The recommendation is
therefore to upgrade uv, after which lockfile vulnerability scanning costs nothing further. It
remains preview, so it belongs as an advisory, non-blocking step; gating a fail-closed release on
a preview tool's false positive would be the wrong trade. The exact release introducing the
subcommand is unverified beyond the 0.11.x line.

**SBOM generation needs no tool.** `uv export --format cyclonedx1.5` was run during the scan and
produced a valid CycloneDX 1.5 SBOM directly from `uv.lock`. It is flagged experimental and wants
`--preview-features sbom-export` to silence the warning. This moots `cyclonedx-py`, whose uv
support remains an open unimplemented request.

**Licence checking is the one genuine hole.** Trivy does not populate licence fields for
uv-managed dependencies; `uv audit` covers vulnerabilities rather than licences; Safety's licence
output is premium-only; `pip-licenses` reads installed-environment metadata through
`importlib.metadata` and so requires a synced virtual environment rather than the lockfile. The
only routes are `uv sync` followed by `pip-licenses`, or a script parsing licence data out of the
CycloneDX SBOM. Both are integration work rather than a dependency-group entry.

Two tools were miscategorised in the original research brief and are corrected here. `deptry` is a
dependency-hygiene linter, not a vulnerability scanner; its DEP003 check maps onto a discipline
this repository already practises by hand at `pyproject.toml:12-18`. Safety's code is MIT, but its
service is account-gated, with a free tier its own pricing marks as not recommended for commercial
purposes.

## Two areas where the answer is to keep what exists

**SQL style linting: skip.** The verdict turned on how much raw SQL the migrations contain, so
they were counted: three of seventeen files, seven occurrences, in `0012`, `0013`, and `0014`. The
migrations are ORM-dominant. `sqlfluff` is well-maintained and real, but lints SQL text for style
and carries thin Postgres safety rules; it does not overlap Squawk and would have almost nothing
to work on here.

**YAML registry validation: redundant.** Reading `src/khepri_gov/validator.py` corrects a premise
carried through the research: the validator uses no Pydantic at all, validating by hand against
`Mapping` and `dict` types, even though `pydantic>=2.11,<3` is a direct dependency. Avoiding it
was a choice, not an oversight.

The schema is small — two top-level fields, five artifact fields, two vocabularies. The
load-bearing logic is domain-specific: `_validate_family_links`, `_validate_supersession`, and the
successor-must-be-active rule. No generic schema language expresses "a superseded document's
successor must itself be in the active state," so that logic stays imperative whatever validates
the surface shape. `jsonschema`, Cerberus, voluptuous, yamale, and strictyaml would each replace
the easy half and leave the hard half untouched, at a cost in type safety.

One zero-dependency simplification exists and is deliberately not recommended: cycle detection is
a hand-rolled depth-first search (`_CycleFinder`, `_find_cycle`) where `graphlib.TopologicalSorter`
would serve. It is not a drop-in — `tests/test_governance_validator.py::test_dependency_cycles_are_rejected`
asserts the literal string `registry: dependency cycle: FND -> FND-001 -> FND`, and
`graphlib.CycleError` orders nodes in the predecessor direction. The registry is small enough that
recursion depth is not a risk, and working, tested, governance-critical code is not worth churning
for the change.

## Carried as unverified

- Grype's `uv.lock` support, inferred from syft cataloger sharing rather than stated in its own
  documentation. One `grype dir:.` run would settle it.
- The exact `uv` release introducing the `audit` subcommand.
- Whether migrations `0014` and `0015` also break offline rendering.
- Whether Squawk needs rule tuning against Alembic's bookkeeping statements.
- gRPC exporter fork-safety alongside the separate worker process role.
- Any published third-party security audit of `cryptography`.

## What needs a decision rather than further research

1. The catalog's specification linkage. `KHEPRI-DEC-012` places the gap outside its own boundary,
   and `README.md` requires active product work to link to an active specification.
2. The Squawk escape hatch for migrations that read results back, together with pull-request-delta
   rather than full-history linting.
3. Whether dependency licence compliance is a requirement. If it is, it is the one area with no
   clean answer and real integration work.
