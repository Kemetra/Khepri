"""What `rra_calculation_oracle.to_csv` must emit for a governed calculation.

Separate from `test_rra_calculation_oracle.py`, which is about the hand-derived
expected *values*. This file is about the bridge that turns those rows into the
CSV a package is built from -- a different subject, and one whose obligations come
from `RRA-003`'s admission rules rather than from any arithmetic.
"""

from __future__ import annotations


def test_the_bridge_emits_the_event_kind_and_status_every_row_proves() -> None:
    """`to_csv`'s own docstring records this as a debt `V-mapping` discharges.

    `RRA-003` requires every row used by a governed calculation to carry an
    event kind and a status, and forbids establishing either "from generic
    headers and observed values". The bridge omitted both while no governed
    spelling existed, which left `MESSY_RETURNS_ROWS` unusable: its return is
    identifiable only by a negative revenue, and inferring the kind from that
    sign is the inference the specification refuses.

    `V-mapping` landed the source contract carrying "event-kind column or
    sale-only declaration", so the spelling now exists and the bridge must use
    it. Without this, no slice can prove a sale-only ratio beside a
    return-inclusive headline -- the whole point of the messy-returns case.
    """
    from tests.rra_calculation_oracle import CSV_COLUMNS, MESSY_RETURNS_ROWS, to_csv

    assert "event_kind" in CSV_COLUMNS
    assert "status" in CSV_COLUMNS

    header, *rows = to_csv(MESSY_RETURNS_ROWS).decode().strip().split("\n")
    kinds = header.split(",").index("event_kind")
    statuses = header.split(",").index("status")

    assert [row.split(",")[kinds] for row in rows] == ["sale", "sale", "return"]
    assert {row.split(",")[statuses] for row in rows} == {"posted"}
