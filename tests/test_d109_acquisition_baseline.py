"""The decision surface's acquisition baseline (`D1-09`; active `RCA-008`).

`SV1-08` ledger §3a fixed this slice's target and it is not projection: the
composed request measures 4003 us p50 of which projection is 11.6 us, about one
part in 345. So what is measured here is the whole surface's acquisition -- the
seven reads a page issues -- and what is asserted is that measuring changed
nothing.

**No wall-clock threshold is asserted.** `SV1-08`'s `_assert_measured` states the
rule: "a wall-clock threshold in CI is a flake, and the ledger is where a
baseline belongs." The figures live in the dated ledger beside this file, and
this module is the committed function that produced every row of it -- evidence
a reader cannot regenerate from committed code is not evidence.

**What this measures, stated so the ledger cannot overclaim.** The port is
scripted, so this is the read fan-out and the orchestration around it, not the
composed end-to-end path `SV1-08` measured over a real projection and store.
That is the right subject here -- `FR-168` governs the number of reads, and the
composed cost is already recorded in §3a.
"""

from __future__ import annotations

import time

from khepri.rca.workspace.decision.controls import ControlSelection
from khepri.runtime.shell_decisions import read_surface
from tests.d109_support import (
    CountingActions,
    ScriptedPort,
    actions,
    admitted_script,
    request_for,
)

#: Same sample count as `SV1-08`, so the two ledgers are comparable.
_SAMPLES = 200


def _surface_samples() -> tuple[list[int], list[int]]:
    """`_SAMPLES` timings of one whole admitted page, and the reads each issued.

    The script, the selection and the request are built once, outside the loop:
    building them inside would measure the fixture. Nothing is warmed, memoized
    or reordered -- the loop drives the same `read_surface` the route drives.
    """
    script = admitted_script()
    selection = ControlSelection(source_id="run1")
    request = request_for()
    timings: list[int] = []
    counts: list[int] = []
    for _ in range(_SAMPLES):
        counting = CountingActions(actions(ScriptedPort(script)))
        started = time.perf_counter_ns()
        read_surface(counting, request, selection=selection)
        timings.append(time.perf_counter_ns() - started)
        counts.append(len(counting.views))
    return timings, counts


def test_the_surface_acquisition_is_a_measured_distribution() -> None:
    """`FR-144` "may measure execution" -- so the whole surface is measured.

    What is asserted is the condition `FR-144` itself imposes: that measuring
    changed nothing, so no iteration warmed, cached or reordered a later one. If
    any run had been served from something retained, its read count would drop
    below the seven every other run issued.
    """
    _timings, counts = _surface_samples()

    # The timings are evidence for the dated ledger, not an assertion. `len == _SAMPLES`
    # restated the loop bound and `median > 0` restated that a clock advances; neither could
    # fail against any defect, so both were dropped (`#529` T-12).
    assert set(counts) == {7}


def test_no_result_survives_between_requests() -> None:
    """`FR-168`'s line, asserted rather than reviewed.

    Coalescing within one request is legitimate; keeping a result *between*
    requests is a cache whatever it is called. Two identical consecutive requests
    must each perform the full seven reads -- a second request served from
    anything retained would read fewer.
    """
    script = admitted_script()
    selection = ControlSelection(source_id="run1")
    request = request_for()

    first = CountingActions(actions(ScriptedPort(script)))
    read_surface(first, request, selection=selection)
    second = CountingActions(actions(ScriptedPort(script)))
    read_surface(second, request, selection=selection)

    assert len(first.views) == 7
    assert first.views == second.views


def test_the_same_port_across_two_requests_still_reads_twice() -> None:
    """The stronger form: one shared port, so nothing can hide in a fresh fake.

    The test above builds a new `ScriptedPort` per request, which would mask a
    cache held on the port itself. Here both requests share one port and the
    projection count must double -- if the surface retained anything keyed by
    run, the second request would not reach the port at all.
    """
    port = ScriptedPort(admitted_script())
    selection = ControlSelection(source_id="run1")
    request = request_for()

    read_surface(CountingActions(actions(port)), request, selection=selection)
    after_first = len(port.requests)
    read_surface(CountingActions(actions(port)), request, selection=selection)

    assert after_first == 7
    assert len(port.requests) == 14


def test_a_within_request_cache_would_be_inert_because_nothing_repeats() -> None:
    """Why the two tests above are the whole obligation, stated as an assertion.

    A cache scoped to one request -- retained on the reader rather than across
    readers -- is the weaker form of the mutant, and neither test above catches
    it. That is not a gap: it is **inert**, because no view is read twice within
    one request, so it could never serve a hit. Asserting that here makes the
    reason explicit rather than incidental, and turns a later slice that
    introduces a repeat into a failure here as well as in the read-count file.

    The distinction matters for `FR-168`: coalescing within a request is
    permitted and a cache between requests is not, so what must be proved is
    that there is nothing left to coalesce.
    """
    port = ScriptedPort(admitted_script())
    counting = CountingActions(actions(port))

    read_surface(counting, request_for(), selection=ControlSelection(source_id="run1"))

    assert counting.views
    assert len(counting.views) == len(set(counting.views))
