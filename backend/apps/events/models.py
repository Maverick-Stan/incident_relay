from mongoengine import DateTimeField, DictField, Document, EmbeddedDocument, EmbeddedDocumentField, ObjectIdField, StringField, ValidationError

from apps.shared.domain import DISPOSITIONS, SEVERITIES, utc


class TriageDecision(EmbeddedDocument):
    rule = StringField(required=True, choices=DISPOSITIONS)
    reason = StringField(required=True, max_length=1000)
    matched_incident_id = ObjectIdField(db_field="matchedIncidentId", null=True)
    matched_event_id = ObjectIdField(db_field="matchedEventId", null=True)
    decided_at = DateTimeField(db_field="decidedAt", required=True)


class Event(Document):
    meta = {"collection": "events", "indexes": [
        {"fields": ["service_id", "source", "source_event_id"], "unique": True},
        ("service_id", "received_at"), ("service_id", "grouping_key", "received_at"), "incident_id",
    ]}

    service_id = ObjectIdField(db_field="serviceId", required=True)
    source = StringField(required=True, max_length=120)
    source_event_id = StringField(db_field="sourceEventId", required=True, max_length=200)
    raw_payload = DictField(db_field="rawPayload", required=True)
    normalized_title = StringField(db_field="normalizedTitle", required=True, max_length=200)
    normalized_severity = StringField(db_field="normalizedSeverity", required=True, choices=SEVERITIES)
    fingerprint = StringField(required=True, regex=r"^[0-9a-f]{64}$")
    grouping_key = StringField(db_field="groupingKey", required=True, regex=r"^[0-9a-f]{64}$")
    received_at = DateTimeField(db_field="receivedAt", required=True)
    disposition = StringField(required=True, choices=DISPOSITIONS)
    incident_id = ObjectIdField(db_field="incidentId", required=True)
    duplicate_of_event_id = ObjectIdField(db_field="duplicateOfEventId", null=True)
    triage_decision = EmbeddedDocumentField(TriageDecision, db_field="triageDecision", required=True)

    def clean(self):
        if (self.disposition == "SUPPRESSED_DUPLICATE") != bool(self.duplicate_of_event_id):
            raise ValidationError("Only suppressed duplicates require a duplicate event link.")
        if self.triage_decision:
            if self.triage_decision.rule != self.disposition or self.triage_decision.matched_event_id != self.duplicate_of_event_id:
                raise ValidationError("Triage metadata must agree with the event outcome.")
            expected = None if self.disposition == "CREATED_INCIDENT" else self.incident_id
            if self.triage_decision.matched_incident_id != expected:
                raise ValidationError("Triage incident links must agree with the event outcome.")
            if self.received_at and utc(self.triage_decision.decided_at) < utc(self.received_at):
                raise ValidationError("A decision cannot predate receipt.")

    def save(self, *args, **kwargs):
        if not self._created:
            raise ValidationError("Recorded events are immutable.")
        return super().save(*args, **kwargs)
