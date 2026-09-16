import contextlib
import io
import json
import os
import unittest
from datetime import timedelta

from bson import ObjectId, json_util
from django.conf import settings
from django.test import Client
from mongoengine import ValidationError, connect, disconnect
from mongoengine.connection import get_db
from pymongo.errors import DuplicateKeyError
from pymongo.uri_parser import parse_uri

from apps.events import repository as event_repository, services as events
from apps.events.models import Event
from apps.incidents import repository as incident_repository, services as incidents
from apps.incidents.models import Incident
from apps.services import services
from apps.services.models import Service
from apps.shared.domain import SEVERITIES, utc
from apps.shared.errors import AppError
from apps.users.models import User
from scripts.domain_seed import EXPECTED_COUNTS, PRODUCT_COLLECTIONS, anchor, assert_seed, seed, seed_id
from scripts.seed_data import DEMO_KEYS


class DomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_uri = os.environ.get("MONGODB_TEST_URI", "mongodb://127.0.0.1:27017/incident_relay_test")
        test_name = parse_uri(cls.test_uri)["database"]
        app_name = parse_uri(settings.MONGODB_URI)["database"]
        if not test_name or not test_name.endswith("_test") or test_name == app_name:
            raise RuntimeError("Use a separate MongoDB test database with a name ending in _test.")
        disconnect()
        connect(host=cls.test_uri, uuidRepresentation="standard")
        get_db().command("ping")

    @classmethod
    def tearDownClass(cls):
        database = get_db()
        database.client.drop_database(database.name)
        disconnect()
        connect(host=settings.MONGODB_URI, uuidRepresentation="standard")

    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            seed()
        self.actor = seed_id(1, 1)
        self.base = anchor()
        self.checkout = seed_id(2, 1)

    def at(self, minute):
        return self.base + timedelta(minutes=minute)

    def create_incident(self):
        return incidents.create({"serviceId": str(self.checkout), "title": "Test response", "severity": "LOW"}, actor_id=self.actor, at=self.base)

    def payload(self, source_id="test-delivery"):
        return {"source": "test-monitor", "sourceEventId": source_id, "title": "Database latency", "severity": "HIGH", "labels": {"component": "database", "alertType": "latency"}, "payload": {"latencyMs": 1100}}

    def create_event_incident(self):
        return incidents.create({"serviceId": str(self.checkout), "title": "Database latency"}, origin="EVENT", at=self.base)

    def event(self, incident, payload=None, disposition="CREATED_INCIDENT", **kwargs):
        return events.record(self.checkout, payload or self.payload(), incident.id, disposition, "Verified internal foundation outcome.", received_at=self.at(1), **kwargs)

    def assert_error(self, status, function, *args, **kwargs):
        with self.assertRaises(AppError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.status_code, status)

    def test_seed_has_only_four_collections_and_connected_story(self):
        self.assertEqual(assert_seed(), EXPECTED_COUNTS)
        self.assertEqual(set(get_db().list_collection_names()), PRODUCT_COLLECTIONS)
        story = Incident.objects.get(reference="INC-104")
        self.assertEqual(story.service_id, self.checkout)
        self.assertEqual(story.status, "RESOLVED")
        self.assertTrue(all(step.completed for step in story.workflow_run))
        self.assertEqual([entry.kind for entry in story.timeline], ["CREATED", "EVENT_RECEIVED", "EVENT_RECEIVED", "EVENT_RECEIVED", "CLAIMED", "ACKNOWLEDGED", "STEP_COMPLETED", "STEP_COMPLETED", "NOTE_ADDED", "RESOLVED"])
        rows = list(Event.objects(incident_id=story.id).order_by("received_at"))
        self.assertEqual(rows[2].duplicate_of_event_id, rows[0].id)
        self.assertNotEqual(rows[1].fingerprint, rows[0].fingerprint)
        self.assertEqual(rows[2].fingerprint, rows[0].fingerprint)
        self.assertEqual(len({row.grouping_key for row in rows}), 1)

    def test_seed_is_identical_after_repeat_and_cleans_legacy_collections(self):
        def snapshot():
            return json_util.dumps({name: list(get_db()[name].find().sort("_id")) for name in sorted(PRODUCT_COLLECTIONS)}, sort_keys=True)
        before = snapshot()
        self.create_incident()
        for name in ("people", "workspaceaccounts", "calendars"):
            get_db()[name].insert_one({"legacy": True})
        with contextlib.redirect_stdout(io.StringIO()):
            seed()
        self.assertEqual(snapshot(), before)
        self.assertEqual(set(get_db().list_collection_names()), PRODUCT_COLLECTIONS)

    def test_history_is_ready_for_timestamp_analytics(self):
        resolved = list(Incident.objects(status="RESOLVED"))
        acknowledged = list(Incident.objects(acknowledged_at__ne=None))
        self.assertEqual(len(resolved), 15)
        self.assertEqual(len(acknowledged), 16)
        self.assertTrue(all(utc(row.resolved_at) > utc(row.acknowledged_at) >= utc(row.created_at) for row in resolved))
        self.assertEqual(Event.objects(disposition="GROUPED").count(), 4)
        self.assertEqual(Event.objects(disposition="SUPPRESSED_DUPLICATE").count(), 4)
        self.assertEqual(len({row.service_id for row in resolved}), 4)
        self.assertEqual(len({row.severity for row in resolved}), 4)
        self.assertEqual(len({row.resolved_by for row in resolved}), 5)

    def test_workspace_and_profile_authentication_use_users_without_secret_leaks(self):
        client = Client()
        self.assertEqual(client.get("/api/v1/profiles").status_code, 401)
        response = client.post("/api/v1/auth/login", data=json.dumps({"email": "alex.morgan@calendar.com", "password": "password123"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        result = response.json()["data"]
        self.assertEqual(result["account"]["_id"], str(self.actor))
        header = {"HTTP_AUTHORIZATION": "Bearer " + result["token"]}
        profiles = client.get("/api/v1/profiles", **header).json()["data"]
        self.assertEqual(len(profiles), 5)
        for profile in profiles:
            self.assertFalse({"passwordHash", "allowedProfileIds", "active"} & set(profile))
        switched = client.post("/api/v1/auth/switch-profile", data=json.dumps({"profileId": str(seed_id(1, 2))}), content_type="application/json", **header)
        self.assertEqual(switched.status_code, 200)
        profile_header = {"HTTP_AUTHORIZATION": "Bearer " + switched.json()["data"]["token"]}
        self.assertEqual(client.get("/api/v1/auth/session", **profile_header).status_code, 200)
        self.assertEqual(client.get("/api/v1/calendars", **profile_header).status_code, 404)
        self.assertEqual(client.post("/api/v1/auth/logout", **profile_header).status_code, 204)
        self.assertEqual(set(get_db().list_collection_names()), PRODUCT_COLLECTIONS)

    def test_authentication_rejects_wrong_password_and_disallowed_profile(self):
        client = Client()
        path = "/api/v1/auth/login"
        wrong = client.post(path, data=json.dumps({"email": "alex.morgan@calendar.com", "password": "wrong"}), content_type="application/json")
        self.assertEqual(wrong.status_code, 401)
        login = client.post(path, data=json.dumps({"email": "alex.morgan@calendar.com", "password": "password123"}), content_type="application/json").json()["data"]
        User.objects(id=self.actor).update(set__allowed_profile_ids=[self.actor])
        response = client.post("/api/v1/auth/switch-profile", data=json.dumps({"profileId": str(seed_id(1, 2))}), content_type="application/json", HTTP_AUTHORIZATION="Bearer " + login["token"])
        self.assertEqual(response.status_code, 403)

    def test_service_keys_are_hashed_and_new_keys_are_unique(self):
        first, first_key = services.create({"name": "Test service", "ownerId": str(self.actor)})
        second, second_key = services.create({"name": "Another service", "ownerId": str(self.actor)})
        self.assertNotEqual(first_key, second_key)
        self.assertEqual(first.integration_key_hash, services.hash_key(first_key))
        self.assertEqual(first.integration_key_last_four, first_key[-4:])
        self.assertEqual(services.authenticate_key(first_key).id, first.id)
        self.assert_error(401, services.authenticate_key, "invalid")
        serialized = json_util.dumps(list(get_db().services.find()))
        self.assertNotIn(first_key, serialized)
        self.assertNotIn(second_key, serialized)
        for key in DEMO_KEYS:
            self.assertNotIn(key, serialized)

    def test_service_deletion_and_owner_guards(self):
        self.assert_error(409, services.remove, self.checkout)
        self.assert_error(404, services.create, {"name": "Unknown owner", "ownerId": str(ObjectId())})
        service, _ = services.create({"name": "Unused service", "ownerId": str(self.actor)})
        services.remove(service.id)
        self.assertIsNone(Service.objects(id=service.id).first())

    def test_service_validation_rejects_invalid_windows_and_workflows(self):
        for value in (0, 1441, True, "30", float("inf")):
            with self.subTest(value=value):
                self.assert_error(400, services.create, {"name": "Invalid", "ownerId": str(self.actor), "groupingWindowMinutes": value})
        self.assert_error(400, services.update, self.checkout, {"workflowTemplate": [{"title": "Step", "instructions": "Inspect", "order": 2}]})
        self.assert_error(400, services.update, self.checkout, {"defaultSeverity": "URGENT"})
        self.assert_error(400, services.update, self.checkout, {"integrationKeyHash": "injected"})

    def test_workflow_snapshot_is_independent_of_template_edits(self):
        incident = self.create_incident()
        title = incident.workflow_run[0].title
        services.update(self.checkout, {"workflowTemplate": [{"title": "New checklist", "instructions": "Perform the new procedure.", "order": 1}]})
        old = incidents.get(incident.id)
        self.assertEqual(old.workflow_run[0].title, title)
        self.assertEqual(len(old.workflow_run), 2)
        self.assertEqual(self.create_incident().workflow_run[0].title, "New checklist")

    def test_claim_does_not_acknowledge_and_assignment_requires_users(self):
        incident = self.create_incident()
        claimed = incidents.claim(incident.id, self.actor, at=self.at(1))
        self.assertEqual(claimed.status, "TRIGGERED")
        self.assertIsNone(claimed.acknowledged_at)
        self.assertEqual(claimed.assignee_id, self.actor)
        self.assert_error(409, incidents.claim, incident.id, seed_id(1, 2), at=self.at(2))
        self.assert_error(404, incidents.assign, incident.id, ObjectId(), self.actor, at=self.at(2))

    def test_resolution_requires_acknowledgment_required_steps_and_note(self):
        incident = self.create_incident()
        body = {"resolutionNote": "Recovered and verified."}
        self.assert_error(409, incidents.resolve, incident.id, body, self.actor, at=self.at(1))
        incidents.acknowledge(incident.id, self.actor, at=self.at(2))
        self.assert_error(409, incidents.resolve, incident.id, body, self.actor, at=self.at(3))
        self.assert_error(409, incidents.complete_step, incident.id, 2, self.actor, at=self.at(3))
        incidents.complete_step(incident.id, 1, self.actor, at=self.at(3))
        incidents.complete_step(incident.id, 2, self.actor, at=self.at(4))
        self.assert_error(400, incidents.resolve, incident.id, {"resolutionNote": " "}, self.actor, at=self.at(5))
        resolved = incidents.resolve(incident.id, body, self.actor, at=self.at(5))
        self.assertEqual(resolved.status, "RESOLVED")
        self.assertEqual(resolved.resolved_by, self.actor)

    def test_resolved_incident_is_immutable_for_all_domain_actions(self):
        incident = Incident.objects.get(reference="INC-104")
        before = incident.to_mongo().to_dict()
        calls = [
            (incidents.claim, (incident.id, self.actor), {}),
            (incidents.assign, (incident.id, self.actor, self.actor), {}),
            (incidents.acknowledge, (incident.id, self.actor), {}),
            (incidents.complete_step, (incident.id, 1, self.actor), {"completed": False}),
            (incidents.add_note, (incident.id, {"body": "Late note"}, self.actor), {}),
            (incidents.escalate, (incident.id, {"severity": "CRITICAL", "reason": "Late escalation"}, self.actor), {}),
            (incidents.resolve, (incident.id, {"resolutionNote": "Again"}, self.actor), {}),
        ]
        for function, args, kwargs in calls:
            with self.subTest(action=function.__name__):
                self.assert_error(409, function, *args, **kwargs)
        incident.title = "Bypass attempt"
        self.assertFalse(incident_repository.replace_active(incident))
        self.assertEqual(incidents.get(incident.id).to_mongo().to_dict(), before)

    def test_workflow_reopen_preserves_order_and_audit(self):
        incident = self.create_incident()
        incidents.complete_step(incident.id, 1, self.actor, at=self.at(1))
        incidents.complete_step(incident.id, 2, self.actor, at=self.at(2))
        self.assert_error(409, incidents.complete_step, incident.id, 1, self.actor, completed=False, at=self.at(3))
        incidents.complete_step(incident.id, 2, self.actor, completed=False, at=self.at(3))
        updated = incidents.complete_step(incident.id, 1, self.actor, completed=False, at=self.at(4))
        self.assertTrue(all(not step.completed and step.completed_by is None and step.completed_at is None for step in updated.workflow_run))
        self.assertEqual(updated.timeline[-1].kind, "STEP_REOPENED")

    def test_escalation_increases_severity_and_audits_assignment(self):
        incident = self.create_incident()
        self.assert_error(409, incidents.escalate, incident.id, {"severity": "LOW", "reason": "No increase"}, self.actor)
        updated = incidents.escalate(incident.id, {"severity": "HIGH", "reason": "Two regions are affected.", "assigneeId": str(seed_id(1, 2))}, self.actor, at=self.at(1))
        self.assertEqual(updated.severity, "HIGH")
        self.assertEqual(updated.status, "TRIGGERED")
        self.assertEqual(updated.timeline[-1].details["previousSeverity"], "LOW")
        self.assertEqual(updated.assignee_id, seed_id(1, 2))

    def test_actions_cannot_backdate_activity(self):
        incident = self.create_incident()
        incidents.acknowledge(incident.id, self.actor, at=self.at(2))
        self.assert_error(400, incidents.add_note, incident.id, {"body": "Backdated"}, self.actor, at=self.at(1))

    def test_delivery_retry_is_idempotent_even_after_resolution(self):
        original = Event.objects(source_event_id="incident-104-delivery-0").get()
        incident = incidents.get(original.incident_id)
        before = incident.to_mongo().to_dict()
        returned, created = events.record(original.service_id, original.raw_payload, incident.id, "CREATED_INCIDENT", "Retry")
        self.assertFalse(created)
        self.assertEqual(returned.id, original.id)
        self.assertEqual(Event.objects.count(), 19)
        self.assertEqual(incidents.get(incident.id).to_mongo().to_dict(), before)

    def test_unique_source_index_prevents_duplicate_documents(self):
        row = Event.objects.first().to_mongo().to_dict()
        row["_id"] = ObjectId()
        with self.assertRaises(DuplicateKeyError):
            get_db().events.insert_one(row)
        self.assertEqual(Event.objects.count(), 19)

    def test_recorded_event_is_immutable(self):
        event = Event.objects.first()
        event.raw_payload = {"changed": True}
        with self.assertRaises(ValidationError):
            event.save()
        self.assertNotEqual(event_repository.find(event.id).raw_payload, {"changed": True})

    def test_event_validation_rejects_invalid_or_oversized_payloads(self):
        incident = self.create_event_incident()
        invalid_bodies = [
            {**self.payload(), "severity": "URGENT"},
            {**self.payload(), "payload": {"blob": "x" * 32768}},
            {**self.payload(), "payload": {"metric": float("nan")}},
            {**self.payload(), "payload": {"$operator": "bad"}},
            {**self.payload(), "labels": {"Component": "db", "component": "db"}},
            {**self.payload(), "incidentId": str(incident.id)},
        ]
        for body in invalid_bodies:
            with self.subTest(body=str(body)[:60]):
                self.assert_error(400, self.event, incident, body)
        self.assertEqual(Event.objects.count(), 19)

    def test_event_outcomes_require_correct_service_window_and_fingerprint(self):
        incident = self.create_event_incident()
        first, _ = self.event(incident)
        wrong = {**self.payload("another"), "title": "Different fingerprint"}
        self.assert_error(400, self.event, incident, wrong, "SUPPRESSED_DUPLICATE", duplicate_of=first.id)
        self.assert_error(400, events.record, self.checkout, self.payload("late"), incident.id, "GROUPED", "Late event", received_at=self.at(31))
        other = incidents.create({"serviceId": str(seed_id(2, 2)), "title": "Another service"}, origin="EVENT", at=self.base)
        self.assert_error(400, self.event, other, self.payload("wrong-service"))
        self.assertEqual(Event.objects.count(), 20)

    def test_new_event_is_rejected_for_resolved_incident(self):
        story = Incident.objects.get(reference="INC-104")
        self.assert_error(409, self.event, story, self.payload("new-source-identity"))
        self.assertEqual(Event.objects.count(), 19)

    def test_valid_record_links_incident_and_preserves_raw_payload(self):
        incident = self.create_event_incident()
        body = self.payload()
        body["title"] = "  Database   LATENCY  "
        event, created = self.event(incident, body)
        self.assertTrue(created)
        self.assertEqual(event.raw_payload, body)
        self.assertEqual(event.normalized_title, "database latency")
        self.assertIn(event.id, incidents.get(incident.id).event_ids)
        self.assertEqual(incidents.get(incident.id).timeline[-1].details["eventId"], event.id)

    def test_model_rejects_impossible_resolved_state(self):
        incident = self.create_incident()
        incident.status = "RESOLVED"
        with self.assertRaises(ValidationError):
            incident.validate()

    def service_client(self):
        client = Client()
        login = client.post('/api/v1/auth/login', data=json.dumps({'email': 'alex.morgan@calendar.com', 'password': 'password123'}), content_type='application/json')
        self.assertEqual(login.status_code, 200)
        session = login.json()['data']['token']
        profile = client.post('/api/v1/auth/switch-profile', data=json.dumps({'profileId': str(self.actor)}), content_type='application/json', HTTP_AUTHORIZATION='Bearer ' + session)
        self.assertEqual(profile.status_code, 200)
        client.defaults['HTTP_AUTHORIZATION'] = 'Bearer ' + profile.json()['data']['token']
        return client

    def test_service_api_authentication_and_safe_directory(self):
        anonymous = Client()
        for method, path in [('get', '/api/v1/services'), ('post', '/api/v1/services'), ('get', '/api/v1/services/' + str(self.checkout)), ('patch', '/api/v1/services/' + str(self.checkout)), ('delete', '/api/v1/services/' + str(self.checkout))]:
            self.assertEqual(getattr(anonymous, method)(path).status_code, 401)
        session = anonymous.post('/api/v1/auth/login', data=json.dumps({'email': 'alex.morgan@calendar.com', 'password': 'password123'}), content_type='application/json').json()['data']['token']
        self.assertEqual(anonymous.get('/api/v1/services', HTTP_AUTHORIZATION='Bearer ' + session).status_code, 401)
        client = self.service_client()
        listing = client.get('/api/v1/services')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()['data']), 4)
        self.assertEqual(listing['Cache-Control'], 'no-store')
        self.assertNotIn('integrationKeyHash', listing.content.decode())
        detail = client.get('/api/v1/services/' + str(self.checkout))
        self.assertEqual(detail.json()['data']['name'], 'Checkout API')
        self.assertNotIn('integrationKeyHash', detail.content.decode())
        self.assertEqual(client.get('/api/v1/services/not-an-id').status_code, 400)
        self.assertEqual(client.get('/api/v1/services/' + str(ObjectId())).status_code, 404)

    def test_service_api_create_edit_key_once_and_delete(self):
        client = self.service_client()
        body = {'name': 'New API', 'description': 'Created through the UI API', 'ownerId': str(self.actor), 'defaultSeverity': 'LOW', 'groupingWindowMinutes': 12, 'workflowTemplate': [{'order': 1, 'title': 'Diagnose', 'instructions': 'Read logs', 'required': True}, {'order': 2, 'title': 'Recover', 'instructions': 'Verify recovery', 'required': False}]}
        response = client.post('/api/v1/services', data=json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Cache-Control'], 'no-store')
        result = response.json()['data']
        key = result['integrationKey']
        self.assertGreaterEqual(len(key), 43)
        service_id = result['service']['_id']
        path = '/api/v1/services/' + service_id
        stored = get_db().services.find_one({'_id': ObjectId(service_id)})
        self.assertEqual(stored['integrationKeyHash'], services.hash_key(key))
        self.assertEqual(stored['integrationKeyLastFour'], key[-4:])
        self.assertNotIn(key, json_util.dumps(stored))
        self.assertNotIn('integrationKeyHash', response.content.decode())
        body.update(name='Renamed API', ownerId=str(seed_id(1, 2)), defaultSeverity='CRITICAL', groupingWindowMinutes=45)
        body['workflowTemplate'].reverse()
        for index, row in enumerate(body['workflowTemplate'], 1):
            row['order'] = index
        updated = client.patch(path, data=json.dumps(body), content_type='application/json')
        self.assertEqual(updated.status_code, 200)
        for output in (updated, client.get(path), client.get('/api/v1/services')):
            self.assertNotIn(key, output.content.decode())
            self.assertNotIn('integrationKeyHash', output.content.decode())
        detail = client.get(path).json()['data']
        for field in body:
            self.assertEqual(detail[field], body[field])
        self.assertEqual(get_db().services.find_one({'_id': ObjectId(service_id)})['integrationKeyHash'], stored['integrationKeyHash'])
        self.assertEqual(client.delete(path).status_code, 204)
        self.assertEqual(client.get(path).status_code, 404)
        self.assertEqual(set(get_db().list_collection_names()), PRODUCT_COLLECTIONS)

    def test_service_api_validation_conflict_and_snapshot_preservation(self):
        client = self.service_client()
        path = '/api/v1/services/' + str(self.checkout)
        before = Incident.objects(reference='INC-104').first().workflow_run[0].title
        invalid_bodies = [{'groupingWindowMinutes': 0}, {'groupingWindowMinutes': 1.5}, {'groupingWindowMinutes': True}, {'defaultSeverity': 'URGENT'}, {'name': '  '}, {'ownerId': 'invalid'}, {'integrationKeyHash': 'forbidden'}, {'workflowTemplate': [{'title': 'Bad', 'instructions': 'Bad', 'order': 2}]}, {'workflowTemplate': [{'title': 'Bad', 'instructions': 'Bad', 'required': 'yes'}]}, {}]
        for body in invalid_bodies:
            response = client.patch(path, data=json.dumps(body), content_type='application/json')
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json()['error']['code'], 'VALIDATION_ERROR')
            self.assertTrue(response.json()['error']['details']['fieldErrors'])
        self.assertEqual(client.post('/api/v1/services', data='[]', content_type='application/json').status_code, 400)
        self.assertEqual(client.post('/api/v1/services', data='{', content_type='application/json').status_code, 400)
        missing = client.patch(path, data=json.dumps({'ownerId': str(ObjectId())}), content_type='application/json')
        self.assertEqual(missing.status_code, 404)
        response = client.patch(path, data=json.dumps({'workflowTemplate': [{'title': 'New template', 'instructions': 'New instructions', 'required': True, 'order': 1}]}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Incident.objects(reference='INC-104').first().workflow_run[0].title, before)
        conflict = client.delete(path)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()['error']['code'], 'SERVICE_IN_USE')
        self.assertEqual(client.get(path).status_code, 200)
        # Each relationship independently blocks deletion, even if the other is absent.
        Event.objects(service_id=self.checkout).delete()
        self.assertEqual(client.delete(path).status_code, 409)
        Incident.objects(service_id=self.checkout).delete()
        self.assertEqual(client.delete(path).status_code, 204)

    def test_service_api_empty_directory(self):
        client = self.service_client()
        Event.objects.delete()
        Incident.objects.delete()
        Service.objects.delete()
        response = client.get('/api/v1/services')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'data': []})

    def intake_fixture(self):
        service, key = services.create({'name': 'Intake test service', 'ownerId': str(self.actor)})
        body = {'source': 'monitor', 'sourceEventId': 'delivery-1', 'title': ' Database   Latency ', 'severity': 'HIGH', 'labels': {'Component': ' Database ', 'AlertType': 'Latency'}, 'payload': {'latencyMs': 1200}}
        return service, key, body

    def post_event(self, key, body, path='/api/v1/events', expected=201):
        response = Client().post(path, data=json.dumps(body), content_type='application/json', HTTP_X_INTEGRATION_KEY=key)
        self.assertEqual(response.status_code, expected, response.content)
        return response.json()['data']

    def test_intake_api_all_outcomes_and_retry_before_triage(self):
        from unittest.mock import patch
        service, key, body = self.intake_fixture()
        first = self.post_event(key, body)
        self.assertEqual(first['event']['disposition'], 'CREATED_INCIDENT')
        self.assertEqual(first['event']['normalizedTitle'], 'database latency')
        self.assertEqual(first['event']['rawPayload'], body)
        grouped = self.post_event(key, {**body, 'sourceEventId': 'delivery-2', 'payload': {'latencyMs': 1500}})
        self.assertEqual(grouped['event']['disposition'], 'GROUPED')
        duplicate = self.post_event(key, {**body, 'sourceEventId': 'delivery-3', 'title': 'database latency', 'labels': {'component': 'database', 'alerttype': 'latency'}})
        self.assertEqual(duplicate['event']['disposition'], 'SUPPRESSED_DUPLICATE')
        self.assertEqual(duplicate['event']['duplicateOfEventId'], first['event']['_id'])
        for output in (first, grouped, duplicate):
            self.assertFalse(output['idempotentReplay'])
            self.assertEqual(output['event']['incident']['_id'], first['event']['incident']['_id'])
            self.assertIn(first['event']['incident']['reference'], output['event']['reason'])
            self.assertEqual(output['event']['reason'], output['event']['triageDecision']['reason'])
        before = json_util.dumps(list(get_db().incidents.find({'serviceId':service.id})))
        with patch('apps.events.services.normalize', side_effect=AssertionError('Retry must not run triage normalization')):
            retry = self.post_event(key, {**body, 'payload': {'changedButSameDelivery': True}}, expected=200)
        self.assertTrue(retry['idempotentReplay'])
        self.assertEqual(retry['event'], first['event'])
        self.assertEqual(Event.objects(service_id=service.id).count(), 3)
        self.assertEqual(Incident.objects(service_id=service.id).count(), 1)
        self.assertEqual(before, json_util.dumps(list(get_db().incidents.find({'serviceId':service.id}))))

    def test_intake_api_key_and_validation_failures_do_not_mutate(self):
        service, key, body = self.intake_fixture()
        for headers in ({}, {'HTTP_X_INTEGRATION_KEY':'invalid'}):
            response = Client().post('/api/v1/events', data=json.dumps(body), content_type='application/json', **headers)
            self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service_client().post('/api/v1/events', data=json.dumps(body), content_type='application/json').status_code, 401)
        response = Client().post('/api/v1/services/'+str(self.checkout)+'/events', data=json.dumps(body), content_type='application/json', HTTP_X_INTEGRATION_KEY=key)
        self.assertEqual(response.status_code, 403)
        for invalid in ({**body, 'severity':'URGENT'}, {**body, 'payload':{'big':'x'*33000}}, {**body, 'labels':[]}, {**body, 'sourceEventId':''}, {**body, 'serviceId':str(self.checkout)}, [], {**body, 'payload': {'$bad': 1}}):
            response = Client().post('/api/v1/events', data=json.dumps(invalid), content_type='application/json', HTTP_X_INTEGRATION_KEY=key)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Client().post('/api/v1/events', data='{', content_type='application/json', HTTP_X_INTEGRATION_KEY=key).status_code, 400)
        self.assertEqual(Event.objects(service_id=service.id).count(), 0)
        self.assertEqual(Incident.objects(service_id=service.id).count(), 0)

    def test_intake_duplicate_precedence_across_active_candidates(self):
        service, _, body = self.intake_fixture()
        first, _ = events.ingest(service, body, at=self.at(0))
        other = incidents.create({'serviceId':str(service.id), 'title':'Another active incident', 'severity':'HIGH'}, origin='EVENT', at=self.at(1))
        events.record(service.id, {**body, 'sourceEventId':'other', 'payload':{'latencyMs':1500}}, other.id, 'CREATED_INCIDENT', 'Another active fixture.', received_at=self.at(1))
        duplicate, _ = events.ingest(service, {**body, 'sourceEventId':'exact'}, at=self.at(2))
        self.assertEqual(duplicate.disposition, 'SUPPRESSED_DUPLICATE')
        self.assertEqual(duplicate.incident_id, first.incident_id)
        grouped, _ = events.ingest(service, {**body, 'sourceEventId':'related', 'payload':{'latencyMs':1700}}, at=self.at(3))
        self.assertEqual(grouped.disposition, 'GROUPED')
        # Most recently received matching event wins ties deterministically.
        self.assertEqual(grouped.incident_id, first.incident_id)

    def test_intake_window_boundary_resolved_exclusion_and_retry(self):
        service, _, body = self.intake_fixture()
        first, _ = events.ingest(service, body, at=self.at(0))
        edge, _ = events.ingest(service, {**body, 'sourceEventId':'edge'}, at=self.at(30))
        self.assertEqual(edge.disposition, 'SUPPRESSED_DUPLICATE')
        expired, _ = events.ingest(service, {**body, 'sourceEventId':'expired'}, at=self.at(30)+timedelta(seconds=1))
        self.assertEqual(expired.disposition, 'CREATED_INCIDENT')
        self.assertNotEqual(expired.incident_id, first.incident_id)
        incidents.acknowledge(expired.incident_id, self.actor, at=self.at(31))
        incidents.resolve(expired.incident_id, {'resolutionNote':'Recovered'}, self.actor, at=self.at(32))
        retry, created = events.ingest(service, {**body, 'sourceEventId':'expired'}, at=self.at(33))
        self.assertFalse(created)
        self.assertEqual(retry.id, expired.id)
        new, _ = events.ingest(service, {**body, 'sourceEventId':'after-resolution'}, at=self.at(33))
        self.assertEqual(new.disposition, 'CREATED_INCIDENT')
        self.assertNotEqual(new.incident_id, expired.incident_id)

    def test_intake_delivery_identity_is_scoped_to_service_and_source(self):
        service, key, body = self.intake_fixture()
        first = self.post_event(key, body)
        other, other_key = services.create({'name':'Other intake', 'ownerId':str(self.actor)})
        independent = self.post_event(other_key, body)
        source = self.post_event(key, {**body, 'source':'other-monitor'})
        self.assertNotEqual(first['event']['incident']['_id'], independent['event']['incident']['_id'])
        self.assertEqual(source['event']['disposition'], 'CREATED_INCIDENT')
        self.assertEqual(Event.objects(service_id=service.id).count(), 2)
        self.assertEqual(Event.objects(service_id=other.id).count(), 1)

    def test_event_history_and_incident_links_are_authenticated_and_paginated(self):
        service, key, body = self.intake_fixture()
        path = '/api/v1/services/'+str(service.id)+'/events'
        client = self.service_client()
        self.assertEqual(Client().get(path, HTTP_X_INTEGRATION_KEY=key).status_code, 401)
        self.assertEqual(client.get(path).json()['data']['items'], [])
        first = self.post_event(key, body, path=path)
        for index in range(1, 51):
            events.ingest(service, {**body, 'sourceEventId': 'history-'+str(index)})
        page = client.get(path).json()['data']
        self.assertEqual(len(page['items']), 50)
        self.assertEqual(page['total'], 51)
        self.assertEqual(page['nextOffset'], 50)
        last = client.get(path+'?offset=50').json()['data']
        self.assertEqual(len(last['items']), 1)
        self.assertIsNone(last['nextOffset'])
        self.assertEqual(last['items'][0]['_id'], first['event']['_id'])
        self.assertEqual(client.get(path+'?offset=-1').status_code, 400)
        self.assertEqual(client.get(path+'?offset=abc').status_code, 400)
        incident_path='/api/v1/incidents/'+first['event']['incident']['_id']
        self.assertEqual(Client().get(incident_path).status_code, 401)
        detail=client.get(incident_path).json()['data']
        self.assertEqual(detail['eventCount'], 51)
        self.assertEqual(detail['reference'], first['event']['incident']['reference'])
        self.assertEqual(set(get_db().list_collection_names()), PRODUCT_COLLECTIONS)

    def act(self, client, path, body=None, expected=200):
        response = client.post(path, data=json.dumps(body or {}), content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content)
        return response

    def test_incident_api_requires_authentication_and_valid_ids(self):
        anonymous = Client()
        incident = str(Incident.objects(reference='INC-104').first().id)
        endpoints = [
            ('get', '/api/v1/incidents'), ('post', '/api/v1/incidents'),
            ('get', '/api/v1/incidents/' + incident), ('post', '/api/v1/incidents/' + incident + '/claim'),
            ('post', '/api/v1/incidents/' + incident + '/assign'), ('post', '/api/v1/incidents/' + incident + '/acknowledge'),
            ('post', '/api/v1/incidents/' + incident + '/notes'), ('post', '/api/v1/incidents/' + incident + '/escalate'),
            ('post', '/api/v1/incidents/' + incident + '/resolve'), ('post', '/api/v1/incidents/' + incident + '/steps/1'),
        ]
        for method, path in endpoints:
            self.assertEqual(getattr(anonymous, method)(path).status_code, 401, path)
        session = anonymous.post('/api/v1/auth/login', data=json.dumps({'email': 'alex.morgan@calendar.com', 'password': 'password123'}), content_type='application/json').json()['data']['token']
        self.assertEqual(anonymous.get('/api/v1/incidents', HTTP_AUTHORIZATION='Bearer ' + session).status_code, 401)
        client = self.service_client()
        self.assertEqual(client.get('/api/v1/incidents/not-an-id').status_code, 400)
        self.assertEqual(client.get('/api/v1/incidents/' + str(ObjectId())).status_code, 404)
        self.assertEqual(client.post('/api/v1/incidents', data=json.dumps({'title': 'No service'}), content_type='application/json').status_code, 400)
        self.assertEqual(client.post('/api/v1/incidents', data=json.dumps({'serviceId': str(ObjectId()), 'title': 'Missing'}), content_type='application/json').status_code, 404)

    def test_incident_api_manual_lifecycle_and_invalid_transitions(self):
        client = self.service_client()
        service, _ = services.create({'name': 'API lifecycle', 'ownerId': str(self.actor)})
        created = self.act(client, '/api/v1/incidents', {'serviceId': str(service.id), 'title': 'Checkout errors', 'description': 'Elevated 500s', 'severity': 'LOW'}, 201).json()['data']
        path = '/api/v1/incidents/' + created['_id']
        self.assertEqual((created['status'], created['origin'], created['createdBy'], created['assigneeId']), ('TRIGGERED', 'MANUAL', str(self.actor), None))
        listing = client.get('/api/v1/incidents')
        self.assertEqual(listing['Cache-Control'], 'no-store')
        self.assertIn(created['_id'], [row['_id'] for row in listing.json()['data']])
        # Claiming sets ownership but never advances status (ownership is independent from status).
        claimed = self.act(client, path + '/claim').json()['data']
        self.assertEqual((claimed['assigneeId'], claimed['status']), (str(self.actor), 'TRIGGERED'))
        # Unassign, then reassign to another responder.
        self.assertIsNone(self.act(client, path + '/assign', {'assigneeId': None}).json()['data']['assigneeId'])
        assigned = self.act(client, path + '/assign', {'assigneeId': str(seed_id(1, 2))}).json()['data']
        self.assertEqual((assigned['assigneeId'], assigned['status']), (str(seed_id(1, 2)), 'TRIGGERED'))
        self.assertEqual(self.act(client, path + '/claim', {}, 409).json()['error']['code'], 'ALREADY_ASSIGNED')
        # Invalid transition: cannot resolve before acknowledgment.
        self.assertEqual(self.act(client, path + '/resolve', {'resolutionNote': 'Too early'}, 409).json()['error']['code'], 'INVALID_TRANSITION')
        # TRIGGERED -> ACKNOWLEDGED.
        ack = self.act(client, path + '/acknowledge').json()['data']
        self.assertEqual((ack['status'], ack['acknowledgedBy']), ('ACKNOWLEDGED', str(self.actor)))
        # Invalid transition: acknowledging an already-acknowledged incident.
        self.assertEqual(self.act(client, path + '/acknowledge', {}, 409).json()['error']['code'], 'INVALID_TRANSITION')
        noted = self.act(client, path + '/notes', {'body': 'Mitigation underway'}, 201).json()['data']
        self.assertEqual((noted['noteCount'], noted['notes'][0]['body']), (1, 'Mitigation underway'))
        # Escalation must increase severity and requires a reason.
        self.assertEqual(self.act(client, path + '/escalate', {'severity': 'LOW', 'reason': 'no increase'}, 409).json()['error']['code'], 'SEVERITY_NOT_INCREASED')
        self.assertEqual(self.act(client, path + '/escalate', {'severity': 'CRITICAL'}, 400).json()['error']['code'], 'VALIDATION_ERROR')
        escalated = self.act(client, path + '/escalate', {'severity': 'CRITICAL', 'reason': 'Customer-facing outage', 'assigneeId': str(self.actor)}).json()['data']
        self.assertEqual((escalated['severity'], escalated['assigneeId'], escalated['status']), ('CRITICAL', str(self.actor), 'ACKNOWLEDGED'))
        self.assertEqual(escalated['timeline'][-1]['kind'], 'ESCALATED')
        self.assertEqual(escalated['timeline'][-1]['message'], 'Customer-facing outage')
        self.assertEqual(escalated['timeline'][-1]['details']['previousSeverity'], 'LOW')
        # Resolution requires a note.
        self.assertEqual(self.act(client, path + '/resolve', {'resolutionNote': '  '}, 400).json()['error']['code'], 'VALIDATION_ERROR')
        # ACKNOWLEDGED -> RESOLVED.
        resolved = self.act(client, path + '/resolve', {'resolutionNote': 'Rolled back the deploy.'}).json()['data']
        self.assertEqual((resolved['status'], resolved['resolvedBy'], resolved['resolutionNote']), ('RESOLVED', str(self.actor), 'Rolled back the deploy.'))
        self.assertEqual([entry['kind'] for entry in resolved['timeline']], ['CREATED', 'CLAIMED', 'ASSIGNED', 'ASSIGNED', 'ACKNOWLEDGED', 'NOTE_ADDED', 'ESCALATED', 'RESOLVED'])
        # Resolved incidents are read-only for every mutating action.
        for suffix, body in [('/claim', {}), ('/assign', {'assigneeId': str(self.actor)}), ('/acknowledge', {}), ('/notes', {'body': 'late'}), ('/escalate', {'severity': 'CRITICAL', 'reason': 'late'}), ('/resolve', {'resolutionNote': 'again'}), ('/steps/1', {'completed': True})]:
            self.assertEqual(self.act(client, path + suffix, body, 409).json()['error']['code'], 'INCIDENT_RESOLVED', suffix)

    def test_incident_api_required_steps_gate_resolution(self):
        client = self.service_client()
        created = self.act(client, '/api/v1/incidents', {'serviceId': str(self.checkout), 'title': 'Checkout down', 'severity': 'HIGH'}, 201).json()['data']
        path = '/api/v1/incidents/' + created['_id']
        self.assertGreaterEqual(created['openRequiredSteps'], 1)
        self.act(client, path + '/acknowledge')
        self.assertEqual(self.act(client, path + '/resolve', {'resolutionNote': 'done'}, 409).json()['error']['code'], 'REQUIRED_STEPS_INCOMPLETE')
        # A later step cannot be completed before the earlier ones.
        self.assertEqual(self.act(client, path + '/steps/2', {'completed': True}, 409).json()['error']['code'], 'WORKFLOW_ORDER')
        for order in range(1, len(created['workflowRun']) + 1):
            self.act(client, path + '/steps/' + str(order), {'completed': True})
        resolved = self.act(client, path + '/resolve', {'resolutionNote': 'Recovered and verified.'}).json()['data']
        self.assertEqual((resolved['status'], resolved['openRequiredSteps']), ('RESOLVED', 0))

    def test_incident_workflow_snapshot_is_independent_and_gates_resolution(self):
        client = self.service_client()
        service_path = '/api/v1/services/' + str(self.checkout)
        # A new incident snapshots the service's CURRENT template with every step open.
        created = self.act(client, '/api/v1/incidents', {'serviceId': str(self.checkout), 'title': 'Workflow incident', 'severity': 'HIGH'}, 201).json()['data']
        path = '/api/v1/incidents/' + created['_id']
        original = created['workflowRun']
        self.assertGreaterEqual(created['openRequiredSteps'], 1)
        self.assertTrue(all(not step['completed'] and step['completedBy'] is None and step['completedAt'] is None for step in original))
        # Completing a step records the acting responder and a timestamp on that step only, and audits the timeline.
        completed = self.act(client, path + '/steps/1', {'completed': True}).json()['data']
        first = completed['workflowRun'][0]
        self.assertTrue(first['completed'])
        self.assertEqual(first['completedBy'], str(self.actor))
        self.assertIsNotNone(first['completedAt'])
        self.assertEqual(completed['timeline'][-1]['kind'], 'STEP_COMPLETED')
        # Editing the service template must not change the open incident's snapshot; its completion state is preserved.
        edit = client.patch(service_path, data=json.dumps({'workflowTemplate': [{'title': 'Replaced step', 'instructions': 'A different procedure entirely.', 'required': False, 'order': 1}]}), content_type='application/json')
        self.assertEqual(edit.status_code, 200)
        after_edit = client.get(path).json()['data']['workflowRun']
        self.assertEqual([(s['title'], s['instructions'], s['required'], s['order']) for s in after_edit], [(s['title'], s['instructions'], s['required'], s['order']) for s in original])
        self.assertTrue(after_edit[0]['completed'])
        # Undoing completion clears the actor and timestamp and audits the timeline.
        reopened = self.act(client, path + '/steps/1', {'completed': False}).json()['data']
        self.assertEqual((reopened['workflowRun'][0]['completed'], reopened['workflowRun'][0]['completedBy'], reopened['workflowRun'][0]['completedAt']), (False, None, None))
        self.assertEqual(reopened['timeline'][-1]['kind'], 'STEP_REOPENED')
        # Resolution guardrail: acknowledged but required steps open -> blocked with an explanatory code.
        self.act(client, path + '/acknowledge')
        self.assertEqual(self.act(client, path + '/resolve', {'resolutionNote': 'done'}, 409).json()['error']['code'], 'REQUIRED_STEPS_INCOMPLETE')
        for order in range(1, len(original) + 1):
            self.act(client, path + '/steps/' + str(order), {'completed': True})
        self.assertEqual(self.act(client, path + '/resolve', {'resolutionNote': 'Recovered and verified.'}).json()['data']['status'], 'RESOLVED')
        # A resolved incident and its workflow are read-only.
        self.assertEqual(self.act(client, path + '/steps/1', {'completed': False}, 409).json()['error']['code'], 'INCIDENT_RESOLVED')

    def test_post_incident_analytics_match_seeded_facts(self):
        anonymous = Client()
        self.assertEqual(anonymous.get('/api/v1/analytics').status_code, 401)
        client = self.service_client()
        response = client.get('/api/v1/analytics')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        data = response.json()['data']
        # Mean time to resolve: arithmetic mean over the 15 resolved incidents only (683 minutes total);
        # the triggered INC-115 and acknowledged-but-unresolved INC-116 are excluded.
        self.assertEqual(data['resolution']['sampleSize'], 15)
        self.assertAlmostEqual(data['resolution']['meanSeconds'], 683 * 60 / 15)
        # Mean time to acknowledge: mean over every incident that reached acknowledgment (16 = 15 resolved + INC-116).
        self.assertEqual(data['acknowledgement']['sampleSize'], 16)
        self.assertAlmostEqual(data['acknowledgement']['meanSeconds'], 125 * 60 / 16)
        # Grouped and suppressed counts come straight from stored events.
        self.assertEqual((data['events']['grouped'], data['events']['suppressed'], data['events']['created'], data['events']['total']), (4, 4, 11, 19))
        self.assertEqual(data['totals'], {'incidents': 17, 'resolved': 15, 'acknowledged': 16, 'unresolved': 2})
        # Every volume breakdown reconciles to the full incident count.
        for key in ('volumeByService', 'volumeBySeverity', 'volumeByResponder'):
            self.assertEqual(sum(row['count'] for row in data[key]), 17, key)
        # Per-service and per-responder figures agree with an independent query over the same stored facts.
        for row in data['volumeByService']:
            self.assertEqual(row['count'], Incident.objects(service_id=ObjectId(row['serviceId'])).count())
        self.assertEqual([row['severity'] for row in data['volumeBySeverity']], list(SEVERITIES))
        unassigned = [row for row in data['volumeByResponder'] if row['responderId'] is None]
        self.assertEqual(unassigned[0]['name'], 'Unassigned')
        self.assertEqual(unassigned[0]['count'], Incident.objects(assignee_id=None).count())
        # The date-window rule is documented once and travels with the payload.
        self.assertIsNone(data['window']['since'])
        self.assertIn('inclusive', data['window']['rule'].lower())

    def test_analytics_window_excludes_out_of_range_incidents(self):
        client = self.service_client()
        full = client.get('/api/v1/analytics').json()['data']
        # A future-only window contains no seeded incidents, so resolution has an empty sample and a null mean.
        empty = client.get('/api/v1/analytics?since=2099-01-01T00:00:00Z').json()['data']
        self.assertEqual(empty['totals']['incidents'], 0)
        self.assertIsNone(empty['resolution']['meanSeconds'])
        self.assertEqual(empty['resolution']['sampleSize'], 0)
        self.assertEqual(empty['events']['total'], 0)
        # A window whose end precedes its start is rejected.
        self.assertEqual(client.get('/api/v1/analytics?since=2026-01-02&until=2026-01-01').status_code, 400)
        # A wide window that spans the seed reproduces the all-time figures.
        wide = client.get('/api/v1/analytics?since=2000-01-01T00:00:00Z&until=2100-01-01T00:00:00Z').json()['data']
        self.assertEqual(wide['totals'], full['totals'])
        self.assertEqual(wide['resolution']['sampleSize'], full['resolution']['sampleSize'])
