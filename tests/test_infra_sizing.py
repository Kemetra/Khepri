from __future__ import annotations

import pytest

from khepri.infra.sizing import (
    GP3_PROVISIONING_FLOOR_GIB,
    MAX_EPHEMERAL_STORAGE_GIB,
    MAX_RECEIVE_WAIT_SECONDS,
    MAX_VISIBILITY_TIMEOUT_SECONDS,
    SIZING_KEYS,
    DatabaseSize,
    QueueTimings,
    RetryBounds,
    SizingRefused,
    TaskSize,
    resolve_sizing,
)

# A complete declaration, used as the baseline every refusal test mutates one field of. The
# values are a valid declaration, not an approved one: no approved artifact supplies sizing yet.
DECLARATION = {
    "web_cpu_units": "1024",
    "web_memory_mib": "4096",
    "web_ephemeral_storage_gib": "20",
    "worker_cpu_units": "4096",
    "worker_memory_mib": "16384",
    "worker_ephemeral_storage_gib": "40",
    "database_instance_class": "db.m7g.large",
    "allocated_storage_gib": "100",
    "backup_retention_days": "7",
    "visibility_timeout_seconds": "300",
    "message_retention_seconds": "1209600",
    "receive_wait_seconds": "20",
    "max_receive_count": "3",
    "max_attempts": "3",
}


def _without(key: str) -> dict[str, str]:
    return {name: value for name, value in DECLARATION.items() if name != key}


def _with(key: str, value: str) -> dict[str, str]:
    return DECLARATION | {key: value}


def test_a_complete_declaration_resolves_every_field() -> None:
    sizing = resolve_sizing(DECLARATION)

    assert sizing.services.web.cpu_units == 1024
    assert sizing.services.web.memory_mib == 4096
    assert sizing.services.worker.cpu_units == 4096
    assert sizing.services.worker.memory_mib == 16384
    assert sizing.services.worker.ephemeral_storage_gib == 40
    assert sizing.database.instance_class == "db.m7g.large"
    assert sizing.database.allocated_storage_gib == 100
    assert sizing.database.backup_retention_days == 7
    assert sizing.queue.timings.visibility_timeout_seconds == 300
    assert sizing.queue.timings.receive_wait_seconds == 20
    assert sizing.queue.retries.max_receive_count == 3
    assert sizing.queue.retries.max_attempts == 3


@pytest.mark.parametrize("key", SIZING_KEYS)
def test_every_field_is_required(key: str) -> None:
    with pytest.raises(SizingRefused) as refusal:
        resolve_sizing(_without(key))

    assert key in str(refusal.value)


@pytest.mark.parametrize("key", SIZING_KEYS)
def test_a_blank_field_is_absent_rather_than_zero(key: str) -> None:
    with pytest.raises(SizingRefused):
        resolve_sizing(_with(key, "   "))


def test_an_empty_declaration_names_every_missing_field() -> None:
    with pytest.raises(SizingRefused) as refusal:
        resolve_sizing({})

    message = str(refusal.value)
    assert all(key in message for key in SIZING_KEYS)


def test_a_non_integer_field_is_refused() -> None:
    with pytest.raises(SizingRefused, match="worker_cpu_units must be an integer"):
        resolve_sizing(_with("worker_cpu_units", "four thousand"))


def test_nothing_is_defaulted_when_a_field_is_missing() -> None:
    """A refusal, never a partially populated object built around a fallback."""
    with pytest.raises(SizingRefused):
        resolve_sizing(_without("worker_memory_mib"))


class TestFargatePairs:
    def test_a_cpu_value_fargate_does_not_offer_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="not a Fargate task CPU value"):
            TaskSize(cpu_units=3072, memory_mib=8192, ephemeral_storage_gib=20)

    def test_memory_below_the_floor_for_its_cpu_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="not valid for this cpu_units"):
            TaskSize(cpu_units=4096, memory_mib=4096, ephemeral_storage_gib=20)

    def test_memory_above_the_ceiling_for_its_cpu_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="not valid for this cpu_units"):
            TaskSize(cpu_units=1024, memory_mib=16384, ephemeral_storage_gib=20)

    def test_memory_off_the_step_for_its_cpu_is_refused(self) -> None:
        """8 vCPU steps by 4096 MiB, so a 1024-aligned value is still invalid."""
        with pytest.raises(SizingRefused, match="not valid for this cpu_units"):
            TaskSize(cpu_units=8192, memory_mib=17408, ephemeral_storage_gib=20)

    def test_the_irregular_256_row_is_enumerated_exactly(self) -> None:
        assert TaskSize(cpu_units=256, memory_mib=2048, ephemeral_storage_gib=20)
        with pytest.raises(SizingRefused, match="not valid for this cpu_units"):
            TaskSize(cpu_units=256, memory_mib=1536, ephemeral_storage_gib=20)

    def test_both_edges_of_a_series_row_are_accepted(self) -> None:
        assert TaskSize(cpu_units=4096, memory_mib=8192, ephemeral_storage_gib=20)
        assert TaskSize(cpu_units=4096, memory_mib=30720, ephemeral_storage_gib=20)


class TestEphemeralStorage:
    def test_below_the_fargate_default_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="ephemeral_storage_gib"):
            TaskSize(cpu_units=1024, memory_mib=2048, ephemeral_storage_gib=19)

    def test_above_the_maximum_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="ephemeral_storage_gib"):
            TaskSize(
                cpu_units=1024,
                memory_mib=2048,
                ephemeral_storage_gib=MAX_EPHEMERAL_STORAGE_GIB + 1,
            )


class TestDatabaseSize:
    def test_an_allocation_needing_provisioned_iops_is_refused(self) -> None:
        """At or above the gp3 floor a declaration must also carry IOPS, which this cannot."""
        with pytest.raises(SizingRefused, match="allocated_storage_gib"):
            DatabaseSize(
                instance_class="db.m7g.large",
                allocated_storage_gib=GP3_PROVISIONING_FLOOR_GIB,
                backup_retention_days=7,
            )

    def test_disabled_backups_are_refused(self) -> None:
        """KHEPRI-DEC-005 requires encrypted backups, and zero retention disables them."""
        with pytest.raises(SizingRefused, match="backup_retention_days"):
            DatabaseSize(
                instance_class="db.m7g.large", allocated_storage_gib=100, backup_retention_days=0
            )

    def test_retention_beyond_the_rds_maximum_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="backup_retention_days"):
            DatabaseSize(
                instance_class="db.m7g.large", allocated_storage_gib=100, backup_retention_days=36
            )

    @pytest.mark.parametrize("value", ["m7g.large", "db.large", "db.", ""])
    def test_a_value_that_is_not_an_instance_class_is_refused(self, value: str) -> None:
        with pytest.raises(SizingRefused, match="instance_class"):
            DatabaseSize(
                instance_class=value, allocated_storage_gib=100, backup_retention_days=7
            )


class TestQueueBounds:
    def test_a_zero_visibility_timeout_is_refused(self) -> None:
        """KHEPRI-DEC-005 requires visibility-timeout heartbeats, which zero cannot extend."""
        with pytest.raises(SizingRefused, match="visibility_timeout_seconds"):
            QueueTimings(
                visibility_timeout_seconds=0,
                message_retention_seconds=1209600,
                receive_wait_seconds=20,
            )

    def test_a_visibility_timeout_beyond_the_sqs_maximum_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="visibility_timeout_seconds"):
            QueueTimings(
                visibility_timeout_seconds=MAX_VISIBILITY_TIMEOUT_SECONDS + 1,
                message_retention_seconds=1209600,
                receive_wait_seconds=20,
            )

    def test_retention_below_the_sqs_minimum_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="message_retention_seconds"):
            QueueTimings(
                visibility_timeout_seconds=300,
                message_retention_seconds=59,
                receive_wait_seconds=20,
            )

    def test_a_receive_wait_beyond_the_long_poll_maximum_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="receive_wait_seconds"):
            QueueTimings(
                visibility_timeout_seconds=300,
                message_retention_seconds=1209600,
                receive_wait_seconds=MAX_RECEIVE_WAIT_SECONDS + 1,
            )

    def test_no_long_polling_is_a_bound_rather_than_a_refusal(self) -> None:
        assert QueueTimings(
            visibility_timeout_seconds=300,
            message_retention_seconds=1209600,
            receive_wait_seconds=0,
        )

    def test_a_zero_redrive_count_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="max_receive_count"):
            RetryBounds(max_receive_count=0, max_attempts=3)

    def test_a_zero_attempt_bound_is_refused(self) -> None:
        with pytest.raises(SizingRefused, match="max_attempts"):
            RetryBounds(max_receive_count=3, max_attempts=0)


def test_disagreeing_attempt_bounds_are_not_refused_here() -> None:
    """Requiring the two to agree is a KHEPRI-DEC-007 rule, and that decision is proposed.

    Enforcing it now would act on authority nobody has granted. This test exists so that the
    omission is deliberate and visible rather than looking like a missing check, and it is the
    test to change when that decision is approved.
    """
    bounds = RetryBounds(max_receive_count=3, max_attempts=10)

    assert bounds.max_receive_count != bounds.max_attempts


def test_a_sizing_declaration_is_immutable() -> None:
    sizing = resolve_sizing(DECLARATION)

    with pytest.raises(AttributeError):
        sizing.services.worker.cpu_units = 8192  # type: ignore[misc]
