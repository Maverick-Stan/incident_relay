import hashlib
import json
from datetime import timedelta

from apps.incidents import services as incidents
from apps.incidents import repository as incident_repository
from apps.services import services as service_domain
from apps.shared.documents import now_utc
from apps.shared.domain import DISPOSITIONS, choice, identifier, invalid, text, utc
from apps.shared.errors import AppError

from . import repository
from .models import Event, TriageDecision
from .schema import validate_event


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def normalize(service_id, body, *, validated=None):
    values = dict(validated) if validated is not None else validate_event(body)
    labels, payload = values.pop("labels"), values.pop("payload")
    values["fingerprint"] = digest({"serviceId": str(service_id), "source": values["source"], "title": values["normalized_title"], "severity": values["normalized_severity"], "labels": labels, "payload": payload})
    values["grouping_key"] = digest({"serviceId": str(service_id), "source": values["source"], "component": labels.get("component", ""), "alertType": labels.get("alerttype", values["normalized_title"])})
    return values


def record(service_id, body, incident_id, disposition, reason, *, duplicate_of=None, received_at=None, event_id=None):
    """Persist and validate a trusted internal outcome selected by intake or seed."""
    service = service_domain.get(service_id)
    values = normalize(service.id, body)
    existing = repository.find_delivery(service.id, values["source"], values["source_event_id"])
    if existing is not None:
        return existing, False
    choice(disposition, "disposition", DISPOSITIONS)
    reason = text(reason, "reason", 1000)
    incident = incidents.get(incident_id)
    moment = utc(received_at or now_utc())
    if incident.service_id != service.id:
        invalid("incidentId", "The incident must belong to the event's service.")
    if incident.status == "RESOLVED":
        raise AppError(409, "INCIDENT_RESOLVED", "New events cannot join a resolved incident.")
    if moment < utc(incident.timeline[-1].at):
        invalid("receivedAt", "Events cannot predate the latest incident activity.")
    if moment - utc(incident.created_at) > timedelta(minutes=service.grouping_window_minutes):
        invalid("incidentId", "The incident is outside the service grouping window.")
    previous = repository.for_incident(incident.id)
    if disposition == "CREATED_INCIDENT":
        if incident.origin != "EVENT" or previous:
            invalid("disposition", "An event-created incident can have only one initial event.")
    elif not previous or not any(event.grouping_key == values["grouping_key"] for event in previous):
        invalid("disposition", "Related events must match an existing grouping key.")
    duplicate = None
    if disposition == "SUPPRESSED_DUPLICATE":
        duplicate = repository.find(identifier(duplicate_of, "duplicateOfEventId"))
        if duplicate is None or duplicate.incident_id != incident.id or duplicate.service_id != service.id or duplicate.fingerprint != values["fingerprint"]:
            invalid("duplicateOfEventId", "The duplicate must match a prior event in this incident.")
    elif duplicate_of is not None:
        invalid("duplicateOfEventId", "Only suppressed duplicates may reference a duplicate event.")
    elif disposition == "GROUPED" and any(event.fingerprint == values["fingerprint"] for event in previous):
        invalid("disposition", "An exact duplicate must use duplicate suppression.")
    event = Event(id=event_id, service_id=service.id, **values, received_at=moment, incident_id=incident.id, disposition=disposition, duplicate_of_event_id=duplicate.id if duplicate else None, triage_decision=TriageDecision(rule=disposition, reason=reason, matched_incident_id=None if disposition == "CREATED_INCIDENT" else incident.id, matched_event_id=duplicate.id if duplicate else None, decided_at=moment))
    stored, created = repository.insert_once(event)
    if created:
        incidents.attach_event(incident.id, stored.id, disposition, at=moment)
    return stored, created


def ingest(service, body, *, at=None):
    """Synchronous intake: valid delivery retries return before matching or mutation."""
    validated = validate_event(body)
    existing = repository.find_delivery(service.id, validated["source"], validated["source_event_id"])
    if existing is not None:
        return existing, False

    values = normalize(service.id, body, validated=validated)
    moment = utc(at or now_utc())
    candidates = incident_repository.active_in_window(service.id, moment - timedelta(minutes=service.grouping_window_minutes), moment)
    candidate_ids = [incident.id for incident in candidates]
    # Search every eligible incident for an exact match BEFORE considering grouping.
    matched = repository.matching_event(candidate_ids, "fingerprint", values["fingerprint"])
    duplicate = matched
    if matched is None:
        matched = repository.matching_event(candidate_ids, "grouping_key", values["grouping_key"])
    if matched is not None:
        incident = incidents.get(matched.incident_id)
        age = max(0, int((moment - utc(incident.created_at)).total_seconds() // 60))
        if duplicate is not None:
            disposition = "SUPPRESSED_DUPLICATE"
            reason = f"Suppressed as an exact duplicate of event {duplicate.id}: its fingerprint matches in active incident {incident.reference}, created {age} minutes ago within this service's {service.grouping_window_minutes}-minute window."
        else:
            disposition = "GROUPED"
            reason = f"Grouped into {incident.reference}: the service and grouping key match an active incident created {age} minutes ago within the {service.grouping_window_minutes}-minute window; no exact fingerprint matched."
    else:
        incident = incidents.create({"serviceId": str(service.id), "title": values["normalized_title"], "severity": values["normalized_severity"]}, origin="EVENT", at=moment)
        disposition = "CREATED_INCIDENT"
        reason = f"Created {incident.reference}: no exact fingerprint or related grouping key matched an active incident for this service within its {service.grouping_window_minutes}-minute window."
    return record(service.id, body, incident.id, disposition, reason, duplicate_of=duplicate.id if duplicate else None, received_at=moment)
