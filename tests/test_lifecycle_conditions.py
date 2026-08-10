from __future__ import annotations

from pathlib import Path

from khepri_gov.lifecycle_conditions import (
    lifecycle_condition_errors,
    scan_repository,
    scan_text,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# The exact passage APP-021 removed from governance/families/RCA.md. Both of its
# conditions became false when the family went active and RCA-001 was approved,
# so the exclusion stopped excluding anything at the moment it was needed.
APP_021_DEFECT = """# RCA

## Excludes

- Product implementation while this family remains proposed or its specifications remain draft.
"""

# The replacement: stated against implementation preconditions, which approval
# does not clear, rather than against a lifecycle state.
APP_021_REMEDY = """# RCA

## Excludes

- Product implementation until the implementation preconditions of the governing `RCA`
  specification are met. Neither this charter being `active` nor a specification being
  `approved` is authority to implement.
"""


def test_flags_the_app_021_defect() -> None:
    findings = scan_text("RCA.md", APP_021_DEFECT)

    assert len(findings) == 1
    assert findings[0].line == 5
    assert findings[0].heading == "Excludes"
    assert not findings[0].is_suppressed


def test_accepts_the_app_021_remedy() -> None:
    assert scan_text("RCA.md", APP_021_REMEDY) == []


def test_ignores_lifecycle_mentions_outside_normative_sections() -> None:
    text = """# RCA

## Context

The family stays excluded while this family remains proposed, which is why the
charter was written before the first specification was drafted.
"""

    assert scan_text("RCA.md", text) == []


def test_ignores_a_quoted_defect_inside_corrective_prose() -> None:
    """RCA.md explains its fix by quoting the defective form across two lines."""
    text = """# RCA

## Excludes

- Product implementation until the preconditions are met, because a condition of the
  form "while this family remains proposed or its specifications remain draft" stops
  excluding anything at the moment the family goes active.
"""

    assert scan_text("RCA.md", text) == []


def test_suppression_marker_reports_without_failing() -> None:
    text = """# RCA

## Excludes

- Product implementation while this family remains proposed. <!-- lifecycle-ok: the
  family is retired and will not transition again -->
"""

    findings = scan_text("RCA.md", text)

    assert len(findings) == 1
    assert findings[0].is_suppressed
    assert "retired" in (findings[0].suppressed_reason or "")
    assert lifecycle_condition_errors(findings) == []


def test_until_form_is_flagged() -> None:
    text = """# RRA

## Excludes

- Product implementation until RRA-001 is approved.
"""

    findings = scan_text("RRA.md", text)

    assert len(findings) == 1
    assert not findings[0].is_suppressed


def test_multiple_findings_are_each_reported() -> None:
    text = """# RCA

## Excludes

- Product implementation while this family remains proposed.
- Provider selection while the decision remains draft.
"""

    assert len(scan_text("RCA.md", text)) == 2


def test_repository_scan_returns_findings_with_paths() -> None:
    findings = scan_repository(REPOSITORY_ROOT)

    for finding in findings:
        assert finding.path.startswith("governance/")
        assert finding.line > 0
