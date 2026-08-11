from __future__ import annotations

from pathlib import Path

import pytest

from khepri_gov.cli import main
from tests.governance_support import valid_artifacts, write_registry


def test_validate_command_reports_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_registry(tmp_path, valid_artifacts())
    assert main(["--root", str(tmp_path), "validate"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "Governance validation passed.\n"
    assert captured.err == ""


def test_validate_command_reports_every_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_registry(tmp_path, [])
    assert main(["--root", str(tmp_path), "validate"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "ERROR registry: artifacts must be a non-empty list\n"


@pytest.mark.parametrize(
    "command",
    ["document-digest", "approval-digest", "delegation-guard", "lifecycle-guard"],
)
def test_retired_commands_are_rejected(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main([command])
    assert raised.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
