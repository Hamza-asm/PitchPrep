# PitchPrep: Product Requirements Document

> Place this file at `docs/PRD.md`. The coding agent reads it together with the root `AGENTS.md`.

## 1. Overview

**PitchPrep** is a multi-agent sales research assistant. A salesperson enters a target company and gets back a one-page, source-backed prospect brief and a personalized outreach email draft in about a minute, instead of 20-30 minutes of manual research.

**What makes it different from "a research bot":**
- Every claim in the brief is tied to a source (a scraped page, a news result, or text the user pasted).
- A separate Verifier agent checks each claim against the source excerpts. Unsupported claims are removed and flagged, never silently kept.
- The system measures its own mistakes (groundedness, unsupported-claim rate, Verifier accuracy) with evaluations traced in LangSmith.

**Product goal for the MVP:** a deployed, working single-company flow with a polished landing page, live progress, a verified brief, an editable email draft, saved history, and a visible evaluation setup.

## 2. Problem

Sales development reps spend a large share of their time researching each lead before they can write a relevant message. Generic outreach gets ignored. AI research tools that browse freely tend to pick the wrong website, invent facts, and give no way to check them.

## 3. Target users

- Sales development reps and founders doing outbound.
- Small agencies and local-business sellers, where the target often has a thin web presence (a Google Maps listing and a social page rather than news coverage).

## 4. Scope

### In scope (MVP)
- Intro-first landing page that leads into the workflow.
- One-time seller profile setup (what we sell, ideal customer).
- Single-company brief generation.
- Live progress streaming while the pipeline runs.
- Source-cited brief with per-claim verification status.
- Editable email draft, regenerate email, thumbs up/down feedback.
- Saved brief history.
- LangSmith tracing and an evaluation suite.

### Out of scope (do not build)
- Batch or CSV processing (Groq free-tier limits; listed as future scope).
- Sending emails automatically. The human always reviews and sends.
- CRM integrations.
- User accounts and authentication.
- Named individual contacts. Suggest **target roles** only (for example "Head of Sales"), because scraped personal names are unreliable.
- Scraping Google Maps itself. Users paste data from it instead.

## 5. User experience

### 5.1 Landing page (`/`)

The home page must **not** open on the input form. It is an introduction to the product, and the user enters the workflow deliberately.

Required structure:
1. **Hero section:** product name, a one-line value proposition, a short supporting line, and a **single centered primary button**.
2. **How it works:** three or four steps (add the company, agents research it, claims get verified, you get a brief and email).
3. **Why you can trust it:** explain source citations and the Verifier, ideally with a small sample brief preview showing a cited claim and a verification badge.
4. **Closing section:** repeat the centered call-to-action.

Button label: use **"Let's prep your pitch"**. Acceptable alternatives are "Get started" or "Begin". Pick one and use it consistently.

Clicking the button navigates to the workflow screen at `/app`. There is no form, no input field, and no seller setup on `/`.

Design and motion rules come from the installed skills (see `AGENTS.md`). Requirements that apply regardless of style:
- Responsive from 360px wide up. Many users will be on phones.
- Light and dark mode parity if the chosen design system supports both.
- Respect `prefers-reduced-motion`.
- Accessible: semantic headings, visible focus states, sufficient contrast, keyboard operable.
- No placeholder lorem ipsum, fake logos, or invented customer testimonials or statistics.

### 5.2 Workflow screens (`/app`)

1. **Seller setup (first visit only):** what the user sells and their ideal customer. Saved, editable later.
2. **Target input:**
   - Company name (required)
   - Website link or social link (required, in its own field). Website is preferred. Facebook, Instagram, or LinkedIn is accepted when the company has no website.
   - Paste box (optional): text copied from a Google Maps listing or anywhere else (name, address, phone, category, rating, hours, website, reviews).
3. **Live progress:** stages shown as they complete: Parsing, Collecting sources, Analyzing, Matching, Writing, Verifying.
4. **Brief view:**
   - Company snapshot
   - Recent trigger events
   - Likely needs matched to the seller's product
   - Suggested target roles
   - Email draft
   - Every claim shows its source link and verification status
   - A "limited data" badge when evidence is thin
5. **Review and edit:** edit the email, regenerate it (optionally in a different tone), thumbs up or down with an optional comment.
6. **History:** list of past briefs that can be reopened.

### 5.3 Empty, loading, and error states
Every screen needs all three. Required messages include:
- Link does not appear to match the company: ask the user to confirm the link before continuing.
- Parser cannot identify a company name from the pasted text: say so and ask the user to check the input. Never guess.
- Scrape failed or blocked (common for social pages): continue with the pasted text and other sources, and mark the brief "limited data".
- Rate limit or model error: retry with backoff; if it still fails, show a clear message and keep the user's input.

## 6. Agent pipeline (LangGraph)

The source collector is a **fixed pipeline, not a free-roaming browsing agent.** The model never decides which sites to visit. It scrapes exactly the link the user supplied, and uses search only for extra context such as recent news.

| # | Node | Model (via Groq) | Responsibility |
|---|------|------------------|----------------|
| 1 | Input Parser | GPT-OSS 20B | Extract structured fields (name, location, category, website, phone, rating, reviews) from pasted text |
| 2 | Source Collector | Firecrawl + GPT-OSS 20B | Scrape the supplied link, search recent news, extract sourced excerpts into a schema |
| - | Link check | rules + light LLM check | Verify the scraped page mentions the company; if not, stop and ask the user to confirm |
| 3 | Analyst | GPT-OSS 120B | Identify trigger events and potential needs, each tied to source excerpts |
| 4 | Matcher | GPT-OSS 120B | Map needs to the seller's product, suggest target roles |
| 5 | Writer | GPT-OSS 120B | Produce the brief and email draft, citing source ids for every claim |
| 6 | Verifier | Qwen 3.8 27B | Check each claim against the source excerpts and pasted text |

**Verifier loop:**
- Supported claims pass.
- Unsupported claims go back to the Writer with feedback, up to **2 revision attempts**.
- Anything still unsupported after the limit is **removed** and the brief is flagged with an evidence-limitations note.
- The final brief carries a source verification status and source links.

**Rules for every node:**
- Inputs and outputs are Pydantic models. Use structured output or tool calling with schema validation, and retry on validation failure.
- Model IDs live in configuration (environment variables), never hard-coded. Confirm exact Groq model IDs and which ones support strict JSON schema output in the Groq console before wiring them.
- Retry Groq and Firecrawl calls with exponential backoff and a concurrency cap.
- User-pasted text is a first-class source, labeled "user-provided" in citations.
- Never invent URLs, facts, names, or numbers. If evidence is missing, say so.

## 7. Technical architecture

| Layer | Choice |
|-------|--------|
| Frontend | Next.js (App Router), TypeScript, Tailwind, deployed on Vercel |
| Backend | Python, FastAPI, Pydantic v2, LangGraph |
| Web data | Firecrawl (scrape and search) |
| LLMs | Groq-hosted GPT-OSS 20B, GPT-OSS 120B, Qwen 3.8 27B |
| Database | Supabase (Postgres) |
| Tracing and evals | LangSmith |
| Backend hosting | Render or Google Cloud Run (undecided; keep the app container-friendly either way) |

### Repository layout
```
backend/app/api         FastAPI routes
backend/app/core        config, logging, shared clients
backend/app/schemas     Pydantic models
backend/app/services    Firecrawl, Groq, Supabase, LangSmith wrappers
backend/app/workflows   LangGraph graph, nodes, prompts
backend/evals           evaluation dataset and runner
backend/tests           unit and integration tests
frontend/src            Next.js app
supabase/migrations     SQL migrations (Prioritize mcp first if connection fials then create migration files)
docs                    this PRD and other documentation
```

### API (draft)
- `GET /api/seller-profile`, `PUT /api/seller-profile`
- `POST /api/briefs`: create a run, returns a brief id
- `GET /api/briefs/{id}/stream`: server-sent events with stage updates, ending with the final brief
- `GET /api/briefs`, `GET /api/briefs/{id}`
- `POST /api/briefs/{id}/email/regenerate`
- `POST /api/briefs/{id}/feedback`

Long runs must not block a single browser request: start the run, persist progress, stream or poll for updates.

### Data model (Supabase, draft)
- `seller_profiles`: what they sell, ideal customer
- `briefs`: input fields, status, final output JSON, verification summary, limited-data flag
- `sources`: brief id, type (scraped, search, user-provided), URL, excerpt
- `claims`: brief id, claim text, source ids, verification status
- `feedback`: brief id, rating, comment

There are no user accounts in the MVP, so treat it as a single-tenant demo. Enable row level security anyway, keep all database access behind the backend, and never expose a service-role key to the browser.

### Configuration
Environment variables only, documented in `.env.example` with names and no values: Groq API key, Firecrawl API key, LangSmith key and project, Supabase URL and keys, model IDs per node, allowed frontend origin.

## 8. Evaluation

Traced in LangSmith, with a small dataset in `backend/evals` (target 10-15 companies, including social-only and thin-data cases).

| Metric | How |
|--------|-----|
| Groundedness | Share of final claims supported by source excerpts |
| Unsupported-claim rate | Claims the Verifier removed or flagged |
| **Verifier accuracy** | Run the Verifier on a hand-labeled set of known-supported and known-unsupported claims; report precision and recall |
| Relevance | Do the matched needs fit the seller's product (LLM judge plus spot checks) |
| Personalization | Does the email reference specific, real facts about the company |
| Cost and latency | Per brief |

Use code-based checks where possible, an LLM judge (Qwen 3.8 27B) for subjective scores, and manual review of selected examples. The judge shares a model with the Verifier, so the hand-labeled set is what keeps the Verifier measurement honest. User thumbs up/down are logged to LangSmith as feedback scores.

## 9. Acceptance criteria

- `/` is an intro page with a centered call-to-action that opens `/app`. No form on `/`.
- A user can set up a seller profile, submit a company with a website or social link, watch live progress, and receive a brief.
- Every claim in a brief has at least one source and a verification status. No brief contains a claim the Verifier marked unsupported.
- A wrong-company link triggers the confirmation message instead of continuing.
- Social-only and thin-data inputs produce a "limited data" brief, not fabricated detail.
- Briefs, sources, claims, and feedback persist in Supabase and appear in history.
- Runs appear in LangSmith with per-node traces; the evaluation suite runs and prints a results table.
- Backend tests pass, the frontend lints and builds, and no secrets are committed.

## 10. Suggested build order

1. Schemas, config, and backend skeleton.
2. Workflow nodes with mocked services, then real Firecrawl and Groq calls.
3. Supabase migrations and persistence.
4. API routes and streaming.
5. Landing page.
6. Workflow screens and brief view.
7. Evaluation dataset and runner, LangSmith wiring.
8. Deployment configuration and README.

## 11. Open decisions

- Backend hosting: Render or Cloud Run.
- Exact Groq model IDs, and whether each supports strict JSON schema output (otherwise use tool calling with Pydantic validation and retry).
- Whether Qwen 3.8 27B beats GPT-OSS 120B as Verifier on the labeled claim set. Test both and keep the better one.
