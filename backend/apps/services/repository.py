from .models import Service


def find(service_id):
    return Service.objects(id=service_id).first()


def find_by_key_hash(key_hash):
    return Service.objects(integration_key_hash=key_hash).first()


def list_services():
    return list(Service.objects.order_by("name", "id"))


def insert(service):
    service.validate()
    Service.objects.insert(service)
    return service


def replace(service):
    service.validate()
    Service._get_collection().replace_one({"_id": service.id}, service.to_mongo())
    return service


def remove(service_id):
    return Service.objects(id=service_id).delete()
