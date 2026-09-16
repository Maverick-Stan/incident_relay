# Service Management

Service Management is the first complete product slice. Sign in with the existing demo credentials, select a profile, and use the service directory to view, create, edit, or delete unused services. No dependencies or collections were added.

## UI

The React feature lives in `frontend/src/features/services`. It uses hooks and the existing authenticated fetch client. The directory shows owners, severities, grouping windows, and workflow counts. Details show the full configuration and ordered workflow. The form supports owner selection, all four severities, a 1–1440 minute grouping window, and up to 20 steps with title, instructions, required flag, move-up/down, and removal controls.

Loading, retryable list errors, empty directory, empty workflow, validation errors, save/delete progress, success notices, not-found responses, and deletion conflicts have explicit states. Native field constraints catch basic errors; backend errors remain authoritative. Delete requires an inline confirmation. Navigation is disabled during saving/deleting and while the one-time key awaits dismissal.

## Authenticated API

Every endpoint requires the sample workspace authentication and selected-profile bearer token. No roles or owner-only permission system were introduced.

| Method | Route | Result |
| --- | --- | --- |
| GET | `/api/v1/services` | `200`, `{data: [service, ...]}` sorted by name and ID |
| POST | `/api/v1/services` | `201`, `{data: {service, integrationKey}}` |
| GET | `/api/v1/services/{id}` | `200`, `{data: service}` |
| PATCH | `/api/v1/services/{id}` | `200`, `{data: service}` |
| DELETE | `/api/v1/services/{id}` | `204` when unused; `409 SERVICE_IN_USE` when events or incidents reference it |

Create/edit fields: `name`, `description`, `ownerId`, `defaultSeverity`, `groupingWindowMinutes`, and `workflowTemplate`. Each workflow step accepts `title`, `instructions`, `order` (consecutive from one), and boolean `required`. PATCH is partial and must contain at least one recognized field. Owners must be active users. Unknown fields and invalid values return `400 VALIDATION_ERROR` with field errors. Missing services/owners return 404; malformed IDs return 400. Existing incident snapshots never change when templates are edited.

## Integration key handling

Creation uses `secrets.token_urlsafe(32)` (256 bits of entropy). MongoDB stores only the SHA-256 hash and final four characters. An explicit response serializer omits the hash from every endpoint. The raw key is returned only by the successful creation response with `Cache-Control: no-store`; subsequent reads and edits return only its last four characters. Service edits do not rotate the key.

The UI holds the raw key only in component memory, supports copying it, and clears it on dismissal. It is never put in URLs, local/session storage, or application logs. Reloading or leaving the page loses the raw key; there is no retrieval or rotation endpoint in this slice. The inherited auth tokens continue to use the sample's storage behavior.

## Verification

In the sample-compatible Linux environment:

```bash
bun install && bash setup.sh --seed
cd backend
../.venv/bin/python manage.py check
../.venv/bin/python manage.py test tests --verbosity 2
cd ../frontend
bun run build
```

All 27 backend integration tests passed against real MongoDB, including four new UI-facing API tests. Coverage includes anonymous/session-only rejection; list/detail; create/edit round trips; entropy-length and hash persistence; omission of raw keys and hashes on later reads; workflow snapshot preservation; invalid payloads; empty lists; missing resources; successful unused deletion; and conflict responses for used services. Existing domain/auth tests remain green.

Browser verification against the running Django/Vite app confirmed demo sign-in, seeded service cards, creation with a workflow, one-time key display/dismissal, server validation feedback, and editing the owner and grouping window. Django system checks and the production frontend build passed. External evidence is kept in the workspace's `domain-evidence` directory.

The existing startup command resets known seed collections. Development signing-key defaults, CORS/host settings, and cross-document concurrency limits remain inherited constraints documented in the foundation. Automatic event intake, incidents UI, and analytics are outside this slice.

Live HTTP checks through Vite's `/api` proxy also passed: sign-in/profile selection, list/detail, creation with workflow, persisted owner/severity/window edits, key omission on subsequent reads, 400 validation, 409 used-service deletion, 204 unused-service deletion, and 404 after deletion. Test-created services were removed, leaving the four seeded services. Evidence: `domain-evidence/service-http-smoke.json` outside the application folder.
