from mongoengine import DateTimeField, DictField, EmbeddedDocument, EmbeddedDocumentListField, ListField, ObjectIdField, StringField, ValidationError

from apps.shared.documents import TimestampedDocument
from apps.shared.domain import SEVERITIES, STATUSES, utc
from apps.shared.workflows import WorkflowRunStep


class Note(EmbeddedDocument):
    body = StringField(required=True, max_length=4000)
    author_id = ObjectIdField(db_field="authorId", required=True)
    created_at = DateTimeField(db_field="createdAt", required=True)


class TimelineEntry(EmbeddedDocument):
    kind = StringField(required=True, choices=("CREATED", "CLAIMED", "ASSIGNED", "ACKNOWLEDGED", "ESCALATED", "NOTE_ADDED", "STEP_COMPLETED", "STEP_REOPENED", "EVENT_RECEIVED", "RESOLVED"))
    actor_id = ObjectIdField(db_field="actorId", null=True)
    at = DateTimeField(required=True)
    message = StringField(required=True, max_length=4000)
    details = DictField(default=dict)


class Incident(TimestampedDocument):
    meta = {
        "collection": "incidents",
        "indexes": [{"fields": ["reference"], "unique": True}, ("service_id", "status", "created_at"), "assignee_id"],
    }

    reference = StringField(required=True, regex=r"^INC-[1-9][0-9]*$")
    service_id = ObjectIdField(db_field="serviceId", required=True)
    origin = StringField(required=True, choices=("MANUAL", "EVENT"))
    created_by = ObjectIdField(db_field="createdBy", null=True)
    title = StringField(required=True, max_length=200)
    description = StringField(default="", max_length=4000)
    severity = StringField(required=True, choices=SEVERITIES)
    status = StringField(choices=STATUSES, default="TRIGGERED")
    assignee_id = ObjectIdField(db_field="assigneeId", null=True)
    acknowledged_at = DateTimeField(db_field="acknowledgedAt", null=True)
    acknowledged_by = ObjectIdField(db_field="acknowledgedBy", null=True)
    resolved_at = DateTimeField(db_field="resolvedAt", null=True)
    resolved_by = ObjectIdField(db_field="resolvedBy", null=True)
    resolution_note = StringField(db_field="resolutionNote", default="", max_length=4000)
    event_ids = ListField(ObjectIdField(), db_field="eventIds", default=list)
    workflow_run = EmbeddedDocumentListField(WorkflowRunStep, db_field="workflowRun", default=list)
    notes = EmbeddedDocumentListField(Note, default=list)
    timeline = EmbeddedDocumentListField(TimelineEntry, default=list)

    def clean(self):
        if self.origin == "MANUAL" and not self.created_by:
            raise ValidationError("Manual incidents require a creator.")
        acknowledged = bool(self.acknowledged_at and self.acknowledged_by)
        if (self.status in ("ACKNOWLEDGED", "RESOLVED")) != acknowledged:
            raise ValidationError("Acknowledgment metadata must match the lifecycle state.")
        if self.status == "TRIGGERED" and (self.acknowledged_at or self.acknowledged_by):
            raise ValidationError("Triggered incidents cannot contain acknowledgment metadata.")
        resolved = bool(self.resolved_at and self.resolved_by and self.resolution_note.strip())
        if (self.status == "RESOLVED") != resolved:
            raise ValidationError("Resolution requires an actor, timestamp, and note.")
        if self.status != "RESOLVED" and (self.resolved_at or self.resolved_by or self.resolution_note):
            raise ValidationError("Active incidents cannot contain resolution metadata.")
        if self.created_at and self.acknowledged_at and utc(self.acknowledged_at) < utc(self.created_at):
            raise ValidationError("Acknowledgment cannot predate creation.")
        if resolved and utc(self.resolved_at) < utc(self.acknowledged_at):
            raise ValidationError("Resolution cannot predate acknowledgment.")
        if self.status == "RESOLVED" and any(step.required and not step.completed for step in self.workflow_run):
            raise ValidationError("Complete required workflow steps before resolution.")
        if [step.order for step in self.workflow_run] != list(range(1, len(self.workflow_run) + 1)):
            raise ValidationError("Workflow snapshot order must be consecutive.")
        for index, step in enumerate(self.workflow_run):
            if step.completed and any(not previous.completed for previous in self.workflow_run[:index]):
                raise ValidationError("Workflow steps must be completed in order.")
        times = [utc(entry.at) for entry in self.timeline]
        if times != sorted(times):
            raise ValidationError("Timeline timestamps must be ordered.")
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValidationError("Incident event links must be unique.")
