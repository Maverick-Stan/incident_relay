from datetime import datetime

from apps.events.models import Event
from apps.incidents.models import Incident
from apps.services.models import Service
from apps.shared.domain import SEVERITIES, invalid, utc
from apps.users.models import User

# One date-window rule, applied consistently to every metric below:
# incidents are placed in the window by their creation time and events by their receipt time,
# a record is in range when since <= timestamp <= until (both bounds inclusive, in UTC),
# and an omitted bound is treated as open-ended. The resolution metric additionally counts only
# incidents that are actually resolved; unacknowledged incidents are likewise absent from the
# acknowledgement metric. Every figure is computed live from these stored facts, never from a
# pre-aggregated document.
WINDOW_RULE = (
    "Incidents are counted by their creation time and events by their receipt time. A record is in "
    "range when since <= timestamp <= until, with both bounds inclusive and interpreted in UTC; an "
    "omitted bound is open-ended. Mean time to resolve counts only resolved incidents, and mean time "
    "to acknowledge only acknowledged ones."
)


def parse_bound(value, field):
    if value is None or value == "":
        return None
    try:
        return utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, AttributeError):
        invalid(field, "Provide an ISO-8601 date or timestamp.")


def in_window(moment, since, until):
    moment = utc(moment)
    if since is not None and moment < since:
        return False
    if until is not None and moment > until:
        return False
    return True


def mean_seconds(deltas):
    # Arithmetic mean of elapsed seconds; None when the sample is empty so the UI can say so.
    return sum(deltas) / len(deltas) if deltas else None


def tally(pairs):
    counts = {}
    for key in pairs:
        counts[key] = counts.get(key, 0) + 1
    return counts


def compute(since=None, until=None):
    incidents = [incident for incident in Incident.objects if in_window(incident.created_at, since, until)]
    events = [event for event in Event.objects if in_window(event.received_at, since, until)]

    acknowledged = [incident for incident in incidents if incident.acknowledged_at]
    resolved = [incident for incident in incidents if incident.status == "RESOLVED" and incident.resolved_at]
    ack_deltas = [(utc(incident.acknowledged_at) - utc(incident.created_at)).total_seconds() for incident in acknowledged]
    resolve_deltas = [(utc(incident.resolved_at) - utc(incident.created_at)).total_seconds() for incident in resolved]

    service_names = {str(service.id): service.name for service in Service.objects}
    responder_names = {str(user.id): user.name for user in User.objects}

    by_service = tally(str(incident.service_id) for incident in incidents)
    by_severity = tally(incident.severity for incident in incidents)
    by_responder = tally(str(incident.assignee_id) if incident.assignee_id else None for incident in incidents)
    by_disposition = tally(event.disposition for event in events)

    volume_by_service = sorted(
        ({"serviceId": service_id, "name": service_names.get(service_id, "Unknown service"), "count": count}
         for service_id, count in by_service.items()),
        key=lambda row: (-row["count"], row["name"]),
    )
    volume_by_severity = [{"severity": level, "count": by_severity.get(level, 0)} for level in SEVERITIES]
    volume_by_responder = sorted(
        ({"responderId": responder_id,
          "name": responder_names.get(responder_id, "Unavailable responder") if responder_id else "Unassigned",
          "count": count}
         for responder_id, count in by_responder.items()),
        key=lambda row: (-row["count"], row["name"]),
    )

    return {
        "window": {
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "rule": WINDOW_RULE,
        },
        "acknowledgement": {"meanSeconds": mean_seconds(ack_deltas), "sampleSize": len(ack_deltas)},
        "resolution": {"meanSeconds": mean_seconds(resolve_deltas), "sampleSize": len(resolve_deltas)},
        "volumeByService": volume_by_service,
        "volumeBySeverity": volume_by_severity,
        "volumeByResponder": volume_by_responder,
        "events": {
            "grouped": by_disposition.get("GROUPED", 0),
            "suppressed": by_disposition.get("SUPPRESSED_DUPLICATE", 0),
            "created": by_disposition.get("CREATED_INCIDENT", 0),
            "total": len(events),
        },
        "totals": {
            "incidents": len(incidents),
            "resolved": len(resolved),
            "acknowledged": len(acknowledged),
            "unresolved": len(incidents) - len(resolved),
        },
    }
