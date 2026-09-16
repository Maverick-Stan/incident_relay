import os
from datetime import date, datetime, time, timedelta, timezone

import bcrypt
from bson import ObjectId
from mongoengine.connection import get_db

from apps.events import services as events
from apps.events.models import Event
from apps.incidents import services as incidents
from apps.incidents.models import Incident
from apps.services import services as services
from apps.services.models import Service
from apps.shared.domain import utc
from apps.users import repository as users
from apps.users.models import User
from apps.users.schema import validate_user

from .seed_data import DEMO_KEYS, DEMO_PASSWORD, DEMO_PASSWORD_SALT, HISTORY, SERVICE_ROWS, USER_ROWS

PRODUCT_COLLECTIONS = {"users", "services", "events", "incidents"}
LEGACY_COLLECTIONS = {"people", "workspaceaccounts", "calendars"}
EXPECTED_COUNTS = {"users": 5, "services": 4, "events": 19, "incidents": 17}


def seed_id(kind, number):
    return ObjectId(f"{kind:02x}{number:022x}")


def anchor():
    day = date.fromisoformat(os.environ.get("DEMO_TODAY", "2026-09-15"))
    return datetime.combine(day, time(12), tzinfo=timezone.utc)


def reset_collections():
    database = get_db()
    unexpected = set(database.list_collection_names()) - PRODUCT_COLLECTIONS - LEGACY_COLLECTIONS
    if unexpected:
        raise RuntimeError("Refusing to reset a database containing unrelated collections: " + ", ".join(sorted(unexpected)))
    for model in (Event, Incident, Service, User):
        model.drop_collection()
    for name in LEGACY_COLLECTIONS:
        database.drop_collection(name)


def seed_users(moment):
    ids = [seed_id(1, index) for index in range(1, len(USER_ROWS) + 1)]
    password_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), DEMO_PASSWORD_SALT).decode()
    for index, row in enumerate(USER_ROWS):
        values = validate_user({**row, "password": DEMO_PASSWORD, "allowedProfileIds": [str(value) for value in ids]})
        values.pop("password")
        users.insert(User(id=ids[index], **values, password_hash=password_hash, sort_order=index, created_at=moment, updated_at=moment))
    return ids


def seed_services(user_ids, moment):
    result = []
    for index, row in enumerate(SERVICE_ROWS):
        service, _ = services.create({**row, "ownerId": str(user_ids[index])}, service_id=seed_id(2, index + 1), at=moment, demo_key=DEMO_KEYS[index])
        result.append(service)
    return result


def event_body(number, title, severity, component, slot=0):
    return {
        "source": "demo-monitor",
        "sourceEventId": f"incident-{number}-delivery-{slot}",
        "title": title,
        "severity": severity,
        "labels": {"component": component, "alertType": "latency" if number == 104 else "availability"},
        "payload": {"latencyMs": 1240} if number == 104 else {"check": "service-health", "failureCount": 3},
    }


def seed_events(incident, service, number, moment, *, grouped=False, duplicate=False):
    body = event_body(number, incident.title, incident.severity, service.name)
    first, _ = events.record(service.id, body, incident.id, "CREATED_INCIDENT", f"Created {incident.reference}: no active incident matched this service and grouping key.", received_at=moment, event_id=seed_id(4, number * 10))
    if grouped:
        related = {**body, "sourceEventId": f"incident-{number}-delivery-1", "title": incident.title + " on replica", "payload": {**body["payload"], "node": "replica-2"}}
        events.record(service.id, related, incident.id, "GROUPED", f"Grouped into {incident.reference}: the service and grouping key matched an active incident created 2 minutes ago; the fingerprint differed.", received_at=moment + timedelta(minutes=2), event_id=seed_id(4, number * 10 + 1))
    if duplicate:
        repeated = {**body, "sourceEventId": f"incident-{number}-delivery-2"}
        events.record(service.id, repeated, incident.id, "SUPPRESSED_DUPLICATE", f"Suppressed duplicate for {incident.reference}: the exact fingerprint matched its first event within the 30-minute window.", duplicate_of=first.id, received_at=moment + timedelta(minutes=4), event_id=seed_id(4, number * 10 + 2))


def seed_history(service_rows, user_ids, base):
    for index, row in enumerate(HISTORY):
        number = 100 + index
        service = service_rows[row["service"]]
        actor = user_ids[index % len(user_ids)]
        moment = base - timedelta(days=18 - index, hours=3)
        story = number == 104
        if story:
            moment = base - timedelta(days=3, hours=3)
        origin = "MANUAL" if index % 3 == 0 else "EVENT"
        incident = incidents.create({"serviceId": str(service.id), "title": row["title"], "description": row["description"], "severity": row["severity"]}, actor_id=actor if origin == "MANUAL" else None, origin=origin, at=moment, incident_id=seed_id(3, number), reference=f"INC-{number}")
        if origin == "EVENT":
            seed_events(incident, service, number, moment, grouped=story or index in (1, 7, 13), duplicate=story or index in (2, 8, 14))
        incidents.claim(incident.id, actor, at=moment + timedelta(minutes=5))
        acknowledged_minutes = 6 + index % 5
        incidents.acknowledge(incident.id, actor, at=moment + timedelta(minutes=acknowledged_minutes))
        if index == 7:
            incidents.escalate(incident.id, {"severity": "HIGH", "reason": "Error rate increased across both payment regions.", "assigneeId": str(user_ids[1])}, actor, at=moment + timedelta(minutes=acknowledged_minutes + 1))
            actor = user_ids[1]
        for step in incident.workflow_run:
            incidents.complete_step(incident.id, step.order, actor, at=moment + timedelta(minutes=acknowledged_minutes + step.order * 4))
        incidents.add_note(incident.id, {"body": row["note"]}, actor, at=moment + timedelta(minutes=acknowledged_minutes + 10))
        incidents.resolve(incident.id, {"resolutionNote": row["resolution"]}, actor, at=moment + timedelta(minutes=30 if story else 25 + index * 3))


def seed_active(service_rows, user_ids, base):
    triggered = incidents.create({"serviceId": str(service_rows[0].id), "title": "Checkout database latency has recurred", "severity": "CRITICAL"}, origin="EVENT", at=base - timedelta(minutes=20), incident_id=seed_id(3, 115), reference="INC-115")
    seed_events(triggered, service_rows[0], 115, base - timedelta(minutes=20))
    active = incidents.create({"serviceId": str(service_rows[2].id), "title": "Identity token refresh errors", "description": "A subset of refresh requests fail after the morning deployment.", "severity": "HIGH"}, actor_id=user_ids[2], at=base - timedelta(minutes=60), incident_id=seed_id(3, 116), reference="INC-116")
    incidents.claim(active.id, user_ids[2], at=base - timedelta(minutes=58))
    incidents.acknowledge(active.id, user_ids[2], at=base - timedelta(minutes=55))
    incidents.complete_step(active.id, 1, user_ids[2], at=base - timedelta(minutes=45))
    incidents.add_note(active.id, {"body": "The new token validator is isolated as the likely cause; rollback is being reviewed."}, user_ids[2], at=base - timedelta(minutes=40))


def assert_seed():
    database = get_db()
    names = set(database.list_collection_names())
    if names != PRODUCT_COLLECTIONS:
        raise AssertionError(f"Unexpected collections: {sorted(names)}")
    counts = {name: database[name].count_documents({}) for name in sorted(names)}
    if counts != EXPECTED_COUNTS:
        raise AssertionError(f"Unexpected seed counts: {counts}")
    user_ids = set(User.objects.scalar("id"))
    for user in User.objects:
        user.validate()
        assert set(user.allowed_profile_ids) <= user_ids
    service_ids = set(Service.objects.scalar("id"))
    for service in Service.objects:
        service.validate()
        assert service.owner_id in user_ids
        assert "integrationKey" not in service.to_mongo()
    for incident in Incident.objects:
        incident.validate()
        assert incident.service_id in service_ids
        actors = [incident.created_by, incident.assignee_id, incident.acknowledged_by, incident.resolved_by]
        actors += [step.completed_by for step in incident.workflow_run] + [note.author_id for note in incident.notes] + [entry.actor_id for entry in incident.timeline]
        assert all(actor is None or actor in user_ids for actor in actors)
        linked = list(Event.objects(incident_id=incident.id))
        assert set(incident.event_ids) == {event.id for event in linked}
        for event in linked:
            event.validate()
            assert event.service_id == incident.service_id
            assert utc(event.received_at) >= utc(incident.created_at)
        if incident.resolved_at:
            assert all(utc(entry.at) <= utc(incident.resolved_at) for entry in incident.timeline)
            assert all(not step.completed_at or utc(step.completed_at) <= utc(incident.resolved_at) for step in incident.workflow_run)
    story = Incident.objects.get(reference="INC-104")
    assert story.status == "RESOLVED" and len(story.notes) == 1
    assert [event.disposition for event in Event.objects(incident_id=story.id).order_by("received_at")] == ["CREATED_INCIDENT", "GROUPED", "SUPPRESSED_DUPLICATE"]
    assert (utc(story.acknowledged_at) - utc(story.created_at)).total_seconds() == 600
    assert (utc(story.resolved_at) - utc(story.created_at)).total_seconds() == 1800
    assert Incident.objects(status="RESOLVED").count() == 15
    assert Incident.objects(status="TRIGGERED").count() == 1
    assert Incident.objects(status="ACKNOWLEDGED").count() == 1
    return counts


def seed():
    base = anchor()
    reset_collections()
    user_ids = seed_users(base - timedelta(days=30))
    service_rows = seed_services(user_ids, base - timedelta(days=25))
    seed_history(service_rows, user_ids, base)
    seed_active(service_rows, user_ids, base)
    counts = assert_seed()
    print(f"Incident Relay seed verified; anchor: {base.isoformat()}")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    print("Checkout story INC-104: resolved; 3 events, 2 completed workflow steps, 1 note.")
    return counts
