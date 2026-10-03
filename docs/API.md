# Backend API

The current API is a single-tenant demo without user accounts, as specified in
the PRD. All callers share the seller profile and history. Database credentials
stay in the backend. CORS is restricted to `FRONTEND_ORIGIN`; CORS is not an
authentication boundary. Deployment access controls remain part of the deployment
decision.

Run instructions are in [backend/README.md](../backend/README.md). FastAPI exposes
the exact schemas at `/docs` and `/openapi.json`.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Local liveness; no provider checks |
| GET | `/api/seller-profile` | Profile or `null` before setup |
| PUT | `/api/seller-profile` | Save `offering` and `ideal_customer` |
| POST | `/api/briefs` | Save a queued run; return HTTP 202 with `id`, `status`, `version` |
| GET | `/api/briefs?limit=20&offset=0` | Summary page with `items` and `next_offset`; maximum limit 100 |
| GET | `/api/briefs/{id}` | Input, progress, status, verified result, manual email edit, version, errors |
| GET | `/api/briefs/{id}/stream` | SSE snapshots that can be reconnected |
| POST | `/api/briefs/{id}/confirm-link` | Confirm a mismatched link and enqueue continuation |
| POST | `/api/briefs/{id}/retry` | Resume only the saved failed workflow node; requires `expected_version` |
| PUT | `/api/briefs/{id}/email` | Save the human-edited subject/body |
| POST | `/api/briefs/{id}/email/regenerate` | Enqueue email-only regeneration using saved evidence |
| POST | `/api/briefs/{id}/feedback` | Save rating `1` or `-1` and optional comment; HTTP 204 |

## Start and observe a run

Save the seller profile first. Submit `company_name`, `target_url`, and optional
`pasted_text`. The initial request should leave `link_confirmed` false.

Send a newly generated UUID in the `Idempotency-Key` header for each deliberate
submission. Reuse that UUID when retrying the same HTTP submission. Repeated keys
return the existing run and do not enqueue another one; different input with the
same key returns 409. Without the header, each POST creates a new run.

Creation returns before research begins. Poll the detail route or open the SSE
route. Each event contains a complete public detail snapshot:

- `progress`: the run is queued or running.
- `result`: a terminal or paused state; inspect `status` for completed,
  needs_input, needs_confirmation, or failed.
- `unavailable`: saved progress could not be read; reconnect or poll later.

Event IDs are the persisted version number. `Last-Event-ID` is accepted, and
reconnecting returns the current snapshot. A terminal snapshot is always emitted
so the client can close its EventSource. Closing the stream does not cancel the
research job. Internal workflow state, seller snapshots, worker leases, and trace
IDs are excluded from public detail responses.

## Confirmation, editing, and regeneration

Link confirmation requires `{"confirmed": true, "expected_version": N}` using
the latest detail version. It is accepted only for `needs_confirmation`. Saved
sources are reused; collection is not repeated. To correct a name or link, submit
a new run with a new idempotency key.

For a failed run, `POST /api/briefs/{id}/retry` resumes its saved failed node and
reuses earlier outputs. Firecrawl collection and evidence extraction are separate
checkpoints, so model failures after collection do not scrape again. If source
collection found no usable sources, the same route retries just that collection
step. “Edit company details” only opens the form; submitting it deliberately
creates a new research run.

Email edits require `subject`, `body`, and `expected_version`. The edit is saved
separately as `email_edit`; the cited generated email remains in `result.email`.
The UI must distinguish a human edit from verified generated text.

Regeneration requires `expected_version` and a tone: `professional`, `friendly`,
or `concise`. Only Writer and Verifier run. Previous result/edit remain available
until successful completion, at which point the new generated email replaces
the old generated email and clears the manual edit. Previously verified brief
claims stay unchanged. The regeneration verification summary counts email units.

Stale versions or invalid state transitions return 409. A failed generation keeps
the submitted input. A failed regeneration also keeps the previous result/edit.
No interrupted operation is automatically retried against model providers.

## Errors

Validation errors return 422 with field locations and safe messages, excluding
raw input. Missing brief IDs return 404. Missing seller setup or version conflicts
return 409. Database availability failures return 503. Provider failures are saved
on the run with a safe message and appear in detail/stream responses.

## Verification

The offline suite exercises these routes with ASGI requests, the real LangGraph
workflow, fake provider responses, and an in-memory repository. The HTTP adapter
uses mock transports in tests. Live database transactions were checked separately
through MCP. A full live-provider run has not been performed.
