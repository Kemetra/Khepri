from __future__ import annotations

AUTHENTICATION_FAILURE = "Credentials are invalid or unavailable."
SCOPE_FAILURE = "Scope is invalid or unavailable."
ORGANIZATION_FAILURE = "Organization could not be created."
ACCOUNT_FAILURE = "Account is invalid or unavailable."
ROLE_CHANGE_FAILURE = "Role could not be changed."

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

# The outcomes of an owner-reducing operation. The store reports one of these; the service
# translates it into a refusal above. They live here rather than in `persistence` because both
# layers need the vocabulary and this module is the leaf both already depend on -- a service
# importing from persistence to learn how to raise would invert the dependency.
#
# Reported rather than raised so the whole refusal contract, including FR-013's deliberately
# non-uniform message, stays in one place instead of being split across persistence.
OWNER_CHANGE_APPLIED = "applied"
OWNER_CHANGE_FINAL_OWNER = "final_owner"
OWNER_CHANGE_NOT_APPLICABLE = "not_applicable"


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


class RoleChangeFailed(ValueError):
    """A role change that could not be applied.

    Distinct from `FinalOwnerProtected`, which FR-013 requires to name its cause. This one is
    content-free like the rest: it must not disclose whether the membership exists, because a
    caller probing role changes against account identifiers would otherwise enumerate
    memberships one refusal at a time.
    """
