# `R8-02` — the shell base and the shared unavailable surface

Date: 2026-08-22
Authority: `RCA-002` (`active` at `488e1ae`), `RCA-001`, `KHEPRI-DEC-023`, `KHEPRI-DEC-025`.
Base: `main` @ `488e1ae`.

This note is the scope declaration `RCA-002` implementation precondition 3 requires: it **names
which surfaces this slice delivers and which it does not**, so an unimplemented surface is proven
absent rather than merely unwritten.

## Precondition check

| # | Precondition | Status |
|---|---|---|
| 1 | `RCA-002` is `active` in `governance/registry.yaml` | **Met** — `registry.yaml:263-271`, merged `488e1ae` (`#246`) |
| 2 | `RCA-001`'s preconditions met; merged `R6`/`R7` remains the single canonical checkpoint | **Met** — `R6` and `R7` are `MERGED`; `resolver.for_request` is the checkpoint |
| 3 | The first slice names its surfaces and asserts the absence of the others | **This document, plus the tripwire test below** |

Precondition 3's second half is a test, not a sentence. A scope declaration nobody can fail is not
a constraint.

## Surfaces this slice delivers

| Surface | Address | Why this one first |
|---|---|---|
| Shell base | (not addressable; the frame the surface renders inside) | Every other surface repeats it |
| `unavailable` | any unmatched path under the shell prefix | It is the only surface whose entire behaviour `RCA-002` already fixes |

**Two surfaces, one of them not addressable.** That is deliberate.

## Surfaces this slice does NOT deliver

`analyses`, `team`, `settings`, `account`, `no-membership`, the organization chooser, upload,
review, processing, evidence layer, and report.

**Their absence is asserted, not assumed.** A test enumerates the shell's registered routes and
fails if any path outside the delivered set is reachable. Per the standing trap about scans that
self-disarm, that test carries an **emptiness assertion**: it fails if the route enumeration
returns nothing, so a renamed router cannot make it pass by scanning an empty set.

`no-membership` is the notable omission. `RCA-002` `FR-048` requires it to exist and carry a next
step, and it is the one edge state deliberately *not* collapsed into `unavailable`. It is excluded
here because it needs membership enumeration wired through, which is the next slice's work — and
because delivering it half-formed would make `FR-048`'s "explicit next step" a placeholder.

## Why `unavailable` and not `analyses`

`analyses` is the surface the design handoff proposed first, and it is the wrong first slice.

**`unavailable` is fully specified already.** Six of `RCA-002`'s 23 scenarios land on it —
2, 5, 8, 18, 21, 22 — covering `FR-046`, `FR-050`, `FR-051`, `FR-052`, `FR-043`, and `FR-045`. It
needs no membership listing, no report content, and no journey navigation.

**It is where the header requirement actually bites.** `FR-043` requires every shell response to
attach security headers explicitly, because nothing global will. A happy-path surface would pass a
header test while the refusal path silently omitted them — and the refusal path is the one that
matters, since it is reached by an actor who should learn nothing.

**It is the disclosure boundary.** `FR-050` collapses five distinct states into one response and
`FR-052` constrains what that response may contain. Getting this right first means every later
surface inherits a correct refusal rather than retrofitting one.

`analyses` additionally drags in the organization switcher, whose enumeration is `FR-051`'s
requirement over live membership — more surface area than a slice establishing the pattern should
carry.

## What the code does, and where it lives

**Routes live in `khepri.runtime`, beside `commercial_api.py`. Not in `khepri.rra.journey`.**

This is forced, not preferred. `R7-07` enforces a flat two-way import ban: `khepri.rca` imports no
`khepri.rra` module and `khepri.rra` imports no `khepri.rca` module. A shell route needs
`AuthorizationResolver` (RCA); an RRA-side module holding it would fail that test. The composition
root is the one layer allowed to know both sides, which is why `commercial_api.py` already sits
there for exactly this reason.

The design handoff placed `shell_routes.py` under `khepri.rra.journey` and passed the boundary test
only by declaring its own `MembershipReader` Protocol instead of using the resolver. `RCA-002`
`FR-041` now forbids that outright: no second actor-resolution or membership-resolution path.

**Actor resolution reuses the merged checkpoint verbatim:**

```python
context = services.resolver.for_request(session, organization_id=None, now=now)
```

`commercial_api.py:114` already calls this standalone, before any bridge call, which proves it is
usable for a page render. `AuthorizationContext` carries `account_id`, `organization_id | None`,
and `role | None` — everything a shell frame needs. `organization_id=None` is not an error state;
`RCA-001` `FR-028` requires an account with no membership to authenticate successfully, and the
type documents that. It is `Sealed` and "never stored, never reused", which is `FR-053`'s
no-cached-authorization requirement enforced by the type rather than by convention.

**Security headers reuse `SECURITY_HEADERS`, imported, not restated.** `FR-045` requires the shell
to serve the same policy as the journey; a second copy of the dict would be a second definition of
the policy, and the two would drift. The shipped value already satisfies `FR-045` exactly:
`default-src 'none'` with per-directive `'self'`, no inline source admitted, `frame-ancestors
'none'`, and `Cache-Control: private, no-store`.

**Assets need a shell-owned route.** `rra/journey/routes.py:129` serves `/beta/assets/{name}` from
an allowlist tied to the journey app. A shell mounted at a different prefix is not served by it.
The handoff's proposed one-line `_ASSETS` edit was written for a route module in the wrong package
and does not solve this. The shell serves its own assets from its own allowlist, keeping the beta
surface untouched as `RCA-002`'s exclusions require.

## Templates

`expired.html.j2` already renders expired, deletion-requested, and session-unavailable from one
template with two branches — `FR-050`'s collapse, already built and already tested. This slice does
**not** modify it: `RCA-002` excludes any change to the `RRA` beta journey, its routes, its
templates, or its assets. The shell's `unavailable` template is modelled on it and lives beside the
shell, so the beta and commercial surfaces can diverge later without one breaking the other.

`shell.css` ships from `R8-01` and `tests/test_r801_shell_tokens.py` asserts four consistency
claims about it. That test is read before any component CSS is written, and is not modified.

## Tests

Named for the `RCA-002` scenario each verifies.

| Scenario | Test | Requirement |
|---|---|---|
| 8 | Unknown path under the shell prefix renders `unavailable` | `FR-046` |
| 5 | Expired, deleted, and session-unavailable produce one indistinguishable response | `FR-050` |
| 2 | A foreign organization is refused without being named | `FR-050`, `FR-051` |
| 21 | One denial, examined alone, carries no identifier, type, ownership, or timestamp | `FR-052` |
| 18 | Headers present on the **error** surface, not only the happy path | `FR-043` |
| 22 | Shell header values equal the journey's | `FR-045` |
| — | Routes outside the delivered set are unreachable (with emptiness assertion) | precondition 3 |
| — | No shell module defines its own actor/membership/scope Protocol (with emptiness assertion) | `FR-041` |

**Scenarios 5 and 21 are deliberately two tests, not one.** `RCA-002` `FR-052` says so explicitly:
`FR-050` requires several inputs to produce one indistinguishable output, while `FR-052` constrains
what any single output may contain. One outcome test satisfies both while proving neither — a shell
leaking the object's type in all five collapsed states would still be perfectly indistinguishable
across them.

Each guard is mutation-tested before the slice is called done: a mutant that names the organization
in a denial, one that drops the header attachment, and one that distinguishes two collapsed states
must each be killed by a named test.

## Out of scope, stated so it is not inferred

- No membership enumeration, no organization switcher — next slice.
- No report content in the shell; `FR-057`…`FR-061` are unexercised by this slice and their tests
  come with the surface that renders a report.
- No change to `/beta/…`, to `journey.css`, to `shell.css`, or to `test_r801_shell_tokens.py`.
- No icon, typeface, or third-party asset.
- No sign-in or recovery surface. `RCA-002` A-5 puts them outside the specification:
  `KHEPRI-DEC-025` §2 authorizes one external-authentication route and §3 states Khepri implements
  no credential replacement or password recovery for a Clerk-backed account.
- No migration, no schema change, no dependency change.
