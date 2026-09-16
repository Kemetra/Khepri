"""`RCA-009` `FR-180`: one derivation states a comparison operand.

Authority: active `RCA-009` `FR-180`. The relocation redefines no calculation,
completeness, timezone, compatibility, provenance, ordering, refusal, or
isolation semantics.
"""

from __future__ import annotations

import inspect

from khepri.runtime import comparison_assembly, comparison_operands


def test_the_seam_publishes_both_entry_points() -> None:
    """`FR-180` -- one seam derives operands and admits the pair."""
    assert hasattr(comparison_operands, "derive_operand")
    assert hasattr(comparison_operands, "admit_pair")


def test_the_assembly_holds_no_second_operand_derivation() -> None:
    """`FR-180` -- a second implementation is not authorized anywhere.

    The relocated privates are gone from the assembly module rather than left
    beside the seam as an agreeing copy: two agreeing copies are what this
    requirement exists to prevent.
    """
    relocated = (
        "_operand_from",
        "_manifest_of",
        "_dataset_period",
        "_granularity",
        "_complete",
        "_scope_complete",
        "_session_of",
        "_package_record",
        "_profile_record",
        "_verified_package",
    )
    for name in relocated:
        assert not hasattr(comparison_assembly, name), name


def test_run_selection_stays_with_the_assembly() -> None:
    """`FR-180` -- run *selection* from a version identifier is not relocated."""
    assert hasattr(comparison_assembly, "_latest_completed")
    assert not hasattr(comparison_operands, "_latest_completed")


def test_the_seam_reads_no_clock() -> None:
    """`FR-180` -- the time source is supplied, never read inside the seam."""
    source = inspect.getsource(comparison_operands)
    assert "datetime.now" not in source
    assert "utcnow" not in source
