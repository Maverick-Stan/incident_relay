from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.incidents import services as incidents
from apps.services import services as service_domain
from apps.shared.authentication import require_profile_context, require_workspace_auth
from apps.shared.domain import identifier, invalid
from apps.shared.errors import AppError
from . import repository, services


def serialize(event):
    incident = incidents.get(event.incident_id)
    return {
        "_id": str(event.id), "serviceId": str(event.service_id), "source": event.source,
        "sourceEventId": event.source_event_id, "normalizedTitle": event.normalized_title,
        "normalizedSeverity": event.normalized_severity, "rawPayload": event.raw_payload,
        "receivedAt": event.received_at, "disposition": event.disposition,
        "reason": event.triage_decision.reason,
        "duplicateOfEventId": str(event.duplicate_of_event_id) if event.duplicate_of_event_id else None,
        "incident": {"_id": str(incident.id), "reference": incident.reference, "href": f"/#incidents/{incident.id}"},
        "triageDecision": {"rule": event.triage_decision.rule, "reason": event.triage_decision.reason,
            "matchedIncidentId": str(event.triage_decision.matched_incident_id) if event.triage_decision.matched_incident_id else None,
            "matchedEventId": str(event.triage_decision.matched_event_id) if event.triage_decision.matched_event_id else None,
            "decidedAt": event.triage_decision.decided_at},
    }


def result(data, status=200):
    response = Response({"data": data}, status=status)
    response["Cache-Control"] = "no-store"
    return response


def intake(request, service_id=None):
    service = service_domain.authenticate_key(request.headers.get("X-Integration-Key"))
    if service_id is not None and service.id != identifier(service_id, "serviceId"):
        raise AppError(403, "INTEGRATION_SERVICE_MISMATCH", "This integration key belongs to a different service.")
    event, created = services.ingest(service, request.data)
    return result({"event": serialize(event), "idempotentReplay": not created}, 201 if created else 200)


@api_view(["POST"])
def ingest(request):
    return intake(request)


@require_workspace_auth
@require_profile_context
def history(request, service_id):
    service = service_domain.get(service_id)
    try:
        offset = int(request.query_params.get("offset", "0"))
        if offset < 0:
            raise ValueError()
    except ValueError:
        invalid("offset", "Use a nonnegative integer offset.")
    rows, total = repository.for_service(service.id, offset=offset)
    return result({"items": [serialize(event) for event in rows], "total": total, "nextOffset": offset + len(rows) if offset + len(rows) < total else None})


@api_view(["GET", "POST"])
def service_events(request, service_id):
    # Public POST uses only the integration key; history requires the signed-in profile.
    return intake(request, service_id) if request.method == "POST" else history(request, service_id)
