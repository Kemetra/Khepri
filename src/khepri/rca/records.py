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

## Substitution is not a door; faithful copying is harmless

`dataclasses.replace` and `copy.replace` rebuild an instance by calling the constructor from
ordinary code, so neither is a door and both are refused. That is the load-bearing rule:
producing a *modified* record means going through `create` or `_from_storage` again. A role
change and a verifier destruction are **operations**, not field assignments, and #150 and #149
respectively must write them as such.

`copy.copy` and `copy.deepcopy` are **also doors**, via `__copy__` and `__deepcopy__` on
`Sealed`, and they rebuild from the source record's own attributes. That is not defence in
depth — it closes a real substitution path. `copy.deepcopy(account, {id(account.verifier):
fake})` pre-seeds what a nested field copies to, which is field substitution by another name;
verified before those methods existed, it produced an `Account` holding
`digest=b"recoverable-credential"` that `assert_sealed` accepted and the store persisted.

An earlier version of this docstring asserted these protocols "reproduce every field verbatim
and offer no parameter through which a caller's value can enter". The `memo` argument is exactly
such a parameter. The claim was wrong, and it is recorded here because being wrong in a
docstring is how #148's review rounds kept going.

`pickle` remains unguarded and is out of scope: it restores through `__reduce_ex__` without
calling `__init__`, and a crafted payload is arbitrary code execution against any boundary this
module could offer.

None of this was true of the first version of this module; see the comment on `_opening` for
the forgery it permitted.

## What this does NOT claim

**Python has no private construction.** `object.__setattr__` still mutates a frozen instance,
and nothing stops a module calling `through_door()` itself. Verified, not assumed.

**A door authorizes the thread, not one call.** While it is open, any code running on that
thread can construct any sealed record. The doors therefore keep the window to a single
constructor call: `Account.create` derives its verifier *before* opening, and `Verifier.derive`
runs its ~100ms scrypt outside its own door, so no expensive or re-entrant work happens while
construction is authorized. Keep it that way — a door that wraps a long computation, a
callback, or anything that yields is a wider grant than it looks.

The guarantee is that bypassing a door must be *deliberate and conspicuous* — never something
a caller does by accident while writing ordinary-looking code. `dataclasses.replace` was
precisely such an accident, which is what made it worth fixing rather than documenting.

Docstrings in this package therefore say "unmistakable", never "unbypassable". The removed
docstring on `IsolationScope` claimed "no layer can construct a scope carrying an untrusted
key", which was untrue at the moment it was written, and reviewers trusting it is part of why
#148's rounds continued.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

_MISUSE = (
    "records in khepri.rca are constructed through create() or _from_storage(), "
    "not by calling the class directly or by copying an existing instance"
)

# The capability is a property of the *call*, not of the object.
#
# The first version of this module made it an instance field carrying a module-private
# sentinel. That was wrong, and wrong in the exact way #148's rounds were wrong: it certified
# "this object came through a door" when what needs certifying is "this call is a door".
# `dataclasses.replace(scope, owner_id="own_VictimPharmacyInc000000")` copies every field the
# caller did not override — including the sentinel — onto a record whose remaining fields it
# just rewrote, producing a forgery that `assert_sealed` accepted. Verified before this fix:
# the forged scope committed through `SqlOrganizationStore.create_organization` and
# `resolve_scope` handed the organization's own name back as the analytical boundary.
#
# Thread-local rather than a plain module global because a store may be used from several
# threads, and one thread's construction must not authorize another's.
_opening = threading.local()

# The exact record types persistence accepts, populated by `@register_sealed`. A set of exact
# types rather than an isinstance check, because a subclass passes isinstance while being the
# very thing whose construction may have been altered.
_SEALED_TYPES: set[type] = set()


@contextmanager
def _door() -> Iterator[None]:
    """Mark the dynamic extent of a construction door.

    Re-entrant by depth count: `Organization.create` may construct nested records, and an
    inner door closing must not revoke the outer one.
    """
    depth = getattr(_opening, "depth", 0)
    _opening.depth = depth + 1
    try:
        yield
    finally:
        _opening.depth = depth


def _is_open() -> bool:
    return getattr(_opening, "depth", 0) > 0


class Sealed:
    """Mixin giving a frozen dataclass the two-door construction rule.

    Subclasses declare their fields normally — no sentinel field — and build instances inside
    `through_door()` from their `create` and `_from_storage` classmethods.

    Because the capability lives in the call stack rather than on the instance, there is
    nothing for `dataclasses.replace` or `copy.replace` to carry forward: both call the
    constructor from outside a door and are refused. Modifying a sealed record therefore means
    building a new one through a door, which is what #149 (verifier destruction) and #150
    (role transitions) must do. See the module docstring for why the copy protocols are a
    different case and are deliberately left alone.
    """

    __slots__ = ()

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Refuse a subclass that overrides the door check.

        `__post_init__` is an ordinary method, so the dataclass-generated `__init__` dispatches
        to it dynamically and a subclass can override it with a no-op. Verified: a subclass of
        `Account` doing exactly that constructed a record holding
        `digest=b"recoverable-password"` with no door open, and `assert_sealed` accepted it via
        `isinstance`, defeating FR-002.

        Two things close it. This hook rejects the override at class-definition time, and the
        check itself lives in the name-mangled `__enforce_door` below, which
        `__post_init__` calls — a subclass writing `__post_init__` cannot reach
        `_Sealed__enforce_door`, so even a subclass defined before this hook existed could not
        silence the check without naming the mangled attribute explicitly.
        """
        super().__init_subclass__(**kwargs)
        if "__post_init__" in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} may not override __post_init__: it is the door check"
            )

    def __enforce_door(self) -> None:
        if not _is_open():
            raise TypeError(_MISUSE)

    def __post_init__(self) -> None:
        self.__enforce_door()

    def __deepcopy__(self, memo: dict[int, object]) -> Sealed:
        """Deep-copy by rebuilding through a door, ignoring the caller's `memo`.

        The default implementation restores state through `__reduce_ex__` without calling
        `__init__`, so no door check applies — which was safe only while a copy reproduced every
        field verbatim. It does not: `copy.deepcopy(account, {id(account.verifier): fake})`
        pre-seeds what a nested field copies to, and that is field *substitution*, the same
        capability `dataclasses.replace` has. Verified before this method existed: it produced an
        `Account` holding `digest=b"recoverable-credential"` that `assert_sealed` accepted and
        the store persisted, defeating FR-002 at exactly the boundary this class defends.

        Rebuilding from `self`'s own attributes, rather than from the memo, makes a deep copy
        faithful by construction. Records here are frozen and hold only immutable scalars,
        `bytes`, `datetime`, and other sealed records, so sharing them is safe; there is no
        mutable state a caller could reach through the copy.
        """
        with _door():
            return type(self)(
                **{field: getattr(self, field) for field in self.__dataclass_fields__}
            )

    def __copy__(self) -> Sealed:
        """Shallow-copy through a door, for the same reason `__deepcopy__` exists."""
        with _door():
            return type(self)(
                **{field: getattr(self, field) for field in self.__dataclass_fields__}
            )


@contextmanager
def through_door() -> Iterator[None]:
    """Open a construction door for the duration of the block.

    Every `create` and `_from_storage` in this package wraps its constructor call in this.
    """
    with _door():
        yield


def assert_sealed(*records: object) -> None:
    """Confirm records reached a persistence boundary as instances of a sealed type.

    The stores are internal to `khepri.rca` (#151 Q1), so this is a programming-error check,
    not input validation — it asserts the type discipline held, not that field contents look
    right. Checking contents is what #148's round 2 already proved insufficient: shape cannot
    establish where a value came from.

    With the capability moved into the call stack, an instance of a sealed type can only exist
    if a door was open when it was built, so the type itself is the evidence — but only for the
    types this package declares. `isinstance` is deliberately **not** used: a subclass satisfies
    it by definition, and a subclass is precisely the thing that could have altered how it was
    constructed. Requiring the exact declared type means a record reaching persistence is one of
    ours, not merely something that inherits from one.
    """
    for record in records:
        if type(record) not in _SEALED_TYPES:
            raise TypeError(_MISUSE)


def register_sealed(cls: type) -> type:
    """Declare a type as one persistence will accept. Used as a decorator on each record."""
    _SEALED_TYPES.add(cls)
    return cls
