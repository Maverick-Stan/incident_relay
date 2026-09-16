from django.urls import path
from . import views

urlpatterns = [
    path("services", views.collection),
    path("services/<str:service_id>", views.detail),
]
