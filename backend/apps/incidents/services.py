from mongoengine import NotUniqueError

from apps.services import services as service_domain
from apps.shared.documents import now_utc
from apps.shared.domain import SEVERITIES, identifier, integer, invalid, require, utc
from apps.shared.errors import AppError
from apps.shared.workflows import snapshot
from apps.users import services as users

from . import repository
from .models import Incident, Note, TimelineEntry
from .schema import validate_create, validate_escalation, validate_note, validate_resolution


def get(incident_id):
    return require(repository.find(identifier(incident_id, "incidentId")), "incident")


def mutable(incident_id, actor_id, at=None):
    incident = get(incident_id)
    actor = users.get(actor_id)
    if incident.status == "RESOLVED":
        raise AppError(409, "INCIDENT_RESOLVED", "Resolved incidents are read-only.")
    moment = utc(at or now_utc())
    if moment < utc(incident.created_at) or incident.timeline and moment < utc(incident.timeline[-1].at):
        invalid("timestamp", "Actions cannot predate the latest incident activity.")
    return incident, actor.id, moment


def record(incident, kind, actor_id, moment, message, **details):
    incident.timeline.append(TimelineEntry(kind=kind, actor_id=actor_id, at=moment, message=message, details=details))
    incident.updated_at = moment


def persist(incident):
    if not repository.replace_active(incident):
        raise AppError(409, "INCIDENT_RESOLVED", "The incident is no longer editable.")
    return incident


def create(body, *, actor_id=None, origin="MANUAL", at=None, incident_id=None, reference=None):
    values = validate_create(body)
    service = service_domain.get(values["service_id"])
    if origin not in ("MANUAL", "EVENT"):
        invalid("origin", "Choose MANUAL or EVENT.")
    actor = users.get(actor_id).id if actor_id is not None else None
    if origin == "MANUAL" and actor is None:
        invalid("createdBy", "Manual incidents require a responder.")
    if values.get("assignee_id") is not None:
        users.get(values["assignee_id"])
    moment = utc(at or now_utc())
    incident = Incident(id=incident_id, reference=reference or repository.next_reference(), origin=origin, created_by=actor, workflow_run=snapshot(service.workflow_template), created_at=moment, updated_at=moment, **values)
    if not incident.severity:
        incident.severity = service.default_severity
    record(incident, "CREATED", actor, moment, f"Incident created from {origin.lower()} intake.", origin=origin)
    try:
        return repository.insert(incident)
    except NotUniqueError:
        raise AppError(409, "INCIDENT_REFERENCE_CONFLICT", "The incident reference is already in use. Retry creation.")


def assign(incident_id, assignee_id, actor_id, *, at=None):
    incident, actor, moment = mutable(incident_id, actor_id, at)
    assignee = users.get(assignee_id).id if assignee_id is not None else None
    previous = incident.assignee_id
    incident.assignee_id = assignee
    record(incident, "ASSIGNED", actor, moment, "Incident assignment updated.", previousAssigneeId=previous, assigneeId=assignee)
    return persist(incident)


def claim(incident_id, actor_id, *, at=None):
    incident, actor, moment = mutable(incident_id, actor_id, at)
    if incident.assignee_id is not None:
        raise AppError(409, "ALREADY_ASSIGNED", "Only an unassigned incident may be claimed.")
    incident.assignee_id = actor
    record(incident, "CLAIMED", actor, moment, "Responder claimed the incident.", assigneeId=actor)
    return persist(incident)


def acknowledge(incident_id, actor_id, *, at=None):
    incident, actor, moment = mutable(incident_id, actor_id, at)
    if incident.status != "TRIGGERED":
        raise AppError(409, "INVALID_TRANSITION", "Only triggered incidents can be acknowledged.")
    incident.status = "ACKNOWLEDGED"
    incident.acknowledged_by = actor
    incident.acknowledged_at = moment
    record(incident, "ACKNOWLEDGED", actor, moment, "Responder acknowledged the incident.")
    return persist(incident)


def complete_step(incident_id, order, actor_id, *, completed=True, at=None):
    incident, actor, moment = mutable(incident_id, actor_id, at)
    order = integer(order, "order", 1, len(incident.workflow_run))
    if not isinstance(completed, bool):
        invalid("completed", "Provide a boolean.")
    step = incident.workflow_run[order - 1]
    if step.completed == completed:
        raise AppError(409, "STEP_UNCHANGED", "The step already has that completion state.")
    if completed and any(not previous.completed for previous in incident.workflow_run[:order - 1]):
        raise AppError(409, "WORKFLOW_ORDER", "Complete earlier workflow steps first.")
    if not completed and any(later.completed for later in incident.workflow_run[order:]):
        raise AppError(409, "WORKFLOW_ORDER", "Reopen later workflow steps first.")
    step.completed = completed
    step.completed_by = actor if completed else None
    step.completed_at = moment if completed else None
    kind = "STEP_COMPLETED" if completed else "STEP_REOPENED"
    record(incident, kind, actor, moment, f"{step.title}: {'completed' if completed else 'reopened'}.", order=order)
    return persist(incident)


def add_note(incident_id, body, actor_id, *, at=None):
    message = validate_note(body)
    incident, actor, moment = mutable(incident_id, actor_id, at)
    incident.notes.append(Note(body=message, author_id=actor, created_at=moment))
    record(incident, "NOTE_ADDED", actor, moment, message)
    return persist(incident)


def escalate(incident_id, body, actor_id, *, at=None):
    values = validate_escalation(body)
    incident, actor, moment = mutable(incident_id, actor_id, at)
    if SEVERITIES.index(values["severity"]) <= SEVERITIES.index(incident.severity):
        raise AppError(409, "SEVERITY_NOT_INCREASED", "Escalation must increase severity.")
    previous_severity, previous_assignee = incident.severity, incident.assignee_id
    incident.severity = values["severity"]
    if "assignee_id" in values:
        incident.assignee_id = users.get(values["assignee_id"]).id
    record(incident, "ESCALATED", actor, moment, values["reason"], previousSeverity=previous_severity, severity=incident.severity, previousAssigneeId=previous_assignee, assigneeId=incident.assignee_id)
    return persist(incident)


def resolve(incident_id, body, actor_id, *, at=None):
    note = validate_resolution(body)
    incident, actor, moment = mutable(incident_id, actor_id, at)
    if incident.status != "ACKNOWLEDGED":
        raise AppError(409, "INVALID_TRANSITION", "Acknowledge the incident before resolution.")
    if any(step.required and not step.completed for step in incident.workflow_run):
        raise AppError(409, "REQUIRED_STEPS_INCOMPLETE", "Complete all required workflow steps before resolution.")
    incident.status = "RESOLVED"
    incident.resolved_by = actor
    incident.resolved_at = moment
    incident.resolution_note = note
    record(incident, "RESOLVED", actor, moment, note)
    return persist(incident)


def attach_event(incident_id, event_id, disposition, *, at):
    incident = get(incident_id)
    if event_id in incident.event_ids:
        return incident
    if incident.status == "RESOLVED":
        raise AppError(409, "INCIDENT_RESOLVED", "Resolved incidents cannot receive new events.")
    if utc(at) < utc(incident.timeline[-1].at):
        invalid("receivedAt", "Events cannot predate the latest incident activity.")
    incident.event_ids.append(event_id)
    record(incident, "EVENT_RECEIVED", None, at, f"Event processed: {disposition}.", eventId=event_id, disposition=disposition)
    return persist(incident)
