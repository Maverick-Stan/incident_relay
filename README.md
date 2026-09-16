# Incident Relay

Incident Relay is an explainable incident-response command center for small operations teams. It covers the full path from an inbound monitoring event to a resolved incident with a clear audit trail. Five capabilities are implemented end to end:

- **Service Management** — define services with an owner, a hashed integration key, a grouping window, and an ordered response-workflow template.
- **Event intake & triage** — a public, integration-key-authenticated ingestion endpoint validates and normalizes each delivery, enforces delivery idempotency on `(service, source, sourceEventId)`, and synchronously triages each genuinely new event into exactly one disposition — `CREATED_INCIDENT`, `GROUPED`, or `SUPPRESSED_DUPLICATE` — each with a plain-language reason.
- **Incident Management** — manual creation, claim/assign (ownership kept separate from status), the enforced `TRIGGERED → ACKNOWLEDGED → RESOLVED` lifecycle, notes, manual escalation, and note-gated resolution, with every meaningful action written to the timeline.
- **Incident Workflows** — each incident receives an immutable snapshot of its service's workflow template; responders complete or undo steps with actor and timestamp; required steps gate resolution; resolved incidents are read-only.
- **Post-incident analytics** — arithmetic mean time to acknowledge and mean time to resolve (with sample sizes, excluding unresolved incidents from resolution time), incident volume by service, severity, and responder, and grouped/suppressed event counts — all computed live from stored facts under one documented date-window rule.

A **Command Center** landing page composes these APIs into a single operational overview led by the highest-severity unacknowledged incident.

Design and provenance references: [FINAL_DESIGN.md](FINAL_DESIGN.md), [DOMAIN_FOUNDATION.md](DOMAIN_FOUNDATION.md), [SERVICE_MANAGEMENT.md](SERVICE_MANAGEMENT.md), and [SAMPLE_README.md](SAMPLE_README.md).

## Stack

React 19.2.4, React DOM 19.2.4, Vite 8.2.2, and Bun workspaces on the frontend; Python 3.12, Django 5.1.5, Django REST Framework 3.15.2, and MongoEngine 0.29.1 with MongoDB 8+ on the backend. React hooks manage UI state and a shared native `fetch` client handles HTTP against `/api/v1`. Per-feature schemas validate and normalize requests. Authentication uses bcrypt password hashes and PyJWT HS256 bearer tokens in a two-step flow — workspace login, then selection of an allowed profile — reading credentials and selectable profiles from the same `users` collection. All state persists in four MongoDB collections (`users`, `services`, `events`, `incidents`); workflow snapshots, notes, timelines, and triage decisions are embedded, and analytics are derived at read time rather than stored.

## Structure

```text
frontend/src/features/auth        # Workspace login
frontend/src/features/profiles    # Profile selection
frontend/src/features/command     # Command Center overview
frontend/src/features/services    # Service Management
frontend/src/features/events      # Event intake, triage results, Send Test Event, history
frontend/src/features/incidents   # Incident list, detail, lifecycle actions, workflow
frontend/src/features/analytics   # Post-incident analytics
frontend/src/shared/              # fetch API client, shared components, utilities
backend/apps/auth, backend/apps/users   # Authentication and profiles
backend/apps/services             # Service Management
backend/apps/events               # Ingestion, validation, synchronous triage
backend/apps/incidents            # Incident lifecycle, workflow, notes, timeline
backend/apps/analytics            # Derived metrics
backend/apps/shared               # Auth decorators, domain helpers, errors, health
backend/calendar_backend/         # Django settings and URL composition
backend/scripts/                  # Deterministic seed and coherence assertions
hackerrank.yml                    # Authoritative install/run commands and protected paths
setup.sh                          # Env files, MongoDB readiness, Python setup, seed/reset
skills/validate/                  # Read-only acceptance validator
```

## Prerequisites and setup

Use a Linux-compatible shell with Bash, Bun 1.3+, Python 3.12, uv, and MongoDB 8+ reachable on `127.0.0.1:27017`. The declared commands use `.venv/bin/python`, so a native Windows virtualenv does not satisfy them; use a compatible Linux environment. Preserve LF line endings for shell scripts.

From the repository root, run the exact HackerRank commands:

```bash
bun install && bash setup.sh --seed
bun start
```

`setup.sh` copies any missing `.env` from the committed `*.example` files, creates `.venv`, installs the pinned Python requirements, ensures MongoDB is reachable (starting a local `mongod` if needed), and seeds the database. `bun start` runs setup (which reseeds) and then starts Django and Vite together.

Frontend: [localhost:3000](http://localhost:3000). Backend: [localhost:8000](http://localhost:8000). Health: [api/v1/health](http://localhost:8000/api/v1/health) reports MongoDB connectivity separately from API liveness (HTTP 200 with `"database":"connected"`, or 503 `disconnected`). Vite proxies `/api` to port 8000. Both servers bind `0.0.0.0` with their development reloaders.

## MongoDB and reset behavior

The backend uses the database named in `backend/.env` (`calendar_db` in the committed example) on `127.0.0.1:27017`. Only four product collections are persisted: `users`, `services`, `events`, `incidents`. Every seed and every full start deterministically **resets** these four collections and drops recognized legacy sample collections (`people`, `workspaceaccounts`, `calendars`); any local edits to product collections are discarded on the next start. The reset **refuses** to run when the database contains any unrelated collection. IDs, timestamps, and demo password hashes repeat deterministically. The demo anchor is fixed at `2026-09-15T12:00:00Z`; set `DEMO_TODAY=YYYY-MM-DD` to shift it.

## Seeded demo access

```text
Email:    alex.morgan@calendar.com
Password: password123
```

The two-step login-then-profile-selection flow is intact; all five seeded users are selectable profiles for the demo login (no roles or RBAC were introduced). Service owners and incident responders reference these users directly.

Seed baseline: **5 users, 4 services, 19 events, 17 incidents**. Incidents include 15 resolved plus two active — one `TRIGGERED` (`INC-115`) and one `ACKNOWLEDGED` (`INC-116`). Events break down as 11 created, 4 grouped, and 4 suppressed duplicates. The connected Checkout API story is `INC-104` (resolved; three events spanning `CREATED_INCIDENT`/`GROUPED`/`SUPPRESSED_DUPLICATE`, two completed workflow steps, one note). Demo integration keys are declared in `backend/scripts/seed_data.py`; MongoDB stores only their SHA-256 hash and last four characters.

## Commands and checks

| Command | Purpose |
| --- | --- |
| `bun install && bash setup.sh --seed` | Install both layers, ensure MongoDB, and reset/seed. |
| `bun start` | Reseed, then run Django (8000) and Vite (3000). |
| `bun run seed` | Restore the deterministic seed and run its coherence assertions. |
| `bun run dev:backend` | Start Django only on port 8000. |
| `bun run dev:frontend` | Start Vite only on port 3000. |
| `cd frontend && bun run build` | Build the production frontend. |
| `cd backend && ../.venv/bin/python manage.py check` | Run Django system checks. |
| `cd backend && ../.venv/bin/python manage.py test tests --verbosity 2` | Run the 39 real-MongoDB integration tests in a dedicated `_test` database. |

The repository ships a Prettier config but no formatter dependency or lint script; do not add dependencies to supply missing checks. `skills/validate/` contains the read-only acceptance validator.

## Provenance and constraints

Derived from `ProblemSetters/coderepo-react-django-calendar` (commit `6979b6ad70e3431066a953b0edfb386695dc2019`). Declared dependency versions and the Bun dependency graph must remain unchanged; the pinned Python requirements have no transitive lockfile. Development signing-key defaults and permissive development CORS and allowed-hosts are inherited and are not production security claims. Event intake is synchronous with no queues, workers, AI, or background jobs; delivery idempotency is backed by a unique `(serviceId, source, sourceEventId)` index. Cross-document transactions and distributed race handling are outside v1 scope.
