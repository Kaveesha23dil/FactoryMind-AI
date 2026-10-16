# Optional free-hosting deployment — FactoryMind AI

Prepared 2026-10-16. This is an **operator procedure, not a deployment record**. No resources, accounts, schema, destination records, or live Gemini requests were created by this work. Obtain approval before provisioning or applying migrations. Free-plan eligibility and account restrictions must be checked in the provider dashboards; zero future cost cannot be guaranteed.

## Architecture and migration map

| Concern | Existing local / Google Cloud path | Optional portable path |
|---|---|---|
| Frontend | `apps/web/src/app`, Next.js SSR, server components, dynamic routes and API routes | Same Next.js server; Render native Node service, or eligible Vercel Hobby |
| Backend | `services.api.main:app` | Same FastAPI entry point, repository-root Render Python service |
| API proxy | `apps/web/src/app/api/backend/[...path]/route.ts`, Google-signed backend ID tokens | Server session cookie forwarded as the individual Supabase user JWT; backend independently verifies membership |
| Persistence | SQLite locally; `firestore_repository.py` selects Firestore | `db/postgres.py` supplies a DB-API compatibility adapter to existing parameterized repositories; no ORM rewrite |
| Objects | Local files or `gcs_storage.py` | `supabase_storage.py`, private bucket, backend-only service key, short signed download URLs used server-side |
| Jobs | Local thread / authenticated Cloud Tasks producer and `/process` worker | Explicit authenticated synchronous requests, PostgreSQL status and advisory locks; **not a durable background queue** |
| AI | Existing Gemini SDK/ADK runtime, tools and validated evidence pipeline | Unchanged orchestration; concurrency, cooldown and cache control tables use PostgreSQL |
| Dataset | `datasets/telemetry/ai4i2020.csv`; knowledge under `services/api/knowledge` | Included in repository checkout; backend build root must be repository root |
| Maintenance / settings | Drafts derived from saved reports; browser preferences in localStorage | No invented ticket, approval, audit, or settings tables. Preferences remain browser-local |

Incidents and history, investigations/progress/agent activity/report JSON (including hypotheses/actions), evidence/provenance, counterfactual scenarios and image metadata have migration mappings. IDs and relationships are retained. Reports are not regenerated. Versioned SQL is `services/api/db/migrations/001_portable.sql`. Existing Cloud Run Dockerfiles, Firestore/GCS/Tasks and local SQLite modes remain available. Render uses native runtimes, so a Docker daemon is unnecessary.

## Authentication and workspace scope

This profile is an **invite-only, shared competition workspace**, not a private multi-tenant product. Every approved viewer can read the same curated evidence and investigations. Do not add unrelated customers or confidential factory data. Approved presenter UUIDs can write only when the separate writes flag is enabled. An unlisted authenticated account has no access. If per-user private records are required, deployment is blocked pending record ownership and authorization design.

1. In Supabase Auth disable public signup; create/invite the presenters and reviewers manually, confirm their email, and set passwords securely. No signup UI is provided.
2. Copy their actual Auth user UUIDs into backend `FACTORYMIND_PORTABLE_READERS` and `FACTORYMIND_PORTABLE_WRITERS` (comma-separated). Never put UUID roles under client control.
3. Login at frontend `/login`. The server exchanges credentials with Supabase, verifies backend membership, and issues an HttpOnly, Secure, SameSite=Lax cookie for at most one hour. No refresh token is retained: sign in again after expiry. HTTPS is required. Tokens are not returned to browser JavaScript or placed in localStorage.
4. Backend validates the token using Supabase Auth `/auth/v1/user` on API requests, verifies confirmed membership, then authorizes writes. User-controlled identity/service headers are ignored. Backend URL is public; authentication, not network privacy, protects it. Only `/healthz`, `/readyz` and preflight are public.
5. Configure exact frontend `FACTORYMIND_WEB_ORIGIN` and backend `FACTORYMIND_CORS_ORIGINS`. Cross-origin state changes are rejected by the proxy. Worker `/process` is unavailable in portable mode. No shared visitor secret replaces user auth.

Disable email signup and avoid public password distribution. Rate limiting of password attempts is delegated to Supabase Auth; application AI controls are not a substitute for provider auth abuse controls. Logout removes the browser cookie; a previously stolen access token remains valid until provider expiry/revocation. Use short access-token lifetime and remove the UUID allowlist entry to immediately revoke workspace membership.

## Manual Supabase setup (approval required)

Create an eligible Free project only after approval; do not enable paid upgrades. Create a **private**, non-public Storage bucket named `factorymind-evidence`; apply its image MIME allowlist and 5 MB maximum as an additional defense. Do not expose the `factorymind` schema through the Supabase Data API or grant it to `anon` or `authenticated`. Browser users access records only through authenticated FastAPI endpoints. Backend service-role credentials bypass Storage RLS and must remain backend-only.

Copy the actual **session pooler** connection string from Supabase Connect, using SSL. Use port 5432, not transaction pooler 6543: execution locking uses session advisory locks. IPv4-only hosts usually require the shared pooler. Copy the host/project reference rather than constructing it. Percent-encode password characters. The runtime disables prepared statements; `sslmode=require` is the minimum accepted setting; prefer `verify-full` with the appropriate trusted CA configuration.

[Supabase connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres), [private downloads](https://supabase.com/docs/guides/storage/serving/downloads), [JWT verification](https://supabase.com/docs/guides/auth/jwts).

### Schema and reviewed data import

Run manually from repository root, after approval and a content review. Stop local writers first or use a consistent offline source snapshot. Do not paste credentials into command history, Git, reports or chat. Set the administrative database URL in the process environment using a secret prompt:

```powershell
Set-Location C:\Users\kavee\Documents\factorymind-ai
& .\services\api\.venv\Scripts\python.exe -m pip install -r services/api/requirements-portable.txt
$databaseSecret = Read-Host 'Supabase administrative session-pooler URI with sslmode=require' -AsSecureString
$env:FACTORYMIND_DATABASE_URL = [System.Net.NetworkCredential]::new('', $databaseSecret).Password
# Inspection only: no destination connection or write without --apply.
& .\services\api\.venv\Scripts\python.exe -m scripts.migrate_postgres schema
& .\services\api\.venv\Scripts\python.exe -m scripts.migrate_postgres import --source services/api/data/incidents.db --investigation INV-D944C855CC
# ONLY after approval, review and independent backup planning:
& .\services\api\.venv\Scripts\python.exe -m scripts.migrate_postgres schema --apply
& .\services\api\.venv\Scripts\python.exe -m scripts.migrate_postgres import --source services/api/data/incidents.db --investigation INV-D944C855CC --reviewed --backup backups/portable-reviewed.sqlite --apply
Remove-Item Env:FACTORYMIND_DATABASE_URL
```

The ID above exists in the inspected local database; reassess it before copying. It is a saved Gemini result, with unresolved critic concerns, not confirmed factory failure. Select original and revised investigation IDs together to copy an existing counterfactual pair. The importer selects scenarios only when both parent IDs are selected; it does not fabricate missing comparisons. `--all-terminal` explicitly selects terminal jobs but rejects the import if any selected job is active; reconcile them manually first. Unknown IDs abort. Completed reports must pass the stored evidence/citation audit.

If selected records contain images, add `--images-dir` with an explicitly reviewed local image root; configure backend Supabase URL/service key/bucket for the migration process. Every image must resolve within that root, satisfy decoded image/MIME/size checks and match any existing destination object. Private objects are copied without overwrite. Remote GCS-only images must first be exported and reviewed manually; no automatic GCS migration is provided. Object writes precede the SQL transaction: an SQL failure may leave private orphan objects requiring manual reconciliation; never automatically delete them.

The script opens SQLite read-only, creates a new backup before destination writes, never deletes the source, normalizes timestamp columns to UTC, clears incident notes, anonymizes uploaded filenames, and redacts common key/token/DSN patterns in strings and JSON. Automated redaction is **not** a complete personal-data review; inspect summaries, provenance and images manually. Exact existing records are idempotent; conflicting destination contents abort the database transaction instead of overwriting. Do not rerun with an existing backup filename. The backup itself contains original sensitive data: keep it local and private.

After migration create a restricted runtime role in Supabase SQL Editor, choosing a unique strong password outside source control (SQL below intentionally omits credential creation):

```sql
-- First create a LOGIN role factorymind_backend through a secure admin workflow.
GRANT USAGE ON SCHEMA factorymind TO factorymind_backend;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA factorymind TO factorymind_backend;
REVOKE INSERT, UPDATE ON factorymind.factorymind_schema_versions FROM factorymind_backend;
GRANT DELETE ON factorymind.gemini_request_leases TO factorymind_backend;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA factorymind TO factorymind_backend;
```

Use that restricted role's session-pooler URL on Render, not the schema owner. Follow Supabase's custom-role connection format from its current Connect instructions (pooler username includes the role and project reference). Never grant schema CREATE, table DDL, public Data API access or arbitrary DELETE to the runtime. Apply future migrations with the administrative role separately. Application startup only verifies schema version; it does not create schema.

## Environment configuration

Copy names from `deploy/render-backend.env.example` and `deploy/render-frontend.env.example` into the appropriate provider environment dashboard; replace every placeholder. `.env` files are not build artifacts and must not be uploaded. Backend:

```dotenv
FACTORYMIND_ENV=production
FACTORYMIND_DEPLOYMENT_TARGET=render
FACTORYMIND_PERSISTENCE=postgres
FACTORYMIND_DATABASE_URL=<restricted SSL session-pooler URI, port 5432>
FACTORYMIND_UPLOAD_BACKEND=supabase
FACTORYMIND_UPLOAD_BUCKET=factorymind-evidence
FACTORYMIND_SUPABASE_URL=<actual HTTPS project URL>
FACTORYMIND_SUPABASE_ANON_KEY=<project publishable or anon key>
FACTORYMIND_SUPABASE_SERVICE_KEY=<server-only service-role key>
FACTORYMIND_PORTABLE_READERS=<comma-separated viewer UUIDs>
FACTORYMIND_PORTABLE_WRITERS=<comma-separated presenter UUIDs>
FACTORYMIND_PORTABLE_WRITES_ENABLED=false
FACTORYMIND_PORTABLE_DAILY_AI_LIMIT=5
FACTORYMIND_JOB_DISPATCH=portable
FACTORYMIND_INVESTIGATION_ASYNC=false
FACTORYMIND_INVESTIGATION_TIMEOUT_SECONDS=20
FACTORYMIND_INVESTIGATION_MAX_RETRIES=0
FACTORYMIND_GEMINI_CONCURRENCY=1
FACTORYMIND_GEMINI_MAX_MODEL_CALLS=4
FACTORYMIND_PROVIDER_COOLDOWN_ENABLED=true
FACTORYMIND_INVESTIGATION_CACHE_ENABLED=true
FACTORYMIND_CORS_ORIGINS=<exact HTTPS frontend origin>
AI_PROVIDER=google
AI_INVESTIGATION_ENABLED=false
GEMINI_MODEL=<existing model actually available to your Gemini account>
GOOGLE_GENAI_USE_VERTEXAI=false
```

`GOOGLE_API_KEY` is required on backend only if live AI is enabled. The example retains the repository's configured model; its allocation is not verified. No silent model fallback is introduced. Keep both AI and write flags false for initial saved-demo rollout. Google Cloud credentials/project/tasks are not required by this profile.

Frontend only:

```dotenv
FACTORYMIND_DEPLOYMENT_TARGET=render
FACTORYMIND_BACKEND_URL=<actual HTTPS backend origin>
FACTORYMIND_WEB_ORIGIN=<exact HTTPS frontend origin>
FACTORYMIND_SUPABASE_URL=<same actual HTTPS project URL>
FACTORYMIND_SUPABASE_ANON_KEY=<same publishable/anon key>
NEXT_PUBLIC_API_URL=/api/backend
```

The frontend server needs the anon key for login, not the service key. Never configure database URL, service-role key or Gemini key as a `NEXT_PUBLIC_*` variable. Backend must fail startup if configured as development on Render, or if portable production storage/auth/bounds are incomplete.

## Manual Render deployment

After approval, use `render.yaml` as a reviewed optional Blueprint or configure two Free Web Services manually. Blueprint is not self-contained: add all required environment values above before launching. Auto-deploy is disabled. Confirm selected plan says Free and no paid add-ons/cards/upgrades are required for your account.

Backend root is repository root (no Root Directory). Python 3.12.10. Build: `pip install -r services/api/requirements-portable.txt`. Start:

```sh
python -m uvicorn services.api.main:app --host 0.0.0.0 --port $PORT --workers 1
```

Health path `/healthz`; then check `/readyz` independently for database, dataset and storage availability. Source checkout must contain the dataset CSV and maintenance corpus. No runtime dependence on a developer absolute path. Do not set `FACTORYMIND_DATASET_PATH` unless using a valid packaged path. Do not persist SQLite/uploads on Render's ephemeral filesystem. Dataset/anomaly computations retain existing service caching; no retraining is added to each request. Actual Python 3.12 native dependency installation, cold startup time and peak memory on the Free instance remain deployment gates.

Frontend Root Directory `apps/web`, Node 22. Build `npm ci && npm run build && node scripts/prepare-standalone.mjs`. Start `node .next/standalone/server.js`. Set `HOSTNAME=0.0.0.0`; Render supplies `PORT`. The script includes static assets and public files in standalone output. Use SSR/server hosting; static export or Firebase static hosting cannot serve authenticated proxy/session routes.

Create backend and frontend URLs, then set exact origins on both sides and redeploy their configurations. First deploy remains read-only with AI disabled. Logs must never include request bodies, tokens or connection URLs.

## Eligible Vercel Hobby alternative

Review [Hobby restrictions](https://vercel.com/docs/plans/hobby) before choosing this option: it is for personal non-commercial use; team/competition eligibility must not be assumed. If eligible, manually import with Root Directory `apps/web`, framework Next.js, build `npm run build`, and framework-managed output (do not set static export or standalone start command). Set the frontend environment variables above with the actual Vercel origin; backend CORS must match. Redeploy after variable changes. Preview URLs are not automatically allowed.

The proxy declares `maxDuration=180` and session route `120`; use a configuration supporting these values. [Function limits](https://vercel.com/docs/functions/limitations) depend on Fluid Compute; legacy Hobby limits may be too short. If duration/eligibility is unsuitable, choose Render frontend. No Vercel account or deployment was created here.

## Execution bounds and honest recovery

Portable requests execute only on explicit user actions. A normal investigation retains four model calls; a critic revision/counterfactual can require up to six calls under existing orchestration. Model calls have a 20-second configured timeout and no automatic retries; frontend proxy timeout is 170 seconds. Auth/database/storage/network overhead and cold starts can still exceed this budget. There is no hard end-to-end cancellation guarantee if a client disconnects. Do not advertise production-grade asynchronous completion.

PostgreSQL session locks prevent concurrent execution of the same investigation; execution tokens fence stale writers. Persisted active-job uniqueness and Gemini leases/cooldowns prevent duplicate work/concurrent provider usage. A completed identical job stays cached and does not claim a fresh execution. Counterfactual prepared context/exclusions and separate job identity remain distinct from the original conclusion cache. Stage failures remain failed, never completed by a synthetic fallback. Existing 429/503 classifications and bounded provider handling are retained; portable orchestration retries are disabled. No added calls are needed for Guided Saved Demo.

`FACTORYMIND_PORTABLE_DAILY_AI_LIMIT` counts expensive POST actions per approved user per UTC day, not tokens or individual Gemini calls; rejected/invalid/cached actions can conservatively consume this allowance. It is an abuse budget, not a guarantee against provider quotas. Provider request concurrency remains one across PostgreSQL workers.

After a killed runner, the next explicit authenticated `POST /api/investigations/{id}/execute` can reclaim a stale running job once its database session lock has released. A job with partial evidence is marked failed and preserved; start a new explicit investigation rather than overwriting its evidence. Existing retry/start controls must be inspected against the returned state. A status poll alone does not run a job. Counterfactual/visual multi-step interruption may require manual reconciliation; there is no autonomous scheduler/always-on worker. Do not invoke the old Cloud Tasks `/process` endpoint or add keepalive polling to avoid Free service sleep.

## End-to-end smoke checklist (manual; no live AI by default)

1. Check `/healthz` and `/readyz` after cold start. Inspect Render logs without credentials. Recheck memory/CPU and startup duration in the provider dashboard.
2. Anonymous direct backend `/api/incidents` and frontend `/api/backend/api/incidents` must return 401. An authenticated unlisted account must return 403. Reader writes, forged identity headers, `/process`, cross-origin POST and absent sessions must be rejected.
3. Login an invited viewer over HTTPS; refresh the page, open curated saved investigation, evidence graph, critic review, Maintenance Review, settings and Guided Saved Demo. Check real IDs/provenance resolve, historical counts agree, and saved labels remain visible. Logout and confirm denied access. No new model requests should appear.
4. Reopen the same records after backend restart/sleep and frontend redeploy; compare IDs, counts, report and evidence payloads. Verify database and private object persistence separately.
5. Only with write approval enable `FACTORYMIND_PORTABLE_WRITES_ENABLED=true` for a presenter. Upload a reviewed valid image, confirm oversize/invalid MIME rejection and private bucket access denial without auth. Download through the API; signed URLs must not appear in client responses/logs. Verify a different incident cannot attach that image to its investigation.
6. Only with explicit live-AI approval set backend `GOOGLE_API_KEY`, verify model quota, then enable `AI_INVESTIGATION_ENABLED=true`. Run one real investigation; inspect stage/result persistence, usage logs and citations. Repeat a duplicate start: no duplicate active run. Run a counterfactual only with separate quota approval; ensure excluded evidence is absent and a genuinely revised reasoning execution occurs. No saved counterfactual currently exists in the inspected local snapshot.
7. Test interrupted execution using a disposable staging dataset/instance, confirm no completed lie or overwritten partial evidence, then exercise explicit recovery. Do not kill the only curated demo run.
8. Disable AI/writes after demonstration unless continued access is intended. Keep a local offline saved-demo fallback; the protected hosted demo requires invited login.

## Free-plan limits and rollback

[Render Free](https://render.com/docs/free) can sleep after 15 minutes idle, take about a minute to wake, and offers ephemeral local files. Its 750 included instance hours are shared within a workspace: two continuously awake services do not fit a full month. Free workers/always-on execution are not assumed. Accounts without a payment method may be suspended when included usage is exhausted. Review outbound traffic/build allowances and never add paid scaling or keepalive services.

[Supabase Free pricing](https://supabase.com/pricing) currently lists 500 MB database, 1 GB file storage, 5 GB egress and possible pause after a week inactive. These limits and account availability must be reconfirmed. Gemini quota is independent, may be zero/unavailable, and does not become unlimited through this migration. A read-only saved demo is the safest first rollout.

Rollback: disable portable writes and AI first; restore the previously working Render deployment through its dashboard and matching environment configuration. Never drop the database or delete objects as an automatic rollback. Keep the SQLite backup and previous schema/application revisions together. Repoint local development to its existing defaults (development, SQLite, local uploads, thread jobs) without modifying original database files. To return to Google Cloud, use the original documented production profile (`FACTORYMIND_DEPLOYMENT_TARGET=gcp`, Firestore/GCS/Tasks and Google IAM); portable PostgreSQL changes are not automatically synchronized back to Firestore. Reverse data migration requires a separate reviewed procedure. Removing the optional Render resources must be a manual approved action.

## Verification and remaining blockers

See `free-hosting-readiness.md` for exact tests and changed files. Real PostgreSQL, Supabase Auth/Storage, Render startup/memory, Vercel eligibility and hosted end-to-end flows remain unverified. Do not enable public live writes until those gates pass. This work prepares a constrained optional deployment; it does not establish a working public URL or guarantee indefinite free operation.

## Changed/new file manifest

- `.gitignore`
- `apps/web/scripts/prepare-standalone.mjs`
- `apps/web/src/app/(shell)/layout.tsx`
- `apps/web/src/app/api/backend/[...path]/route.ts`
- `apps/web/src/app/api/session/route.ts`
- `apps/web/src/app/login/page.tsx`
- `apps/web/src/components/layout/LoginForm.tsx`
- `apps/web/src/components/layout/PortableAccess.tsx`
- `apps/web/src/components/settings/SettingsDashboard.tsx`
- `apps/web/src/lib/portableProxyPolicy.ts`
- `apps/web/tests/portable-proxy.test.mjs`
- `apps/web/tests/portable-routes.test.mjs`
- `deploy/render-backend.env.example`
- `deploy/render-frontend.env.example`
- `README.md`
- `render.yaml`
- `reports/free-hosting-deployment.md`
- `reports/free-hosting-readiness.md`
- `scripts/migrate_postgres.py`
- `services/api/agents/request_control.py`
- `services/api/core/config.py`
- `services/api/core/portable.py`
- `services/api/core/production.py`
- `services/api/core/security.py`
- `services/api/db/migrations/001_portable.sql`
- `services/api/db/postgres.py`
- `services/api/main.py`
- `services/api/requirements-portable.txt`
- `services/api/routes/investigations.py`
- `services/api/routes/settings.py`
- `services/api/routes/visual_inspection.py`
- `services/api/services/firestore_repository.py`
- `services/api/services/investigation_service.py`
- `services/api/services/object_storage.py`
- `services/api/services/supabase_storage.py`
- `services/api/services/visual_evidence_service.py`
- `services/api/tests/test_portable.py`
- `services/api/tests/test_postgres_integration.py`
