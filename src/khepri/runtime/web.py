"""ASGI entry point for the approved synchronous RRA web role."""

from khepri.runtime.config import RuntimeSettings
from khepri.runtime.db_roles import DatabaseRole
from khepri.runtime.wiring import build_stack, build_web_app

app = build_web_app(build_stack(RuntimeSettings.from_environment(role=DatabaseRole.APPLICATION)))
