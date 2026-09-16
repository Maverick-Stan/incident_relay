import re

from apps.shared.domain import body_object, identifier, invalid, text
from apps.shared.validation import Errors, read_email


def validate_user(body):
    body_object(body, ("name", "email", "password", "allowedProfileIds", "avatarColor"))
    errors = Errors()
    email = read_email(errors, body, "email", 254)
    errors.raise_if_any()
    profiles = body.get("allowedProfileIds", [])
    if not isinstance(profiles, list):
        invalid("allowedProfileIds", "Provide a list of identifiers.")
    password = body.get("password")
    if not isinstance(password, str) or not password or len(password.encode("utf-8")) > 72:
        invalid("password", "Provide a password containing at most 72 UTF-8 bytes.")
    color = body.get("avatarColor")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        invalid("avatarColor", "Provide a six-digit hexadecimal color.")
    return {
        "name": text(body.get("name"), "name", 120),
        "email": email.lower(),
        "password": password,
        "allowed_profile_ids": [identifier(value, "allowedProfileIds") for value in profiles],
        "avatar_color": color,
    }
