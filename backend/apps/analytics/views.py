from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.shared.authentication import require_profile_context, require_workspace_auth
from apps.shared.domain import invalid

from . import services


@api_view(["GET"])
@require_workspace_auth
@require_profile_context
def summary(request):
    since = services.parse_bound(request.query_params.get("since"), "since")
    until = services.parse_bound(request.query_params.get("until"), "until")
    if since is not None and until is not None and since > until:
        invalid("until", "The end of the window cannot precede its start.")
    response = Response({"data": services.compute(since, until)})
    response["Cache-Control"] = "no-store"
    return response
