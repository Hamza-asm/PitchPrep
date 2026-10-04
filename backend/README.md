# PitchPrep backend

## Current milestone

The backend includes the research workflow, Supabase persistence, a durable job
queue, and API routes for seller setup, generation, history, progress streaming,
link confirmation, failed-stage retries, email editing/regeneration, and feedback.
The evaluation suite is the next milestone.

See [API contracts](../docs/API.md) and [database design](../docs/DATABASE.md).

## Run locally

From `backend/`, with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

For Render, set the service root directory to `backend`, use
`pip install -r requirements.txt` as the build command, and use this start
command so Uvicorn calls the application factory:

```text
uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT
```

The repository also includes `render.yaml` with these settings and the
`/api/health` health-check path.

`GET /api/health` checks application liveness only. It does not contact providers.
Starting the server also starts the queue worker. Queued generation requests use
the configured Groq and Firecrawl credentials. Merely opening API docs or reading
history does not create a generation request. Offline tests inject fake providers.

Settings load `backend/.env`. `.env.example` lists required configuration names
with blank values. Set `FIRECRAWL_BASE_URL` to the provider's v2 API base URL
(`https://api.firecrawl.dev/v2`). Each Groq model comes from its corresponding
`GROQ_MODEL_*` variable. Secrets stay on the backend.

Optional environment settings and defaults:

| Setting | Default |
| --- | --- |
| `APP_ENV` | `development` |
| `PROVIDER_MAX_ATTEMPTS` | `2` total attempts |
| `SCHEMA_MAX_ATTEMPTS` | `2` total generations |
| `GROQ_CONCURRENCY` | `1` per shared client |
| `FIRECRAWL_CONCURRENCY` | `1` per shared client |
| `RETRY_BASE_SECONDS` | `2` |
| `RETRY_MAX_SECONDS` | `30` |
| `PROVIDER_TIMEOUT_SECONDS` | `45` |
| `MODEL_MAX_OUTPUT_TOKENS` | `2048` maximum; per-node hard caps range from 300 to 1400 |
| `NEWS_RESULT_LIMIT` | `2` |
| `PARSER_INPUT_CHARS` | `4000` characters sent to the Parser; full user text remains saved as evidence |
| `COLLECTOR_EXCERPT_CHARS` | `1200` characters per source sent to the Source Collector/Link check |
| `EVIDENCE_QUOTE_LIMIT` | `4` verified excerpts shared with later model stages |
| `EVIDENCE_QUOTE_CHARS` | `700` characters maximum per retained quote |
| `SOURCE_MAX_CHARS` | `8000` per web source |
| `WORKER_POLL_SECONDS` | `2` |
| `WORKER_LEASE_SECONDS` | `120` |
| `STREAM_POLL_SECONDS` | `1` |

Saved workflow-state schemas retain the prior list-size limits so older briefs
remain readable. Separate constrained schemas keep new Analyst, Matcher, Writer,
and Verifier responses within the current token budget.

`GROQ_BASE_URL` and `LANGSMITH_ENDPOINT` may override SDK endpoint defaults.
Provider retries and schema retries are separate bounded layers: a node may
make up to four requests with the defaults if both kinds of failures occur.
A provider cooldown longer than the configured maximum ends the attempt rather
than retrying early. Shared client instances must be reused across runs so their
concurrency limits apply across those runs.

## Workflow behavior

`ResearchWorkflow.run(request, seller, on_progress=...)` returns validated state.
The application lifespan shares one instance of each service across runs, starts
the research worker, and closes clients on shutdown. Inject test doubles into
`create_app(settings, repository=..., workflow=...)` for offline development.
Configured LangSmith traces are flushed on shutdown.
Trace inputs and outputs are hidden to avoid sending pasted text or source bodies.

The collector scrapes only the supplied link and searches for news snippets.
Missing company names and mismatched links pause the pipeline. Blocked pages can
continue with pasted text or news, with a limited-data flag. Every brief claim,
email subject, and paragraph gets a verification decision. Missing decisions,
invalid citations, and fabricated evidence quotes fail verification. After at
most two Writer revisions, unsupported units are removed and flagged.

The model still performs semantic verification; matching an evidence quote is
an additional structural check, not proof of the model's judgment. Live output
quality and provider compatibility need a separately authorized smoke test.

Groq HTTP failures log only the workflow node, HTTP status, and provider request
ID; prompts, response bodies, credentials, and pasted data are not logged.
Application logs are written to stdout for hosted runtime logs. Each research
stage records its start and finish with a run ID, node, and status; failures
record a safe error code. Groq usage and local schema failures record token
counts, finish reason, and validation field paths/error types, without response
content. Use the runtime log view after a run, rather than deployment build logs.

Runs and progress are saved outside the browser request. The database permits
one active run across workers. A lost lease cancels work; interrupted runs become
failed and are not automatically retried. Link confirmation resumes at Analyst.
Email regeneration uses saved sources and reruns Writer/Verifier only, keeping
the verified brief claims intact. Manual email edits are stored separately from
the verified generated result and carry no verification guarantee.

Failed workflow stages can be resumed from the saved node checkpoint. Source
fetching and evidence extraction are separate stages, so a later model failure
does not repeat Firecrawl. “Edit company details” only opens the editable form; a
new run starts only after the user submits it. Groq 429 responses are not retried
automatically. Per-stage completion-token caps and compact evidence payloads
reduce prompt and output usage; they cannot guarantee a request fits a provider
rate window in every case.

Feedback is saved first. A background delivery loop sends numeric scores to the
corresponding successful LangSmith trace; comments remain in Supabase. Delivery
failures leave feedback pending. This delivery path has offline tests but has not
been exercised against live LangSmith during this phase.

## Offline tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use synthetic credentials and data, injected model doubles, and HTTP mock
transports. Real HTTP transports are blocked, and LangSmith tracing is disabled.
They do not call Groq, Firecrawl, Supabase, or LangSmith.

Database functions and access controls were separately verified through Supabase
MCP using transactions that rolled back all synthetic test rows. No live Groq or
Firecrawl smoke test has been run. The application Data API transport is covered
with mocks; database behavior is verified through MCP.
