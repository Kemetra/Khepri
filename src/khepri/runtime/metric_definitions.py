"""The metric-catalog adapter (`D1-05`), bound at the composition root.

`khepri.rca` may not import `khepri.rra` (`R7-01` §3: a bridge inside RCA would
make every RCA test transitively depend on RRA), and `RCA-006`'s package
boundary bars it outright. The evidence drawer needs `RRA-011`'s catalog, so it
declares a Protocol and this module binds the implementation -- `ports.py`'s
rule, "the consumer owns the Protocol; the composition root binds the
implementation".

`khepri.runtime` is where that binding belongs: it already imports both sides,
as `run_quality.py` does for the same catalog.

**A pass-through and nothing else.** `UnknownCode` propagates rather than being
caught: `RRA-011` requires a lookup to fail closed, and an adapter that returned
a placeholder would put an invented definition in front of a customer.
"""

from __future__ import annotations

from khepri.rra import definitions

__all__ = ["CatalogDefinitions"]


class CatalogDefinitions:
    """`RRA-011`'s catalog, behind the drawer's Protocol."""

    def formula_version(self, code: str) -> str:
        """The governed version of the contract that computes this metric."""
        return definitions.define_metric(code).formula_version

    def describe(self, code: str, language: str) -> str:
        """The metric's governed description in one of the two languages."""
        return definitions.describe_metric(code, language)
