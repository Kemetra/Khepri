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
