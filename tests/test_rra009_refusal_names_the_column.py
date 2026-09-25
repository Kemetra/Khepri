"""A result refusal's fourth part names a column, not the refused metric (`#560` item 2).

`RRA-009` §Refusals: part 4 names "which missing field or evidence caused it, named as a column
the customer would recognise in their own export". `wording.caveat_prose` fills the `{column}` and
`{field}` placeholders with the refused metric's business name, so `units_by_channel` refused for
a gapped column reads "Units sold is in your file but some rows leave it empty".

**`required_input_unavailable` is pinned for the combined fix.** It is also a section reason, and
`caveat_prose` routes every section reason to its section sentence ("This analysis -- not
available"), so today the metric is not named at all (count 0). Fixing that routing alone would
reach the result sentence and name the metric twice (count 2); only routing *and* the column give
1. `incomplete_transaction_identifiers` and `family_version_pairing_unadmitted` share that routing
defect; it is outside `#560` and recorded on the PR rather than pinned here.

**Pinned as a strict `xfail`, not fixed here.** The joined `<result>:<reason>` code carries no
refusing input, and a renderer that guessed one would be recomputing (`RRA-009` §Preservation).
The fix threads the refusing semantic onto `RefusedResult` in `facts.py`, which another slice owns,
and needs the owner to name the part-4 column vocabulary. When that lands this test XPASSes, strict
fails it, and the marker comes off -- the future slice's RED step already written.

The assertion is deliberately vocabulary-free: the metric's name is stated once, as part 1, and is
not restated where the column belongs.
"""

from __future__ import annotations

import pytest

from khepri.rra.rendering.wording import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    business_metric_name,
    caveat_prose,
)

RESULT = "units_by_channel"
COLUMN_REASONS = (
    "required_input_unavailable",
    "incomplete_column_coverage",
    "ambiguous_mapping",
)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#560 item 2: the refusing input is not on RefusedResult (facts.py); deferred",
)
@pytest.mark.parametrize("language", (LANGUAGE_ENGLISH, LANGUAGE_ARABIC))
@pytest.mark.parametrize("reason", COLUMN_REASONS)
def test_the_missing_column_is_not_the_refused_metric(reason: str, language: str) -> None:
    prose = caveat_prose(f"{RESULT}:{reason}", language)
    name = business_metric_name(RESULT, language)

    assert prose.count(name) == 1
