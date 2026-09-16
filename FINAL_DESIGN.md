# Incident Relay: Final Product Design

Status: **Frozen for v1 implementation**  
Decision date: **2026-09-15**

This document is the approved product and architecture boundary for the HackerRank Build Your Own PagerDuty assignment. Implementation may refine names, copy, layouts, and internal code structure, but it must not add product scope or change the domain rules below without an explicit design decision.

## 1. Product thesis

Incident Relay is an explainable incident-response command center for small operations teams. It converts noisy monitoring events into owned, actionable incidents, guides responders through service-specific recovery steps, and measures the response afterward.

The primary product story is:

> A monitoring event enters the system. The system determines whether it should create an incident, join an active incident, or be suppressed as a duplicate. A responder claims and acknowledges the incident, follows the service's response workflow, resolves it, and reviews the resulting response metrics.

The product favors explicit state, deterministic decisions, auditability, and metrics derived from recorded facts.

## 2. Scope decision

The v1 product deliberately excludes on-call scheduling and automated escalation policies. Those features require substantial time-based and background-processing behavior. The implementation instead prioritizes a complete synchronous loop from signal intake through triage, response, resolution, and analysis.

Service ownership, manual assignment, and manual escalation provide sufficient ownership semantics for a small operations team.

## 3. Selected features

| Feature | Final v1 scope |
| --- | --- |
| Service and Event Management | Service creation, viewing, editing, guarded deletion, owner, integration key, grouping window, event simulator, and event history |
| Alert Triage | Normalization, fingerprinting, delivery idempotency, duplicate suppression, related-event grouping, incident creation, and an explanation for every decision |
| Incident Management | Manual creation, claim/assignment, acknowledgment, manual escalation, notes, resolution, and timeline |
| Incident Workflows | Per-service workflow templates, immutable incident snapshots, and ordered step completion |
| Post-Incident Analytics | Mean time to acknowledge, mean time to resolve, sample sizes, incident volume by service/severity/responder, and grouping/suppression counts |

## 4. Explicit non-goals

The following are not part of v1:

- On-call rotations or schedules
- Automated escalation policies or timers
- Background jobs, queues, or worker processes
- WebSockets or real-time push updates
- Email, SMS, or external notifications
- External monitoring integrations
- LLM-based classification or triage
- Branching or conditional workflows
- Incident reopening
- Manual reassignment of an event between incidents
- Distributed locks, transactions, or advanced concurrency control
- A separately persisted Alert entity
- Separate analytics, workflow-run, triage-decision, or escalation collections

## 5. Domain language

### Event

An immutable incoming payload from a monitoring source. Processing metadata may be added to the event, but its source identity and raw payload are not rewritten.

### Alert

The normalized operational interpretation of an event. Alert is a product concept, not a separately persisted MongoDB collection. Its normalized attributes are stored on the Event document.

### Incident

The coordinated response record for a service. An incident can be created from one or more events or created manually by a responder.

### Triage decision

The stored explanation of how an event was handled: it created an incident, joined an existing incident, or was suppressed as a duplicate.

## 6. Incident lifecycle

The only incident states are:

```text
TRIGGERED -> ACKNOWLEDGED -> RESOLVED
```

Rules:

- Ownership is independent from lifecycle state.
- Claiming or assigning an incident does not acknowledge it.
- An unassigned incident may be claimed by the current responder.
- Acknowledgment records the responder and timestamp.
- Resolution records the responder, timestamp, and a required resolution note.
- An incident is not reopened in v1. A recurrence creates a new incident.
- A resolved incident is an immutable operational record. Assignment, acknowledgment, severity, notes, workflow steps, escalation, and resolution controls are read-only after resolution; the timeline remains visible.
- Required workflow steps must be complete before baseline resolution is allowed.
- A resolution override with a reason is a stretch enhancement, not a v1 completion requirement.

## 7. Manual escalation

Escalation is a synchronous human action, not a policy engine.

An escalation:

- increases severity;
- may assign the incident to another responder;
- requires a reason; and
- creates a detailed timeline entry.

The incident does not store a separate `escalationLevel`. Severity and timeline history are the source of truth.

The severity taxonomy is:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

## 8. Event intake and triage

### Integration key

- Generate keys with Python's `secrets` module using sufficient entropy.
- Display a new raw key once.
- Store only its SHA-256 hash and final four display characters.
- Authenticate event intake through the `X-Integration-Key` header.
- Use no additional cryptography dependency.
- A seeded local demo key may be documented as a demo credential, while only its hash is stored in MongoDB.

### Idempotent delivery

The unique source identity is:

```text
(serviceId, source, sourceEventId)
```

Receiving the same source identity again returns the existing event and incident outcome. It does not insert a second event and is not counted as a newly suppressed duplicate.

### Triage sequence

1. Validate the integration key and request body.
2. Reject unsupported severity values and oversized or invalid payloads.
3. Check the unique source identity and return the prior result for a delivery retry.
4. Normalize the title, severity, and stable payload labels.
5. Calculate a fingerprint for exact duplicate detection.
6. Calculate a broader grouping key for related-event matching.
7. Search only active incidents for the same service and within its configured grouping window.
8. Apply one of the dispositions below and store the explanation.

Dispositions:

```text
CREATED_INCIDENT
GROUPED
SUPPRESSED_DUPLICATE
```

- `CREATED_INCIDENT`: no qualifying active incident exists, so a new triggered incident is created.
- `GROUPED`: a related active incident matches the service and grouping key, but the event is not an exact duplicate.
- `SUPPRESSED_DUPLICATE`: an exact fingerprint match exists within the applicable window. The event is stored for auditability and linked to the incident, but it does not create a new responder-facing alert.

Each event records a short human-readable reason such as:

> Grouped into INC-104 because the service and grouping key matched an active incident created 11 minutes ago.

The system guarantees idempotent retries for the same source event. It does not attempt to solve races between two different related events arriving at precisely the same time.

## 9. Persistence model

The application uses four product collections:

```text
users
services
events
incidents
```

### Service

```text
id
name
description
ownerId
integrationKeyHash
integrationKeyLastFour
defaultSeverity
groupingWindowMinutes
workflowTemplate[]
createdAt
updatedAt
```

Deletion rules:

- An unused service can be deleted.
- A service with related events or incidents cannot be deleted; the API returns a conflict response.
- Service archiving is a future enhancement.

### Event

```text
id
serviceId
source
sourceEventId
rawPayload
normalizedTitle
normalizedSeverity
fingerprint
groupingKey
receivedAt
disposition
incidentId
duplicateOfEventId
triageDecision:
  rule
  reason
  matchedIncidentId
  matchedEventId
  decidedAt
```

### Incident

```text
id
reference
serviceId
origin                 MANUAL | EVENT
createdBy
title
description
severity
status                 TRIGGERED | ACKNOWLEDGED | RESOLVED
assigneeId
createdAt
acknowledgedAt
acknowledgedBy
resolvedAt
resolvedBy
resolutionNote
eventIds[]
workflowRun[]
notes[]
timeline[]
```

Workflow snapshots, notes, and timeline entries are embedded because they belong to and are normally read with a single incident.

## 10. Workflow behavior

- A service owns an ordered workflow template.
- Creating an incident copies that template into an incident-owned workflow snapshot.
- Later service-template edits never change existing incidents.
- Each step contains a title, instructions, order, required flag, completion state, completion actor, and completion timestamp.
- Completing or reopening a step creates a timeline entry.
- Branches, approvals, timers, and automatic actions are excluded.

## 11. Analytics definitions

Analytics are calculated from incident timestamps and stored lifecycle facts. There is no analytics collection.

- **MTTA:** arithmetic mean of `acknowledgedAt - createdAt` for incidents acknowledged in the selected population.
- **MTTR:** arithmetic mean of `resolvedAt - createdAt` for incidents resolved in the selected population.
- Always display the applicable sample size.
- Never treat an unresolved incident as having zero resolution time.
- Show incident volume by service, severity, and responder.
- Show grouped-event and suppressed-duplicate counts.
- Use one documented date-window rule consistently across cards and charts.

The UI should expand the abbreviations in helper text so their meaning is unambiguous.

## 12. Product surfaces

### Command Center

- Highest-severity unacknowledged incident as the dominant action area
- Open incident, critical incident, MTTA, and MTTR summary cards
- Active incident list
- Recent event activity
- Direct claim and acknowledge actions where appropriate

### Incidents

- Filterable incident list
- Manual incident creation
- Incident detail with ownership, lifecycle actions, severity, events, workflow, notes, and timeline

### Services

- Service list and detail
- Create and edit service
- Owner, default severity, grouping window, and workflow template management
- One-time integration-key display
- Event history
- Test-event simulator

### Analytics

- Response-time cards with sample sizes
- Volume breakdowns by service, severity, and responder
- Grouping and suppression counts

The event simulator is a drawer or modal launched from a service rather than a top-level navigation destination.

## 13. Seeded demonstration

The deterministic seed tells one connected story:

1. Checkout API owns a database-latency response workflow.
2. The first Critical latency event creates incident `INC-104`.
3. A related but non-identical event is grouped into the incident.
4. A later exact duplicate is suppressed and linked to the incident.
5. A responder claims and acknowledges the incident.
6. Diagnostic and mitigation workflow steps are completed.
7. A note is added and the incident is resolved.
8. Analytics reflect its response times, grouping, and suppression data.

The baseline also includes:

- one unacknowledged active incident;
- one acknowledged active incident;
- several services and responders; and
- approximately 12-20 coherent historical incidents so analytics are meaningful.

## 14. Technical and acceptance constraints

- Preserve the sample React, Vite, Bun, Django, Django REST Framework, MongoEngine, authentication, and MongoDB stack.
- Use the existing authentication and access model. Do not introduce roles, RBAC, or a new permissions subsystem unless the repository contract requires it.
- Do not add or replace dependencies without explicit approval.
- Organize code by product feature and keep HTTP, business, and persistence concerns separate.
- Every reachable product interaction must use a real backend API and MongoDB where data is involved.
- Every public product route must have a reachable frontend consumer.
- Preserve deterministic setup, seed reset, ports, commands, and authentication conventions.
- Implement loading, empty, validation, authorization, success, disabled, and error states where applicable.
- Use responsive, keyboard-accessible interfaces and local assets only.
- Use an original visual identity rather than PagerDuty branding.
- Maintain American English in product copy and source.

## 15. Definition of done

The design is complete only when all five selected features:

- are reachable in the UI;
- call real frontend API clients;
- reach Django routes and thin HTTP handlers;
- execute business rules in services;
- persist through repositories into MongoDB;
- handle expected validation and failure states;
- are represented by coherent deterministic seed data; and
- pass the repository's static and runtime validator.

## 16. Change control

Implementation discoveries may change naming, layout, or internal code structure. Any proposal to add a collection, dependency, public feature, background process, external service, or new lifecycle state must be treated as a scope change and explicitly approved before implementation.
