# Atomic Approval Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable, digest-locked approval packages and prepare a validated proposed
`APP-002` that can approve the RRA governance set through one later human action.

**Architecture:** Keep artifact lifecycle state authoritative in the existing registries. Add
package parsing, canonical hashing, document hashing, transition validation, dependency closure,
and approval materialization in a focused `approval_packages.py` module called by the repository
validator. Add read-only digest commands so packages can be prepared without hand-calculated
hashes.

**Tech Stack:** Python 3.13, PyYAML 6, `hashlib`, `json`, `pathlib`, pytest 8, Ruff, uv

## Global Constraints

- Read `AGENTS.md`, `governance/CONSTITUTION.md`, and all affected registries before editing.
- Treat existing YAML registries as authoritative for identity, state, ownership, dependencies,
  and approval evidence.
- Do not claim or record human approval from this plan, chat approval, automation, CI, or a merge.
- Keep `Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876`
  immutable and reference-only.
- Do not copy predecessor governance, specifications, catalogs, ledgers, or application code.
- Do not add product application code.
- Version 1 package states are exactly `proposed` and `approved`.
- Version 1 initial transitions are exactly decision `proposed -> accepted`, family
  `proposed -> active`, and specification `draft -> approved`.
- Approval renewal preserves an artifact's approved-or-later state and requires an exact
  `supersedes_approval_ref`.
- Full governed Markdown documents are SHA-256 locked.
- `APP-001-bootstrap.md` is the only legacy unstructured repository approval evidence.
- This plan ends with `APP-002` in `proposed`; no RRA registry state changes are authorized.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before handoff.

---

### Task 1: Canonical package and document digests

**Files:**
- Create: `src/khepri_gov/approval_packages.py`
- Create: `tests/__init__.py`
- Create: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes: package mappings loaded from YAML and repository document paths.
- Produces:
  - `document_digest(path: Path) -> str`
  - `manifest_payload(package: Mapping[str, Any]) -> dict[str, Any]`
  - `manifest_digest(package: Mapping[str, Any]) -> str`
  - `load_package(path: Path) -> tuple[dict[str, Any] | None, list[str]]`

- [ ] **Step 1: Create the approval-package test module and write failing digest tests**

Create an empty `tests/__init__.py`, then add:

```python
# tests/test_approval_packages.py
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from khepri_gov.approval_packages import document_digest, manifest_digest


def example_package() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "APP-002",
        "title": "Example",
        "state": "proposed",
        "owner": "AHMED-SHAABAN",
        "scope": "Approve exact artifacts.",
        "exclusions": ["Product code"],
        "manifest_digest": "sha256:" + ("0" * 64),
        "artifacts": [
            {
                "id": "KHEPRI-DEC-002",
                "document": "governance/decisions/KHEPRI-DEC-002.md",
                "document_sha256": "sha256:" + ("a" * 64),
                "from_state": "proposed",
                "to_state": "accepted",
            }
        ],
    }


def test_manifest_digest_is_canonical_and_excludes_approval_state() -> None:
    package = example_package()

    assert manifest_digest(package) == (
        "sha256:796d415bf26999eb891b4af35f1b4f49f814abb4ed83a1320e5f646fb0ac0f07"
    )

    approved = deepcopy(package)
    approved["state"] = "approved"
    approved["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-29",
        "approved_manifest_digest": manifest_digest(package),
        "evidence_ref": (
            "https://github.com/Kemetra/Khepri/pull/4"
            "#issuecomment-0000000000"
        ),
    }
    assert manifest_digest(approved) == manifest_digest(package)


def test_document_digest_hashes_exact_utf8_bytes(tmp_path: Path) -> None:
    document = tmp_path / "decision.md"
    document.write_text("# KHEPRI-DEC-002\n", encoding="utf-8")

    assert document_digest(document) == (
        "sha256:9b08cd92ee3f228e9d7167a935ec8acf13567019c633471fa6dab2bc1f5790ef"
    )
```

- [ ] **Step 2: Run the focused tests and confirm the missing module failure**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named
'khepri_gov.approval_packages'`.

- [ ] **Step 3: Implement the canonical digest primitives**

Create:

```python
# src/khepri_gov/approval_packages.py
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

PACKAGE_SCHEMA_VERSION = 1
PACKAGE_STATES = {"proposed", "approved"}
DIGEST_PREFIX = "sha256:"
MANIFEST_FIELDS = (
    "schema_version",
    "id",
    "title",
    "owner",
    "scope",
    "exclusions",
    "artifacts",
)


def _sha256(content: bytes) -> str:
    return f"{DIGEST_PREFIX}{hashlib.sha256(content).hexdigest()}"


def document_digest(path: Path) -> str:
    return _sha256(path.read_bytes())


def manifest_payload(package: Mapping[str, Any]) -> dict[str, Any]:
    return {field: package.get(field) for field in MANIFEST_FIELDS}


def manifest_digest(package: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        manifest_payload(package),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256(encoded)


def load_package(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None, [f"approval-packages:{path.name}: invalid YAML"]
    if not isinstance(loaded, dict):
        return None, [f"approval-packages:{path.name}: root must be a mapping"]
    return loaded, []
```

- [ ] **Step 4: Run focused tests and Ruff**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
uv run ruff check src/khepri_gov/approval_packages.py tests/test_approval_packages.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit the digest primitives**

```text
git add src/khepri_gov/approval_packages.py tests/__init__.py tests/test_approval_packages.py
git -c commit.gpgsign=false commit -m "feat(governance): add approval package digests"
```

---

### Task 2: Closed package shape and provenance validation

**Files:**
- Modify: `src/khepri_gov/approval_packages.py`
- Modify: `src/khepri_gov/validator.py:557-578`
- Modify: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes:
  - `root: Path`
  - `registries: Mapping[str, list[dict[str, Any]]]`
  - digest functions from Task 1
- Produces:
  - `validate_approval_packages(root, registries) -> list[str]`
- `validate_repository()` appends the returned errors after registry and reference validation.

- [ ] **Step 1: Add test fixture helpers and the first valid proposed-package test**

Append:

```python
from khepri_gov.approval_packages import (
    document_digest,
    manifest_digest,
)
from tests.test_cli import read_yaml, run_validator, valid_repository, write_document, write_yaml


def add_proposed_decision(root: Path) -> str:
    document = "governance/decisions/KHEPRI-DEC-002.md"
    write_document(root, document)
    path = root / "governance/registries/decisions.yaml"
    data = read_yaml(path)
    decisions = data["decisions"]
    assert isinstance(decisions, list)
    decisions.append(
        {
            "id": "KHEPRI-DEC-002",
            "title": "Atomic packages",
            "state": "proposed",
            "owner": "AHMED-SHAABAN",
            "document": document,
        }
    )
    write_yaml(path, data)
    return document


def proposed_package(root: Path) -> tuple[Path, dict[str, object]]:
    document = add_proposed_decision(root)
    package: dict[str, object] = {
        "schema_version": 1,
        "id": "APP-002",
        "title": "Atomic package",
        "state": "proposed",
        "owner": "AHMED-SHAABAN",
        "scope": "Approve the exact listed decision.",
        "exclusions": ["Product application code"],
        "artifacts": [
            {
                "id": "KHEPRI-DEC-002",
                "document": document,
                "document_sha256": document_digest(root / document),
                "from_state": "proposed",
                "to_state": "accepted",
            }
        ],
    }
    package["manifest_digest"] = manifest_digest(package)
    path = root / "governance/approvals/APP-002.yaml"
    write_yaml(path, package)
    return path, package


def test_valid_proposed_package_passes(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    proposed_package(tmp_path)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Add parameterized failing shape and provenance tests**

Add tests that mutate one field at a time and assert these exact errors:

```python
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda package: package.update(schema_version=2),
            "approval-packages:APP-002: unsupported schema_version 2",
        ),
        (
            lambda package: package.update(state="executed"),
            "approval-packages:APP-002: invalid state 'executed'",
        ),
        (
            lambda package: package.update(owner="UNKNOWN"),
            "approval-packages:APP-002: unknown owner 'UNKNOWN'",
        ),
        (
            lambda package: package.update(manifest_digest="sha256:" + ("0" * 64)),
            "approval-packages:APP-002: manifest_digest does not match canonical payload",
        ),
    ],
)
def test_package_shape_fails_closed(
    tmp_path: Path,
    mutation: object,
    message: str,
) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    mutation(package)  # type: ignore[operator]
    write_yaml(path, package)

    result = run_validator(tmp_path)

    assert result.returncode != 0
    assert message in result.stderr
```

Add separate tests for:

```text
approval-packages:APP-002: filename must match package id
approval-packages:APP-002: missing required field 'scope'
approval-packages:APP-002: unknown field 'extra'
approval-packages:APP-002: exclusions must be a list of non-empty strings
approval-packages:APP-002: artifacts must be a non-empty list
approval-packages:APP-002: duplicate artifact id 'KHEPRI-DEC-002'
approval-packages:APP-002: unknown artifact 'UNKNOWN'
approval-packages:APP-002: artifact document does not match registry
approval-packages:APP-002: document_sha256 does not match governed document
approval-packages:APP-002: proposed package must not contain approval
```

For every mutation other than `manifest_digest`, recompute `package["manifest_digest"]` before
writing so each test isolates its intended rule.

- [ ] **Step 3: Run the proposed-package tests and confirm validation is not integrated**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
```

Expected: the invalid packages incorrectly pass because `validate_repository()` does not load
them yet.

- [ ] **Step 4: Implement package discovery and closed shape validation**

Add these constants and public entry point to `approval_packages.py`:

```python
PACKAGE_REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "title",
    "state",
    "owner",
    "scope",
    "exclusions",
    "manifest_digest",
    "artifacts",
}
PACKAGE_OPTIONAL_FIELDS = {"approval"}
ARTIFACT_REQUIRED_FIELDS = {
    "id",
    "document",
    "document_sha256",
    "from_state",
    "to_state",
}
ARTIFACT_OPTIONAL_FIELDS = {"supersedes_approval_ref"}
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def validate_approval_packages(
    root: Path,
    registries: Mapping[str, list[dict[str, Any]]],
) -> list[str]:
    errors: list[str] = []
    packages: list[tuple[Path, dict[str, Any]]] = []
    approval_dir = root / "governance" / "approvals"
    for path in sorted(approval_dir.glob("APP-*.yaml")):
        package, load_errors = load_package(path)
        errors.extend(load_errors)
        if package is not None:
            packages.append((path, package))

    known_authorities = {
        item["id"]: item
        for item in registries.get("authorities", [])
        if isinstance(item.get("id"), str)
    }
    known_artifacts = {
        item["id"]: item
        for registry in ("decisions", "families", "specifications")
        for item in registries.get(registry, [])
        if isinstance(item.get("id"), str)
    }
    for path, package in packages:
        _validate_package_shape(
            root,
            path,
            package,
            known_authorities,
            known_artifacts,
            errors,
        )
    return errors
```

Implement `_validate_package_shape()` with these exact rules:

- label with a valid ID as `approval-packages:{package_id}`, otherwise use the filename;
- reject missing and unknown package fields;
- require integer schema version `1`;
- require ID pattern `APP-[0-9]{3}` and filename `{package_id}.yaml`;
- require non-empty string title, owner, and scope;
- require `state` in `PACKAGE_STATES`;
- require an active known owner;
- require a list of non-empty string exclusions;
- require a non-empty artifact list;
- reject missing and unknown artifact fields;
- reject duplicate artifact IDs;
- require every artifact ID to exist in a decision, family, or specification registry;
- require the package document path to equal the artifact registry document;
- require a lowercase prefixed SHA-256 digest and exact current document match;
- require exact `manifest_digest(package)` equality; and
- forbid `approval` when `state` is `proposed`.

Import and call it from `validator.py`:

```python
from khepri_gov.approval_packages import validate_approval_packages

# At the end of validate_repository(), before return:
errors.extend(validate_approval_packages(root, registries))
```

- [ ] **Step 5: Run focused and full tests**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
uv run pytest
uv run ruff check .
```

Expected: all commands pass.

- [ ] **Step 6: Commit shape validation**

```text
git add src/khepri_gov/approval_packages.py src/khepri_gov/validator.py tests/test_approval_packages.py
git -c commit.gpgsign=false commit -m "feat(governance): validate approval package shape"
```

---

### Task 3: Transition, materialization, and dependency closure

**Files:**
- Modify: `src/khepri_gov/approval_packages.py`
- Modify: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes: shape-valid packages and existing registry graphs.
- Produces:
  - atomic proposed/approved state validation;
  - exact approval-field materialization;
  - package-order dependency closure.

- [ ] **Step 1: Write failing transition and proposed-state tests**

Add parameterized tests covering:

```text
decision proposed -> accepted: valid
family proposed -> active: valid
specification draft -> approved: valid
decision proposed -> rejected: unsupported
family proposed -> retired: unsupported
specification draft -> implemented: unsupported
proposed package artifact not at from_state: invalid
initial transition with supersedes_approval_ref: invalid
```

Use these exact failure messages:

```text
approval-packages:APP-002: unsupported transition for KHEPRI-DEC-002: proposed -> rejected
approval-packages:APP-002: KHEPRI-DEC-002 must remain at from_state 'proposed'
approval-packages:APP-002: initial approval must not supersede prior evidence
```

- [ ] **Step 2: Write failing approved-materialization tests**

Create a helper that changes the example package and registry together:

```python
def approve_package(
    root: Path,
    path: Path,
    package: dict[str, object],
    *,
    evidence_ref: str = (
        "https://github.com/Kemetra/Khepri/pull/4"
        "#issuecomment-0000000000"
    ),
) -> None:
    digest = manifest_digest(package)
    package["state"] = "approved"
    package["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-29",
        "approved_manifest_digest": digest,
        "evidence_ref": evidence_ref,
    }
    decisions_path = root / "governance/registries/decisions.yaml"
    decisions = read_yaml(decisions_path)
    artifact = decisions["decisions"][1]  # type: ignore[index]
    artifact.update(
        {
            "state": "accepted",
            "approved_by": "AHMED-SHAABAN",
            "approved_at": "2026-07-29",
            "approval_ref": "governance/approvals/APP-002.yaml",
        }
    )
    write_yaml(decisions_path, decisions)
    write_yaml(path, package)
```

Test one valid approved package, then independently break:

```text
approval-packages:APP-002: approved package requires approval mapping
approval-packages:APP-002: approval missing required field 'evidence_ref'
approval-packages:APP-002: approval has unknown field 'extra'
approval-packages:APP-002: unknown or inactive approver 'UNKNOWN'
approval-packages:APP-002: package owner and approver must match
approval-packages:APP-002: approved_manifest_digest must equal manifest_digest
approval-packages:APP-002: evidence_ref must be a Khepri GitHub review or comment URL
approval-packages:APP-002: KHEPRI-DEC-002 must be at to_state 'accepted'
approval-packages:APP-002: KHEPRI-DEC-002 approved_by does not match package
approval-packages:APP-002: KHEPRI-DEC-002 approved_at does not match package
approval-packages:APP-002: KHEPRI-DEC-002 approval_ref must be governance/approvals/APP-002.yaml
```

- [ ] **Step 3: Write failing dependency-order tests**

Build a fixture with proposed family `RRA`, draft `RRA-001`, and draft `RRA-002` depending on
`RRA-001`. Test:

```text
FND already active, then RRA, RRA-001, RRA-002: valid
RRA-001 before RRA: family not active before specification
RRA-002 before RRA-001: dependency not approved before specification
dependency omitted from package and still draft: dependency closure failure
```

Use these messages:

```text
approval-packages:APP-002: family 'RRA' is not active before RRA-001
approval-packages:APP-002: dependency 'RRA-001' is not approved before RRA-002
```

- [ ] **Step 4: Run focused tests and confirm failures**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
```

Expected: newly added transition, materialization, and ordering tests fail.

- [ ] **Step 5: Implement transition and atomic materialization checks**

Add:

```python
INITIAL_TRANSITIONS = {
    "decisions": {("proposed", "accepted")},
    "families": {("proposed", "active")},
    "specifications": {("draft", "approved")},
}
APPROVED_OR_LATER = {
    "decisions": {"accepted"},
    "families": {"active", "retired"},
    "specifications": {"approved", "implemented", "verified", "retired"},
}
APPROVAL_FIELDS = ("approved_by", "approved_at", "approval_ref")
PACKAGE_APPROVAL_FIELDS = {
    "approved_by",
    "approved_at",
    "approved_manifest_digest",
    "evidence_ref",
}
```

Create an index that retains artifact registry type:

```python
known_artifacts = {
    item["id"]: (registry, item)
    for registry in ("decisions", "families", "specifications")
    for item in registries.get(registry, [])
    if isinstance(item.get("id"), str)
}
```

Implement `_validate_transitions_and_materialization()`:

- Walk artifacts in package order.
- Accept only `INITIAL_TRANSITIONS[registry]` without supersession.
- Accept same-state renewal only when the state belongs to `APPROVED_OR_LATER[registry]` and
  `supersedes_approval_ref` is present.
- For proposed packages require current state `from_state`.
- For approved packages require current state `to_state`.
- Require the approval mapping to contain exactly `PACKAGE_APPROVAL_FIELDS`.
- Accept `approved_at` as a YAML date/datetime or ISO 8601 date string, using the same behavior
  as the existing registry validator.
- Require a known active approver equal to owner.
- Require `approved_manifest_digest == manifest_digest`.
- Parse `evidence_ref` with `urlparse`; require HTTPS, host `github.com`, path beginning
  `/Kemetra/Khepri/pull/` or `/Kemetra/Khepri/issues/`, and fragment beginning
  `issuecomment-` or `pullrequestreview-`.
- Require all three artifact approval fields to equal the package values and package path.

Implement dependency closure by maintaining simulated family/specification states after each
package entry. Apply each transition to the simulated state after validating that entry, so a
family or dependency must appear earlier, not merely somewhere in the package.

- [ ] **Step 6: Run focused and full verification**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

Expected: all commands pass.

- [ ] **Step 7: Commit atomic transition validation**

```text
git add src/khepri_gov/approval_packages.py tests/test_approval_packages.py
git -c commit.gpgsign=false commit -m "feat(governance): enforce atomic package transitions"
```

---

### Task 4: Renewal chains and legacy-evidence boundary

**Files:**
- Modify: `src/khepri_gov/approval_packages.py`
- Modify: `tests/test_approval_packages.py`

**Interfaces:**
- Consumes: current registry `approval_ref` values and all YAML packages.
- Produces: one linear approval chain per artifact and a closed legacy Markdown exception.

- [ ] **Step 1: Write failing renewal-chain tests**

Create an approved `APP-002` for one accepted decision. Change that decision document and add a
proposed `APP-003` with:

```yaml
from_state: accepted
to_state: accepted
supersedes_approval_ref: governance/approvals/APP-002.yaml
```

Assert the chain is valid. Then test these failures:

```text
changed governed document without proposed superseding package
supersedes reference differs from current artifact approval_ref
two proposed packages claim the same artifact
renewal changes the lifecycle state
approved APP-003 materializes without replacing artifact approval_ref
```

Use exact messages:

```text
approval-packages:APP-002: governed document for KHEPRI-DEC-002 changed without renewal
approval-packages:APP-003: KHEPRI-DEC-002 does not currently use the superseded approval
approval-packages: artifact KHEPRI-DEC-002 appears in multiple proposed packages
approval-packages:APP-003: renewal must preserve state 'accepted'
```

- [ ] **Step 2: Write failing legacy evidence tests**

Test that `governance/approvals/APP-001-bootstrap.md` remains valid. Add an accepted artifact
whose `approval_ref` is `governance/approvals/APP-999.md` and assert:

```text
approval-packages: unstructured approval evidence is limited to APP-001-bootstrap.md
```

Keep direct external URL approval references valid for existing fixtures.

- [ ] **Step 3: Run focused tests and confirm failures**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
```

Expected: renewal and legacy-boundary tests fail.

- [ ] **Step 4: Implement linear renewal validation**

Track:

```python
proposed_claims: dict[str, str] = {}
packages_by_path: dict[str, dict[str, Any]] = {}
```

For each proposed renewal:

- reject a second proposed claimant;
- require current registry `approval_ref == supersedes_approval_ref`;
- require the superseded path to identify an approved YAML package;
- require the prior package to contain the same artifact;
- require `from_state == to_state == current registry state`; and
- require the changed current document to match the new package digest.

For each artifact whose current `approval_ref` names an approved YAML package:

- validate its current document against that package when no renewal is proposed;
- otherwise validate against the proposed successor;
- require any approved successor to replace the registry `approval_ref`; and
- leave historical package files immutable and valid without comparing their old document digest
  to the current tree.

Scan approved artifact references and reject repository-relative Markdown approval evidence other
than exact path `governance/approvals/APP-001-bootstrap.md`.

- [ ] **Step 5: Run all checks**

Run:

```text
uv run pytest tests/test_approval_packages.py -q
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

Expected: all commands pass.

- [ ] **Step 6: Commit renewal and legacy rules**

```text
git add src/khepri_gov/approval_packages.py tests/test_approval_packages.py
git -c commit.gpgsign=false commit -m "feat(governance): validate approval renewal chains"
```

---

### Task 5: Digest CLI and package governance documentation

**Files:**
- Modify: `src/khepri_gov/cli.py:11-29`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_approval_packages.py`
- Create: `governance/decisions/KHEPRI-DEC-004-atomic-approval-packages.md`
- Modify: `governance/registries/decisions.yaml`
- Create: `governance/templates/approval-package.yaml`
- Modify: `governance/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes:
  - `document_digest(path: Path) -> str`
  - `load_package(path: Path)`
  - `manifest_digest(package)`
- Produces:
  - `uv run khepri-gov --root ROOT document-digest PATH`
  - `uv run khepri-gov --root ROOT approval-digest PATH`
  - proposed decision `KHEPRI-DEC-004`

- [ ] **Step 1: Write failing CLI digest tests**

Refactor the existing subprocess helper into:

```python
def run_cli(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in [source_path, environment.get("PYTHONPATH", "")] if part
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "khepri_gov.cli",
            "--root",
            str(root),
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return run_cli(root, "validate")
```

Import `run_cli` into `tests/test_approval_packages.py` after the helper refactor and add:

```python
def test_document_digest_command(tmp_path: Path) -> None:
    document = tmp_path / "decision.md"
    document.write_text("# KHEPRI-DEC-002\n", encoding="utf-8")

    result = run_cli(tmp_path, "document-digest", "decision.md")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "sha256:9b08cd92ee3f228e9d7167a935ec8acf13567019c633471fa6dab2bc1f5790ef\n"
    )


def test_approval_digest_command(tmp_path: Path) -> None:
    path = tmp_path / "APP-002.yaml"
    write_yaml(path, example_package())

    result = run_cli(tmp_path, "approval-digest", "APP-002.yaml")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "sha256:796d415bf26999eb891b4af35f1b4f49f814abb4ed83a1320e5f646fb0ac0f07\n"
    )
```

Also test a missing path and malformed package return code `1` with one `ERROR` line and no
traceback.

- [ ] **Step 2: Run CLI tests and confirm parser rejection**

Run:

```text
uv run pytest tests/test_cli.py tests/test_approval_packages.py -q
```

Expected: new commands fail because argparse only accepts `validate`.

- [ ] **Step 3: Implement read-only digest commands**

Keep `--root` before the command. Extend the parser with a positional `path` required for digest
commands and forbidden for validation. Dispatch:

```python
if arguments.command == "validate":
    if arguments.path is not None:
        parser.error("validate does not accept a path")
    return _run_validate(arguments.root)

path = (arguments.root / arguments.path).resolve()
if not path.is_relative_to(arguments.root.resolve()) or not path.is_file():
    print("ERROR path does not resolve to a repository file", file=sys.stderr)
    return 1
if arguments.command == "document-digest":
    print(document_digest(path))
    return 0
package, errors = load_package(path)
if errors:
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    return 1
assert package is not None
print(manifest_digest(package))
return 0
```

Use command choices `validate`, `document-digest`, and `approval-digest`.

- [ ] **Step 4: Add the proposed mechanism decision**

Create `governance/decisions/KHEPRI-DEC-004-atomic-approval-packages.md` with:

```markdown
# KHEPRI-DEC-004: Atomic approval packages and bounded implementation authority

## Context

Khepri requires explicit named-human approval, but repeating one coherent approval decision
across related decisions, a family, and dependent specifications creates delay without adding
review quality.

## Proposed decision

Adopt digest-locked approval packages as structured evidence. One active human authority may
approve an exact, dependency-closed manifest once. Automation may then materialize only the
listed lifecycle transitions when the approved manifest digest and governed document digests are
unchanged.

Artifact registries remain authoritative for lifecycle state. A package never grants authority
by itself, and implementation within approved specifications needs no repeated product approval
unless a governed artifact changes.

## Consequences

- Packages fail closed on partial application, stale documents, missing dependencies, ambiguous
  renewal chains, or inconsistent evidence.
- Full governed documents are immutable under one approval; changes require explicit renewal.
- Automation calculates, validates, and materializes but never approves.
- Architecture/provider selection and beta launch authorization remain separately governed.

This decision remains proposed until exact traceable human approval is supplied.
```

Append this registry entry without approval fields:

```yaml
  - id: KHEPRI-DEC-004
    title: Atomic approval packages and bounded implementation authority
    state: proposed
    owner: AHMED-SHAABAN
    document: governance/decisions/KHEPRI-DEC-004-atomic-approval-packages.md
```

- [ ] **Step 5: Add the package template and documentation**

Create `governance/templates/approval-package.yaml` with a syntactically complete example using
valid symbolic SHA-256 strings of 64 lowercase zeroes. State in comments that real packages must
replace them with `document-digest` and `approval-digest` output.

Update `governance/README.md` and `README.md` to document:

- package files are structured evidence, not authoritative lifecycle registries;
- proposed versus approved behavior;
- exact digest commands;
- the one-action approval statement must identify authority, package ID, and manifest digest;
- `APP-001-bootstrap.md` is the only legacy Markdown exception; and
- `KHEPRI-DEC-004` remains proposed.

- [ ] **Step 6: Run focused and full checks**

Run:

```text
uv run pytest tests/test_cli.py tests/test_approval_packages.py -q
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

Expected: all commands pass; `KHEPRI-DEC-004` remains proposed.

- [ ] **Step 7: Commit tooling and governance documentation**

```text
git add src/khepri_gov/cli.py tests/test_cli.py tests/test_approval_packages.py governance README.md
git -c commit.gpgsign=false commit -m "feat(governance): define atomic approval packages"
```

---

### Task 6: Prepare proposed APP-002 without claiming approval

**Files:**
- Create: `governance/approvals/APP-002.yaml`
- Test: repository-wide validation

**Interfaces:**
- Consumes: digest CLI, `KHEPRI-DEC-002` through `KHEPRI-DEC-004`, `RRA`, and
  `RRA-001` through `RRA-007`.
- Produces: one valid proposed package and its exact manifest digest for later human review.

- [ ] **Step 1: Create the package manifest skeleton with exact scope and ordering**

Create `governance/approvals/APP-002.yaml` with:

```yaml
schema_version: 1
id: APP-002
title: RRA private beta governance approval
state: proposed
owner: AHMED-SHAABAN
scope: >-
  Approve the selective-transfer protocol, the bounded RRA private-beta decision, the atomic
  approval-package mechanism, the RRA family, and RRA-001 through RRA-007 exactly as digested.
exclusions:
  - Product application code
  - Runtime or provider selection
  - Beta launch authorization
  - Commercial authentication, workspaces, organizations, billing, scheduling, and agency features
  - Any claim that technical review or automation is human approval
manifest_digest: sha256:0000000000000000000000000000000000000000000000000000000000000000
artifacts:
```

Append these exact ordered artifact records:

| ID | Document | From | To |
|---|---|---|---|
| `KHEPRI-DEC-002` | `governance/decisions/KHEPRI-DEC-002-selective-transfer-protocol.md` | `proposed` | `accepted` |
| `KHEPRI-DEC-003` | `governance/decisions/KHEPRI-DEC-003-rra-private-beta.md` | `proposed` | `accepted` |
| `KHEPRI-DEC-004` | `governance/decisions/KHEPRI-DEC-004-atomic-approval-packages.md` | `proposed` | `accepted` |
| `RRA` | `governance/families/RRA.md` | `proposed` | `active` |
| `RRA-001` | `governance/specifications/RRA-001.md` | `draft` | `approved` |
| `RRA-002` | `governance/specifications/RRA-002.md` | `draft` | `approved` |
| `RRA-003` | `governance/specifications/RRA-003.md` | `draft` | `approved` |
| `RRA-004` | `governance/specifications/RRA-004.md` | `draft` | `approved` |
| `RRA-005` | `governance/specifications/RRA-005.md` | `draft` | `approved` |
| `RRA-006` | `governance/specifications/RRA-006.md` | `draft` | `approved` |
| `RRA-007` | `governance/specifications/RRA-007.md` | `draft` | `approved` |

Each record contains exactly `id`, `document`, `document_sha256`, `from_state`, and `to_state`.
Do not add `supersedes_approval_ref`; these are initial approvals.

- [ ] **Step 2: Calculate and insert every exact document digest**

Run this PowerShell loop to calculate every table row:

```powershell
$documents = @(
  'governance/decisions/KHEPRI-DEC-002-selective-transfer-protocol.md',
  'governance/decisions/KHEPRI-DEC-003-rra-private-beta.md',
  'governance/decisions/KHEPRI-DEC-004-atomic-approval-packages.md',
  'governance/families/RRA.md',
  'governance/specifications/RRA-001.md',
  'governance/specifications/RRA-002.md',
  'governance/specifications/RRA-003.md',
  'governance/specifications/RRA-004.md',
  'governance/specifications/RRA-005.md',
  'governance/specifications/RRA-006.md',
  'governance/specifications/RRA-007.md'
)
foreach ($document in $documents) {
  uv run khepri-gov document-digest $document
}
```

Insert each output beside its corresponding path. Re-run the loop after insertion and compare
each path/output pair byte-for-byte to prevent transposition.

- [ ] **Step 3: Calculate and insert the exact manifest digest**

Run:

```text
uv run khepri-gov approval-digest governance/approvals/APP-002.yaml
```

Replace `manifest_digest` with the exact output, then rerun the same command and confirm the file
value equals stdout.

- [ ] **Step 4: Prove the package remains proposed and atomic**

Run:

```text
uv run khepri-gov validate
```

Expected: `Governance validation passed.` Confirm with `git diff` that:

- `APP-002` has no `approval` block;
- `KHEPRI-DEC-002`, `KHEPRI-DEC-003`, and `KHEPRI-DEC-004` remain `proposed`;
- `RRA` remains `proposed`;
- `RRA-001` through `RRA-007` remain `draft`; and
- none of those artifacts gained `approved_by`, `approved_at`, or `approval_ref`.

- [ ] **Step 5: Run final verification**

Run:

```text
uv run khepri-gov validate
uv run ruff check .
uv run pytest
git diff --check
```

Expected: all commands pass.

- [ ] **Step 6: Commit the proposed package**

```text
git add governance/approvals/APP-002.yaml
git -c commit.gpgsign=false commit -m "feat(governance): propose RRA atomic approval package"
```

- [ ] **Step 7: Stop at the human approval gate**

Report the exact committed `APP-002` manifest digest. Do not transition any registry state.
The next authorized action requires durable GitHub evidence. Copy the literal `sha256:` line
printed in Step 3 into this exact statement:

```text
I, Ahmed Shaaban (AHMED-SHAABAN), approve APP-002 manifest
and authorize only its listed state transitions and mechanical insertion of this evidence
without changing the manifest payload.
```

Place the literal digest immediately after the word `manifest` in that statement. Do not
abbreviate it or substitute a branch, commit, pull-request number, or chat reference.

After that evidence exists, write a short continuation plan that inserts its exact URL/date,
changes `APP-002` to `approved`, atomically materializes all eleven registry transitions, and
runs the full verification suite. Do not reuse chat text or infer identity as evidence.
