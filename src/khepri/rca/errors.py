from __future__ import annotations

AUTHENTICATION_FAILURE = "Credentials are invalid or unavailable."
SCOPE_FAILURE = "Scope is invalid or unavailable."
ORGANIZATION_FAILURE = "Organization could not be created."
ACCOUNT_FAILURE = "Account is invalid or unavailable."

# FR-013 is a deliberate exception to the content-free refusal rule the messages above follow.
# It requires the operation to "fail closed and MUST state that the final owner cannot be
# removed" -- so unlike every other refusal here, this one names its cause.
#
# That is coherent rather than a contradiction. FR-004 and FR-034 keep refusals content-free to
# prevent enumeration: a caller must not learn whether an account or a resource exists. Here the
# caller is already an authenticated member of the organization in question, so they know it
# exists and know its membership. There is nothing left to disclose, and a uniform refusal would
# instead leave an owner unable to tell "you cannot remove the last owner" from "something went
# wrong" -- which is the outcome FR-013 names explicitly to avoid.
FINAL_OWNER_FAILURE = "The final owner of an organization cannot be removed or disabled."


class AuthenticationFailed(PermissionError):
    pass


class ScopeAccessDenied(PermissionError):
    pass


class OrganizationCreationFailed(ValueError):
    pass


class AccountOperationFailed(PermissionError):
    pass


class FinalOwnerProtected(PermissionError):
    pass
