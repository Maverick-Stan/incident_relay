from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.shared.authentication import require_workspace_auth

from . import services


@api_view(["GET"])
@require_workspace_auth
def list_profiles(request):
    return Response({"data": services.list_profiles(request.account.get("allowedProfileIds"))})
