import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from django.conf import settings

from apps.users import services as person_service
from apps.shared.errors import AppError
from apps.shared.validation import is_object_id

from . import repository

TOKEN_ALGORITHM = "HS256"
TOKEN_TYPES = ["workspace", "profile"]
DURATION_PATTERN = re.compile(r"^(\d+)([smhd])$")
SECONDS_PER_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}
DEFAULT_EXPIRY_SECONDS = 86400


def expiry_seconds(value):
    matched = DURATION_PATTERN.match(value or "")

    if not matched:
        return DEFAULT_EXPIRY_SECONDS

    return int(matched.group(1)) * SECONDS_PER_UNIT[matched.group(2)]


def public_account(account):
    return {"_id": str(account["_id"]), "name": account["name"], "email": account["email"]}


def sign(account, profile_id=None):
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(account["_id"]),
        "type": "profile" if profile_id else "workspace",
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=expiry_seconds(settings.JWT_EXPIRES_IN)),
        "aud": settings.JWT_AUDIENCE,
        "iss": settings.JWT_ISSUER,
    }

    if profile_id:
        payload["profileId"] = str(profile_id)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=TOKEN_ALGORITHM)


def allows_profile(account, profile_id):
    return any(str(value) == str(profile_id) for value in account.get("allowedProfileIds", []))


def login(email, password):
    account = repository.find_active_by_email(email.lower())
    valid = account is not None and bcrypt.checkpw(password.encode(), account["passwordHash"].encode())

    if not valid:
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")

    return {"account": public_account(account), "token": sign(account)}


def decode(token):
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[TOKEN_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
    except jwt.PyJWTError:
        raise AppError(401, "INVALID_TOKEN", "Your Incident Relay session is invalid or has expired.")


def authenticate(token):
    payload = decode(token)

    if not is_object_id(payload.get("sub")) or payload.get("type") not in TOKEN_TYPES:
        raise AppError(401, "INVALID_TOKEN", "Your Incident Relay session is invalid or has expired.")

    account = repository.find_active_by_id(payload["sub"])

    if account is None:
        raise AppError(401, "ACCOUNT_UNAVAILABLE", "This Incident Relay workspace is no longer available.")

    if payload["type"] == "profile" and not allows_profile(account, payload.get("profileId")):
        raise AppError(403, "PROFILE_FORBIDDEN", "This profile is not available in the current workspace.")

    return account, payload


def session(account):
    return {"account": public_account(account)}


def switch_profile(account, profile_id):
    if not allows_profile(account, profile_id):
        raise AppError(403, "PROFILE_FORBIDDEN", "This profile is not available in the current workspace.")

    profile = person_service.find_profile_by_id(profile_id)

    if profile is None:
        raise AppError(404, "PROFILE_NOT_FOUND", "This Incident Relay profile is no longer available.")

    return {"profile": profile, "token": sign(account, profile_id)}
