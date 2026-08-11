# Minimal Single-Owner Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Khepri's multi-authority approval system with one merge-approved registry and one fail-closed validation command.

**Architecture:** `governance/registry.yaml` becomes the sole machine-readable artifact index. `src/khepri_gov/validator.py` validates its schema and graph, while `src/khepri_gov/cli.py` exposes only `khepri-gov validate`; Git merges by the sole owner supply approval identity and time.

**Tech Stack:** Python 3.13, PyYAML 6, argparse, pytest 8, Ruff, uv.

## Global Constraints

- Change governance only; product behavior, runtime architecture, privacy boundaries, and infrastructure remain unchanged.
- Keep only `active` and `retired` lifecycle states.
- Keep every error fail-closed and path-oriented, without tracebacks.
- Preserve removed evidence in Git history rather than an archive directory.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before handoff.
- Keep every new or rewritten file simple enough for a CodeScene Code Health score of 10.00.

---

## File Structure

- `governance/registry.yaml`: the only authoritative artifact metadata.
- `governance/CONSTITUTION.md`: short single-owner operating contract.
- `governance/decisions/KHEPRI-DEC-017-minimal-single-owner-governance.md`: migration rationale.
- `src/khepri_gov/validator.py`: YAML shape, artifact, path, dependency, family, and supersession validation.
- `src/khepri_gov/cli.py`: the single `validate` command.
- `tests/governance_support.py`: focused valid-repository fixture builder.
- `tests/test_governance_validator.py`: validator boundary tests.
- `tests/test_cli.py`: CLI behavior only.
- `.github/workflows/governance.yml`: validate, Ruff, pytest, and benchmark jobs; no lifecycle or delegation jobs.
- `AGENTS.md`, `README.md`, and `governance/README.md`: current operating instructions.

Legacy approval, delegation, renewal, lifecycle, digest, reference-assessment, registry, and test files are deleted after their replacements pass.

---

### Task 1: Build the Unified Registry Validator

**Files:**
- Create: `tests/governance_support.py`
- Create: `tests/test_governance_validator.py`
- Rewrite: `src/khepri_gov/validator.py`

**Interfaces:**
- Produces: `validate_repository(root: pathlib.Path) -> list[str]`.
- Consumes: `root/governance/registry.yaml` and artifact Markdown files below `root`.

- [ ] **Step 1: Add a valid repository fixture**

Create `tests/governance_support.py` with a `write_registry(root, artifacts)` helper that writes
schema version 2 and creates each declared Markdown document:

```python
from pathlib import Path
from typing import Any

import yaml


def valid_artifacts() -> list[dict[str, Any]]:
    return [
        {
            "type": "family",
            "id": "FND",
            "state": "active",
            "document": "governance/families/FND.md",
            "depends_on": [],
        },
        {
            "type": "specification",
            "id": "FND-001",
            "state": "active",
            "document": "governance/specifications/FND-001.md",
            "depends_on": ["FND"],
        },
    ]
```

- [ ] **Step 2: Write failing validator tests**

Cover a valid registry plus malformed YAML, unsupported schema, missing/unknown fields, duplicate
IDs/documents, invalid paths, unknown/self/duplicate dependencies, cycles, a specification with
zero or two family dependencies, active-to-retired dependencies, and invalid supersession:

```python
def test_valid_registry_passes(tmp_path: Path) -> None:
    write_registry(tmp_path, valid_artifacts())
    assert validate_repository(tmp_path) == []


def test_active_artifact_cannot_depend_on_retired_artifact(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    artifacts[0]["state"] = "retired"
    write_registry(tmp_path, artifacts)
    assert validate_repository(tmp_path) == [
        "registry: FND-001: active artifact depends on retired artifact 'FND'"
    ]
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run: `uv run pytest tests/test_governance_validator.py -q`

Expected: collection or assertion failures because the version-1 validator does not load the
unified registry.

- [ ] **Step 4: Implement the minimal validator**

Rewrite `src/khepri_gov/validator.py` around these constants and public entry point:

```python
SCHEMA_VERSION = 2
REGISTRY_PATH = Path("governance/registry.yaml")
ARTIFACT_FIELDS = {"type", "id", "state", "document", "depends_on"}
OPTIONAL_FIELDS = {"superseded_by"}
ARTIFACT_TYPES = {"decision", "family", "specification"}
ARTIFACT_STATES = {"active", "retired"}


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    artifacts = _load_artifacts(root, errors)
    if artifacts is None:
        return errors
    index = _validate_artifacts(root, artifacts, errors)
    _validate_dependencies(artifacts, index, errors)
    _validate_cycles(artifacts, index, errors)
    _validate_family_links(artifacts, index, errors)
    _validate_supersession(artifacts, index, errors)
    return errors
```

Use small functions, collect all safe-to-discover errors, and never infer malformed fields.

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/test_governance_validator.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the validator slice**

```powershell
git add src/khepri_gov/validator.py tests/governance_support.py tests/test_governance_validator.py
git commit -m "refactor(governance): add unified registry validator"
```

---

### Task 2: Migrate the Authoritative Governance Model

**Files:**
- Create: `governance/registry.yaml`
- Rewrite: `governance/CONSTITUTION.md`
- Create: `governance/decisions/KHEPRI-DEC-017-minimal-single-owner-governance.md`
- Test: `tests/test_governance_validator.py`

**Interfaces:**
- Consumes: `validate_repository(root)` from Task 1.
- Produces: a valid real repository registry with 33 governed artifacts.

- [ ] **Step 1: Add a failing real-registry test**

```python
def test_repository_registry_is_valid() -> None:
    root = Path(__file__).parents[1]
    assert validate_repository(root) == []
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run pytest tests/test_governance_validator.py::test_repository_registry_is_valid -q`

Expected: FAIL because `governance/registry.yaml` does not exist.

- [ ] **Step 3: Create schema-version-2 registry data**

Migrate the three families, sixteen existing decisions, and thirteen specifications. Add
`KHEPRI-DEC-017` as an active decision. Keep operative decisions, families, and specifications
`active`; retire proposed, rejected, superseded, assessment, approval-package, delegation, and
reserved-set artifacts whose mechanisms this migration removes.
Preserve `KHEPRI-DEC-003.superseded_by: KHEPRI-DEC-014`. Add each specification's family ID to
its `depends_on` list.

- [ ] **Step 4: Replace the constitution**

Write version 2.0.0 with five rules: sole owner, merge-to-main approval, unified-registry
authority, specification-before-code, and fail-closed validation. State the two lifecycle values
and make clear that branch/PR content is proposed until merged.

- [ ] **Step 5: Add the migration decision**

`KHEPRI-DEC-017` records the problem, decision, retained guarantees, removed mechanisms, migration
mapping, and consequence: Git history preserves old evidence while the current tree reflects the
single-owner model.

- [ ] **Step 6: Run real-registry validation**

Run: `uv run pytest tests/test_governance_validator.py -q`

Expected: all focused tests pass.

- [ ] **Step 7: Commit the governance model**

```powershell
git add governance/CONSTITUTION.md governance/registry.yaml governance/decisions/KHEPRI-DEC-017-minimal-single-owner-governance.md tests/test_governance_validator.py
git commit -m "gov: adopt minimal single-owner registry"
```

---

### Task 3: Reduce the CLI to One Command

**Files:**
- Rewrite: `src/khepri_gov/cli.py`
- Rewrite: `tests/test_cli.py`

**Interfaces:**
- Consumes: `validate_repository(root: Path) -> list[str]`.
- Produces: `main(argv: Sequence[str] | None = None) -> int` supporting only `validate` and
  optional `--root PATH`.

- [ ] **Step 1: Replace CLI tests with the retained contract**

```python
def test_validate_command_reports_success(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    write_registry(tmp_path, valid_artifacts())
    assert main(["--root", str(tmp_path), "validate"]) == 0
    assert capsys.readouterr().out == "Governance validation passed.\n"


def test_validate_command_reports_every_error(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    write_registry(tmp_path, [])
    assert main(["--root", str(tmp_path), "validate"]) == 1
    assert "ERROR registry: artifacts must not be empty" in capsys.readouterr().err
```

Also assert that `document-digest`, `approval-digest`, `delegation-guard`, and `lifecycle-guard`
are rejected by argparse.

- [ ] **Step 2: Run CLI tests and verify they fail**

Run: `uv run pytest tests/test_cli.py -q`

Expected: failures because the old commands remain and old fixtures target version-1 registries.

- [ ] **Step 3: Implement the single-command CLI**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="khepri-gov")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("command", choices=["validate"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    errors = validate_repository(arguments.root)
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        return 1
    print("Governance validation passed.")
    return 0
```

- [ ] **Step 4: Run CLI and validator tests**

Run: `uv run pytest tests/test_cli.py tests/test_governance_validator.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the CLI slice**

```powershell
git add src/khepri_gov/cli.py tests/test_cli.py
git commit -m "refactor(governance): expose validation only"
```

---

### Task 4: Delete Retired Governance Machinery

**Files:**
- Delete: `src/khepri_gov/approval_packages.py`
- Delete: `src/khepri_gov/approval_renewals.py`
- Delete: `src/khepri_gov/approval_transition_validation.py`
- Delete: `src/khepri_gov/delegation.py`
- Delete: `src/khepri_gov/digests.py`
- Delete: `src/khepri_gov/lifecycle.py`
- Delete: `src/khepri_gov/lifecycle_conditions.py`
- Delete: `src/khepri_gov/reference_assessments.py`
- Delete: `tests/lifecycle_support.py`
- Delete: `tests/test_approval_packages.py`
- Delete: `tests/test_delegation.py`
- Delete: `tests/test_lifecycle_conditions.py`
- Delete: `tests/test_lifecycle_integrity.py`
- Delete: `tests/test_lifecycle_packages.py`
- Delete: `tests/test_lifecycle_registry.py`
- Delete: `governance/approvals/`, `governance/delegations/`, `governance/authorities/`, and
  `governance/reference-reviews/` contents.
- Delete: old files under `governance/registries/`.
- Delete: `governance/templates/approval-package.yaml`, `governance/templates/approval.md`, and
  `governance/templates/reference-assessment.md`.

**Interfaces:**
- Consumes: the passing replacement validator and CLI.
- Produces: no import or active-file reference to retired governance machinery.

- [ ] **Step 1: Delete legacy implementations, tests, records, and registries**

Use a reviewable patch so Git retains exact deletion history.

- [ ] **Step 2: Prove no runtime imports remain**

Run:

```powershell
rg -n "approval_packages|approval_renewals|approval_transition_validation|khepri_gov\.delegation|khepri_gov\.lifecycle|reference_assessments" src tests
```

Expected: no matches.

- [ ] **Step 3: Run the focused governance suite**

Run: `uv run pytest tests/test_cli.py tests/test_governance_validator.py -q`

Expected: all tests pass.

- [ ] **Step 4: Commit the removal slice**

```powershell
git add -A src/khepri_gov tests governance
git commit -m "refactor(governance): remove approval and delegation machinery"
```

---

### Task 5: Align Instructions, Templates, Documentation, and CI

**Files:**
- Rewrite: `AGENTS.md`
- Rewrite: `governance/README.md`
- Modify: `README.md`
- Modify: `.github/workflows/governance.yml`
- Rewrite: `governance/templates/decision.md`
- Rewrite: `governance/templates/family.md`
- Rewrite: `governance/templates/specification.md`

**Interfaces:**
- Consumes: unified registry and `khepri-gov validate`.
- Produces: current contributor guidance with no active operational dependency on removed files or
  commands.

- [ ] **Step 1: Update repository instructions**

Make `AGENTS.md` point to `governance/registry.yaml`, retain specification-linked slices and the
three required checks, and replace approval-package language with merge-to-main approval.

- [ ] **Step 2: Rewrite governance documentation and templates**

Explain the sole-owner workflow in five steps: branch, edit document and registry together, run
validation, open/review PR, owner merges. Templates contain only outcome/context, decision or
requirements, exclusions, and verification.

- [ ] **Step 3: Update the root README**

Replace plural-registry and digest-approval sections with the unified registry and merge approval.
Keep product status claims aligned with active/retired registry entries and label historical design
documents as non-authoritative.

- [ ] **Step 4: Remove retired CI jobs**

Delete `lifecycle-guard` and `delegation-guard` jobs from `.github/workflows/governance.yml`. Keep
validate, Ruff, pytest, and benchmark behavior unchanged.

- [ ] **Step 5: Scan active operational surfaces for stale references**

Run:

```powershell
rg -n "governance/registries|approval-digest|document-digest|delegation-guard|lifecycle-guard|governance/approvals|governance/delegations" AGENTS.md README.md governance .github src tests
```

Expected: no active references; historical decision prose may name the retired model only when
clearly describing history.

- [ ] **Step 6: Run documentation-adjacent gates**

Run: `uv run khepri-gov validate` and `uv run ruff check .`

Expected: both pass.

- [ ] **Step 7: Commit the operating-surface update**

```powershell
git add AGENTS.md README.md governance .github/workflows/governance.yml
git commit -m "docs: align repository with single-owner governance"
```

---

### Task 6: Verify the Complete Migration

**Files:**
- Modify only files required to correct a demonstrated migration defect.

**Interfaces:**
- Consumes: Tasks 1 through 5.
- Produces: a clean, independently verifiable governance simplification branch.

- [ ] **Step 1: Run governance validation**

Run: `uv run khepri-gov validate`

Expected: `Governance validation passed.`

- [ ] **Step 2: Run Ruff**

Run: `uv run ruff check .`

Expected: `All checks passed!`

- [ ] **Step 3: Run the complete test suite**

Run: `uv run pytest`

Expected: all tests pass; local-stack tests may skip when the stack is unavailable.

- [ ] **Step 4: Inspect the final diff and worktree**

Run:

```powershell
git diff main...HEAD --check
git status --short
git diff main...HEAD --stat
```

Expected: no whitespace errors, a clean worktree, and a net deletion of governance code and data.

- [ ] **Step 5: Confirm the migration commit sequence**

Run: `git log --oneline main..HEAD`

Expected: the design checkpoint followed by focused validator, registry, CLI, removal, and
documentation commits; no unrelated product change appears.
