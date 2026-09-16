from mongoengine import NotUniqueError

from .models import Event


def find(event_id):
    return Event.objects(id=event_id).first()


def find_delivery(service_id, source, source_event_id):
    return Event.objects(service_id=service_id, source=source, source_event_id=source_event_id).first()


def exists_for_service(service_id):
    return Event.objects(service_id=service_id).first() is not None


def for_incident(incident_id):
    return list(Event.objects(incident_id=incident_id).order_by("received_at", "id"))


def for_service(service_id, offset=0, limit=50):
    query = Event.objects(service_id=service_id).order_by("-received_at", "-id")
    return list(query.skip(offset).limit(limit)), query.count()


def matching_event(incident_ids, field, value):
    # Callers supply a fixed internal field name, never a request-controlled query.
    return Event.objects(incident_id__in=incident_ids, **{field: value}).order_by("-received_at", "-id").first()


def insert_once(event):
    try:
        event.save(force_insert=True)
        return event, True
    except NotUniqueError:
        existing = find_delivery(event.service_id, event.source, event.source_event_id)
        if existing is None:
            raise
        return existing, False
