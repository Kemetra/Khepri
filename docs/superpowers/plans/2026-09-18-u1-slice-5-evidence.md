# `U1` slice 5 — the state grammar: evidence

Execution record for `docs/superpowers/plans/2026-09-18-u1-slice-5-execution-plan.md`.
Branch `claude/u1-slice-5-state-grammar`, based on `main` at `34a802b`.

**Baseline moved.** The plan was written against `b26de23`. By execution `main` was at
`34a802b`, carrying `#481` (`U1-03`), `#483` (slice 4) and `#482` (`FND-004`). Every path
the plan cites was re-verified unchanged:

```text
$ git diff --stat b26de23 HEAD -- src/khepri/runtime/shell_templates/ \
    src/khepri/runtime/shell_assets/ src/khepri/rra/journey/assets/ \
    src/khepri/runtime/shell_decisions.py src/khepri/rca/ \
    src/khepri/rra/semantic_views/ tests/test_r807_shell_quality.py
(empty)
```

The `role=` inventory was re-run and matches the plan exactly: thirteen attributes, three
`role="alert"`, at the cited lines.

**The environment warning did not apply.** The plan requires `PYTHONPATH=$PWD/src` because
the author's Windows checkout had two stray worktrees shadowing `khepri`. This Linux
container has none — `git worktree list` shows one entry — and the interpreter resolves
correctly without it:

```text
$ .venv/bin/python -c "import khepri; print(khepri.__file__)"
/home/user/Khepri/src/khepri/__init__.py
```

`PYTHONPATH=$PWD` is still needed to import `tests.d105_support` from an ad-hoc script,
but not for `pytest`, which puts the rootdir on the path itself.

---

## Four of the plan's claims were falsified by the tree

Each was established before the work depending on it, and each is recorded here rather
than silently worked around.

### 1. Finding 3 is right that the cards path is broken, and wrong about how

The plan states the cards path "states the `stated_no_rows` sentence for a `stated_absence`
finding". Driven through the real route with an empty `ExecutiveOverviewView`:

```text
--- en | EXECUTIVE_OVERVIEW.empty_rule = stated_absence
  decision-empty count: 1
  stated_no_rows   in body: False   'Nothing matched this request.'
  stated_absence   in body: False   'The source published no value for this.'
  decision.no_rows copy: 'This analysis published no figures.'
```

**Neither governed sentence appears.** The template renders `decision.no_rows` — a third,
non-governed chrome sentence equal to neither `EMPTY_WORDING` value. The governed rule is
not mis-stated as the other rule; it is discarded and replaced by chrome copy. The same
violation of `FR-163`, and a plainer one. The strict-xfail reason carries the corrected
text.

### 2. Task 3's carve-out was inert as scoped

Task 3 prescribes a scan over "rules whose selector names a state class", plus an
`.invitation-warning` carve-out to prevent a false positive. Written that way the carve-out
can never be reached: `.invitation-warning` names no state class, so it never enters the
branch it exempts — a defined-but-never-attached shape inside a guard written to catch
exactly that.

The scan therefore asserts the stronger invariant the carve-out implies: the `--danger`
family reaches **one** rule in the shell. Verified:

```text
$ grep -n "var(--danger" shell.css shell-components.css workspace.css
shell-components.css:159:  color: var(--danger);
```

Matched on `var(--danger...)` rather than the bare token, so `shell.css`'s `:root` block —
which *defines* the family at `:68-71` — is not read as a usage of it.

### 3. The §F reachability table is wrong about `team`, and its mutant is a no-op

The plan's table lists `team` under "No state region". `team.html.j2` carries **two**
`.empty-state` regions: `:30` an empty member list, `:96` an empty invitation list. Both
legitimate.

So the plan's prescribed mutant — adding an `.empty-state` to `team.html.j2` — is a no-op.
Proven rather than asserted:

```text
T6 PLAN'S mutant: empty-state on team          expect=PASS got=PASS OK
T6 empty-state on switcher (replacement)       expect=FAIL got=FAIL OK
```

With governed copy the plan's mutant leaves all 13 tests passing. It fails only if the
added markup *also* hard-codes its sentence, which trips a different assertion entirely.
`switcher.html.j2` is genuinely stateless and is the valid replacement.

### 4. Two of the three exit mutants have nothing to delete

The plan asserts an exit anchor inside "a refused `decision`"'s own document-card, and on
`no_membership`. Measured:

```text
refused decision, cards carrying a state -> anchors in card:
  ['decision-empty']       0
  ['decision-refusal']     0
  ['decision-unavailable'] 0

no_membership anchors: skip-link, frame-language.  No exit anchor at all.
unavailable   anchors: skip-link, frame-language, "Go to your organizations".
```

- `decision` renders the **full** frame navigation, so the plan's premise for including it
  — that its frame "drops or narrows the navigation" — is not true of that surface, and a
  refused section's card needs no exit of its own.
- `no_membership` correctly carries no destination. An authenticated account in no
  organization has nowhere in the product to go, and inventing one is what `FR-193`
  forbids. Its next step is a sentence: "Ask an organization owner to invite you."

The invariant is therefore scoped to the surfaces whose frame renders no destination
navigation (`unavailable`, `no_membership`, `switcher`) and asks for an anchor that is not
frame chrome **or** a stated next step. That has teeth on all three; the plan's version
would have been RED on two with no in-scope fix `FR-193` permits.

---

## Mutation record

Every guard, mutated after the implementation was committed. `expect` is what the plan or
the guard's own claim requires; `dirty after revert` is `git status --short src/ tests/`.

```text
== Task 1 ==   (re-targeted by pattern — see the lesson below)
T1 merge two state classes on refusal      expect=FAIL got=FAIL OK
T1 refusal renamed decision-error          expect=FAIL got=FAIL OK
T1 error-shaped token beside refusal       expect=FAIL got=FAIL OK
== Task 2 ==
T2 delete the section.empty branch         expect=FAIL got=FAIL OK
T2 third key in EMPTY_WORDING              expect=FAIL got=FAIL OK
T2 two governed sentences collapsed        expect=FAIL got=FAIL OK
== Task 3 ==
T3 paint the refusal with --danger         expect=FAIL got=FAIL OK
T3 .error-summary rule in a shell sheet    expect=FAIL got=FAIL OK
T3 the SAME rule inside a comment          expect=PASS got=PASS OK
T3 .empty-state painted --danger-ink       expect=FAIL got=FAIL OK
T3 carve-out unjustified (rename)          expect=FAIL got=FAIL OK
T3 second var(--danger) usage              expect=FAIL got=FAIL OK
T3 role=alert restored on the refusal      expect=FAIL got=FAIL OK
T3 role=alert restored on unsupported      expect=FAIL got=FAIL OK
== Task 4 ==
T4 <script> on overview                    expect=FAIL got=FAIL OK
T4 aria-busy on analyses                   expect=FAIL got=FAIL OK
T4 spinner on legal_page                   expect=FAIL got=FAIL OK
T4 inline onclick on data                  expect=FAIL got=FAIL OK
== Task 5 ==
T5 transition on its own line              expect=FAIL got=FAIL OK
T5 PACKED single-line transition           expect=FAIL got=FAIL OK
T5 bare @keyframes                         expect=FAIL got=FAIL OK
T5 the SAME declaration commented          expect=PASS got=PASS OK
T5 transform (not named by FR-203)         expect=FAIL got=FAIL OK
== Task 6 ==
T6 PLAN'S mutant: empty-state on team      expect=PASS got=PASS OK   (the no-op, proven)
T6 empty-state on switcher                 expect=FAIL got=FAIL OK
T6 decision-refusal on overview            expect=FAIL got=FAIL OK
T6 exit anchor deleted from unavailable    expect=FAIL got=FAIL OK
T6 next-step deleted from no_membership    expect=FAIL got=FAIL OK
T6 <svg> inside an empty state             expect=FAIL got=FAIL OK

final tree: 0 dirty
```

Three load-bearing rows:

- **`T4 spinner on legal_page`** is the mutant that would pass against a scan inheriting
  `test_every_shell_template_is_measured`'s blind spot — that instrument scans only
  `shell_templates/`, leaving `legal_templates/` in §Scope and reached by nothing.
- **`T5 bare @keyframes`** is why the second pattern exists. An at-rule carries no
  property-colon, so the declaration pattern cannot see it at all.
- **`T3 the SAME rule inside a comment`** and **`T5 the SAME declaration commented`** are
  the comment-stripping proofs; both must pass, and do.

### A lesson: line-numbered mutants go stale the moment implementation edits the file

Task 1's three mutants were written as `sed -i '11s|...|'` against
`_decision_sections.html.j2:11`. They failed correctly at Task 1. Re-run after Task 8 they
reported **PASS**, which read as a regression in the guard. It was not: Task 8 inserted a
ten-line Jinja comment above that element, moving the refusal from `:11` to `:21`, so the
`sed` was mutating a comment line and doing nothing.

Re-targeted by pattern (`<p class="decision-refusal" role="status">`) all three fail as they
should. **Mutants must be pattern-targeted, not line-targeted**, or a later task silently
disarms them and the record reports a guard that was never exercised.

---

## Verification

```text
$ .venv/bin/python -m pytest -q          # the FULL suite, committed implementation
5575 passed, 130 skipped, 2 xfailed in 380.59s

  main at 34a802b:  5555 passed, 130 skipped, 1 xfailed
  delta:            +20 passed  (7 in r808, 13 in r809), +1 xfailed
```

The `+1 xfailed` is Task 2's strict-xfail cards-path test, which is the expected reading,
not a pass.

```text
$ pytest tests/test_r808_shell_state_grammar.py tests/test_r809_shell_state_contracts.py \
         tests/test_r807_shell_quality.py tests/test_r801_shell_tokens.py -q
63 passed, 43 skipped, 1 xfailed

$ pytest tests/test_d105_decision_sections.py tests/test_d105_evidence_drawer.py \
         tests/test_d103_metric_card.py tests/test_d104_breakdowns_and_limits.py \
         tests/test_d108_print.py tests/test_d107_controls.py -q
168 passed            # the RCA-008 suites the ARIA change reaches, print included

$ .venv/bin/khepri-gov validate    Governance validation passed.   (exit 0)
$ .venv/bin/python -m ruff check . All checks passed!              (exit 0)
$ git diff --check                                                 (exit 0, clean)
```

The skip counts differ from the plan's expectations because this container skips more
environment-gated cases (Playwright browser runs); the totals are consistent.

`ruff format` was **not** run — there is no CI format gate, and the repository carries
pre-existing format drift that reformatting would sweep into this diff.

---

## What changed

```text
 src/khepri/runtime/shell_assets/workspace.css               |  21 +-   comment only
 src/khepri/runtime/shell_templates/_decision_cards.html.j2  |  12 +-   role + comment
 src/khepri/runtime/shell_templates/_decision_sections.html.j2| 12 +-   role + comment
 src/khepri/runtime/shell_templates/compare.html.j2          |  12 +-   role + comment
 src/khepri/runtime/shell_templates/decision.html.j2         |  12 +-   role + comment
 tests/test_r808_shell_state_grammar.py                      | 584 +    new
 tests/test_r809_shell_state_contracts.py                    | 221 +    new
```

**No Python source file changed. No `shell_copy.py` entry was added.** `shell.css` is
untouched and stays tokens-only. `shell-components.css` gained nothing. No CSS rule was
added, changed or removed anywhere — `workspace.css`'s diff is comment text only.

---

## Deferrals carried forward, each with its owner

| Item | Owner |
|---|---|
| The cards-path `FR-163` collapse — `_DecisionView.empty` is a `bool` and the template renders a non-governed chrome sentence | **An `RCA-008` slice.** It owns `FR-163` and `shell_decisions.py`. Held by the strict xfail, which fails when fixed |
| A `prefers-reduced-motion` block on the shell sheets | **Nobody — REFUSED as unnecessary.** Zero motion exists; the block would gate nothing. If a later slice adds motion it adds the block with it, and Task 5's invariant fails until it does |
| A `loading` state presentation | **Nobody at the shell.** Structurally unreachable; the invariant is asserted instead |
| An `error` state presentation | A slice implementing a shell export or processing surface, which needs a route and is barred by `FR-193` |
| `FR-199`'s false premise corrected in place | **The owner's call** — recorded by the allocation plan, a task in no slice |
| Reducing `test_r807_shell_quality.py` below the 600-line gate (788 lines) | A dedicated split, owner-visible. This slice added two new modules rather than making the overage worse |
