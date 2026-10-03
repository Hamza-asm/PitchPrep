# PitchPrep frontend

Next.js App Router, TypeScript, Tailwind, Outfit, and Geist Mono. Visual requirements live in `../docs/DESIGN.md`; product behavior lives in `../docs/PRD.md`.

## Local setup

From `frontend/`:

```sh
npm ci
npm run dev
```

Use `frontend/.env.example` to create your local `.env`. Set `NEXT_PUBLIC_API_BASE_URL` to the backend origin, without `/api` or a trailing path. Public environment variables are embedded at build time; rebuild after changing the backend origin. Provider keys and Supabase credentials belong only in the backend environment.

Start the backend separately using `../backend/README.md`. Its allowed CORS origin must match the frontend origin. Open `http://localhost:3000`.

## Screens

- `/`: product introduction, decorative mockups, pipeline explanation, and calls to open the workspace.
- `/app`: seller setup, company/link/pasted-text input, and saved brief history.
- `/app/[id]`: streamed progress with polling recovery, link confirmation, sourced brief, email editor, regeneration, and feedback.

Failed submissions retain input and reuse the same idempotency key when retried unchanged. Mutating saved briefs uses the API's expected version. Email regeneration requires saving edits first; manual email edits are identified as unverified. Claims and evidence limitations remain visible alongside the email. Source links only allow HTTP(S).

Research begins only on an explicit submission or regeneration action. There is no automatic email sending or browser access to the database.

## Verification without provider calls

```sh
npm run lint
npm run build
npm run test:e2e
```

The browser suite creates a separate production build in `.next-e2e` using a fixed, intercepted API origin, then serves it on `127.0.0.1:3100` with installed Google Chrome. Your `.env` and regular `.next` build are unchanged. Set `PLAYWRIGHT_CHANNEL=msedge` to use installed Edge instead. A clean build needs access to Google Fonts for Next.js font compilation; fonts are then served locally.

All API routes in the browser tests are intercepted with synthetic fixtures. Requests to other hosts are blocked, and service workers are disabled. No backend process, Groq, Firecrawl, Supabase, or LangSmith connection is needed by the tests. Tests cover landing accessibility and reduced motion, seller setup, submission retry, source links, email edits/copy/regeneration, feedback, confirmation, progress, connection errors, and mobile layout.

Screenshots and failure traces are written to ignored `test-results/`. On restricted Windows runners, Playwright needs permission to stop its local server process tree during teardown.

See `../docs/FRONTEND_REVIEW.md` for the verification record and remaining checks.
