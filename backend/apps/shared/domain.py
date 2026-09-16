import json
from datetime import timezone

from bson import ObjectId

from .errors import AppError, ValidationError

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
STATUSES = ("TRIGGERED", "ACKNOWLEDGED", "RESOLVED")
DISPOSITIONS = ("CREATED_INCIDENT", "GROUPED", "SUPPRESSED_DUPLICATE")


def invalid(field, message):
    raise ValidationError([], {field: [message]})


def body_object(body, allowed):
    if not isinstance(body, dict):
        invalid("body", "Provide a JSON object.")
    if any(not isinstance(key, str) for key in body):
        invalid("body", "Object field names must be strings.")
    unknown = set(body) - set(allowed)
    if unknown:
        invalid("body", "Unsupported fields: " + ", ".join(sorted(unknown)))
    return body


def text(value, field, maximum=200, optional=False):
    if optional and value is None:
        return ""
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        invalid(field, f"Provide nonempty text of at most {maximum} characters.")
    return value.strip()


def identifier(value, field="id"):
    if isinstance(value, ObjectId):
        return value
    if not isinstance(value, str) or len(value) != 24 or not ObjectId.is_valid(value):
        invalid(field, "Provide a valid identifier.")
    return ObjectId(value)


def choice(value, field, choices):
    if not isinstance(value, str) or value not in choices:
        invalid(field, "Choose one of: " + ", ".join(choices))
    return value


def integer(value, field, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        invalid(field, f"Provide an integer from {minimum} to {maximum}.")
    return value


def utc(moment):
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def json_payload(value, maximum=32768):
    if not isinstance(value, dict):
        invalid("payload", "Provide a JSON object.")

    def check(node, depth=0):
        if depth > 8:
            invalid("payload", "Payload nesting cannot exceed eight levels.")
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(key, str) or not key or "." in key or key.startswith("$"):
                    invalid("payload", "Payload keys cannot be empty, contain dots, or start with $.")
                check(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                check(child, depth + 1)

    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=False)
        size = len(encoded.encode("utf-8"))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        invalid("payload", "Provide finite, JSON-compatible values.")
    if size > maximum:
        invalid("payload", f"Payload cannot exceed {maximum} bytes.")
    check(value)
    return json.loads(encoded)


def require(found, kind):
    if found is None:
        raise AppError(404, "NOT_FOUND", f"The requested {kind} does not exist.")
    return found
