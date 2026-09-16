import hashlib
import secrets

from apps.shared.documents import now_utc
from apps.shared.domain import identifier, require
from apps.shared.errors import AppError
from apps.users import services as users

from . import repository
from .models import Service
from .schema import validate_service


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def get(service_id):
    return require(repository.find(identifier(service_id, "serviceId")), "service")


def create(body, *, service_id=None, at=None, demo_key=None):
    values = validate_service(body)
    users.get(values["owner_id"])
    raw_key = demo_key if demo_key is not None else secrets.token_urlsafe(32)
    if not isinstance(raw_key, str) or len(raw_key) < 32:
        raise ValueError("Integration keys must contain at least 32 characters.")
    moment = at or now_utc()
    service = repository.insert(Service(id=service_id, **values, integration_key_hash=hash_key(raw_key), integration_key_last_four=raw_key[-4:], created_at=moment, updated_at=moment))
    return service, raw_key


def update(service_id, body, *, at=None):
    service = get(service_id)
    values = validate_service(body, partial=True)
    if "owner_id" in values:
        users.get(values["owner_id"])
    for key, value in values.items():
        setattr(service, key, value)
    service.updated_at = at or now_utc()
    return repository.replace(service)


def authenticate_key(raw_key):
    if not isinstance(raw_key, str) or not raw_key or len(raw_key) > 256:
        raise AppError(401, "INVALID_INTEGRATION_KEY", "Provide a valid integration key.")
    found = repository.find_by_key_hash(hash_key(raw_key))
    if found is None:
        raise AppError(401, "INVALID_INTEGRATION_KEY", "Provide a valid integration key.")
    return found


def remove(service_id):
    from apps.events import repository as events
    from apps.incidents import repository as incidents

    service = get(service_id)
    if events.exists_for_service(service.id) or incidents.exists_for_service(service.id):
        raise AppError(409, "SERVICE_IN_USE", "A service with events or incidents cannot be deleted.")
    repository.remove(service.id)
