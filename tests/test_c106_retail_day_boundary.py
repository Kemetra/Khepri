"""`RRA-008` §Period rule, from the C1-06 caller: two manifests, two retail-day boundaries.

A coverage manifest attests one timezone, and that timezone is the retail day boundary every
attested day is stated in (`coverage_request.py`; the shell labels it "Retail day boundary").
The frozen period type carries an hour, not a zone, so the C1-06 assembly must state the
boundary comparison itself -- under the cause the family already froze.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from khepri.rra.analysis.comparison_narrative import refusal_wording
from khepri.rra.analysis.dataset_period import CAUSE_RETAIL_DAY
from khepri.runtime import comparison_assembly
from tests.c106_support import comparison_actions, completed_pair
from tests.test_c106_comparison_orchestration import _request
from tests.w104_support import member
from tests.w104b_support import journey


def _zoned(zones: list[str]):
    """`stored_manifest` as the assembly sees it, each operand's manifest in the next zone."""
    original = comparison_assembly.stored_manifest
    queue = list(zones)

    def shifted(profile):
        manifest = original(profile)
        return replace(manifest, timezone=queue.pop(0))

    return shifted


def test_two_zones_refuse_under_the_retail_day_boundary_cause(tmp_path) -> None:
    """Review on `#409`: both operands were given hour zero regardless of zone, so a pair whose
    manifests attest Africa/Cairo and Asia/Riyadh was admitted as if its days began together,
    and the family's retail-day-boundary refusal could never fire from this caller."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)

    with patch(
        "khepri.runtime.comparison_assembly.stored_manifest",
        side_effect=_zoned(["Africa/Cairo", "Asia/Riyadh"]),
    ):
        outcome = actions.request(
            _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
        )

    assert outcome.refused
    assert outcome.refusal is not None
    assert outcome.refusal.cause == CAUSE_RETAIL_DAY
    assert outcome.refusal.wording == refusal_wording(CAUSE_RETAIL_DAY)
    assert not any(tmp_path.iterdir())


def test_one_zone_on_both_sides_is_admitted(tmp_path) -> None:
    """The control: the same zone, whatever it is, is one boundary."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)

    with patch(
        "khepri.runtime.comparison_assembly.stored_manifest",
        side_effect=_zoned(["Asia/Riyadh", "Asia/Riyadh"]),
    ):
        outcome = actions.request(
            _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
        )

    assert outcome.admitted
