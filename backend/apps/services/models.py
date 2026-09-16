from mongoengine import EmbeddedDocumentListField, IntField, ObjectIdField, StringField, ValidationError

from apps.shared.documents import TimestampedDocument
from apps.shared.domain import SEVERITIES
from apps.shared.workflows import WorkflowTemplateStep


class Service(TimestampedDocument):
    meta = {"collection": "services", "indexes": ["owner_id", {"fields": ["integration_key_hash"], "unique": True}]}

    name = StringField(required=True, max_length=120)
    description = StringField(default="", max_length=2000)
    owner_id = ObjectIdField(db_field="ownerId", required=True)
    integration_key_hash = StringField(db_field="integrationKeyHash", required=True, regex=r"^[0-9a-f]{64}$")
    integration_key_last_four = StringField(db_field="integrationKeyLastFour", required=True, min_length=4, max_length=4)
    default_severity = StringField(db_field="defaultSeverity", choices=SEVERITIES, default="HIGH")
    grouping_window_minutes = IntField(db_field="groupingWindowMinutes", min_value=1, max_value=1440, default=30)
    workflow_template = EmbeddedDocumentListField(WorkflowTemplateStep, db_field="workflowTemplate", default=list)

    def clean(self):
        if len(self.workflow_template) > 20 or [step.order for step in self.workflow_template] != list(range(1, len(self.workflow_template) + 1)):
            raise ValidationError("Workflow steps must have consecutive order values starting at one.")
