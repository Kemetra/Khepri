# Narrative model allowlist — design

Date: 2026-08-22
Status: design. **No code written.** See "Why this is design and not implementation" below.
Depends on: `KHEPRI-DEC-026` §2 (proposed), `KHEPRI-DEC-008` gate 8.

## What this settles

`KHEPRI-DEC-008` gate 8 requires "a governed model allowlist and pinned adapter/request-schema
version". Pinning exists: `NARRATIVE_VERSION`, `adapter_version` on every attempt, and
`NarrativeDraft.request_digest`. The allowlist does not — `src/khepri/runtime/config.py` defines no
provider, model, or narrative key.

`KHEPRI-DEC-026` §2 states the requirement: provider and model selection is operational
configuration behind an allowlist, never a literal in application code, and a model absent from the
allowlist is a refusal rather than a default.

This document designs that mechanism so it can be implemented in one bounded slice the moment
authority exists.

## Why this is design and not implementation

`KHEPRI-DEC-026` is proposed on a branch. Under Constitution II it governs nothing until the owner
merges it, and Constitution IV admits product code only against an active specification.

The prohibition is not merely formal. `KHEPRI-DEC-024` §14 reads: "No Clerk SDK, dependency,
secret, **environment variable**, adapter, route, middleware, UI, schema, migration, or production
code." `#240` shipped exactly those categories and `#241` had to retro-authorize it, even though a
post-merge audit found the implementation conformant to every boundary `-024` drew, with no
functional or security defect.

Adding `KHEPRI_AI_PROVIDER` and `KHEPRI_AI_MODEL` to `config.py` now would be the same act against
an unmerged decision: an environment variable for a provider integration that no active artifact
authorizes. The mechanism is designed here instead, and stays designed until `KHEPRI-DEC-026` is
merged.

## Design

### Shape, following the Clerk precedent exactly

`_clerk_settings` is the repository's worked pattern for a disabled-by-default external provider,
and the allowlist should be indistinguishable from it in shape:

```
NARRATIVE_PROVIDER_VARIABLE = "KHEPRI_NARRATIVE_PROVIDER"   # default "disabled"
NARRATIVE_MODEL_VARIABLE    = "KHEPRI_NARRATIVE_MODEL"      # required when enabled

NarrativeProvider = Literal[...]        # populated by the G9-02 evaluation, not invented here
_NARRATIVE_PROVIDERS = frozenset(...)   # same
_NARRATIVE_MODELS: Mapping[str, frozenset[str]] = {}   # provider -> approved snapshots

@dataclass(frozen=True, slots=True)
class NarrativeProviderSettings:
    provider: NarrativeProvider
    model: str

def _narrative_settings(environment) -> NarrativeProviderSettings | None:
    provider = environment.get(NARRATIVE_PROVIDER_VARIABLE, "disabled")
    if provider == "disabled":
        return None
    if provider not in _NARRATIVE_PROVIDERS:
        raise RuntimeConfigurationError(...)
    model = _required(environment, NARRATIVE_MODEL_VARIABLE)
    if model not in _NARRATIVE_MODELS.get(provider, frozenset()):
        raise RuntimeConfigurationError(...)
    return NarrativeProviderSettings(provider=provider, model=model)
```

`RuntimeSettings` gains `narrative: NarrativeProviderSettings | None`.

### Four properties this shape buys, and why each matters

**1. Disabled is a type, not a flag.** The function returns `None`, never a
half-populated object. "Enabled but unconfigured" is unrepresentable, so no downstream code can
mistake a disabled provider for a usable one. This is why `_clerk_settings` returns
`ClerkIdentitySettings | None` rather than carrying an `enabled: bool`.

**2. An empty allowlist enables nothing, by construction.** `_NARRATIVE_MODELS` starts empty. With
no entries, every non-disabled provider value fails the membership test and the process refuses to
start. There is no code path in which an unapproved model reaches a provider, and no default to
fall back to — which is exactly what `KHEPRI-DEC-026` §2 requires. The allowlist can therefore be
implemented *before* a model is chosen, and populated later by the artifact that chooses one.

**3. Validation at configuration time, not call time.** `_clerk_issuer` rejects a non-HTTPS URL when
settings are built, so a misconfigured process never starts. The allowlist does the same: an
unapproved model is a `RuntimeConfigurationError` at startup, not a refusal on the first report.
Fail-closed means the process declines to run, not that the first customer request errors.

**4. Model changes cannot alter analytical behaviour.** The model name reaches the adapter and
nothing else. Facts, calculations, and citations come from `FactPackage`, and `validate` grounds
every response against the request, so swapping an allowlisted snapshot changes prose wording and
nothing that a number depends on.

### What the allowlist deliberately does not do

- **No routing.** One provider, one model, per configuration. No cheap-to-expensive escalation, no
  arbitration, no fallback between providers — `KHEPRI-DEC-026` §4 excludes all of it.
- **No default model.** Absent configuration is disabled, never "use the sensible one".
- **No secret.** An API credential is a separate concern, drawn from the secret store the target
  capability contract requires, and is not part of the allowlist. `NarrativeProviderSettings` holds
  no credential field, so it cannot appear in a repr or a log line.
- **No provider names invented here.** `NarrativeProvider` is populated by the `G9-02` evaluation
  once a selection is justified. Writing `"openai"` into a `Literal` today would be the literal in
  application code that `KHEPRI-DEC-026` §2 forbids.

## Tests the implementing slice owes

1. Absent `KHEPRI_NARRATIVE_PROVIDER` yields `narrative is None`.
2. Explicit `disabled` yields `None`.
3. An unknown provider raises `RuntimeConfigurationError`.
4. A known provider with a model absent from the allowlist raises — **the load-bearing test.**
5. A known provider with no model variable at all raises, rather than defaulting.
6. With `_NARRATIVE_MODELS` empty, every provider value raises. This is the emptiness assertion:
   without it, test 4 would pass vacuously once the allowlist is populated for a different provider.
7. `NarrativeProviderSettings` repr contains no credential, because it has no credential field.
8. Existing `RuntimeSettings.from_environment` tests still pass with the new optional field.

Test 6 is the one this repository's own lesson demands: a scan or guard scoped to one value
self-disarms when the input moves, so every allowlist check needs a proof that the empty case
refuses.

## Sequencing

1. Owner merges `KHEPRI-DEC-026`.
2. Implement this design — one bounded slice touching `config.py` and its tests, with
   `_NARRATIVE_MODELS` empty and `NarrativeProvider` carrying no members until (3).
3. `G9-02` evaluation completes with a justified provider and snapshot; the allowlist is populated.
4. Gates 1–3, the HTTP dependency, and egress are authorized; only then a transport.

Steps 2 and 3 are separable on purpose. The mechanism is provably safe while empty, so it can land
before any provider is chosen, and choosing one later is a data change rather than a structural one.
