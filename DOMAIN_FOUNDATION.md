# Domain foundation

This document records the domain foundation stage. Service Management has since been implemented; see [SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md) for the current service UI/API. The boundaries below describe the original foundation. It does not expose service/event/incident product routes, choose triage outcomes automatically, calculate analytics endpoints, or build product feature screens. The sample's sign-in, session, profile selection, and sign-out remain usable; the authenticated frontend is a minimal holding page.

## Four collections

| Collection | Contents and important indexes |
| --- | --- |
| `users` | User identity, bcrypt password hash, active flag, allowed profile IDs, avatar metadata. Unique email. |
| `services` | Owner ID, integration-key hash/last four, severity, grouping window, ordered workflow template. Unique integration-key hash; owner index. |
| `events` | Immutable source identity/raw payload, normalized title/severity, fingerprint/grouping key, incident/duplicate links, embedded triage decision. Unique `(serviceId, source, sourceEventId)`; service/time/grouping and incident indexes. |
| `incidents` | Lifecycle and actor timestamps, service/assignee IDs, event IDs, embedded workflow snapshot, notes, and timeline. Unique reference; service/status/time and assignee indexes. |

There are no accounts, profiles, alerts, counters, analytics, or workflow-run collections. `people`, `workspaceaccounts`, and `calendars` are recognized only as old sample collections to remove during seed reset. The legacy calendar event schema and its indexes are replaced during reset.

## Authentication compatibility

`apps/auth` retains bcrypt verification, HS256 JWTs, token claims, issuer/audience, expiry, and the workspace-token → selected-profile-token flow. Its repository now reads credentials from `users`. A selected profile is an allowed active user from that same collection. Actor IDs on incidents and owner IDs on services therefore resolve directly to those users.

The sample permits each seeded login to switch to every seeded profile; the seed preserves that access convention using `allowedProfileIds`. No roles or RBAC were added. Profile responses use an explicit safe-field projection that excludes password hashes and authorization configuration. Existing auth URLs, `/api/v1/profiles`, and frontend token-storage keys remain unchanged. Calendar-only routes were retired instead of being pointed at monitoring-event documents.

## Layers and boundaries

Each product domain lives under `backend/apps/{users,services,events,incidents}/` with `models.py`, `repository.py`, `schema.py`, and `services.py`. HTTP views/URLs exist only for the currently consumed authentication/profile routes. Shared files contain validation primitives and embedded workflow value objects, not new collections.

- **Services:** create/update validation, active-user ownership checks, guarded deletion, `secrets.token_urlsafe(32)` integration keys, SHA-256 storage, and key authentication. Creation returns the raw key to its caller once; persistence contains only the hash and last four characters. The explicit `demo_key` keyword is solely for known local seed credentials.
- **Incidents:** creation copies the service workflow into an independent snapshot. Claim/assignment does not acknowledge. Acknowledgment and resolution record actors/timestamps. Resolution requires acknowledgment, a nonempty note, and all required steps. Resolved records reject every mutation through the service and repository boundary. Escalation must increase severity and records the reason and assignment change. Steps complete in order; reopening an earlier step requires later completed steps to be reopened first. Actions cannot backdate recorded activity.
- **Events:** strict source/severity/payload validation, deep-copy preservation of raw input, canonical hashing, immutable records, unique delivery identity, and consistent incident/duplicate links. `events.services.record(...)` accepts a trusted internal triage outcome and validates it; it is not a public intake endpoint or an automatic triage engine. Identical delivery retries return the original record without adding timeline entries or duplicate counts, including after resolution. New events cannot join resolved incidents or incidents outside the service window.
- **Users:** active-user lookup and safe profile listing back the auth and actor/owner validation boundaries. Seed inputs pass the user schema; public user-management routes are deferred.

Payloads are capped at 32 KiB and eight nesting levels, with finite JSON values, safe object keys, and at most 20 string labels. Workflow templates have at most 20 consecutively ordered steps. Grouping windows are integers from 1 to 1440 minutes. The severity vocabulary is exactly `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.

Fingerprint inputs are service, source, normalized title/severity, normalized labels, and payload. The broader grouping key uses service, source, component, and alert type (falling back to normalized title). Delivery identity is excluded from fingerprinting. These deterministic helpers supply the future triage implementation; internal outcome validation already distinguishes grouping from exact duplication.

References are allocated from the highest existing `INC-` number and protected by a unique index; no counter collection was introduced. Concurrent reference conflicts return a conflict error. Cross-document transactions, distributed locks, and races between different incoming events remain outside the frozen v1 scope.

## Deterministic seed

`backend/scripts/seed.py` keeps the sample command entrypoint and delegates to `domain_seed.py`. `seed_data.py` holds human-readable users, services, credentials, and history. Defaults are fixed to **2026-09-15T12:00:00Z**; setting `DEMO_TODAY=YYYY-MM-DD` shifts the anchor explicitly. IDs, timestamps, passwords' demo hashes, key hashes, references, notes, and outcomes repeat identically for the same anchor.

The fixed bcrypt salt is for the documented local demo password only. It is not an account-creation policy. Generated service keys use Python's `secrets` module.

| Collection | Seed count |
| --- | ---: |
| users | 5 |
| services | 4 |
| events | 19 |
| incidents | 17 |

Services: Checkout API, Payments Gateway, Identity Service, and Notifications Service. All owners and responders resolve to seeded users. There are **15 resolved incidents**, one unassigned triggered incident, and one acknowledged incident with an incomplete workflow. History covers all four severities/services and all five responders. There are four grouped events and four suppressed duplicates; delivery retries do not contribute to either count.

### Checkout API story: INC-104

At the default anchor, the story takes place on September 12, 2026:

| UTC | Recorded fact |
| --- | --- |
| 09:00 | Critical database-latency event creates `INC-104`. |
| 09:02 | Related replica event groups into it with a different fingerprint. |
| 09:04 | A new delivery identity with the original payload is suppressed as an exact duplicate. |
| 09:05 | Casey Bennett claims the incident. |
| 09:10 | Casey acknowledges it. |
| 09:14 | Database diagnosis step completed. |
| 09:18 | Mitigation and checkout verification completed. |
| 09:20 | Mitigation note recorded. |
| 09:30 | Incident resolved with a required resolution note. |

Its acknowledgment duration is 10 minutes and resolution duration is 30 minutes. `INC-115` is a later active Checkout recurrence; the resolved story stays immutable. `INC-116` is an acknowledged Identity incident with its first step complete. Historical `INC-107` includes a manual severity escalation and reassignment.

Reset drops and rebuilds the four known product collections, removing old schema indexes and ad hoc data, then removes the three recognized legacy collections. It refuses to proceed if unrelated collection names exist. It never drops an entire configured application database. Runtime credentials/database URI remain environment-driven through the existing sample setup; the default database name remains `calendar_db` for setup compatibility.

## Validation

From the repository root in the sample-compatible Linux environment:

```bash
bash setup.sh --seed
cd backend
../.venv/bin/python manage.py check
../.venv/bin/python manage.py test tests --verbosity 2
```

The integration suite uses real MongoDB and only the already-declared dependencies plus Python/Django test tools. It reconnects to `mongodb://127.0.0.1:27017/incident_relay_test` by default. `MONGODB_TEST_URI` can override that address, but its database name must end in `_test` and differ from the application database. The suite removes only that dedicated test database afterward and restores the application connection.

Tests cover deterministic reset, exact collections, all references, the connected story, analytics-ready history, secret-safe authentication/profile selection, ownership/deletion/key rules, immutable workflow snapshots, lifecycle/step/escalation/chronology guards, resolved immutability, malformed and oversized payloads, duplicate source indexes, source retries, and MongoDB-backed event/incident links.

## Remaining implementation

Future work can add thin authenticated feature handlers and screens over these services. Event intake still needs automatic incident matching/outcome selection and HTTP integration-key handling. Analytics must consistently select incidents by `createdAt` in a UTC half-open date interval `[from, to)`, compute acknowledgment/resolution durations only where present, and display sample sizes. No analytics route or collection is implemented here. The inherited development signing-key fallbacks and development CORS/host configuration remain final-acceptance concerns from the baseline report.
