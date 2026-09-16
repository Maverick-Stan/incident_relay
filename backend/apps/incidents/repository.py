from .models import Incident


def find(incident_id):
    return Incident.objects(id=incident_id).first()


def list_incidents():
    return list(Incident.objects.order_by("-created_at", "reference"))


def active_in_window(service_id, since, until):
    return list(Incident.objects(service_id=service_id, status__in=("TRIGGERED", "ACKNOWLEDGED"), created_at__gte=since, created_at__lte=until).order_by("-created_at", "-id"))


def exists_for_service(service_id):
    return Incident.objects(service_id=service_id).first() is not None


def next_reference():
    numbers = [int(row.reference.split("-")[1]) for row in Incident.objects.only("reference")]
    return f"INC-{max(numbers, default=100) + 1}"


def insert(incident):
    incident.validate()
    Incident.objects.insert(incident)
    return incident


def replace_active(incident):
    incident.validate()
    result = Incident._get_collection().replace_one({"_id": incident.id, "status": {"$ne": "RESOLVED"}}, incident.to_mongo())
    return result.matched_count == 1
