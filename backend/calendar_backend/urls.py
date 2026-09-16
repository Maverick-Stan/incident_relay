from pathlib import Path

from django.http import FileResponse
from django.urls import include, path, re_path
from rest_framework.decorators import api_view

from apps.shared.authentication import require_profile_context, require_workspace_auth
from apps.shared.views import health, not_found, route_not_found

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


def landing_page(request):
    return FileResponse(open(PUBLIC_DIR / "index.html", "rb"), content_type="text/html")


def favicon(request):
    return FileResponse(open(PUBLIC_DIR / "favicon.svg", "rb"), content_type="image/svg+xml")


@api_view(["GET", "POST", "PATCH", "PUT", "DELETE"])
@require_workspace_auth
@require_profile_context
def unknown_api_route(request, path):
    return route_not_found(request)


urlpatterns = [
    path("", landing_page),
    path("favicon.svg", favicon),
    path("api/v1/health", health),
    path("api/v1/", include("apps.auth.urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.services.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/", include("apps.incidents.urls")),
    path("api/v1/", include("apps.analytics.urls")),
    re_path(r"^api/v1/(?P<path>.*)$", unknown_api_route),
    re_path(r"^.*$", not_found),
]
