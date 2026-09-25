"""A result refusal's fourth part names a column, not the refused metric (`#560` item 2).

`RRA-009` §Refusals: part 4 names "which missing field or evidence caused it, named as a column
the customer would recognise in their own export". `wording.caveat_prose` used to fill the
`{column}` and `{field}` placeholders with the refused metric's business name, so
`units_by_channel` refused for a gapped column read "Units sold is in your file but some rows leave
it empty".

This was a strict `xfail` until the refusing input travelled on `RefusedResult`. It is now the RED
test of the slice that carries it: given the input, the metric is stated once, as part 1, and the
column the customer mapped is named where part 4 belongs, using the journey's own mapping label.
The labels are written out rather than read from `JOURNEY_COPY`, which would restate the table.

The real-bundle path to the same sentence is `test_rra009_refusal_inputs.py`.
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
#: The journey's mapping label for `channel`, the input `units_by_channel` needs beside units.
CHANNEL_LABEL = {LANGUAGE_ENGLISH: "Sales channel", LANGUAGE_ARABIC: "قناة البيع"}


@pytest.mark.parametrize("language", (LANGUAGE_ENGLISH, LANGUAGE_ARABIC))
@pytest.mark.parametrize("reason", COLUMN_REASONS)
def test_the_missing_column_is_not_the_refused_metric(reason: str, language: str) -> None:
    prose = caveat_prose(f"{RESULT}:{reason}", language, refusing_input="channel")
    name = business_metric_name(RESULT, language)

    assert prose.count(name) == 1, prose
    assert CHANNEL_LABEL[language] in prose, prose
    assert "{" not in prose, prose
