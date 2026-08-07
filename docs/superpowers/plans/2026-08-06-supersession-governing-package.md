# Governing-Package Supersession Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `khepri-gov validate` accept a repository where an artifact is superseded after a prior approval was renewed, so the strict `xfail` in `tests/test_approval_packages.py` can be removed.

**Architecture:** Introduce one predicate — a package *governs* an artifact when the registry entry names it in `approval_ref` — and split the four failing checks by role. Registry-agreement checks run only for the governing package; historical packages are checked for lifecycle legality instead. One new per-artifact invariant replaces the four relaxed per-package assumptions, and is written and tested *before* any relaxation lands.

**Tech Stack:** Python 3.13, uv, pytest, ruff. No new dependencies.

## Global Constraints

- Every new file must score **10.00** on CodeScene and no tracked hotspot may decline. CI is the only authority; local tooling does not reproduce server thresholds.
- Keep constructors and helper signatures to **two or three arguments** rather than sitting at a limit.
- Type annotations on every function signature; `from __future__ import annotations` at module top, matching the existing modules.
- Prefer `@dataclass(frozen=True)` for new value types.
- The baseline to compare against is **1604 passed, 9 skipped, 1 xfailed**. On completion it must be **1605 passed, 9 skipped, 0 xfailed**.
- No governed artifact, registry entry, or approval package changes in this plan. It is validation logic and tests only.
- `uv run khepri-gov validate` must pass on the real repository after every task, not only on fixtures.

## File Structure

| File | Responsibility |
|---|---|
| `src/khepri_gov/governing_packages.py` | **New.** Decide which package governs an artifact, and assert the registry agrees with exactly one. Nothing else. |
| `src/khepri_gov/approval_packages.py` | Modified at `validate_approval_packages` (`:379-448`) to call the new invariant once, after the per-package loop. |
| `src/khepri_gov/approval_transition_validation.py` | Modified: `_approval_errors` (`:191`) becomes governing-aware. |
| `src/khepri_gov/approval_renewals.py` | Modified: `_preserves_state` (`:148`) splits by role; `_requires_prior_ref` (`:189`) loses its live-registry branch. |
| `tests/test_approval_packages.py` | All tests. The repository keeps a flat `tests/` directory named by governed specification — do **not** create `tests/khepri_gov/`. |

---

> ## Executed 2026-08-06 — what actually happened
>
> The plan was followed and **Task 1 was dropped as unnecessary.** Writing its two tests
> and running them proved both halves of the "new" invariant already existed:
> `_state_errors` compares the governing package's `to_state` to the registry state, and
> `_package_evidence_errors` requires every `approval_ref` to resolve to an approved
> package containing the artifact — including the `APP-001-bootstrap.md` case this plan
> flagged as a *critical real-world constraint* needing a `.yaml` guard. It needed none;
> `BOOTSTRAP_EVIDENCE` already handles it.
>
> No `governing_packages.py` module was created. Task 2 needed only an inline comparison,
> so `governs()` was never written either. Tasks 2–5 ran as planned, with two amendments:
>
> - `assert_invalid` matches **`stderr`**, not `stdout`. Every "not in `result.stdout`"
>   assertion in Tasks 2–4 below would have passed vacuously. They were written against
>   `stderr`.
> - Removing the last `replaces_approval=True` caller left that parameter and
>   `_replacement_matches` dead, so both were deleted — a simplification the plan did not
>   anticipate. Net −41 lines against +103.
>
> Final counts: **1607 passed, 9 skipped, 0 xfailed** — not the 1609 predicted below,
> because three planned tests turned out to be redundant. The `0 xfailed` is the assertion
> that mattered.
>
> Tasks 1–5 are left as written, since a plan is a record of what was intended.

### Task 1: The per-artifact governing invariant — DROPPED, see above

Written first, because it is the backstop for every relaxation that follows. Landing the relaxations first would leave a window with no check at all.

**Files:**
- Create: `src/khepri_gov/governing_packages.py`
- Modify: `src/khepri_gov/approval_packages.py:443-448`
- Test: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes: `packages_by_path: Mapping[str, Mapping[str, Any]]` and `known_artifacts: Mapping[str, tuple[str, Artifact]]`, both already built inside `validate_approval_packages` at `:400-409`.
- Produces:
  - `governs(package_ref: str, artifact: Mapping[str, Any]) -> bool`
  - `governing_agreement_errors(known_artifacts: Mapping[str, tuple[str, Any]], packages_by_path: Mapping[str, Mapping[str, Any]]) -> list[str]`

**Critical real-world constraint:** `KHEPRI-DEC-001` carries `approval_ref: governance/approvals/APP-001-bootstrap.md` — a Markdown bootstrap record, not an `APP-*.yaml` package. It will never appear in `packages_by_path`. The invariant must apply only to refs ending in `.yaml`; legacy evidence is already handled by `_legacy_evidence_errors`.

- [ ] **Step 1: Write the failing tests**

```python
def test_artifact_approval_ref_must_name_an_approved_package(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1]["approval_ref"] = "governance/approvals/APP-404.yaml"
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages: KHEPRI-DEC-002 approval_ref names no approved package",
    )


def test_governing_package_to_state_must_equal_registry_state(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1]["state"] = "rejected"
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages: KHEPRI-DEC-002 state 'rejected' does not match "
        "the governing package",
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_approval_packages.py -k "governing or names_no_approved" -v`
Expected: both FAIL. The first currently produces a different message; the second currently passes for the wrong reason (no check exists).

- [ ] **Step 3: Write the new module**

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PACKAGE_SUFFIX = ".yaml"


def governs(package_ref: str, artifact: Mapping[str, Any]) -> bool:
    """True when the registry entry names this package as its current authority."""
    return artifact.get("approval_ref") == package_ref


def _approved_package_for(
    approval_ref: str,
    artifact_id: str,
    packages_by_path: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    package = packages_by_path.get(approval_ref)
    if package is None or package.get("state") != "approved":
        return None
    for entry in package.get("artifacts") or []:
        if isinstance(entry, dict) and entry.get("id") == artifact_id:
            return entry
    return None


def _artifact_errors(
    artifact_id: str,
    artifact: Mapping[str, Any],
    packages_by_path: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    approval_ref = artifact.get("approval_ref")
    if not isinstance(approval_ref, str) or not approval_ref.endswith(PACKAGE_SUFFIX):
        return []
    entry = _approved_package_for(approval_ref, artifact_id, packages_by_path)
    if entry is None:
        return [
            f"approval-packages: {artifact_id} approval_ref names no approved package"
        ]
    state = artifact.get("state")
    if entry.get("to_state") == state:
        return []
    return [
        f"approval-packages: {artifact_id} state {state!r} does not match "
        "the governing package"
    ]


def governing_agreement_errors(
    known_artifacts: Mapping[str, tuple[str, Any]],
    packages_by_path: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Every artifact naming a YAML approval must agree with exactly that package."""
    errors: list[str] = []
    for artifact_id, (_registry, artifact) in sorted(known_artifacts.items()):
        errors.extend(_artifact_errors(artifact_id, artifact, packages_by_path))
    return errors
```

- [ ] **Step 4: Wire it into the validator**

In `src/khepri_gov/approval_packages.py`, add the import beside the existing `approval_renewals` import, then extend the tail of `validate_approval_packages` (currently `:443-448`):

```python
    errors.extend(
        renewal_and_legacy_evidence_errors(
            RenewalScope(root, packages_by_path, known_artifacts)
        )
    )
    errors.extend(governing_agreement_errors(known_artifacts, packages_by_path))
    return errors
```

- [ ] **Step 5: Run the new tests and the full suite**

Run: `uv run pytest tests/test_approval_packages.py -v`
Expected: the two new tests PASS. The strict xfail still xfails — this task does not fix it.

Run: `uv run pytest -q`
Expected: `1606 passed, 9 skipped, 1 xfailed` (two new tests added).

- [ ] **Step 6: Verify the real repository is still valid**

Run: `uv run khepri-gov validate`
Expected: `Governance validation passed.`

This is the step that catches the `APP-001-bootstrap.md` case. If it reports `KHEPRI-DEC-001 approval_ref names no approved package`, the `.yaml` suffix guard in `_artifact_errors` is wrong or missing.

- [ ] **Step 7: Run ruff and commit**

```bash
uv run ruff check .
git add src/khepri_gov/governing_packages.py src/khepri_gov/approval_packages.py tests/test_approval_packages.py
git commit -m "feat: assert every artifact agrees with the package that governs it"
```

---

### Task 2: Registry-agreement checks become governing-only

**Files:**
- Modify: `src/khepri_gov/approval_transition_validation.py:191-218`
- Test: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes: `governs` from Task 1.
- Produces: no new public names. `_approval_errors` gains one early return.

This retires checks 1 and 2 for historical packages: `_approval_field_errors` (`:311`) and `_approval_ref_errors` (`:213`).

- [ ] **Step 1: Write the failing test**

```python
def test_superseded_package_keeps_its_own_approval_fields(tmp_path: Path) -> None:
    """A historical package is not re-judged against a registry that moved on."""
    valid_repository(tmp_path)
    _, _, renewal_path, renewal = approved_package_with_renewal(tmp_path)
    approve_renewal_in_registry(tmp_path, renewal_path, renewal)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "approval_ref must be" not in result.stdout
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_approval_packages.py::test_superseded_package_keeps_its_own_approval_fields -v`
Expected: this may already pass, because `_approval_is_carried_over` handles the plain renewal case. If it passes, keep it as a regression guard and move to Step 3 — the xfail scenario is the one that fails, and Task 4 completes it.

- [ ] **Step 3: Make `_approval_errors` governing-aware**

Replace `_approval_errors` (`:191-199`) with:

```python
    def _approval_errors(
        self,
        item: TransitionItem,
        approval: Mapping[str, Any] | None,
    ) -> list[str]:
        if approval is None:
            return []
        if self._approval_is_carried_over(item):
            return []
        if self._is_historical(item):
            return []
        errors = _approval_field_errors(item, approval)
        errors.extend(self._approval_ref_errors(item))
        return errors

    def _is_historical(self, item: TransitionItem) -> bool:
        """An approved package the registry no longer names is a record, not a claim."""
        if self.package.state != "approved":
            return False
        if governs(self.package.package_ref, item.artifact):
            return False
        return self.approved_packages.has_successor(
            self.package.package_ref,
            item.ref,
        )
```

Note `has_successor` is called **without** `replaces_approval`, matching `_state_is_settled` (`:179-182`), which already tolerates a successor of any `to_state`. That asymmetry between the two call sites is the defect's fingerprint.

Add `from khepri_gov.governing_packages import governs` to the imports.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/test_approval_packages.py -q`
Expected: all pass; the strict xfail still xfails.

- [ ] **Step 5: Verify and commit**

```bash
uv run khepri-gov validate
uv run ruff check .
git add src/khepri_gov/approval_transition_validation.py tests/test_approval_packages.py
git commit -m "fix: judge registry agreement only for the package that governs"
```

---

### Task 3: Split renewal state preservation by role

**Files:**
- Modify: `src/khepri_gov/approval_renewals.py:141-155`
- Test: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes: `LIFECYCLE_TRANSITIONS` and `EntryUnderReview`, both already imported in that module.
- Produces: no new public names.

This is check 3. Today `_preserves_state` compares `from_state` against `artifact.get("state")` — the live value — so a renewal recorded when the artifact was `accepted` fails once the artifact reaches `superseded`.

- [ ] **Step 1: Write the failing test**

```python
def test_historical_renewal_is_checked_for_legality_not_agreement(
    tmp_path: Path,
) -> None:
    valid_repository(tmp_path)
    _, _, renewal_path, renewal = approved_package_with_renewal(tmp_path)
    approve_renewal_in_registry(tmp_path, renewal_path, renewal)
    successor = registry_successor(tmp_path)
    write_yaml(
        tmp_path / "governance/approvals/APP-004.yaml",
        superseding_package(tmp_path, successor),
    )
    supersede_in_registry(tmp_path, successor)

    result = run_validator(tmp_path)

    assert "renewal must preserve state" not in result.stdout
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_approval_packages.py::test_historical_renewal_is_checked_for_legality_not_agreement -v`
Expected: FAIL — stdout contains `renewal must preserve state 'superseded'`.

- [ ] **Step 3: Split the check**

Replace `_renewal_state_errors` and `_preserves_state` (`:141-155`) with:

```python
def _renewal_state_errors(item: EntryUnderReview) -> list[str]:
    if _preserves_state(item):
        return []
    current_state = item.known[1].get("state")
    return [f"{item.review.label}: renewal must preserve state {current_state!r}"]


def _preserves_state(item: EntryUnderReview) -> bool:
    registry, artifact = item.known
    from_state = item.entry.get("from_state")
    to_state = item.entry.get("to_state")
    if from_state != to_state:
        return (from_state, to_state) in LIFECYCLE_TRANSITIONS[registry]
    if _is_current_authority(item):
        return from_state == artifact.get("state")
    return _is_known_state(registry, from_state)


def _is_current_authority(item: EntryUnderReview) -> bool:
    return item.known[1].get("approval_ref") == item.review.ref


def _is_known_state(registry: str, state: object) -> bool:
    edges = LIFECYCLE_TRANSITIONS[registry]
    return any(state in edge for edge in edges)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_approval_packages.py::test_historical_renewal_is_checked_for_legality_not_agreement -v`
Expected: PASS.

- [ ] **Step 5: Confirm the legality check still bites**

Run: `uv run pytest tests/test_approval_packages.py -k renewal -v`
Expected: all pass, including `test_renewal_must_supersede_current_approval` and the existing state-preservation tests, which cover the governing case.

- [ ] **Step 6: Verify and commit**

```bash
uv run khepri-gov validate
uv run ruff check .
git add src/khepri_gov/approval_renewals.py tests/test_approval_packages.py
git commit -m "fix: check a historical renewal for legality, not present agreement"
```

---

### Task 4: The prior-reference check loses its live read

**Files:**
- Modify: `src/khepri_gov/approval_renewals.py:189-193`
- Test: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: no new public names.

This is check 4, the half that contradicts check 2. `_requires_prior_ref` returns `True` when the package is `proposed` **or** when its `to_state` ends authority. The second branch demands the registry still name the superseded approval even after this package has taken over.

- [ ] **Step 1: Write the failing test**

```python
def test_approved_supersession_does_not_require_the_prior_registry_ref(
    tmp_path: Path,
) -> None:
    valid_repository(tmp_path)
    _, _, renewal_path, renewal = approved_package_with_renewal(tmp_path)
    approve_renewal_in_registry(tmp_path, renewal_path, renewal)
    successor = registry_successor(tmp_path)
    write_yaml(
        tmp_path / "governance/approvals/APP-004.yaml",
        superseding_package(tmp_path, successor),
    )
    supersede_in_registry(tmp_path, successor)

    result = run_validator(tmp_path)

    assert "does not currently use the superseded approval" not in result.stdout
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_approval_packages.py::test_approved_supersession_does_not_require_the_prior_registry_ref -v`
Expected: FAIL — stdout contains `APP-004: KHEPRI-DEC-002 does not currently use the superseded approval`.

- [ ] **Step 3: Drop the live branch**

Replace `_requires_prior_ref` (`:189-193`) with:

```python
def _requires_prior_ref(item: EntryUnderReview) -> bool:
    """Only an unrecorded package can be checked against the registry it will change."""
    return item.review.is_proposed
```

The substantive guarantee is unchanged: `_prior_package_errors` (`:157`) still requires `supersedes_approval_ref` to name an approved package containing the artifact, and it reads packages rather than the registry.

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_approval_packages.py::test_approved_supersession_does_not_require_the_prior_registry_ref -v`
Expected: PASS.

- [ ] **Step 5: Verify and commit**

```bash
uv run khepri-gov validate
uv run ruff check .
git add src/khepri_gov/approval_renewals.py tests/test_approval_packages.py
git commit -m "fix: check the superseded reference only before the transition is recorded"
```

---

### Task 5: Remove the xfail marker

**Files:**
- Modify: `tests/test_approval_packages.py:1064-1071` and the comment block above the helpers
- Test: the same file

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: nothing.

- [ ] **Step 1: Confirm the pinned test now passes with the marker still on**

Run: `uv run pytest tests/test_approval_packages.py::test_approved_renewal_survives_a_later_supersession -v`
Expected: **XPASS with a failure**, because the marker is `strict=True`. A strict xfail that passes is reported as a failure — that is the marker doing its job, and it is the signal the fix works.

- [ ] **Step 2: Remove the marker**

Delete the `@pytest.mark.xfail(strict=True, reason=...)` decorator (`:1064-1071`) entirely. Leave the test body and docstring untouched.

Rewrite the module comment block above the helpers so it describes the invariant that now holds rather than the defect that no longer does. Keep the history — it records why four checks were arranged this way — but state that the governing-package model replaced it, and name this plan.

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/test_approval_packages.py::test_approved_renewal_survives_a_later_supersession -v`
Expected: PASS.

- [ ] **Step 4: Run every gate**

```bash
uv run khepri-gov validate
uv run ruff check .
uv run pytest
uv run python -m khepri.rra.benchmark_gate
git diff --name-only origin/main...HEAD | uv run khepri-gov delegation-guard
```

Expected: `pytest` reports **1609 passed, 9 skipped, 0 xfailed** — the 1604 baseline, plus five tests added across Tasks 1–4, plus the un-xfailed test now counted as passed. If `xfailed` is anything other than `0`, the marker was weakened rather than removed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_approval_packages.py
git commit -m "test: remove the supersession xfail, the defect is fixed"
```

---

## Self-Review

**Spec coverage.** Design §1 → Task 1 (`governs`). §2 → Task 2. §3 → Task 3. §4 → Task 4. §5 → Task 1, deliberately first. Verification bullet "marker removed not weakened" → Task 5 Step 4. Verification bullet "negative test per relaxed check" → Task 1 Steps 1–2 cover the missing-package and state-mismatch cases; the "two packages both governing" case is **structurally impossible** under `governs`, since one `approval_ref` string cannot equal two package refs, so it needs no test. Out-of-scope items appear in no task, correctly.

**Placeholders.** None. Every code step carries real code; every run step carries a real command and expected output.

**Type consistency.** `governs(package_ref: str, artifact: Mapping[str, Any]) -> bool` is defined in Task 1 and consumed in Task 2 with that signature. `governing_agreement_errors` is defined and called once, in Task 1. `_is_historical`, `_is_current_authority`, and `_is_known_state` are each defined in the task that uses them. `item.review.ref` in Task 3 matches the field `_prior_package_errors` already reads.

**One risk the plan cannot remove.** Task 1's invariant is stronger than anything in the current code, so it may surface a pre-existing disagreement in the real registries. Step 6 of Task 1 exists to find that immediately. If it fires on something other than `APP-001-bootstrap.md`, stop: a real inconsistency in governed state is a finding for the owner, not something to loosen the new check around.
