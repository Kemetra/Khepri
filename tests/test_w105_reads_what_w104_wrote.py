"""`W1-05` reads what `W1-04` wrote -- through the real stores, the real isolation door, and a
session whose organization identifier is *not* its scope.

Review on `#373` found the shell passing `context.organization_id` to a store keyed by the opaque
`owner_id` (`FR-031`). Every unit test passed, because every stub reader answered whatever scope
it was asked about; the production wiring would have rendered empty surfaces over an organization
full of rows. This module is the test that could not have passed: the version is created by
`WorkspaceActions` through the real `RRA-003` admission (`tests/w104_support.py`), the shell is
built over the same `SqlWorkspaceRecordStore` and an `IsolationService` over the same tables, and
the member's `owner_id` is asserted to differ from their `organization_id` before anything is read.

A second organization on the same engine sees none of it, which is `FR-042` and `FR-051` holding
across the scope boundary the store enforces.
"""

from __future__ import annotations

from khepri.runtime.shell_copy import SHELL_COPY
from tests.w104_support import LATER, OTHER_CSV, member, world
from tests.w105_support import admitted_version, page


def test_the_scope_is_not_the_organization() -> None:
    """The premise every case below rests on, stated as its own assertion so a future change that
    made the two identifiers coincide would fail here rather than silently weaken the others."""
    w = world()
    who = member(w)

    assert who.owner_id != who.organization_id


def test_data_shows_the_version_the_actions_recorded() -> None:
    w = world()
    who = member(w)
    admitted_version(w, who)

    html = page(w, who, "data")

    assert html.count('class="data-item"') == 1
    assert SHELL_COPY["en"]["data_admitted"] in html
    assert SHELL_COPY["en"]["data_empty"] not in html


def test_overview_shows_the_run_the_actions_started() -> None:
    w = world()
    who = member(w)
    _session_id, version_id = admitted_version(w, who)
    w.services.start_analysis_run(who.caller, version_id=version_id, now=LATER)

    html = page(w, who, "overview")

    assert html.count('class="latest-work"') == 1
    assert SHELL_COPY["en"]["run_state_started"] in html
    assert SHELL_COPY["en"]["overview_no_work"] not in html


def test_another_organization_on_the_same_engine_sees_nothing() -> None:
    """`FR-042`/`FR-051` across the scope boundary: the store's `owner_id` filter, reached through
    the second member's own resolution, and not a filter the shell applied."""
    w = world()
    who = member(w)
    other = member(w, email="other@example.test", name="Other")
    admitted_version(w, who, OTHER_CSV)

    html = page(w, other, "data")

    assert "data-item" not in html
    assert SHELL_COPY["en"]["data_empty"] in html
