from mongoengine import BooleanField, DateTimeField, EmbeddedDocument, IntField, ObjectIdField, StringField, ValidationError


class WorkflowTemplateStep(EmbeddedDocument):
    title = StringField(required=True, max_length=160)
    instructions = StringField(required=True, max_length=2000)
    order = IntField(required=True, min_value=1, max_value=20)
    required = BooleanField(default=True)


class WorkflowRunStep(EmbeddedDocument):
    title = StringField(required=True, max_length=160)
    instructions = StringField(required=True, max_length=2000)
    order = IntField(required=True, min_value=1, max_value=20)
    required = BooleanField(default=True)
    completed = BooleanField(default=False)
    completed_by = ObjectIdField(db_field="completedBy", null=True)
    completed_at = DateTimeField(db_field="completedAt", null=True)

    def clean(self):
        if self.completed != bool(self.completed_by and self.completed_at):
            raise ValidationError("Completed steps require an actor and timestamp.")
        if not self.completed and (self.completed_by or self.completed_at):
            raise ValidationError("Open steps cannot have completion metadata.")


def snapshot(template):
    return [WorkflowRunStep(title=step.title, instructions=step.instructions, order=step.order, required=step.required) for step in template]
