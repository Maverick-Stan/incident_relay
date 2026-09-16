from django.urls import path
from . import views

urlpatterns = [
    path("events", views.ingest),
    path("services/<str:service_id>/events", views.service_events),
]
