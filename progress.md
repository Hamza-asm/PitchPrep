# PitchPrep project progress

Last updated: **2026-10-03**

The core application is implemented: backend research, persistence, API, landing page, and workflow screens. The main remaining work is the evaluation suite, controlled live integration verification, and deployment.

This tracker follows [docs/PRD.md](docs/PRD.md). **Implemented** means the code exists; **verified** identifies the checks already performed. Offline tests and mocked browser journeys do not establish live provider compatibility or research quality.

## Phase overview

| PRD phase | Implementation status | Remaining work |
| --- | --- | --- |
| 1. Schemas, configuration, backend skeleton | Implemented; local integration verified | None for this phase |
| 2. Workflow nodes and provider integrations | Implemented; offline verified | Deliberate live Groq/Firecrawl smoke test and output-quality review |
| 3. Supabase persistence | Applied to the development project; local and deployed API transport verified | Verify a complete live research run and durable result persistence |
| 4. API routes and streaming | Implemented; offline coverage | Exercise the browser-to-backend-to-database flow with a real run |
| 5. Landing page | Implemented; frontend checks passed | Final user review and any requested polish |
| 6. Workflow screens and brief view | Implemented; mocked browser checks passed | Live integration, physical-device and accessibility review |
| 7. Evaluation dataset, runner, LangSmith wiring | Tracing/feedback wiring implemented; evaluation suite not implemented | Dataset, labeled verifier cases, metrics, runner, results, and live trace confirmation |
| 8. Deployment configuration and README | Render configuration deployed; basic frontend/backend routes verified | Complete live research verification, hosted access review, and operational sign-off |

## Completed work

### Project setup and configuration

- [x] Established the PRD, agent instructions, design specification, and repository structure.
- [x] Installed project skills and recorded them in `skills-lock.json`.
- [x] Added backend dependencies, including LangGraph; Firecrawl uses direct HTTP calls through HTTPX.
- [x] Created frontend and backend `.env.example` files with blank configuration values.
- [x] Cleaned ignore rules and allowed environment examples to be tracked.
- [x] Implemented environment-backed backend settings and per-node model configuration.
- [x] Kept provider credentials and Supabase service-role access on the backend.

These items describe setup already completed. They do not certify that every current local environment value is valid.

### Backend research pipeline

- [x] FastAPI application factory, lifecycle, CORS, and local health endpoint.
- [x] Pydantic models for inputs, workflow state, model outputs, citations, and API responses.
- [x] Input Parser, Source Collector, link check, Analyst, Matcher, Writer, and Verifier.
- [x] Fixed source collection: scrape the supplied link and search for recent news context.
- [x] User-pasted text retained as a labeled source.
- [x] Company/link mismatch pauses for explicit confirmation.
- [x] Missing-input and limited-data paths for insufficient or blocked sources.
- [x] Structured-output validation and bounded retries on schema failures.
- [x] Provider backoff, timeouts, and shared concurrency limits.
- [x] Source-reference and extracted-quote checks.
- [x] Verification of brief claims, email subject, and email paragraphs.
- [x] Writer revision loop capped at two attempts; remaining unsupported units removed and limitations recorded.
- [x] Email-only regeneration reuses saved evidence and preserves verified brief claims.
- [x] LangSmith tracing wrapper with hidden inputs/outputs.
- [x] Failed-stage retry resumes from saved checkpoints and reuses completed sources/stages.
- [x] Groq strict-schema sanitization preserves field names, inlines `$ref` definitions, and keeps Pydantic validation local.
- [x] Groq diagnostics classify request rejection, authentication, model-not-found, rate-limit, truncation, and local validation failures without logging prompts or responses.
- [x] GPT-OSS calls use low reasoning effort, per-node output budgets, and safe token-usage metadata logging.
- [x] Persisted analysis checkpoints remain readable when older runs contain larger finding lists.

Implementation: [backend/app](backend/app). Operational details: [backend/README.md](backend/README.md).

### Supabase and durable execution

- [x] Applied `seller_profiles`, `briefs`, `sources`, `claims`, and `feedback` tables through Supabase MCP.
- [x] Enabled RLS and restricted application database access to the backend service role.
- [x] Added transactional database functions for job acquisition, progress/results, retries of eligible actions, and email edits.
- [x] Persisted job checkpoints, versions, leases, and trace associations.
- [x] Limited execution to one active job across backend processes.
- [x] Added lease renewal and protection against writes by expired workers.
- [x] Saved final output, sources, and claims atomically.
- [x] Added optimistic version checks for edits, confirmation, and regeneration.
- [x] Preserved prior results when email regeneration fails.
- [x] Recorded interrupted runs as failed instead of automatically replaying provider calls.
- [x] Added durable feedback delivery state for LangSmith scores.
- [x] Previously verified database grants, leases, rollback behavior, and persistence through MCP using rolled-back synthetic rows.

Details and applied migration names: [docs/DATABASE.md](docs/DATABASE.md). Remote database state was not rechecked while creating this tracker.

### API and frontend workflow

- [x] Seller-profile read/save routes.
- [x] Research submission with idempotency support.
- [x] Paginated brief history and individual brief retrieval.
- [x] Persisted SSE snapshots and frontend polling recovery.
- [x] Link confirmation, manual email saving, email regeneration, and feedback routes.
- [x] Introductory `/` landing page with the primary action leading to `/app`.
- [x] Static, `aria-hidden` landing mockups with no real form controls.
- [x] Seller setup and editing.
- [x] Company name, website/social URL, and optional pasted-context input.
- [x] Six-stage progress display, confirmation, and failure recovery.
- [x] Brief sections, source links/excerpts, verification badges, and evidence-limitations notes.
- [x] Email editor, copy, save, and tone-based regeneration.
- [x] Manual edits identified as not automatically verified.
- [x] Feedback controls and saved history navigation.
- [x] Loading, empty, and error states.
- [x] Responsive layouts, keyboard focus, reduced motion, and mobile navigation.
- [x] Input retained after submission failures; unchanged retries reuse the idempotency key.
- [x] Public API-origin validation with a clear setup error for malformed configuration.
- [x] Workflow-start warning explains shared demo data, free-tier Groq limits, blocked links, and limited evidence.

Contracts: [docs/API.md](docs/API.md). Frontend guide: [frontend/README.md](frontend/README.md).

### Documentation and checks already performed

- [x] Detailed [repository README](Readme.md) with the supplied thumbnail and tech-stack badges.
- [x] Architecture and agent workflow diagrams; both parsed and rendered with Mermaid after correcting the reserved node ID.
- [x] Backend, frontend, API, database, and design documentation.
- [x] Offline backend tests passed during the backend phase.
- [x] Frontend lint and production build passed during the frontend phase.
- [x] Seven Playwright journeys passed using a separate production test build and intercepted API responses.
- [x] Automated accessibility checks found no violations in the tested landing, input, and brief states.
- [x] Tested 360px layouts, increased input-screen text size, and reduced-motion behavior.
- [x] Inspected desktop/mobile screenshots during frontend implementation.
- [x] Phase 2 focused provider/workflow verification: configured model IDs and Firecrawl endpoint were read without secrets; schema, workflow, repository, and frontend checks passed for the changed slices.

Verification record: [docs/FRONTEND_REVIEW.md](docs/FRONTEND_REVIEW.md).

These are previous observed results, not fresh test executions for this documentation update. Repeat the relevant checks after subsequent code changes.

## Completion criteria

The project is complete when the PRD acceptance criteria are demonstrated in the deployed application:

- [ ] Landing page opens the workflow deliberately, with no working form on `/`.
- [ ] Seller setup, company submission, live progress, and final brief work together in the deployed flow.
- [ ] Retained claims carry valid sources and verification statuses; unsupported units are removed.
- [ ] Wrong-company links require confirmation, and thin evidence produces explicit limitations.
- [ ] Briefs, evidence, edits, and feedback persist and remain accessible through history.
- [ ] Email editing/regeneration and source review work without automatic email sending.
- [ ] Runs, node traces, and numeric feedback are confirmed in LangSmith.
- [ ] The evaluation suite runs and produces documented results, including labeled Verifier precision/recall.
- [ ] Required tests, lint, and build pass for the release being reviewed.
- [ ] Deployment/access decisions and operational instructions are documented, with credentials excluded from tracked files.

This checklist represents final integrated acceptance. Several individual features are already implemented and tested offline, but those boxes stay open until the complete deployed flow is verified.

## Scope boundaries

Batch/CSV processing, automatic email sending, CRM integrations, user accounts, named-contact scraping, and direct Google Maps scraping remain outside this MVP. They are not tasks required for completion.

## Remaining Work and Reasons

| Work item | Why it remains incomplete | Next action |
| --- | --- | --- |
| Live Groq and Firecrawl compatibility smoke test | Live provider calls can consume quota and are explicitly gated on Hamza's approved request budget. Offline mocks cannot certify model IDs, provider response modes, or research quality. | Approve a bounded live request budget, then run one end-to-end case. |
| Evaluation dataset and runner | `backend/evals/` has no completed dataset, labeled verifier cases, scoring metrics, report writer, or offline evaluation tests yet. | Build the offline schemas, fixtures, metrics, runner, and documentation. |
| Full live application verification | Persistence, progress streaming, history reopening, thin-data behavior, regeneration, feedback delivery, and LangSmith spans require an approved live research run. | Use the approved smoke run to verify the complete browser-to-provider flow. |
| Final user-facing review | Automated browser checks cover representative states, but Hamza's product review, screen-reader pass, physical-device check, second-browser check, and Lighthouse review are still outstanding. | Review the running app and address concrete findings within PRD scope. |
| Deployment | Render frontend and backend are reachable, and basic backend routes return HTTP 200; the complete hosted research flow is not yet verified. | Run an approved live smoke test, then verify SSE, persistence, feedback, and worker behavior. |

Phase 1 verification on 2026-10-03: `GET /api/health`, `/api/seller-profile`, and `/api/briefs?limit=1&offset=0` returned HTTP 200; the frontend origin returned HTTP 200. No secrets or saved record contents were printed.

Phase 2 result on 2026-10-03: provider/workflow code was verified offline; configured model IDs and the Firecrawl endpoint were read without secrets; `46 passed` backend tests. No live provider request was made because the required request budget was not specified.

Deployment verification on 2026-10-03: `https://pitchprep-1.onrender.com` returned HTTP 200; the corrected backend `https://pitchprep.onrender.com` returned HTTP 200 for `/api/health`, `/api/seller-profile`, and `/api/briefs?limit=1&offset=0`. A full hosted research run has not yet been verified.

The completion checklist above remains intentionally unchecked for requirements that depend on live verification or deployment; those requirements are represented here with their blocking reason rather than being marked complete from mocked results.

Update this file after each phase with the implementation changes, checks actually run, observed results, unresolved issues, and next action. Do not mark live verification or deployment complete from mocked results.

## Retry and token usage update

- [x] Failed workflow nodes are saved as checkpoints; retry resumes at that node and reuses completed outputs and sources.
- [x] Firecrawl source fetching is separated from model-based evidence extraction, preventing later Groq failures from scraping again.
- [x] “Edit company details” opens the form without starting work. A new full run begins only after explicit form submission.
- [x] No-source pauses can retry source collection alone.
- [x] Interrupted runs without a saved node infer it from persisted progress; the retry button shows a visible 90-second countdown before enabling.
- [x] Reduced model context and output budgets: parser input 4,000 characters, collector excerpts 1,200 characters, four verified quotes of at most 700 characters, fewer news snippets, and per-node output-token caps. Groq 429 responses are not automatically retried.
- [x] Supabase development RPC and job-kind constraint updated to permit checkpoint retries; database schema/function definition verified via MCP.
- [x] Frontend `npm run lint` and `npm run build` pass for the countdown and retry UI update.
- [x] Focused backend software checks for retry/schema/token changes passed; no Groq or Firecrawl calls were made by the test suite.
- [x] Older saved workflow states retain their original list-size compatibility limits; separate constrained schemas keep new model output budgets in place.

## 2026-10-04 Writer validation follow-up

A manual deployed run for Linear reached Writing and failed with `invalid_model_output` on repeated stage retries. The screenshot establishes that earlier stages completed, but does not identify which Writer fields failed validation. The deployed backend's allowlisted `Groq usage node=writer` and `Groq output failed local schema validation node=writer` log lines are needed for the exact cause; no additional live provider requests were made during this follow-up.

Locally, Groq schema retries now include the failed field paths and error types in the correction instruction, and the public error text distinguishes schema validation from output truncation. Offline tests were updated for the existing no-retry-on-429 behavior and the bounded Writer revision loop. `python -m pytest -q` in `backend/` passed: **49 passed**. These changes remain in the working tree and are not deployed.

The provided Render excerpt contained startup and HTTP access lines only. Application logging is now explicitly routed to stdout, with safe per-stage run ID, node, status, and error-code records. `python -m pytest -q` passed after this addition: **50 passed**. The deployed failure still requires runtime logs from a run after these local changes are deployed; no new live run was made here.

The subsequent runtime log identified the Linear Writer failure precisely: two Groq completions ended normally (`finish_reason=stop`), but `claims.3.source_ids:too_short` failed local validation both times. The Writer now discards an uncited model claim before building the strict persisted draft, records an evidence-limitation note, and marks the brief as limited data. All retained claims still require source IDs and Verifier approval. Full offline backend suite: **51 passed**. A new hosted retry after deployment is still needed to confirm the live result.
