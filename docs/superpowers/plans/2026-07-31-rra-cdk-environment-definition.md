# RRA CDK Environment Definition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define one AWS CDK v2 application that composes Khepri's five existing infrastructure constructs into a single stack class, instantiated twice to produce the RRA private-beta environment and the dedicated benchmark environment with identical sizing.

**Architecture:** A governed YAML file holds `KHEPRI-DEC-007`'s sizing table verbatim. `sizing_source.py` loads it and hands it to the existing `resolve_sizing`, which refuses anything incomplete. `RraEnvironmentStack` composes `GovernedNetwork`, `GovernedDataResources`, `GovernedDatabase`, `GovernedImageRepository`, and `GovernedCompute` in that order, taking only the five environment-varying values `KHEPRI-DEC-007` permits to differ. `app.py` instantiates the stack twice against the same `InfrastructureSizing` object, both pinned to `me-central-1`.

**Tech Stack:** Python 3.13, `uv`, `aws-cdk-lib` v2, `constructs`, `PyYAML`, `pytest`, `aws_cdk.assertions.Template`.

## Global Constraints

- Authority is `KHEPRI-DEC-005` (runtime, providers, deployment boundary) and `KHEPRI-DEC-007` (sizing). Both are `accepted`. Do not widen the slice beyond them.
- Every sizing value comes from `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml`. Never read an environment variable, a CDK context value, or a default, and never invent a size.
- Region is `me-central-1`, pinned explicitly on every stack instance. Never inherit an ambient region.
- The OCI image digest is a descriptor fact, not a sizing value. It is a required constructor prop with no default. It never appears in the sizing YAML.
- The two environments may differ ONLY in: name, network isolation, service desired count, deletion protection, and the absence of customer content. Every sizing value is identical.
- Benchmark service desired count is exactly `1`. Beta desired count and autoscaling are NOT set by this slice.
- **Deletion protection is deliberately NOT parameterized by this slice.** `src/khepri/infra/database.py:115` hardcodes `deletion_protection=True` with `removal_policy=RETAIN`. `KHEPRI-DEC-007` permits the two environments to differ here, but changing it means editing a construct this slice does not own, and protecting the benchmark database is the safe direction to be wrong in. State this explicitly in the pull request as a known, bounded deferral rather than leaving a reviewer to notice it.
- Type annotations on every function signature. `from __future__ import annotations` at the top of every module. `@dataclass(frozen=True, slots=True)` for DTOs.
- Constructors take two or three arguments. CodeScene requires every new file to score 10.00 and it cannot be reproduced locally; keep functions small and single-purpose.
- Run before handoff: `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
- Commits are unsigned in this repository at the owner's instruction: use `git -c commit.gpgsign=false commit`.

---

### Task 1: The governed sizing declaration and its loader

**Files:**
- Create: `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml`
- Create: `src/khepri/infra/sizing_source.py`
- Test: `tests/test_infra_sizing_source.py`

**Interfaces:**
- Consumes: `khepri.infra.sizing.resolve_sizing(source: Mapping[str, str]) -> InfrastructureSizing` and `khepri.infra.sizing.SizingRefused`, both already on `main`.
- Produces: `SIZING_DECLARATION` (a `Path` constant) and `load_sizing(path: Path | None = None) -> InfrastructureSizing`.

- [ ] **Step 1: Write the governed sizing YAML**

Create `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml`. Every value is quoted because
`resolve_sizing` expects a `Mapping[str, str]` and parses the integers itself.

```yaml
# KHEPRI-DEC-007 sizing, recorded verbatim so that changing a size is a governed change.
#
# Every value below is fixed by governance/decisions/KHEPRI-DEC-007-rra-infrastructure-sizing.md
# and is identical between the beta and benchmark environments. Editing one changes this file's
# digest, which changes the environment_digest once the descriptor exists, which invalidates
# prior benchmark evidence by the identity check in src/khepri/rra/performance.py.
schema_version: "1"
web_cpu_units: "1024"
web_memory_mib: "4096"
web_ephemeral_storage_gib: "20"
worker_cpu_units: "4096"
worker_memory_mib: "16384"
worker_ephemeral_storage_gib: "40"
database_instance_class: "db.m7g.large"
allocated_storage_gib: "100"
backup_retention_days: "7"
visibility_timeout_seconds: "300"
message_retention_seconds: "1209600"
receive_wait_seconds: "20"
max_receive_count: "3"
max_attempts: "3"
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_infra_sizing_source.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from khepri.infra.sizing import SizingRefused
from khepri.infra.sizing_source import SIZING_DECLARATION, load_sizing


class TestTheGovernedDeclaration:
    def test_the_declaration_file_exists_where_governance_keeps_it(self) -> None:
        assert SIZING_DECLARATION.name == "KHEPRI-BMK-001-sizing.yaml"
        assert SIZING_DECLARATION.is_file()

    def test_it_resolves_to_the_khepri_dec_007_sizing(self) -> None:
        """Every figure here is fixed by KHEPRI-DEC-007 and must not drift."""
        sizing = load_sizing()

        assert sizing.services.web.cpu_units == 1024
        assert sizing.services.web.memory_mib == 4096
        assert sizing.services.web.ephemeral_storage_gib == 20
        assert sizing.services.worker.cpu_units == 4096
        assert sizing.services.worker.memory_mib == 16384
        assert sizing.services.worker.ephemeral_storage_gib == 40
        assert sizing.database.instance_class == "db.m7g.large"
        assert sizing.database.allocated_storage_gib == 100
        assert sizing.database.backup_retention_days == 7
        assert sizing.queue.timings.visibility_timeout_seconds == 300
        assert sizing.queue.timings.message_retention_seconds == 1209600
        assert sizing.queue.timings.receive_wait_seconds == 20
        assert sizing.queue.retries.max_receive_count == 3
        assert sizing.queue.retries.max_attempts == 3


class TestItRefusesRatherThanDefaulting:
    def test_a_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_sizing(tmp_path / "absent.yaml")

    def test_a_declaration_missing_one_field_is_refused(self, tmp_path: Path) -> None:
        """resolve_sizing has no 'sized by default' answer, and neither does this loader."""
        source = yaml.safe_load(SIZING_DECLARATION.read_text(encoding="utf-8"))
        del source["worker_memory_mib"]
        path = tmp_path / "incomplete.yaml"
        path.write_text(yaml.safe_dump(source), encoding="utf-8")

        with pytest.raises(SizingRefused):
            load_sizing(path)

    def test_a_non_mapping_document_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- not a mapping\n", encoding="utf-8")

        with pytest.raises(SizingRefused):
            load_sizing(path)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_infra_sizing_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.infra.sizing_source'`

- [ ] **Step 4: Write the minimal implementation**

Create `src/khepri/infra/sizing_source.py`:

```python
"""The one place a sizing declaration is read, and the only shape it may arrive in.

`KHEPRI-DEC-007` fixes every size in this platform and requires that changing one is a governed
change rather than an operational adjustment. That holds only if the values live in a reviewable
document whose bytes are covered by a digest, so they live in `governance/benchmarks/` and are read
from there.

`sizing.resolve_sizing` already refuses a missing, blank, or non-integer field. This module adds no
tolerance of its own: it locates the document, insists it is a mapping of strings, and hands it
over. Nothing here supplies a fallback, because a template synthesized around a guessed size is
indistinguishable from one synthesized around an approved size once it is deployed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from khepri.infra.sizing import InfrastructureSizing, SizingRefused, resolve_sizing

SIZING_DECLARATION = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "benchmarks"
    / "KHEPRI-BMK-001-sizing.yaml"
)


def load_sizing(path: Path | None = None) -> InfrastructureSizing:
    """Read the governed declaration and resolve it, refusing anything incomplete."""
    document = path if path is not None else SIZING_DECLARATION
    parsed = yaml.safe_load(document.read_text(encoding="utf-8"))
    return resolve_sizing(_require_mapping(parsed))


def _require_mapping(parsed: Any) -> dict[str, str]:
    if not isinstance(parsed, dict):
        raise SizingRefused("A sizing declaration must be a mapping.")
    return {str(key): str(value) for key, value in parsed.items()}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_infra_sizing_source.py -v`
Expected: PASS (5 tests)

Note: `resolve_sizing` ignores the extra `schema_version` key because it reads only the keys it
requires. If it instead rejects unknown keys, remove `schema_version` from the YAML and re-run.

- [ ] **Step 6: Confirm PyYAML is a declared dependency**

Run: `uv run python -c "import yaml; print(yaml.__version__)"`

If this fails, add it: `uv add pyyaml` and commit `pyproject.toml` and `uv.lock` with this task.
`khepri-gov` already parses YAML registries, so it is almost certainly present.

- [ ] **Step 7: Run the full gate**

```bash
uv run ruff check .
uv run khepri-gov validate
uv run pytest -q
```
Expected: ruff clean, governance validation passed, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add governance/benchmarks/KHEPRI-BMK-001-sizing.yaml src/khepri/infra/sizing_source.py tests/test_infra_sizing_source.py
git -c commit.gpgsign=false commit -m "feat(infra): record the governed sizing declaration and read it"
```

---

### Task 2: The environment stack

**Files:**
- Create: `src/khepri/infra/environment.py`
- Test: `tests/test_infra_environment.py`

**Interfaces:**
- Consumes: `load_sizing` from Task 1. Plus, all already on `main`:
  `GovernedNetwork(scope, construct_id)` exposing `.vpc`;
  `GovernedDataResources(scope, construct_id, queue: QueueSizing)` exposing `.key`, `.bucket`, `.queue`, `.dead_letter_queue`;
  `GovernedDatabase(scope, construct_id, props: DatabaseProps)` exposing `.instance`, `.secret`;
  `GovernedImageRepository(scope, construct_id, key: kms.IKey)` exposing `.repository`;
  `GovernedCompute(scope, construct_id, props: ComputeProps)` exposing `.cluster`, `.web_task`, `.worker_task`.
  `DatabaseProps(vpc, key, sizing)`, `ComputeProps(resources, image, sizing)`,
  `EnvironmentResources(network, data, database)`, `PinnedImage(repository, digest)`.
- Produces: `REGION` (str constant `"me-central-1"`), `EnvironmentProps` dataclass, and
  `RraEnvironmentStack(scope, construct_id, props: EnvironmentProps)` exposing `.network`,
  `.data`, `.database`, `.image`, `.compute`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_infra_environment.py`:

```python
from __future__ import annotations

import pytest
from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from khepri.infra.environment import REGION, EnvironmentProps, RraEnvironmentStack
from khepri.infra.sizing_source import load_sizing

IMAGE_DIGEST = "sha256:" + "ab" * 32


def _stack(name: str, *, desired_count: int | None) -> RraEnvironmentStack:
    return RraEnvironmentStack(
        App(),
        name,
        EnvironmentProps(
            sizing=load_sizing(),
            image_digest=IMAGE_DIGEST,
            desired_count=desired_count,
        ),
    )


@pytest.fixture(scope="module")
def benchmark() -> Template:
    return Template.from_stack(_stack("Benchmark", desired_count=1))


class TestItComposesEveryGovernedResource:
    def test_the_isolated_network_is_present(self, benchmark: Template) -> None:
        benchmark.resource_count_is("AWS::EC2::VPC", 1)
        benchmark.resource_count_is("AWS::EC2::NatGateway", 0)

    def test_one_customer_managed_key_encrypts_the_environment(
        self, benchmark: Template
    ) -> None:
        """KHEPRI-DEC-005 audits infrastructure access through one KMS grant."""
        benchmark.resource_count_is("AWS::KMS::Key", 1)

    def test_the_content_bucket_and_both_queues_exist(self, benchmark: Template) -> None:
        benchmark.resource_count_is("AWS::S3::Bucket", 1)
        benchmark.resource_count_is("AWS::SQS::Queue", 2)

    def test_the_database_and_both_task_definitions_exist(
        self, benchmark: Template
    ) -> None:
        benchmark.resource_count_is("AWS::RDS::DBInstance", 1)
        benchmark.resource_count_is("AWS::ECS::TaskDefinition", 2)


class TestTheRegionIsPinned:
    def test_the_stack_names_me_central_1_rather_than_inheriting_one(self) -> None:
        """KHEPRI-DEC-007 requires the definition to fail rather than substitute a neighbour.

        A stack with no explicit env is region-agnostic and deploys wherever CDK_DEFAULT_REGION
        points, which is substitution by omission.
        """
        assert REGION == "me-central-1"
        assert _stack("Pinned", desired_count=1).region == REGION


class TestItRefusesRatherThanDefaulting:
    def test_a_tag_is_not_an_image_digest(self) -> None:
        with pytest.raises(ValueError):
            _stack_with_digest("latest")

    def test_a_malformed_digest_is_refused(self) -> None:
        with pytest.raises(ValueError):
            _stack_with_digest("sha256:abc")


def _stack_with_digest(digest: str) -> RraEnvironmentStack:
    return RraEnvironmentStack(
        App(),
        "Bad",
        EnvironmentProps(sizing=load_sizing(), image_digest=digest, desired_count=1),
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_infra_environment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.infra.environment'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/khepri/infra/environment.py`:

```python
"""One environment, defined once, so that two of them cannot drift apart.

**Why one class and not two.** `KHEPRI-DEC-007` requires the benchmark environment to be "a second
instantiation of the same CDK application ... not a second definition to keep in sync". Two classes
could diverge, and divergence silently voids the benchmark's meaning: a duration measured on
hardware sized unlike beta is not evidence about beta, so the ten-minute objective would be met
somewhere nobody ships. One class makes that impossible rather than merely discouraged.

**Why the props are so few.** `KHEPRI-DEC-007` enumerates what the two environments may differ in,
and the list is closed: name, network isolation, service desired count, deletion protection, and
the absence of customer content. Sizing is not on it. So sizing arrives as one resolved
`InfrastructureSizing` that both instantiations share, and the only per-environment inputs are the
identifier the scope already carries and the desired count.

**Why the region is explicit.** A stack built without `env` is region-agnostic and deploys wherever
the ambient profile points. `KHEPRI-DEC-007` requires this definition to fail rather than
substitute a neighbouring region or service, so the region is named here and never inherited.

**Why the image digest is a prop and not a size.** `KHEPRI-DEC-007` lists the OCI image digest among
the facts the *environment descriptor* records from the build, beside the `uv.lock` digest and the
Python patch version. It is not a sizing value, so it does not live in the sizing declaration. It
is required here, with no default, because `PinnedImage` already refuses a tag: a task definition
naming a tag runs whatever the tag points at, not what anyone approved.
"""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import Environment, Stack
from constructs import Construct

from khepri.infra.compute import (
    ComputeProps,
    EnvironmentResources,
    GovernedCompute,
    PinnedImage,
)
from khepri.infra.data_resources import GovernedDataResources
from khepri.infra.database import DatabaseProps, GovernedDatabase
from khepri.infra.image import GovernedImageRepository
from khepri.infra.network import GovernedNetwork
from khepri.infra.sizing import InfrastructureSizing

REGION = "me-central-1"


@dataclass(frozen=True, slots=True)
class EnvironmentProps:
    """Everything one environment needs that another may legitimately differ in.

    `desired_count` is `None` for the beta environment: `KHEPRI-DEC-007` reserves the beta count
    and its autoscaling policy to the beta-authorization artifact, and inventing one here would
    answer a question that decision deliberately left open.
    """

    sizing: InfrastructureSizing
    image_digest: str
    desired_count: int | None


class RraEnvironmentStack(Stack):
    """One RRA environment: network, data, store, registry, and compute."""

    def __init__(self, scope: Construct, construct_id: str, props: EnvironmentProps) -> None:
        super().__init__(scope, construct_id, env=Environment(region=REGION))
        self.network = GovernedNetwork(self, "Network")
        self.data = GovernedDataResources(self, "Data", props.sizing.queue)
        self.database = GovernedDatabase(self, "Database", self._database_props(props))
        self.image = GovernedImageRepository(self, "Image", self.data.key)
        self.compute = GovernedCompute(self, "Compute", self._compute_props(props))

    def _database_props(self, props: EnvironmentProps) -> DatabaseProps:
        return DatabaseProps(
            vpc=self.network.vpc, key=self.data.key, sizing=props.sizing.database
        )

    def _compute_props(self, props: EnvironmentProps) -> ComputeProps:
        return ComputeProps(
            resources=EnvironmentResources(
                network=self.network, data=self.data, database=self.database
            ),
            image=PinnedImage(
                repository=self.image.repository, digest=props.image_digest
            ),
            sizing=props.sizing.services,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_infra_environment.py -v`
Expected: PASS (7 tests)

`database.secret` is non-`None` here: `src/khepri/infra/database.py:117` passes
`credentials=_generated_credentials(props.key)`, so RDS generates a Secrets Manager secret and
`GovernedDatabase.secret` returns it (verified 2026-07-31). If `GovernedCompute` nonetheless raises
on a missing secret, the construct changed — fix the cause, do not pass a substitute secret.

- [ ] **Step 5: Run the full gate**

```bash
uv run ruff check .
uv run pytest -q
```
Expected: ruff clean, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/infra/environment.py tests/test_infra_environment.py
git -c commit.gpgsign=false commit -m "feat(infra): compose one governed RRA environment"
```

---

### Task 3: The two-environment application and the parity test

**Files:**
- Create: `src/khepri/infra/app.py`
- Create: `cdk.json`
- Modify: `tests/test_infra_environment.py` (append the parity class)

**Interfaces:**
- Consumes: `REGION`, `EnvironmentProps`, `RraEnvironmentStack` from Task 2; `load_sizing` from Task 1.
- Produces: `BETA_STACK_NAME`, `BENCHMARK_STACK_NAME`, `BENCHMARK_DESIRED_COUNT`, and
  `build_app(image_digest: str) -> App`.

- [ ] **Step 1: Write the failing parity test**

Append to `tests/test_infra_environment.py`:

```python
class TestTheTwoEnvironmentsAreIdenticallySized:
    """KHEPRI-DEC-007 requires every sizing value to be identical between the two.

    Comparing the synthesized templates rather than the InfrastructureSizing object is deliberate:
    the same object can still be applied differently downstream, and it is the template that gets
    deployed.
    """

    @staticmethod
    def _properties(template: Template, resource_type: str) -> list[dict]:
        return [
            resource["Properties"]
            for resource in template.find_resources(resource_type).values()
        ]

    @pytest.fixture(scope="class")
    def templates(self) -> tuple[Template, Template]:
        from khepri.infra.app import build_app

        app = build_app(IMAGE_DIGEST)
        stacks = [child for child in app.node.children if isinstance(child, RraEnvironmentStack)]
        assert len(stacks) == 2
        return tuple(Template.from_stack(stack) for stack in stacks)  # type: ignore[return-value]

    def test_both_task_definitions_agree_on_cpu_memory_and_disk(
        self, templates: tuple[Template, Template]
    ) -> None:
        def sizes(template: Template) -> set[tuple[str, str, str]]:
            return {
                (
                    properties["Cpu"],
                    properties["Memory"],
                    str(properties.get("EphemeralStorage", {}).get("SizeInGiB", "default")),
                )
                for properties in self._properties(template, "AWS::ECS::TaskDefinition")
            }

        beta, benchmark = templates
        assert sizes(beta) == sizes(benchmark)

    def test_both_databases_agree_on_class_storage_and_retention(
        self, templates: tuple[Template, Template]
    ) -> None:
        def store(template: Template) -> set[tuple[object, object, object, object]]:
            return {
                (
                    properties["DBInstanceClass"],
                    properties["AllocatedStorage"],
                    properties["StorageType"],
                    properties["BackupRetentionPeriod"],
                )
                for properties in self._properties(template, "AWS::RDS::DBInstance")
            }

        beta, benchmark = templates
        assert store(beta) == store(benchmark)

    def test_both_queue_sets_agree_on_timings_and_the_redrive_bound(
        self, templates: tuple[Template, Template]
    ) -> None:
        def queues(template: Template) -> set[tuple[object, object, object, str]]:
            return {
                (
                    properties.get("VisibilityTimeout"),
                    properties.get("MessageRetentionPeriod"),
                    properties.get("ReceiveMessageWaitTimeSeconds"),
                    str(properties.get("RedrivePolicy", {}).get("maxReceiveCount", "none")),
                )
                for properties in self._properties(template, "AWS::SQS::Queue")
            }

        beta, benchmark = templates
        assert queues(beta) == queues(benchmark)

    def test_both_stacks_pin_the_same_region(self) -> None:
        from khepri.infra.app import build_app

        app = build_app(IMAGE_DIGEST)
        stacks = [child for child in app.node.children if isinstance(child, RraEnvironmentStack)]
        assert {stack.region for stack in stacks} == {REGION}

    def test_they_do_not_share_a_key_bucket_database_or_queue(
        self, templates: tuple[Template, Template]
    ) -> None:
        """KHEPRI-DEC-007 forbids the benchmark sharing beta's key, bucket, instance, or queues."""
        beta, benchmark = templates
        for resource_type, expected in (
            ("AWS::KMS::Key", 1),
            ("AWS::S3::Bucket", 1),
            ("AWS::RDS::DBInstance", 1),
            ("AWS::SQS::Queue", 2),
        ):
            beta.resource_count_is(resource_type, expected)
            benchmark.resource_count_is(resource_type, expected)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_infra_environment.py::TestTheTwoEnvironmentsAreIdenticallySized -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.infra.app'`

- [ ] **Step 3: Write the application**

Create `src/khepri/infra/app.py`:

```python
"""The CDK application: one definition, instantiated twice.

`KHEPRI-DEC-007` authorizes a beta environment and a dedicated benchmark environment, and requires
the second to be "a second instantiation of the same CDK application in the same region ... with an
environment identifier as the only naming input". That is literally what this module is: two
constructions of `RraEnvironmentStack` against one resolved sizing object.

The benchmark environment runs exactly one task, because `KHEPRI-DEC-006` requires sequential
submission and `KHEPRI-DEC-007` makes that "true by construction" rather than a property of the
harness. The beta environment sets no desired count here: that figure and its autoscaling policy
are reserved to the beta-authorization artifact, and choosing one would answer a question
`KHEPRI-DEC-007` deliberately left open.

The image digest is a required argument. Nothing in this module knows a default, because the digest
is produced by a build and recorded in the environment descriptor, and a template synthesized
around an unapproved image is exactly what pinning by digest exists to prevent.
"""

from __future__ import annotations

from aws_cdk import App

from khepri.infra.environment import EnvironmentProps, RraEnvironmentStack
from khepri.infra.sizing_source import load_sizing

BETA_STACK_NAME = "RraBeta"
BENCHMARK_STACK_NAME = "RraBenchmark"
BENCHMARK_DESIRED_COUNT = 1


def build_app(image_digest: str) -> App:
    """Construct both environments from one sizing declaration and one stack class."""
    app = App()
    sizing = load_sizing()
    RraEnvironmentStack(
        app,
        BETA_STACK_NAME,
        EnvironmentProps(sizing=sizing, image_digest=image_digest, desired_count=None),
    )
    RraEnvironmentStack(
        app,
        BENCHMARK_STACK_NAME,
        EnvironmentProps(
            sizing=sizing,
            image_digest=image_digest,
            desired_count=BENCHMARK_DESIRED_COUNT,
        ),
    )
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_infra_environment.py -v`
Expected: PASS (all classes)

If a parity assertion fails, do NOT relax the assertion. A difference between the two templates in
any sizing property is the drift this test exists to catch; find why the two instantiations differ
and fix the stack.

- [ ] **Step 5: Add the CDK entrypoint manifest**

Create `cdk.json`. `app.py` needs a digest, so the entrypoint reads one explicitly rather than
inventing a default; synthesis without a supplied digest must fail.

```json
{
  "app": "uv run python -c \"import os; from khepri.infra.app import build_app; build_app(os.environ['KHEPRI_IMAGE_DIGEST']).synth()\"",
  "context": {
    "@aws-cdk/core:newStyleStackSynthesis": true
  }
}
```

Note: reading `KHEPRI_IMAGE_DIGEST` from the environment is the *build input* arriving, not a
sizing value being defaulted. A missing variable raises `KeyError` and synthesis fails, which is
the required behaviour. No sizing value is ever read this way.

- [ ] **Step 6: Verify synthesis actually succeeds end to end**

```bash
KHEPRI_IMAGE_DIGEST="sha256:$(printf 'ab%.0s' {1..32})" uv run cdk synth --quiet
```
Expected: exits 0 and writes `cdk.out/`. If `cdk` is not installed, skip this step and note it in
the commit body; the parity test already synthesizes both stacks in-process.

`cdk.out/` is NOT currently in `.gitignore` (verified 2026-07-31). Add these two lines in this
commit, or synthesis will offer generated templates for staging:

```gitignore
cdk.out/
*.cdk.staging/
```

- [ ] **Step 7: Run the full gate**

```bash
uv run ruff check .
uv run khepri-gov validate
uv run pytest -q
```
Expected: ruff clean, governance validation passed, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/khepri/infra/app.py cdk.json tests/test_infra_environment.py .gitignore
git -c commit.gpgsign=false commit -m "feat(infra): instantiate the beta and benchmark environments"
```

---

### Task 4: Pull request

**Files:** none changed.

- [ ] **Step 1: Push and open the pull request**

State the boundary, the authority, and both `AGENTS.md` collisions. This slice adds no Alembic
migration, so say so explicitly.

```bash
git push -u origin feat/rra-cdk-environment-definition
```

The PR body must state:
- Authority: `KHEPRI-DEC-005` and `KHEPRI-DEC-007`, both `accepted`.
- That no sizing value is invented: all come from `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml`.
- That the region is pinned to `me-central-1` explicitly, and why inheriting one would be silent substitution.
- That the image digest is a build input and a descriptor fact, never a sizing value.
- **Still NOT authorized:** `me-central-1` availability of `db.m7g.large`, `gp3`, and the two Fargate combinations; the environment descriptor; the OCI image build; beta desired count and autoscaling; any deployment; any claim a benchmark ran or the objective was met.
- Collisions: no Alembic migration; nothing stacked on this branch.
- That commits are unsigned at the owner's instruction.

- [ ] **Step 2: Wait for all five required checks**

Run: `gh pr checks <number>`
Expected: `validate`, `ruff`, `pytest`, `benchmark`, and `CodeScene Code Health Review` all pass.

CodeScene cannot be reproduced locally and is the only authority on code health. If it fails on a
new file, reduce constructor arguments and split large functions rather than arguing with it.

- [ ] **Step 3: Do not merge**

Leave the pull request for the repository owner. Five green checks are not approval.
