import functools

from apps.auth import services as auth_service
from apps.users import services as person_service

from .errors import AppError
from .validation import is_object_id

BEARER_PREFIX = "Bearer "


def read_token(request):
    authorization = request.headers.get("Authorization", "")

    if not authorization.startswith(BEARER_PREFIX):
        raise AppError(401, "AUTH_REQUIRED", "Sign in to the Incident Relay workspace to continue.")

    token = authorization[len(BEARER_PREFIX) :].strip()

    if not token:
        raise AppError(401, "AUTH_REQUIRED", "Sign in to the Incident Relay workspace to continue.")

    return token


def resolve_profile(request):
    profile_id = request.auth_payload.get("profileId") or ""

    if not profile_id:
        raise AppError(401, "PROFILE_REQUIRED", "Select an Incident Relay profile to continue.")

    if not is_object_id(profile_id):
        raise AppError(401, "INVALID_PROFILE", "Select a valid Incident Relay profile.")

    if not auth_service.allows_profile(request.account, profile_id):
        raise AppError(403, "PROFILE_FORBIDDEN", "This profile is not available in the current workspace.")

    profile = person_service.find_profile_by_id(profile_id)

    if profile is None:
        raise AppError(401, "PROFILE_NOT_FOUND", "This Incident Relay profile is no longer available.")

    return profile


def require_workspace_auth(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        request.account, request.auth_payload = auth_service.authenticate(read_token(request))

        return view(request, *args, **kwargs)

    return wrapper


def require_profile_context(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        request.profile = resolve_profile(request)
        request.profile_id = str(request.profile["_id"])

        return view(request, *args, **kwargs)

    return wrapper
