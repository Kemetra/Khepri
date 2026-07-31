from __future__ import annotations

import json

import pytest
from aws_cdk import App, Stack
from aws_cdk.assertions import Template

from khepri.infra.compute import (
    BROWSERS_PATH,
    BROWSERS_PATH_VARIABLE,
    DATABASE_SECRET_VARIABLE,
    SKIP_BROWSER_DOWNLOAD_VARIABLE,
    WEB_CONTAINER_NAME,
    WORKER_CONTAINER_NAME,
    ComputeProps,
    EnvironmentResources,
    GovernedCompute,
    PinnedImage,
)
from khepri.infra.data_resources import GovernedDataResources
from khepri.infra.database import DatabaseProps, GovernedDatabase
from khepri.infra.image import GovernedImageRepository
from khepri.infra.network import GovernedNetwork
from khepri.infra.sizing import (
    DatabaseSize,
    QueueSizing,
    QueueTimings,
    RetryBounds,
    ServiceSizing,
    TaskSize,
)

WEB_CPU = 1024
WEB_MEMORY = 4096
WORKER_CPU = 4096
WORKER_MEMORY = 16384
WORKER_STORAGE = 40

# A syntactically valid digest. It pins nothing real: no approved environment descriptor exists,
# so this is a fixture, not an identity.
IMAGE_DIGEST = "sha256:" + "ab" * 32


def _service_sizing() -> ServiceSizing:
    return ServiceSizing(
        web=TaskSize(cpu_units=WEB_CPU, memory_mib=WEB_MEMORY, ephemeral_storage_gib=20),
        worker=TaskSize(
            cpu_units=WORKER_CPU,
            memory_mib=WORKER_MEMORY,
            ephemeral_storage_gib=WORKER_STORAGE,
        ),
    )


def _queue_sizing() -> QueueSizing:
    return QueueSizing(
        timings=QueueTimings(
            visibility_timeout_seconds=300,
            message_retention_seconds=1209600,
            receive_wait_seconds=20,
        ),
        retries=RetryBounds(max_receive_count=3, max_attempts=3),
    )


def _build() -> Template:
    stack = Stack(App(), "ComputeStack")
    network = GovernedNetwork(stack, "Network")
    data = GovernedDataResources(stack, "Data", _queue_sizing())
    database = GovernedDatabase(
        stack,
        "Database",
        DatabaseProps(
            vpc=network.vpc,
            key=data.key,
            sizing=DatabaseSize(
                instance_class="db.m7g.large",
                allocated_storage_gib=100,
                backup_retention_days=7,
            ),
        ),
    )
    image = GovernedImageRepository(stack, "Image", data.key)
    GovernedCompute(
        stack,
        "Compute",
        ComputeProps(
            resources=EnvironmentResources(network=network, data=data, database=database),
            image=PinnedImage(repository=image.repository, digest=IMAGE_DIGEST),
            sizing=_service_sizing(),
        ),
    )
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template() -> Template:
    return _build()


def _task_definition(template: Template, container_name: str) -> dict:
    """The one task definition carrying this container, and it must be exactly one."""
    tasks = template.find_resources("AWS::ECS::TaskDefinition").values()
    matching = [task["Properties"] for task in tasks if _carries(task, container_name)]

    assert len(matching) == 1, f"Expected one task definition holding {container_name}"
    return matching[0]


def _carries(task: dict, container_name: str) -> bool:
    return container_name in [c["Name"] for c in task["Properties"]["ContainerDefinitions"]]


def _role_actions(template: Template, role_logical_id: str) -> set[str]:
    """Every action any inline policy grants to one role."""
    policies = template.find_resources("AWS::IAM::Policy").values()
    attached = [policy for policy in policies if _targets_role(policy, role_logical_id)]
    return {action for policy in attached for action in _allowed_actions(policy)}


def _targets_role(policy: dict, role_logical_id: str) -> bool:
    return role_logical_id in json.dumps(policy["Properties"].get("Roles", []))


def _allowed_actions(policy: dict) -> set[str]:
    statements = policy["Properties"]["PolicyDocument"]["Statement"]
    allowed = [entry for entry in statements if entry.get("Effect") == "Allow"]
    return {action for entry in allowed for action in _actions_of(entry)}


def _actions_of(statement: dict) -> list[str]:
    """CloudFormation renders a lone action as a string and several as a list."""
    action = statement.get("Action", [])
    return [action] if isinstance(action, str) else list(action)


def _role_logical_id(template: Template, container_name: str) -> str:
    task = _task_definition(template, container_name)
    return json.dumps(task["TaskRoleArn"]).split('"')[3]


class TestOneClusterInTheGovernedNetwork:
    def test_exactly_one_cluster_is_created(self, template: Template) -> None:
        template.resource_count_is("AWS::ECS::Cluster", 1)

    def test_no_second_vpc_is_created(self, template: Template) -> None:
        """`ecs.Cluster` invents a VPC when it is not given one; that would strand the tasks."""
        template.resource_count_is("AWS::EC2::VPC", 1)


class TestTaskDefinitions:
    def test_two_task_definitions_exist(self, template: Template) -> None:
        template.resource_count_is("AWS::ECS::TaskDefinition", 2)

    def test_the_web_task_carries_its_declared_size(self, template: Template) -> None:
        task = _task_definition(template, WEB_CONTAINER_NAME)

        assert task["Cpu"] == str(WEB_CPU)
        assert task["Memory"] == str(WEB_MEMORY)

    def test_the_worker_task_carries_its_declared_size(self, template: Template) -> None:
        task = _task_definition(template, WORKER_CONTAINER_NAME)

        assert task["Cpu"] == str(WORKER_CPU)
        assert task["Memory"] == str(WORKER_MEMORY)

    def test_the_worker_gets_the_ephemeral_storage_the_browser_needs(
        self, template: Template
    ) -> None:
        """The figure exists because --disable-dev-shm-usage moves allocations onto disk."""
        task = _task_definition(template, WORKER_CONTAINER_NAME)

        assert task["EphemeralStorage"] == {"SizeInGiB": WORKER_STORAGE}

    def test_the_web_task_declares_no_ephemeral_storage_at_the_default(
        self, template: Template
    ) -> None:
        """A task definition accepts 21 to 200 GiB and is refused at 20, so the Fargate default
        cannot be stated. KHEPRI-DEC-007 records the web service at exactly that default, so the
        template honours it by omission rather than by a number the platform would reject."""
        task = _task_definition(template, WEB_CONTAINER_NAME)

        assert "EphemeralStorage" not in task

    def test_both_tasks_require_fargate(self, template: Template) -> None:
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            assert _task_definition(template, name)["RequiresCompatibilities"] == ["FARGATE"]

    def test_the_cpu_architecture_is_recorded_rather_than_defaulted(
        self, template: Template
    ) -> None:
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            task = _task_definition(template, name)
            assert task["RuntimePlatform"]["CpuArchitecture"] == "X86_64"


class TestContainers:
    def test_both_containers_run_the_same_repository_image(self, template: Template) -> None:
        images = set()
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            task = _task_definition(template, name)
            images.add(json.dumps(task["ContainerDefinitions"][0]["Image"]))

        assert len(images) == 1

    def test_the_image_is_referenced_by_digest_and_never_by_a_tag(
        self, template: Template
    ) -> None:
        """A tag resolves at every task placement, so a tag is not a pin.

        ECR tag immutability refuses to overwrite a tag, but BatchDeleteImage followed by a fresh
        push of the same tag is not an overwrite. A digest cannot be re-pointed at all.
        """
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            rendered = json.dumps(_task_definition(template, name)["ContainerDefinitions"][0])

            assert IMAGE_DIGEST in rendered
            assert ":latest" not in rendered

    def test_an_absent_or_tag_shaped_digest_is_refused(self) -> None:
        stack = Stack(App(), "RefusedImageStack")
        data = GovernedDataResources(stack, "Data", _queue_sizing())
        repository = GovernedImageRepository(stack, "Image", data.key).repository

        for value in ("", "   ", "latest", "beta", "sha256:", "sha256:abc", "ab" * 32):
            with pytest.raises(ValueError):
                PinnedImage(repository=repository, digest=value)

    def test_an_uppercase_digest_is_refused(self) -> None:
        """The digest reaches a template verbatim, so case is part of the identity."""
        stack = Stack(App(), "UppercaseImageStack")
        data = GovernedDataResources(stack, "Data", _queue_sizing())
        repository = GovernedImageRepository(stack, "Image", data.key).repository

        with pytest.raises(ValueError):
            PinnedImage(repository=repository, digest="sha256:" + "AB" * 32)

    def test_the_browser_path_is_pinned_and_download_is_refused(
        self, template: Template
    ) -> None:
        """A task that cannot find the baked browser must fail, not fetch an unrecorded one."""
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            container = _task_definition(template, name)["ContainerDefinitions"][0]
            environment = {entry["Name"]: entry["Value"] for entry in container["Environment"]}

            assert environment[BROWSERS_PATH_VARIABLE] == BROWSERS_PATH
            assert environment[SKIP_BROWSER_DOWNLOAD_VARIABLE] == "1"

    def test_the_credential_arrives_as_a_secret_reference(self, template: Template) -> None:
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            container = _task_definition(template, name)["ContainerDefinitions"][0]
            secrets = {entry["Name"]: entry for entry in container["Secrets"]}

            assert DATABASE_SECRET_VARIABLE in secrets

    def test_no_credential_appears_in_a_plain_environment_variable(
        self, template: Template
    ) -> None:
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            container = _task_definition(template, name)["ContainerDefinitions"][0]
            rendered = json.dumps(container["Environment"])

            assert "password" not in rendered.lower()
            assert "secret" not in rendered.lower()

    def test_each_container_logs_to_its_own_retained_group(self, template: Template) -> None:
        template.resource_count_is("AWS::Logs::LogGroup", 3)  # two services plus VPC flow logs

        groups = set()
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            container = _task_definition(template, name)["ContainerDefinitions"][0]
            options = container["LogConfiguration"]["Options"]
            assert container["LogConfiguration"]["LogDriver"] == "awslogs"
            groups.add(json.dumps(options["awslogs-group"]))

        assert len(groups) == 2


class TestLeastPrivilege:
    """The asymmetry between the two roles is the governed property, so it is tested directly."""

    def test_the_web_role_may_send_to_the_queue(self, template: Template) -> None:
        actions = _role_actions(template, _role_logical_id(template, WEB_CONTAINER_NAME))

        assert "sqs:SendMessage" in actions

    def test_the_web_role_may_not_receive_from_the_queue(self, template: Template) -> None:
        """A web task consuming a job would bypass the bounded worker entirely."""
        actions = _role_actions(template, _role_logical_id(template, WEB_CONTAINER_NAME))

        assert "sqs:ReceiveMessage" not in actions
        assert "sqs:DeleteMessage" not in actions

    def test_the_worker_role_may_receive_from_the_queue(self, template: Template) -> None:
        actions = _role_actions(template, _role_logical_id(template, WORKER_CONTAINER_NAME))

        assert "sqs:ReceiveMessage" in actions
        assert "sqs:DeleteMessage" in actions

    def test_the_worker_role_may_not_send_to_the_queue(self, template: Template) -> None:
        """Retry and dead-lettering are decided by PostgreSQL and SQS redrive, not by the worker."""
        actions = _role_actions(template, _role_logical_id(template, WORKER_CONTAINER_NAME))

        assert "sqs:SendMessage" not in actions

    def test_the_worker_may_extend_its_own_lease(self, template: Template) -> None:
        """Visibility-timeout heartbeats are how a long render keeps its message invisible."""
        actions = _role_actions(template, _role_logical_id(template, WORKER_CONTAINER_NAME))

        assert "sqs:ChangeMessageVisibility" in actions

    def test_both_roles_reach_the_content_bucket(self, template: Template) -> None:
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            actions = _role_actions(template, _role_logical_id(template, name))

            assert "s3:GetObject*" in actions
            assert "s3:PutObject" in actions

    def test_both_roles_may_delete_objects_because_RRA_002_requires_it(
        self, template: Template
    ) -> None:
        """Immediate deletion must permanently remove indexed objects and abort partial uploads."""
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            actions = _role_actions(template, _role_logical_id(template, name))

            assert "s3:DeleteObject*" in actions
            assert "s3:Abort*" in actions

    def test_neither_role_may_act_on_the_bucket_itself(self, template: Template) -> None:
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            actions = _role_actions(template, _role_logical_id(template, name))

            assert "s3:DeleteBucket" not in actions
            assert "s3:PutBucketPolicy" not in actions
            assert "s3:*" not in actions

    def test_neither_role_carries_a_service_wide_or_total_wildcard(
        self, template: Template
    ) -> None:
        """Suffixed forms like `s3:GetObject*` are CDK's grants; a bare or service-wide `*`
        would be an escalation, so those are what this refuses."""
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            actions = _role_actions(template, _role_logical_id(template, name))

            assert "*" not in actions
            assert not any(action.endswith(":*") for action in actions)
            assert "iam:PassRole" not in actions

    def test_both_roles_may_use_the_environment_key(self, template: Template) -> None:
        """The bucket grant carries this; no separate key grant is made, and none is needed.

        `grant_read_write` on a KMS-encrypted bucket already emits the key actions, so an explicit
        `grant_encrypt_decrypt` would be a second statement granting what the first already did.
        """
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            actions = _role_actions(template, _role_logical_id(template, name))

            assert "kms:Decrypt" in actions
            assert "kms:GenerateDataKey*" in actions

    def test_neither_task_role_may_read_the_database_secret_directly(
        self, template: Template
    ) -> None:
        """The execution role fetches it at task start; the task role has no path to it."""
        for name in (WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME):
            actions = _role_actions(template, _role_logical_id(template, name))

            assert "secretsmanager:GetSecretValue" not in actions

    def test_the_two_roles_are_distinct(self, template: Template) -> None:
        web = _role_logical_id(template, WEB_CONTAINER_NAME)
        worker = _role_logical_id(template, WORKER_CONTAINER_NAME)

        assert web != worker


class TestImageRepository:
    def test_tags_are_immutable(self, template: Template) -> None:
        """KHEPRI-DEC-007 pins Chromium through the image digest; a movable tag breaks that."""
        template.has_resource_properties(
            "AWS::ECR::Repository", {"ImageTagMutability": "IMMUTABLE"}
        )

    def test_images_are_scanned_on_push(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::ECR::Repository", {"ImageScanningConfiguration": {"ScanOnPush": True}}
        )

    def test_the_repository_is_encrypted_with_the_environment_key(
        self, template: Template
    ) -> None:
        repositories = template.find_resources("AWS::ECR::Repository")
        properties = next(iter(repositories.values()))["Properties"]

        assert properties["EncryptionConfiguration"]["EncryptionType"] == "KMS"

    def test_untagged_images_expire(self, template: Template) -> None:
        repositories = template.find_resources("AWS::ECR::Repository")
        properties = next(iter(repositories.values()))["Properties"]
        policy = json.loads(properties["LifecyclePolicy"]["LifecyclePolicyText"])

        assert policy["rules"][0]["selection"]["tagStatus"] == "untagged"


def test_a_resized_declaration_reaches_the_task_definitions() -> None:
    stack = Stack(App(), "ResizedComputeStack")
    network = GovernedNetwork(stack, "Network")
    data = GovernedDataResources(stack, "Data", _queue_sizing())
    database = GovernedDatabase(
        stack,
        "Database",
        DatabaseProps(
            vpc=network.vpc,
            key=data.key,
            sizing=DatabaseSize(
                instance_class="db.m7g.large",
                allocated_storage_gib=100,
                backup_retention_days=7,
            ),
        ),
    )
    image = GovernedImageRepository(stack, "Image", data.key)
    GovernedCompute(
        stack,
        "Compute",
        ComputeProps(
            resources=EnvironmentResources(network=network, data=data, database=database),
            image=PinnedImage(repository=image.repository, digest=IMAGE_DIGEST),
            sizing=ServiceSizing(
                web=TaskSize(cpu_units=2048, memory_mib=4096, ephemeral_storage_gib=21),
                worker=TaskSize(cpu_units=8192, memory_mib=32768, ephemeral_storage_gib=60),
            ),
        ),
    )
    template = Template.from_stack(stack)

    assert _task_definition(template, WORKER_CONTAINER_NAME)["Cpu"] == "8192"
    assert _task_definition(template, WEB_CONTAINER_NAME)["Cpu"] == "2048"
