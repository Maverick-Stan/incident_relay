from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.shared.authentication import require_profile_context, require_workspace_auth
from . import repository, services


def serialize(service):
    return {
        "_id": str(service.id), "name": service.name, "description": service.description,
        "ownerId": str(service.owner_id), "defaultSeverity": service.default_severity,
        "groupingWindowMinutes": service.grouping_window_minutes,
        "integrationKeyLastFour": service.integration_key_last_four,
        "workflowTemplate": [dict(title=s.title, instructions=s.instructions, order=s.order, required=s.required) for s in service.workflow_template],
        "createdAt": service.created_at.isoformat(), "updatedAt": service.updated_at.isoformat(),
    }


def response(data, status=200):
    result = Response({"data": data}, status=status)
    result["Cache-Control"] = "no-store"
    return result


@api_view(["GET", "POST"])
@require_workspace_auth
@require_profile_context
def collection(request):
    if request.method == "GET":
        return response([serialize(service) for service in repository.list_services()])
    service, key = services.create(request.data)
    return response({"service": serialize(service), "integrationKey": key}, 201)


@api_view(["GET", "PATCH", "DELETE"])
@require_workspace_auth
@require_profile_context
def detail(request, service_id):
    if request.method == "DELETE":
        services.remove(service_id)
        return Response(status=204)
    service = services.update(service_id, request.data) if request.method == "PATCH" else services.get(service_id)
    return response(serialize(service))
