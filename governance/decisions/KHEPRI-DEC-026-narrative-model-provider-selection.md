# KHEPRI-DEC-026: Narrative model-provider selection and enabling gates

> Proposed. Not active. This document is a proposal on a branch and governs nothing until the sole
> owner merges it to `main`. It is deliberately absent from `governance/registry.yaml`; the
> registry records only `active` and `retired` artifacts, and adding a row here would assert an
> approval the owner has not given.

## Context

Khepri has a complete, provider-neutral model boundary and no authority to put a provider behind
it. Those two facts have been true simultaneously since `RRA-005` was implemented, and this
decision exists to resolve the second without disturbing the first.

### What already exists

`src/khepri/rra/narrative.py` implements `RRA-005`. It owns `NarrativeAdapter`, the `Protocol` a
provider satisfies; `_REQUEST_SCHEMA`, the allowlist projection that decides what may leave the
process; `GOVERNED_REASONS`, the closed set of outcomes a provider failure may be recorded as; and
`NarrativeAttempt`, whose every field is a version string, language code, reason code, or duration,
so the record cannot carry customer content by construction. `NarrativeService.compose` converts
every provider exception, including unanticipated ones, into a governed refusal, and `validate`
rejects a draft that states a number the request did not supply or cites an identifier it does not
contain.

`DeterministicNarrator` satisfies that `Protocol` without any provider and is what
`src/khepri/runtime/wiring.py` selects. Khepri therefore produces grounded bilingual narrative
today with no external model involved, and the deterministic facts-only path `RRA-005` and
`RRA-006` authorize is the live path rather than a fallback.

The gap is named in the code. The `NarrativeAdapter` docstring reads: "A replaceable provider.
Selection needs its own architecture decision." This is that decision.

### Why the existing authority is insufficient

`RRA-005` requires "contractual provider controls that disable training on Khepri data and provider
retention" and states that "final provider selection needs a separate approved architecture
decision."

`KHEPRI-DEC-008` carries a "Narrative provider" section forward from `KHEPRI-DEC-005`. It names the
OpenAI Responses API as the initial target and fixes the gates: an executed data-processing
agreement; explicit organization and project approval for Zero Data Retention; technical
verification of the approved configuration; `store=false` on every request; synchronous requests
only; no background mode, conversations, assistants, threads, files, vector stores, hosted tools,
extended prompt caching, or provider-side state; no raw rows, source column values, owner or
session identifiers, storage locations, secrets, or unapproved personal data; a governed model
allowlist and a pinned adapter and request-schema version; and response validation rejecting
unsupported numbers, citations, claims, or unsafe labels. It states that training opt-out without
verified Zero Data Retention is insufficient, and that if any gate is absent, revoked, or
unverifiable the adapter remains disabled.

That section describes a provider. It does not authorize writing one, and three things establish
that reading rather than assume it:

1. The enumerated "Follow-on obligations" of `KHEPRI-DEC-008` authorize five pieces of work — the
   target-selection artifact, the PostgreSQL claim-and-redrive replacement, envelope encryption,
   unlocking `config.py` from its AWS pins, and re-issuing the sizing benchmark. The narrative
   adapter is not among them.
2. `KHEPRI-DEC-008` states in its own words that the exact model snapshot "is an operational
   configuration selected through bilingual grounding, latency, refusal, and privacy-gate
   evidence". No such evidence exists, so no snapshot has been selected.
3. `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` records `G9/AI1` as `PROPOSED`, requiring
   "stable evidence contracts and provider/privacy authority", and makes the implementation task
   `AI1-02` depend on `G9-02`, whose output is an active architecture decision. `G9-03`, "Activate
   AI assistant specification", is what the roadmap marks as conferring "Implementation authority".

The comparable case is recent and instructive. `#240` merged a Clerk private-beta implementation
that a post-merge audit found conformant to every boundary `KHEPRI-DEC-024` drew, across eleven
capabilities and five absence checks, with no functional or security defect. `#241` still had to
propose `KHEPRI-DEC-025`, because `-024` "authorizes neither an implementation nor an assumption
that the existing schema is sufficient". A conformant implementation of an unauthorized capability
is an unauthorized implementation.

### The state of the gates

Nothing in the repository records any `KHEPRI-DEC-008` gate as satisfied. There is no evidence
directory under `governance/`, no artifact recording an executed data-processing agreement, and
none recording an approved or technically verified Zero Data Retention configuration. No OpenAI
environment variable, secret name, or configuration key exists in `src/` or `tests/`; the single
occurrence of the word in `src/` is the comment in `infra/network.py` that explains why egress is
withheld. `src/khepri/runtime/config.py` defines no provider, model, or narrative key.

Two mechanical constraints stand behind the governance one. `project.dependencies` in
`pyproject.toml` contains no HTTP client — `httpx2` is a `dev` group entry and absent from the
built wheel — so a provider transport cannot be written without a runtime dependency change. And
`infra/network.py` provisions no NAT gateway and no internet route, recording that enabling
narrative generation "requires adding egress deliberately, which is a governed change rather than a
configuration one". `src/khepri/infra/` is additionally frozen by `KHEPRI-DEC-008` and closed to
new slices.

## Decision

### 1. The existing boundary is affirmed, and no layer is added above it

`NarrativeAdapter` is the model-provider boundary for narrative. No shared `AIProvider`,
`ModelProvider`, or equivalent generic interface is introduced above it.

A generic `generate(request) -> response` would be strictly weaker than what exists.
`NarrativeAdapter` is typed to `NarrativeRequest`, so `_REQUEST_SCHEMA` projection is the only way
to construct an argument for it; a generic interface would accept an arbitrary payload, which is
the shape `RRA-005` prohibits. Where a future use case needs a provider, it defines its own port,
its own request schema, and its own validator. Duplication between ports is accepted deliberately
as the cheaper error.

### 2. Provider and model selection

The OpenAI Responses API is affirmed as the sole candidate target, as `KHEPRI-DEC-008` anticipated,
constrained by every gate that decision lists. It is not confirmed as the selected provider here,
and this decision deliberately stops short of that.

`KHEPRI-DEC-008` states that the model snapshot "is an operational configuration selected through
bilingual grounding, latency, refusal, and privacy-gate evidence". That evidence does not exist,
and no artifact in this repository records it. Confirming a selection on the strength of a
candidate name, while the Context of this very decision argues that missing evidence is part of why
implementation is unauthorized, would be the same error in the opposite direction. The comparable
Clerk path produced an evaluation artifact —
`docs/superpowers/specs/2026-08-14-r3-provider-evaluation-clerk.md` — before admission; the
narrative provider has no equivalent.

Selection is therefore completed by the provider-evaluation artifact that `G9-02` still owes, which
must record bilingual grounding, latency, refusal, and privacy-gate evidence against the candidate.
Until that artifact is merged, no provider is selected and no adapter may be written.

What this decision does settle, and what holds for whichever provider that evaluation confirms:
provider and model selection is expressed as operational configuration behind an allowlist, never
as a literal in application code, and a model absent from the allowlist is a refusal rather than a
default.

Changing provider, or materially changing provider data handling, requires a new or superseding
architecture decision. Changing the model within the allowlist does not, and must not alter
analytical behaviour: facts, calculations, and citations come from `FactPackage`, and `validate`
grounds every response against the request.

### 3. Fail closed, and what "disabled" means

Absent any gate, the adapter is not merely inactive but unconstructed: no configuration key
enables it, and `DeterministicNarrator` remains what `wiring.py` selects. Khepri delivers the
deterministic cited facts-only report. No silent provider call, and no automatic fallback between
providers, is authorized in either direction.

### 4. What this decision does not authorize

It does not authorize writing the adapter. Implementation requires, in addition to this decision:
the provider-evaluation artifact of §2 merged, confirming a selection on recorded evidence; the
`KHEPRI-DEC-008` gates recorded as satisfied by an artifact the owner has merged; a runtime HTTP
dependency authorized explicitly, since `project.dependencies` contains no client; and egress
authorized deliberately as `infra/network.py` requires.

It authorizes no semantic mapping assistance. `src/khepri/rra/mapping.py` remains sole first-line
authority for mapping, and no AI seam is added to the upload journey. Whether column names, labels,
or inferred types may cross a provider boundary is not settled here and must not be assumed;
transmission of raw rows or arbitrary cell values is prohibited and is not made authorizable by
this decision.

It authorizes no Ask Khepri work, which belongs to `G9`/`AI1` and needs `G9-01` through `G9-03`. It
authorizes no chat history, vector store, embedding, agent, tool, or retrieval infrastructure; no
model routing, benchmarking, arbitration, or provider fallback; and nothing commercial.

## Consequences

- The gap the `NarrativeAdapter` docstring names is closed as a matter of authority. The
  implementation gap remains open by design, behind gates whose evidence is external.
- No abstraction is added, so no code changes on merge. `main` continues to produce narrative
  deterministically, and the four portability properties hold unchanged: the host may change
  without touching the provider, and the provider may change without touching the host, because
  `KHEPRI-DEC-008` states the runtime as a capability contract and the narrative provider as a
  separate section of it.
- A model allowlist is required before an adapter exists, so the first adapter slice cannot
  introduce an unpinned model.
- The deterministic narrator is confirmed as a governed product path rather than a placeholder, and
  a report bundle remains reachable with every provider disabled.
- This decision supersedes nothing. `KHEPRI-DEC-008` remains active and unchanged; this decision
  settles the selection question that decision reserved.
