# AI model-provider foundation: what exists, what is blocked, and what is needed

Date: 2026-08-22
Status: design note. Authorizes nothing. `KHEPRI-DEC-026` is the proposal this note supports.

## Question asked

Design and implement the smallest safe AI model-provider boundary — distinct from the cloud host —
so that Khepri can later support grounded report narrative, semantic mapping assistance, and Ask
Khepri without any of them depending on OpenAI SDK or API details.

## Finding: the provider-neutral foundation already exists, and nothing should be added above it

`src/khepri/rra/narrative.py` implements `RRA-005` and already *is* the model-provider boundary.
It is not a partial version of one.

| Property the boundary needs | Where it already lives |
|---|---|
| Replaceable provider seam | `NarrativeAdapter` (`Protocol`): `adapter_version`, `draft(request, *, timeout_seconds)` |
| Bounded request contract | `_REQUEST_SCHEMA` — an allowlist *projection*, so a field added to the fact package is absent from the request until somebody names it |
| Timeout / failure / refusal / malformed | `REASON_PROVIDER_TIMEOUT`, `REASON_PROVIDER_FAILED`, `REASON_PROVIDER_REFUSED`, `REASON_ADAPTER_MISMATCH`, closed over by `GOVERNED_REASONS` |
| No provider exception leaks upward | `NarrativeService.compose` converts every exception, including unanticipated ones, into a governed reason |
| Content-free telemetry | `NarrativeAttempt` — every field is a version string, language code, reason code, or duration; there is no field a value could occupy |
| Response pinning | `NarrativeDraft.request_digest` must equal `NarrativeRequest.digest` |
| Fail closed | A refused narrative yields no prose; `DeterministicNarrator` is wired in `wiring.py`, so no provider is contacted |

Three conclusions follow.

**No shared `AIProvider` or `ModelProvider` layer should be introduced.** A generic
`generate(request) -> response` above `NarrativeAdapter` would be strictly weaker than what
exists: `NarrativeAdapter` is typed to `NarrativeRequest`, so the projection is the only way to
build one. A generic layer would accept an arbitrary payload, which is the shape `RRA-005`
forbids. Duplication across future use cases is the cheaper mistake.

**Each future use case gets its own port.** Semantic mapping and Ask Khepri differ in allowed
inputs, validation, and refusal semantics, so each owns its own request schema and validator, in
the shape `NarrativeAdapter` already demonstrates.

**Model and provider selection is genuinely missing, and it is a decision, not code.** The
`NarrativeAdapter` docstring says so directly: "A replaceable provider. Selection needs its own
architecture decision."

## Finding: implementing a concrete provider is blocked twice over, independently

### 1. Authority

- `RRA-005` requires "contractual provider controls that disable training on Khepri data and
  provider retention; final provider selection needs a separate approved architecture decision."
- `KHEPRI-DEC-008` (active) names the OpenAI Responses API as the initial adapter target and lists
  its gates: an executed data-processing agreement; explicit organization and project approval for
  Zero Data Retention; technical verification of that configuration; `store=false`; synchronous
  requests only; no provider-side state; a governed model allowlist; a pinned adapter and
  request-schema version. It states that "training opt-out without verified Zero Data Retention is
  insufficient", and that if any gate is absent the OpenAI adapter remains disabled.
- The enumerated "Follow-on obligations" of `KHEPRI-DEC-008` authorize five pieces of work.
  Writing the OpenAI adapter is not among them. In a repository that enumerates its
  authorizations, absence from that list is the signal.
- `governance/registry.yaml` holds no artifact, decision or specification, governing an AI or model
  provider. A case-insensitive search for `ai`, `openai`, `model`, `narrative`, `llm`, `semantic`,
  and `provider` matches only the two Clerk identity-provider decisions.
- The roadmap agrees. `G9/AI1` is `PROPOSED`, "Requires stable evidence contracts and
  provider/privacy authority". Task `AI1-02`, "Build provider-neutral adapter and pinned
  request/response schema", depends on `G9-02`, "Decide provider/model/data-processing/ZDR/retention
  and adapter constraints", whose stated output is an active architecture decision. `G9-03` is what
  confers "Implementation authority". None of the three exists.

Gate status, verified against the repository: no artifact records an executed data-processing
agreement, or an approved or technically verified Zero Data Retention configuration. No
`governance/` evidence directory exists. No OpenAI environment variable, secret name, or
configuration key appears anywhere in `src/` or `tests/`. The single occurrence of the word in
`src/` is the comment in `infra/network.py` explaining why egress is withheld.

The precedent for proceeding anyway is recorded and unfavourable. `#240` merged a Clerk
implementation that a post-merge audit found conformant to every boundary `KHEPRI-DEC-024` drew,
with no functional or security defect — and `#241` still had to propose `KHEPRI-DEC-025` to
authorize it, because `-024` "authorizes neither an implementation nor an assumption that the
existing schema is sufficient". Conformance is not authorization.

### 2. Dependency

`project.dependencies` in `pyproject.toml` contains no HTTP client. `httpx2` sits in
`[dependency-groups].dev` and is therefore absent from the built wheel; `botocore` is pinned for
`Config` and S3 signing, not as a general transport. A real OpenAI Responses transport would
require adding a runtime dependency, which is reserved for explicit authorization.

Two further constraints reinforce this. `src/khepri/infra/` is frozen by `KHEPRI-DEC-008`, which
closes it to new slices. And `infra/network.py` deliberately provisions no NAT gateway and no
internet route, stating that enabling narrative generation "requires adding egress deliberately,
which is a governed change rather than a configuration one".

## Architecture test

The four required questions, answered against the design as it stands on `main`:

- **Khepri on DigitalOcean with OpenAI — yes.** `KHEPRI-DEC-008` defines the runtime as a
  capability contract, and the narrative provider is a separate section of it. Neither section
  references the other.
- **Move to Hetzner, keep the provider — yes.** The host is a descriptor change. `NarrativeAdapter`
  contains no hosting concept.
- **Stay on the host, replace the provider — yes, without touching analytical logic.** A second
  adapter satisfies the same `Protocol`, and `validate` grounds the response against the request,
  so the guarantees do not depend on which provider answered. It requires a new architecture
  decision as a matter of governance, not of code.
- **Every provider disabled, deterministic calculations still authoritative — yes, and this is the
  state on `main` today.** `wiring.py` selects `DeterministicNarrator`, facts come from
  `FactPackage`, and no code path reaches a provider.

The cloud boundary and the model boundary are therefore already independent. This note adds nothing
to make them so, because nothing is needed.

## What is proposed instead

`KHEPRI-DEC-026` — affirm the existing `NarrativeAdapter` as the model-provider boundary, refuse
the generic layer above it, and fix the conditions under which a provider may later be selected and
an adapter written. It selects no provider and authorizes no implementation by itself: the
provider-evaluation artifact `G9-02` owes must record bilingual grounding, latency, refusal, and
privacy-gate evidence first, and the `KHEPRI-DEC-008` gates must be recorded as satisfied.

## Deferred, and deliberately not designed here

Semantic mapping assistance, where `mapping.py` remains sole first-line authority and no seam is
added; Ask Khepri (`G9`/`AI1`); additional providers; model routing; provider fallback; and any
egress change.
