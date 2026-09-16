from apps.shared.domain import SEVERITIES, body_object, choice, invalid, json_payload, text


def validate_event(body):
    body_object(body, ("source", "sourceEventId", "title", "severity", "labels", "payload"))
    raw = json_payload(body)
    labels = body.get("labels", {})
    if not isinstance(labels, dict) or len(labels) > 20:
        invalid("labels", "Provide an object with at most 20 labels.")
    normalized = {}
    for key, value in labels.items():
        label = text(key, "labels", 80).casefold()
        if label in normalized:
            invalid("labels", "Label names must be unique after normalization.")
        normalized[label] = " ".join(text(value, "labels", 200).casefold().split())
    return {
        "source": text(body.get("source"), "source", 120),
        "source_event_id": text(body.get("sourceEventId"), "sourceEventId", 200),
        "normalized_title": " ".join(text(body.get("title"), "title", 200).casefold().split()),
        "normalized_severity": choice(body.get("severity"), "severity", SEVERITIES),
        "labels": normalized,
        "payload": json_payload(body.get("payload", {})),
        "raw_payload": raw,
    }
