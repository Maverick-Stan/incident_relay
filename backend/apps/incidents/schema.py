from apps.shared.domain import SEVERITIES, body_object, choice, identifier, invalid, text


def validate_create(body):
    body_object(body, ("serviceId", "title", "description", "severity", "assigneeId"))
    values = {
        "service_id": identifier(body.get("serviceId"), "serviceId"),
        "title": text(body.get("title"), "title", 200),
        "description": "" if body.get("description", "") == "" else text(body.get("description"), "description", 4000),
    }
    if "severity" in body:
        values["severity"] = choice(body["severity"], "severity", SEVERITIES)
    if body.get("assigneeId") is not None:
        values["assignee_id"] = identifier(body["assigneeId"], "assigneeId")
    return values


def validate_note(body):
    body_object(body, ("body",))
    return text(body.get("body"), "body", 4000)


def validate_resolution(body):
    body_object(body, ("resolutionNote",))
    return text(body.get("resolutionNote"), "resolutionNote", 4000)


def validate_assignment(body):
    body_object(body, ("assigneeId",))
    if "assigneeId" not in body:
        invalid("assigneeId", "Provide an assignee id, or null to unassign.")
    value = body["assigneeId"]
    return None if value is None else identifier(value, "assigneeId")


def validate_escalation(body):
    body_object(body, ("severity", "reason", "assigneeId"))
    values = {"severity": choice(body.get("severity"), "severity", SEVERITIES), "reason": text(body.get("reason"), "reason", 2000)}
    if "assigneeId" in body:
        values["assignee_id"] = identifier(body["assigneeId"], "assigneeId")
    return values
