# PitchPrep persistence

Applied through Supabase MCP to development project `wrkzisamhwqtqrotyqlj`.
The initial schema is recorded in Supabase migration history. The later retry
RPC/constraint update was applied directly through MCP `execute_sql`; no local
migration file was created, following `AGENTS.md`.

## Tables

| Table | Purpose |
| --- | --- |
| `seller_profiles` | One singleton seller profile |
| `briefs` | Request and seller snapshot, queued/running/final status, workflow checkpoint, progress, result, manual email edit, version, lease and trace identifiers |
| `sources` | Per-brief source IDs, origin type, URL, excerpt, collection timestamp |
| `claims` | Per-brief verified claims with nonempty source IDs |
| `feedback` | Latest thumbs rating/comment per brief, successful-result trace ID, durable delivery event ID and synchronization flag |

Sources and claims use `(brief_id, id)` primary keys. Feedback uses `brief_id` as
its key. Foreign keys reference the brief, and all foreign-key lookups have index
coverage. History and queued/running jobs have dedicated indexes.

## Access controls

RLS is enabled on all five tables. `anon` and `authenticated` have no table or
function access. There are intentionally no client RLS policies: browser access
goes through FastAPI, and the backend service role has explicit grants.
Supabase's advisor reports informational “RLS Enabled No Policy” notices for
this intentional arrangement. No security warnings remained in the final check.

All application functions use `SECURITY INVOKER` and a fixed empty search path.
Only the service role can execute them. Public execution grants were also removed
from the pre-existing `rls_auto_enable()` event-trigger helper; the trigger itself
is retained.

This follows Supabase's documented separation of
[Data API grants and row-level security](https://supabase.com/docs/guides/api/securing-your-api).

## Durable execution

`pitchprep_claim_job` uses a transaction advisory lock to allow one active run
across backend processes. A claim receives a random lease token and expiration.
The worker renews its lease while running. Every progress/checkpoint/final write
checks the token and expiration, preventing an old worker from overwriting a
later state.

Expired runs become failed with `run_interrupted`; they are never automatically
requeued. This avoids spending provider quota by replaying uncertain work after
a process crash. Graceful shutdown cancels active work and saves a failure where
the database is reachable. Queued work remains durable across restarts.

`pitchprep_save_job` saves final output, sources, and claims in one transaction.
It rejects missing claim source references; any failure rolls back the whole
write. Successful-result trace IDs are retained independently from later failed
attempts so feedback stays attached to the result being reviewed.

`pitchprep_enqueue_again` accepts link confirmation, email regeneration, or a
checkpoint retry from eligible states, with a matching version. A retry requires
a supported node name in the saved workflow state and preserves prior progress.
`pitchprep_save_email` uses the same optimistic version check to prevent stale
edits.

## Applied migrations

1. `pitchprep_persistence_and_job_queue`
2. `pitchprep_feedback_delivery_and_function_permissions`
3. `pitchprep_preserve_successful_result_trace`

## Verification performed

- Inspected table RLS, role grants, and function execution privileges.
- Tested claims under the service role, exclusive job acquisition, wrong/expired
  lease rejection, persistence of results/sources/claims, stale edit rejection,
  regeneration enqueueing, interrupted-run handling, and feedback insertion.
- Tested transaction rollback when a claim referenced a missing source, including
  absence of partial source writes.
- Checked successful trace association and ran the Supabase security advisor.

All synthetic verification rows were rolled back. No Groq or Firecrawl requests
were involved in database verification.
