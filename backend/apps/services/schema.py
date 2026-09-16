from apps.shared.domain import SEVERITIES, body_object, choice, identifier, integer, invalid, text
from apps.shared.workflows import WorkflowTemplateStep

FIELDS = ("name", "description", "ownerId", "defaultSeverity", "groupingWindowMinutes", "workflowTemplate")


def validate_workflow(rows):
    if not isinstance(rows, list) or len(rows) > 20:
        invalid("workflowTemplate", "Provide at most 20 ordered steps.")
    steps = []
    for index, row in enumerate(rows, 1):
        body_object(row, ("title", "instructions", "order", "required"))
        order = integer(row.get("order", index), "order", 1, 20)
        if order != index:
            invalid("order", "Steps must be ordered consecutively starting at one.")
        required = row.get("required", True)
        if not isinstance(required, bool):
            invalid("required", "Provide a boolean.")
        steps.append(WorkflowTemplateStep(title=text(row.get("title"), "title", 160), instructions=text(row.get("instructions"), "instructions", 2000), order=order, required=required))
    return steps


def validate_service(body, partial=False):
    body_object(body, FIELDS)
    if partial and not body:
        invalid("body", "Provide at least one field to update.")
    readers = {
        "name": ("name", lambda value: text(value, "name", 120)),
        "description": ("description", lambda value: "" if value == "" else text(value, "description", 2000, optional=True)),
        "ownerId": ("owner_id", lambda value: identifier(value, "ownerId")),
        "defaultSeverity": ("default_severity", lambda value: choice(value, "defaultSeverity", SEVERITIES)),
        "groupingWindowMinutes": ("grouping_window_minutes", lambda value: integer(value, "groupingWindowMinutes", 1, 1440)),
        "workflowTemplate": ("workflow_template", validate_workflow),
    }
    values = body if partial else {"description": "", "defaultSeverity": "HIGH", "groupingWindowMinutes": 30, "workflowTemplate": [], **body}
    if not partial:
        for key in ("name", "ownerId"):
            if key not in values:
                invalid(key, "This field is required.")
    return {readers[key][0]: readers[key][1](value) for key, value in values.items()}
