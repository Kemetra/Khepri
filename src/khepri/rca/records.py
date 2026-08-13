"""The two-door construction rule for `khepri.rca` records (#151).

Every record in this package exposes exactly two ways to come into existence:

| Door | Name | Caller | Guarantee |
|---|---|---|---|
| Creation | `Record.create(...)` | the service layer | allocates and validates |
| Reconstruction | `Record._from_storage(...)` | `persistence` only | preserves stored values |

Creation flows one way and reconstruction the other; they never meet. A record rebuilt from a
row is never handed to a creation path, and `create` has no parameter for a stored-only field,
so an untrusted value is not merely rejected — it is unexpressible.

## Why the package needs this at all

PR #148 ran four review rounds on `IsolationScope`, each fixing the previous finding and
producing the next: validate in the service (store callers bypass it) → validate the key's
shape (`own_AcmePharmacy000000000000` passes) → let the type allocate its own key and add a
`restore` for reads → **`restore` is itself the bypass**. The loop does not terminate by local
fixes, because each answers "who guards this?" for one record while leaving the others open.
The distinction the fourth round backed into — that creation and reconstruction are different
operations needing different doors — is made explicit here, and applied uniformly.

## What this does NOT claim

**Python has no private construction.** `object.__setattr__` still mutates a frozen instance,
and nothing stops a module importing `SEALED`. Verified, not assumed.

The guarantee is that bypassing a door must be *deliberate and conspicuous* — never something
a caller does by accident while writing ordinary-looking code. Docstrings in this package
therefore say "unmistakable", never "unbypassable". The removed docstring on `IsolationScope`
claimed "no layer can construct a scope carrying an untrusted key", which was untrue at the
moment it was written, and reviewers trusting it is part of why #148's rounds continued.
"""

from __future__ import annotations

from dataclasses import field
from typing import Any

# The capability that distinguishes a door from a direct call. Module-private by convention;
# see the module docstring on what that is and is not worth.
SEALED = object()

_MISUSE = (
    "records in khepri.rca are constructed through create() or _from_storage(), "
    "not by calling the class directly"
)


def sealed_field() -> Any:
    """The sentinel field every sealed record carries.

    `kw_only=True` keeps this default-valued field from forcing defaults onto the fields
    declared before it, which is otherwise a `TypeError` at class-definition time.
    `compare=False` and `repr=False` keep it out of `__eq__`, `__hash__`, and `__repr__`, so a
    record created through one door equals the same record rebuilt through the other — which
    persistence round-trip tests depend on.
    """
    return field(kw_only=True, compare=False, repr=False, default=None)


class Sealed:
    """Mixin giving a frozen dataclass the two-door construction rule.

    Subclasses declare their fields plus `_token: object = sealed_field()`, and provide
    `create` and `_from_storage` classmethods that pass `_token=SEALED`.
    """

    __slots__ = ()

    def __post_init__(self) -> None:
        if getattr(self, "_token", None) is not SEALED:
            raise TypeError(_MISUSE)


def assert_sealed(*records: object) -> None:
    """Confirm records reached a persistence boundary through a construction door.

    The stores are internal to `khepri.rca` (#151 Q1), so this is a programming-error check,
    not input validation — it is deliberately an assertion about provenance rather than about
    field contents. Checking contents is what #148's round 2 already proved insufficient:
    shape cannot establish where a value came from.
    """
    for record in records:
        if getattr(record, "_token", None) is not SEALED:
            raise TypeError(_MISUSE)
