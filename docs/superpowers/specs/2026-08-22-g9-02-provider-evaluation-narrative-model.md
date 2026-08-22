# Provider evaluation — narrative model provider against `KHEPRI-DEC-008` gates

Date: 2026-08-22
Task: `G9-02` — decide provider, model, data-processing, ZDR, retention, and adapter constraints.
Status: evaluation in progress. Authorizes no code. Four gates remain open and are procurement
items, not findings.

## What this document is for

`KHEPRI-DEC-008` names the OpenAI Responses API as the initial narrative adapter target and makes
it "subject to all of the following gates". `KHEPRI-DEC-026` affirms that boundary but deliberately
selects no provider, because `KHEPRI-DEC-008` also states that the model snapshot "is an
operational configuration selected through bilingual grounding, latency, refusal, and privacy-gate
evidence" and no such evidence exists. This document is where that evidence is assembled.

It follows the shape of `2026-08-14-r3-provider-evaluation-clerk.md`, which is the repository's
worked precedent for admitting an external provider: evaluate against the gates, separate what the
owner can settle from what the vendor must supply, and authorize nothing.

## Result

Nine gates. **Five are already discharged by code on `main`**, structurally rather than by
configuration. **Four require material no automated agent can obtain** and are procurement items
for the owner. None is a finding against the provider.

The unusual feature of this evaluation is the first half of that split. `RRA-005` was implemented
before any provider existed, and the adapter contract it produced already enforces most of what
`KHEPRI-DEC-008` demands of a provider integration. The gates that remain open are all
contractual or account-level.

### Gate disposition

| # | Gate (`KHEPRI-DEC-008`) | Disposition | Basis |
|---|---|---|---|
| 1 | Executed data-processing agreement | **OPEN — procurement** | No artifact records one. Owner action. |
| 2 | Explicit organization and project approval for Zero Data Retention | **OPEN — procurement** | Account-level setting; requires portal access and OpenAI approval. |
| 3 | Technical verification of the approved ZDR configuration | **OPEN — procurement** | Depends on gate 2. Must be verified against the live account, not inferred. |
| 4 | `store=false` on every request | **OPEN — enforceable in adapter** | No transport exists yet. Becomes a code obligation the moment one does; see below. |
| 5 | Synchronous requests only | **DISCHARGED by contract shape** | `NarrativeAdapter.draft` is a synchronous method returning `NarrativeDraft`. There is no async surface to misuse. |
| 6 | No background mode, conversations, assistants, threads, files, vector stores, hosted tools, extended prompt caching, or provider-side state | **DISCHARGED by contract shape** | `draft(request, *, timeout_seconds)` takes one projected request and returns one draft. The Protocol exposes no handle, thread, file, or session identifier, so there is nothing for provider-side state to attach to. |
| 7 | No raw rows, source column values, owner/session identifiers, storage locations, secrets, or unapproved personal data | **DISCHARGED structurally** | `_REQUEST_SCHEMA` is an allowlist projection. Its complete field set is version strings, `languages`, `monetary_precision`, and the `facts`/`series`/`comparisons`/`refusals`/`caveats` entries — `fact_id`, `citation_id`, `metric`, `measure`, `value`, `value_percent`, `precision`, `unit_kind`, `granularity`, `dimension`, counts, `label`, `rows`, `caveats`. No field exists that a raw row, column value, owner identifier, session identifier, or storage location could occupy. The profile and source digests are withheld deliberately. |
| 8 | Governed model allowlist and pinned adapter/request-schema version | **HALF DISCHARGED** | Pinning exists: `NARRATIVE_VERSION = "rra005.narrative.v1"`, `adapter_version` recorded on every attempt, and `NarrativeDraft.request_digest` must equal `NarrativeRequest.digest`. The **model allowlist does not exist** — `src/khepri/runtime/config.py` defines no provider, model, or narrative key. `KHEPRI-DEC-026` §2 requires it before an adapter. |
| 9 | Response validation rejecting unsupported numbers, citations, claims, or unsafe labels | **DISCHARGED** | `narrative.validate` enforces exactly this. 21 reason constants are closed over by `GOVERNED_REASONS`, and a reason outside that set is recorded as `provider_failed` rather than repeated. 181 tests exercise it. |

## Sourcing discipline

This evaluation had **no network access**. That is a material limitation on its scope and is
recorded here rather than worked around.

Every disposition above is sourced from artifacts inside this repository: `KHEPRI-DEC-008`,
`RRA-005`, `src/khepri/rra/narrative.py`, `src/khepri/runtime/config.py`, `pyproject.toml`, and the
test suite. **No claim is made about OpenAI's current API surface, pricing, model snapshots,
regional availability, retention defaults, or contractual terms**, because none of that was
retrievable.

This is the distinction the Clerk evaluation drew when `trust.clerk.com` returned 403: a retrieval
failure by an automated agent is not an absence of documentation. Gates 1 through 4 are classified
as procurement items — get the document, check the setting — rather than as blockers asserting the
guarantee does not exist. Nobody has looked yet.

**What this means for the four open gates:** they cannot be closed from this repository by anybody,
agent or human. Gates 1 and 2 are contractual and account-level. Gate 3 is a verification against a
live account. Gate 4 is a code obligation with no code to attach to.

## The finding that matters architecturally

**Five gates were satisfied before the provider question was asked, and this is load-bearing rather
than lucky.**

`RRA-005` required the adapter to "accept only approved aggregate facts, safe labels, caveats,
language instructions, and citation identifiers", and `narrative.py` implemented that as a
projection instead of a filter. The docstring states the reasoning: anything the fact package gains
later "is absent from the request until somebody adds it to the schema deliberately. A blocklist
would have the opposite default, and the field that mattered would be the one nobody thought to
name."

The consequence for this evaluation is that gate 7 — the longest and most privacy-critical of the
nine — needs no provider-side assurance at all. Whatever OpenAI does with a request, the request
cannot contain a raw row, because no schema field can hold one. Gates 5 and 6 fall the same way:
the Protocol is a single synchronous call with no handle to hang provider-side state from, so
"no threads, no vector stores, no assistants" is a property of the signature rather than a
configuration to audit.

This inverts the usual dependency. Most of what `KHEPRI-DEC-008` demands is enforced on Khepri's
side of the boundary, so the provider is trusted for less than the gate list implies. What remains
genuinely provider-dependent is retention: gates 1 through 3, all of which concern what the
provider does with material it has legitimately received.

## Remaining evidence — procurement checklist

Four items. These are the only outstanding blockers to writing an adapter, alongside the model
allowlist and the dependency/egress authorizations `KHEPRI-DEC-026` §4 names.

---

**Gate 1 — Executed data-processing agreement**

```
Evidence needed:  A countersigned DPA covering the personal-data classes a narrative request can
                  carry, with the subprocessor list and change-notification terms.
Why it matters:   RRA-005 requires "contractual provider controls that disable training on Khepri
                  data and provider retention". A DPA is where that obligation becomes binding.
Satisfies:        Executed agreement, plus the current subprocessor list.
Fails:            Standard terms of service alone; a training opt-out toggle without contract.
Note:             Gate 7 limits what the DPA has to cover. A narrative request carries aggregate
                  facts, safe labels, and citation identifiers only, so the personal-data surface
                  is narrower than a general-purpose integration's. Worth stating in procurement:
                  it may simplify the review.
```

**Gate 2 — Organization and project approval for Zero Data Retention**

```
Evidence needed:  Written confirmation that ZDR is approved for the specific organization AND
                  project the adapter will use.
Why it matters:   KHEPRI-DEC-008 states in terms that "training opt-out without verified Zero Data
                  Retention is insufficient". Approval is per-account, not a published property of
                  the API, so it cannot be inferred from documentation.
Satisfies:        Confirmation naming the organization and project.
Fails:            A blog post or docs page describing ZDR as available; approval for a different
                  project.
```

**Gate 3 — Technical verification of the approved ZDR configuration**

```
Evidence needed:  A verification, against the live account, that the approved configuration is the
                  one in effect — not that it was requested.
Why it matters:   Gate 3 is separate from gate 2 deliberately. An approval that is not in effect is
                  the failure mode the gate exists to catch, and KHEPRI-DEC-008 makes an
                  unverifiable gate equivalent to an absent one.
Satisfies:        Recorded verification against the account the adapter will authenticate as.
Fails:            Inferring effect from approval; verifying a different project.
Ordering:         After gate 2, before any request carrying customer-derived content.
```

**Gate 4 — `store=false` on every request**

```
Evidence needed:  Not vendor evidence. A code obligation, discharged when the adapter is written.
Why it matters:   Belt-and-braces against gates 2 and 3: if ZDR were silently not in effect,
                  store=false is the second control.
Satisfies:        The transport sets it unconditionally, with a test proving a request cannot be
                  constructed without it — asserted on the outgoing payload, not on a default
                  argument a caller could override.
Fails:            A configurable flag defaulting to false. Per this repository's own lesson,
                  a guard that can be turned off is evidence of intent, not a control.
```

## Model snapshot selection — not yet possible, and why

`KHEPRI-DEC-008` requires the snapshot to be selected on "bilingual grounding, latency, refusal,
and privacy-gate evidence". None can be gathered now:

- **Bilingual grounding** needs candidate drafts run through `narrative.validate` against real fact
  packages, measuring how often a model states an ungrounded number or breaks Arabic/English
  parity. That needs a transport, which needs gates 1 through 3.
- **Latency** needs live measurement against the 20-second default in `NarrativeService`.
- **Refusal quality** needs to distinguish a model that declines cleanly from one that invents
  prose when the facts are thin.
- **Privacy-gate evidence** is gates 1 through 3 themselves.

The ordering is therefore fixed and non-negotiable: contract and ZDR first, then a transport
behind them, then snapshot evidence, then selection. `KHEPRI-DEC-026` deliberately stops before
this point rather than naming a snapshot it could not justify.

**What can be decided now, and should be:** the allowlist mechanism. `KHEPRI-DEC-026` §2 requires
provider and model to be operational configuration behind an allowlist, with an absent model
refused rather than defaulted. That is designable without any vendor evidence, follows the
`KHEPRI_CLERK_MODE` convention already in `config.py`, and is the one part of this program that is
neither blocked nor speculative.

## Replaceability

`KHEPRI-DEC-008` requires that changing providers be possible without rewriting analytical logic,
and the evaluation confirms it holds — for a reason worth stating precisely.

A second provider satisfies `NarrativeAdapter` and nothing else changes, because `validate` grounds
the response against the *request* rather than against the provider. The question "was this number
supplied?" has one answer and it does not depend on who answered. `DeterministicNarrator` is the
existing proof: it satisfies the Protocol with no provider, no network, and no credentials, and
`wiring.py` selects it today.

The cost is stated rather than hidden: switching providers still requires a new or superseding
architecture decision under `KHEPRI-DEC-008`, and a fresh snapshot evaluation, because grounding
quality is a property of the model rather than of the contract.

## Recommendation

1. **Merge `KHEPRI-DEC-026`** — it settles the boundary and refuses the generic layer without
   depending on any open gate.
2. **Pursue gates 1 and 2 as procurement**, noting in the DPA review that gate 7 already narrows
   the personal-data surface to aggregate facts and citation identifiers.
3. **Design the model allowlist** as the next code-adjacent slice. It is unblocked, it is required
   before any adapter, and it cannot leak: an allowlist with no entries enables nothing.
4. **Do not write a transport** until gates 1 through 3 are recorded as satisfied, a runtime HTTP
   dependency is authorized, and egress is authorized deliberately as `infra/network.py` requires.

### Sequencing note — this document authorizes no code

`G9-02`'s output is an active architecture decision, and this evaluation is the evidence for one,
not the decision itself. `G9-03` is what the roadmap marks as conferring implementation authority.
Nothing here changes what may be built.
