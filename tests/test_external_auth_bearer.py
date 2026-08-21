"""Authorization-header parsing for the private-beta external authentication route.

Written to lock `_bearer`'s behavior before `#240`'s Complex Conditional finding was restructured.
The route's malformed-header cases had **no** coverage: `tests/test_clerk_private_beta_e2e.py`
exercises only a well-formed `Bearer <token>` header, so every refusal branch below could have
changed shape during a refactor without a single test failing.

`_bearer` is imported directly rather than driven through HTTP. It is a pure function, and asserting
against it names the property under test; a 404 from the route would also be produced by an unlinked
subject or a disabled account, so an HTTP-level assertion could pass while the parser was broken.
"""

from __future__ import annotations

import pytest

from khepri.runtime.external_auth_api import _bearer

VALID = "eyJhbGciOiJSUzI1NiJ9.payload.signature"


def test_a_well_formed_header_yields_the_credential() -> None:
    assert _bearer(f"Bearer {VALID}") == VALID


@pytest.mark.parametrize(
    "header",
    [
        pytest.param(None, id="absent-header"),
        pytest.param("", id="empty-header"),
        pytest.param("Bearer", id="scheme-only-no-space"),
        pytest.param("Bearer ", id="scheme-and-space-but-no-credential"),
        pytest.param(f"bearer {VALID}", id="lowercase-scheme"),
        pytest.param(f"BEARER {VALID}", id="uppercase-scheme"),
        pytest.param(f"Basic {VALID}", id="wrong-scheme"),
        pytest.param(f"Token {VALID}", id="other-scheme"),
        pytest.param(VALID, id="bare-credential-no-scheme"),
        pytest.param(f"Bearer  {VALID}", id="double-space-leaves-leading-space"),
        pytest.param(f"Bearer {VALID} ", id="trailing-space"),
        pytest.param(f"Bearer {VALID}\t", id="trailing-tab"),
        pytest.param(f"Bearer {VALID}\n", id="trailing-newline"),
        pytest.param(f"Bearer part {VALID}", id="embedded-space"),
        pytest.param(f"Bearer part\t{VALID}", id="embedded-tab"),
        pytest.param(f"Bearer part\n{VALID}", id="embedded-newline"),
        pytest.param("Bearer  token", id="embedded-non-breaking-space"),
    ],
)
def test_every_malformed_header_is_refused_identically(header: str | None) -> None:
    """One refusal shape for absent, mis-scheme, empty, and whitespace-bearing headers.

    The scheme is case-sensitive by design: `Bearer` is the only accepted spelling, so a case
    variant is a malformed header rather than a tolerated one.

    Embedded and surrounding whitespace are refused rather than trimmed. A credential is opaque
    material, so silently rewriting it would make the value Khepri verifies differ from the value
    the caller sent.
    """
    assert _bearer(header) is None
