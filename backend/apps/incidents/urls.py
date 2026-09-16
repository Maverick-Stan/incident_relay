from django.urls import path
from . import views

urlpatterns = [
    path("incidents", views.collection),
    path("incidents/<str:incident_id>", views.detail),
    path("incidents/<str:incident_id>/claim", views.claim),
    path("incidents/<str:incident_id>/assign", views.assign),
    path("incidents/<str:incident_id>/acknowledge", views.acknowledge),
    path("incidents/<str:incident_id>/notes", views.notes),
    path("incidents/<str:incident_id>/escalate", views.escalate),
    path("incidents/<str:incident_id>/resolve", views.resolve),
    path("incidents/<str:incident_id>/steps/<int:order>", views.step),
]
