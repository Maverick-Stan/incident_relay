from bson import ObjectId
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.shared.authentication import require_profile_context, require_workspace_auth

from . import repository, services
from .schema import validate_assignment


def oid(value):
    return str(value) if value else None


def clean(details):
    # Timeline details hold ObjectId references that must render as strings for the client.
    return {key: (str(value) if isinstance(value, ObjectId) else value) for key, value in (details or {}).items()}


def summarize(incident):
    return {
        "_id": str(incident.id), "reference": incident.reference, "serviceId": str(incident.service_id),
        "origin": incident.origin, "title": incident.title, "severity": incident.severity, "status": incident.status,
        "assigneeId": oid(incident.assignee_id), "createdBy": oid(incident.created_by),
        "createdAt": incident.created_at, "updatedAt": incident.updated_at,
        "acknowledgedAt": incident.acknowledged_at, "resolvedAt": incident.resolved_at,
        "eventCount": len(incident.event_ids), "noteCount": len(incident.notes),
        "openRequiredSteps": sum(1 for step in incident.workflow_run if step.required and not step.completed),
    }


def serialize(incident):
    return {
        **summarize(incident),
        "description": incident.description,
        "acknowledgedBy": oid(incident.acknowledged_by),
        "resolvedBy": oid(incident.resolved_by), "resolutionNote": incident.resolution_note,
        "eventIds": [str(value) for value in incident.event_ids],
        "workflowRun": [{"order": step.order, "title": step.title, "instructions": step.instructions,
            "required": step.required, "completed": step.completed, "completedBy": oid(step.completed_by),
            "completedAt": step.completed_at} for step in incident.workflow_run],
        "notes": [{"body": note.body, "authorId": oid(note.author_id), "createdAt": note.created_at} for note in incident.notes],
        "timeline": [{"kind": entry.kind, "actorId": oid(entry.actor_id), "at": entry.at, "message": entry.message,
            "details": clean(entry.details)} for entry in incident.timeline],
    }


def envelope(data, status=200):
    response = Response({"data": data}, status=status)
    response["Cache-Control"] = "no-store"
    return response


def detail_response(incident, status=200):
    return envelope(serialize(incident), status)


@api_view(["GET", "POST"])
@require_workspace_auth
@require_profile_context
def collection(request):
    if request.method == "POST":
        return detail_response(services.create(request.data, actor_id=request.profile_id, origin="MANUAL"), 201)
    return envelope([summarize(incident) for incident in repository.list_incidents()])


@api_view(["GET"])
@require_workspace_auth
@require_profile_context
def detail(request, incident_id):
    return detail_response(services.get(incident_id))


@api_view(["POST"])
@require_workspace_auth
@require_profile_context
def claim(request, incident_id):
    return detail_response(services.claim(incident_id, request.profile_id))


@api_view(["POST"])
@require_workspace_auth
@require_profile_context
def assign(request, incident_id):
    return detail_response(services.assign(incident_id, validate_assignment(request.data), request.profile_id))


@api_view(["POST"])
@require_workspace_auth
@require_profile_context
def acknowledge(request, incident_id):
    return detail_response(services.acknowledge(incident_id, request.profile_id))


@api_view(["POST"])
@require_workspace_auth
@require_profile_context
def notes(request, incident_id):
    return detail_response(services.add_note(incident_id, request.data, request.profile_id), 201)


@api_view(["POST"])
@require_workspace_auth
@require_profile_context
def escalate(request, incident_id):
    return detail_response(services.escalate(incident_id, request.data, request.profile_id))


@api_view(["POST"])
@require_workspace_auth
@require_profile_context
def resolve(request, incident_id):
    return detail_response(services.resolve(incident_id, request.data, request.profile_id))


@api_view(["POST"])
@require_workspace_auth
@require_profile_context
def step(request, incident_id, order):
    body = request.data if isinstance(request.data, dict) else {}
    return detail_response(services.complete_step(incident_id, order, request.profile_id, completed=body.get("completed", True)))
