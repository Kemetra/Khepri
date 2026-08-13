from __future__ import annotations

AUTHENTICATION_FAILURE = "Credentials are invalid or unavailable."
SCOPE_FAILURE = "Scope is invalid or unavailable."
ORGANIZATION_FAILURE = "Organization could not be created."


class AuthenticationFailed(PermissionError):
    pass


class ScopeAccessDenied(PermissionError):
    pass


class OrganizationCreationFailed(ValueError):
    pass
