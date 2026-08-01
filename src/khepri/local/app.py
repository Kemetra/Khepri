"""The ASGI entry point, for `uvicorn khepri.local.app:app`.

Module-level construction, which means importing this connects to PostgreSQL and
the local S3 endpoint. That is right for an entry point and wrong for anything
else, so nothing in the package imports it — the tests build their own stack.
"""

from __future__ import annotations

from khepri.local.wiring import build_stack, build_web_app

app = build_web_app(build_stack())

__all__ = ["app"]
