# FactoryMind AI — Google Cloud deployment readiness

Team: AetherForge · AI Builder Cup 2026 · deadline: October 18, 2026

Audit and verification: October 14, 2026 (Asia/Colombo).

## 1. Current readiness and architecture

The application now has a private Cloud Run deployment profile, container definitions, Firestore repository adapters, private GCS image storage, and authenticated Cloud Tasks investigation delivery. Local SQLite, local uploads, and the existing Gemini agents remain available for development. This is deployment preparation, not a verified cloud deployment. No resources were created, and no code was committed, pushed, or deployed.

| Component | Actual entry point / implementation |
|---|---|
| Backend | `services.api.main:app`, FastAPI lifespan warms repositories and the anomaly engine |
| Frontend | `apps/web/src/app`, Next.js 16.4 / React 19.3, standalone output |
| Python dependencies | `services/api/requirements.txt`; additional pinned cloud dependencies in `requirements-cloud.txt` |
| Node dependencies | `apps/web/package.json` and lockfile; server proxy uses `google-auth-library` |
| Dataset | `datasets/telemetry/ai4i2020.csv`, approximately 10,000 synthetic observations |
| Knowledge | Packaged `services/api/knowledge/documents.json`; synthetic troubleshooting guidance, not real factory maintenance records |
| Local persistence | `services/api/data/incidents.db`, SQLite repositories for incidents, investigations/evidence, counterfactuals, and image metadata |
| Local jobs | Existing in-process worker / standalone poller; these are not the production dispatch mechanism |
| Cloud persistence | Native Firestore collections selected through the same repository contracts |
| Cloud jobs | Cloud Tasks POST to authenticated `/api/investigations/{id}/process`; transaction claims and expiring leases |
| Images | Private GCS objects plus Firestore metadata in production; existing local files in development |
| Gemini | Google ADK / Google Gen AI SDK; configured model, bounded calls/retries, usage logging, quota categories and shared cooldowns |

Problems found: local files and SQLite would disappear with Cloud Run instance replacement; background threads could be suspended or terminated; process-local controls do not coordinate multiple instances; writes lacked production authentication; frontend browsers could not invoke a private backend directly; filtered counterfactual context was not persisted for a restarted worker. Live tests also treated the presence of a key as permission to call Gemini, including keys loaded automatically from `.env`.

Changes address these problems without rewriting the agents or changing ordinary API response contracts. Production fails startup if configured with SQLite, local uploads, thread dispatch, scripted AI, wildcard CORS, missing caller configuration, or an excessive agent time budget. Authentication covers reads and writes; only health probes bypass it. Model failures remain failed records, not completed reports.

## 2. Files modified

- Backend configuration and entry point: `services/api/core/config.py`, `.env.example`, `main.py`; new `core/production.py` and `core/security.py`.
- Persistence and jobs: `db/database.py`, `services/incident_service.py`, `investigation_service.py`, `investigation_repository.py`, `counterfactual_service.py`, `visual_evidence_service.py`; new `services/firestore_repository.py`, `task_dispatch.py`, `object_storage.py`.
- Shared Gemini controls: `agents/request_control.py`; new `agents/firestore_control.py`.
- Routes and uploads: `routes/investigations.py`, `routes/visual_inspection.py`, `services/image_utils.py`.
- Containers/dependencies: backend and frontend `Dockerfile` / `Dockerfile.dockerignore`, root `.dockerignore`, `.gcloudignore`, `.gitignore`, `requirements-cloud.txt`, frontend `package.json`, lockfile, `next.config.ts`.
- Frontend private proxy: new `src/app/api/backend/[...path]/route.ts`, `src/app/api/health/route.ts`, `src/lib/backendProxyPolicy.ts`.
- Tests: new `services/api/tests/test_cloud_readiness.py`, `apps/web/tests/backend-proxy.test.mjs`; live smoke tests now require explicit opt-in.
- Deployment examples: `deploy/backend.env.example.yaml`, `frontend.env.example.yaml`, `cloudbuild-api.yaml`, `cloudbuild-web.yaml`; this report.

## 3. Required Google Cloud services

Provision only after review: Cloud Run, Artifact Registry, Cloud Build (if used), Firestore Native mode, Cloud Storage, Cloud Tasks, Secret Manager, and Cloud Logging. Use one selected region consistently where supported. Gemini Developer API quota/billing remains separate; Vertex AI is an explicit optional provider configuration, not an automatic fallback.

Cloud service clients use Application Default Credentials from the service identity; do not package service-account JSON keys. [Cloud Run service identity](https://docs.cloud.google.com/run/docs/securing/service-identity).

## 4. Environment and credentials

Use `deploy/backend.env.example.yaml` and `frontend.env.example.yaml` as templates; replace every placeholder and save actual configuration in ignored `deploy/backend.env.yaml` / `frontend.env.yaml`.

Required backend settings: `FACTORYMIND_ENV=production`, `FACTORYMIND_PERSISTENCE=firestore`, `FACTORYMIND_FIRESTORE_DATABASE`, `FACTORYMIND_FIRESTORE_PREFIX`, `GOOGLE_CLOUD_PROJECT`, `FACTORYMIND_UPLOAD_BACKEND=gcs`, `FACTORYMIND_UPLOAD_BUCKET`, exact canonical `FACTORYMIND_AUTH_AUDIENCE`, API/worker service-account email allowlists, `FACTORYMIND_JOB_DISPATCH=tasks`, full queue resource name, task target, task service account, deadline, asynchronous execution, configured CORS origins, AI provider and model.

The example uses a 900-second task deadline, 40-second agent request timeout, one retry, global Gemini concurrency one, four ADK calls maximum per agent, cache enabled, and shared cooldowns. Startup checks the six-stage worst-case retry budget against the deadline. Cloud Run request timeout must be at least the configured task deadline. The browser proxy has a 895-second upstream timeout, so long synchronous counterfactual operations may require reconciliation if interrupted.

For Gemini Developer API, inject `GOOGLE_API_KEY` from Secret Manager using `--set-secrets`; never put it in YAML, Docker build arguments, frontend environment variables, or logs. For an explicitly selected Vertex configuration, unset the API key, set `GOOGLE_GENAI_USE_VERTEXAI=true`, project/location, and grant scoped Vertex permissions. Confirm model availability and quotas in that project before use. The current configured `gemini-3.8-flash` model is preserved; availability is not guaranteed and no silent model substitution occurs.

Frontend: image build sets `NEXT_PUBLIC_API_URL=/api/backend`; runtime `FACTORYMIND_BACKEND_URL` is the canonical private backend HTTPS origin, and `FACTORYMIND_WEB_ORIGIN` must match the browser's actual trusted origin. Proxy paths cannot access the worker process endpoint; writes check Origin, uploads have a six-MiB proxy limit, and request credentials are minted server-side. Both services must remain IAM-private. For team access through `gcloud run services proxy --port=8080`, use `http://localhost:8080` as the web origin. A public competition demo needs a separately configured user authentication/IAP solution before making the frontend public.

## 5. Dataset and upload packaging

Both Docker builds use the repository root as context. Backend explicitly copies the CSV to `/app/datasets/telemetry/ai4i2020.csv`, matching the existing path resolution. Knowledge JSON is included with backend services. Ground-truth labels retain their evaluation-only role and are not added to investigation inputs. Synthetic data/documents retain their synthetic provenance.

Runtime image uploads use private GCS keys `uploads/{filename}` with create-only generation preconditions and pinned-generation reads. Production validates image decoding/format and a pixel budget, not only MIME/signature; upload reads are bounded. Image content is served through the authenticated API. No public bucket URLs are returned. Existing legacy local fixtures remain accepted in the development profile. Document upload/indexing is not currently an application feature: packaged knowledge is deployed with the image; do not claim arbitrary uploaded documents are indexed.

## 6. Database migration requirements

Firestore is a new storage adapter, not an automatic migration of existing SQLite data. Before switching, stop/drain writers and workers, back up SQLite and local image files, and reconcile queued/running jobs. Import only completed/failed jobs or explicitly mark interrupted jobs failed; legacy running records lack cloud lease metadata.

Preserve all incident/investigation/scenario/image IDs, timestamps, statuses, reports, stage histories, agent activity, cache metadata and evidence IDs. Decode SQLite JSON columns before importing. Use collections named `{prefix}_incidents`, `_investigations`, `_counterfactuals`, `_images`; incident events and investigation evidence belong to their respective document subcollections. Rebuild `_incident_locks` and `_investigation_locks` from active records using the adapter's key rules, otherwise duplicate prevention cannot cover imported records. Evidence must remain immutable and source references must remain valid.

Upload original image bytes under their existing filenames and update image metadata `storage_backend` to `google_cloud_storage`; verify checksums and private access. Do not import local absolute paths as usable cloud object references. Validate counts, report/evidence equality, representative API reads and duplicate prevention before enabling writers. No migration or export was executed automatically. Firestore records are capped at 850 KB by the adapter; large existing reports/filtered contexts need review before import. Firestore query adapters currently preserve offset/count contracts by scanning matching records and sorting in memory; this is suitable for bounded demo data, not a large production fleet.

## 7. Build and deployment commands (review before running)

Commands below are examples for PowerShell. They create paid resources or deploy revisions and were NOT executed. Create project, services, private bucket, Native Firestore database, Artifact Registry repository, identities, secret, queue, and scoped IAM bindings first through your approved infrastructure process.

```powershell
$project = 'YOUR_PROJECT'
$region = 'YOUR_REGION'
$registry = "$region-docker.pkg.dev/$project/factorymind"
docker build -f services/api/Dockerfile -t "${registry}/api:readiness" .
docker build -f apps/web/Dockerfile -t "${registry}/web:readiness" .
# Alternative: remote builds, after reviewing the .gcloudignore upload list.
gcloud builds submit --project=$project --config=deploy/cloudbuild-api.yaml --substitutions="_IMAGE=${registry}/api:readiness" .
gcloud builds submit --project=$project --config=deploy/cloudbuild-web.yaml --substitutions="_IMAGE=${registry}/web:readiness" .
gcloud tasks queues update factorymind --project=$project --location=$region --max-concurrent-dispatches=1 --max-dispatches-per-second=0.1 --max-attempts=10 --max-retry-duration=3600s --min-backoff=60s --max-backoff=300s
gcloud run deploy factorymind-api --project=$project --region=$region --image="${registry}/api:readiness" --service-account="factorymind-api@$project.iam.gserviceaccount.com" --no-allow-unauthenticated --port=8080 --timeout=900 --concurrency=8 --max-instances=2 --memory=1Gi --env-vars-file=deploy/backend.env.yaml --set-secrets=GOOGLE_API_KEY=factorymind-gemini-key:1 --startup-probe='httpGet.path=/healthz,httpGet.port=8080,initialDelaySeconds=0,timeoutSeconds=5,periodSeconds=10,failureThreshold=24'
gcloud run services describe factorymind-api --project=$project --region=$region --format='value(status.url)'
gcloud run deploy factorymind-web --project=$project --region=$region --image="${registry}/web:readiness" --service-account="factorymind-web@$project.iam.gserviceaccount.com" --no-allow-unauthenticated --port=8080 --timeout=900 --max-instances=2 --memory=512Mi --env-vars-file=deploy/frontend.env.yaml
gcloud run services proxy factorymind-web --project=$project --region=$region --port=8080
```

For a first backend deployment when the canonical URL is unknown, use a private bootstrap revision with investigations disabled and placeholder HTTPS audience/target, then read `status.url`, replace both with the exact URL, inject the secret, and enable investigations in a second revision. The placeholder audience intentionally prevents normal authenticated API use. Never dispatch work until the second revision, IAM and queue setup are verified.

Health: backend `/healthz` liveness and `/readyz` startup/dependency readiness; frontend `/api/health`. Readiness checks Firestore and the bucket without calling Gemini. The Cloud Run startup probe above checks liveness only after lifespan succeeds; manually verify readiness before releasing traffic. With Docker running, start a local development-profile container on port 8080 and request `/healthz` / `/readyz`; production container smoke checks need real test infrastructure or emulators.

Cloud Tasks delivery is bounded to at most 30 minutes by the platform. Active duplicate delivery receives 503/Retry-After; completed or persistently failed model jobs are acknowledged without re-consuming quota. The configured retry window must outlast the job lease. [Cloud Run and Cloud Tasks](https://docs.cloud.google.com/run/docs/triggering/using-tasks).

## 8. IAM and security

- Backend identity: Firestore `roles/datastore.user`, Cloud Tasks `roles/cloudtasks.enqueuer` scoped to the queue, `roles/iam.serviceAccountUser` on the task identity, Secret Manager accessor on the specific Gemini secret. Bucket-scoped permissions need `storage.objects.create`, `storage.objects.get`, and `storage.buckets.get` for readiness; use a reviewed custom role rather than broad Storage Admin.
- Frontend identity: `roles/run.invoker` on the backend service only. Task identity: invoker on the backend only. Backend middleware additionally separates web and worker principals; use distinct allowlists.
- Team/judges: invoker on the frontend only for private access. Do not grant `allUsers` invoker. Deployer/build identities need only the required build, artifact push, deployment and service-account impersonation permissions; avoid project Owner/Editor.
- Use uniform bucket-level access and public access prevention. Firestore browser-client rules should deny direct access; server IAM governs these adapters. Do not distribute service-account keys.
- Cloud Run OIDC audience must be the canonical receiving service URL. The proxy sends an application Authorization token and an X-Serverless-Authorization token so the signed application token remains available to backend validation. [Service-to-service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service).
- CORS is explicitly configured. Local development remains unauthenticated for its existing workflow and must not be exposed publicly. Production application state APIs require verified allowlisted identities.
- Gemini usage controls are shared across instances through Firestore; daily exhaustion is not repeatedly retried. Controls limit concurrent usage, not the provider's daily quota or billing spend. Retain provider-side budgets/quotas and private access.
- No tracked key/environment credential files were found in the targeted Git inventory. Docker/Cloud Build excludes environment files, dependency caches, local stores and common credential filenames. Review `gcloud meta list-files-for-upload` before any remote build; filenames alone cannot detect a secret pasted into source.

## 9. Verification results

| Check | Result |
|---|---|
| Complete backend suite after opt-in correction | 196 passed; 2 live tests skipped (198 collected) |
| New cloud tests | 22 passed within the full suite: configuration, auth roles, health, fake Firestore transaction contracts/leases/evidence, GCS mocks, image validation, Cloud Tasks payload and restart context |
| Frontend proxy tests | 4 passed |
| `npx tsc --noEmit` | Passed after correcting typed upload body |
| `npm run lint` | Passed |
| `npm run build` | Passed after removing route runtime setting incompatible with Cache Components; standalone route output generated |
| `python -m pip check` | Passed, no broken requirements |
| `git diff --check` | Passed; Windows line-ending warnings only |
| Docker builds and container health | Follow-up passed: both `factorymind-api:readiness` and `factorymind-web:readiness` built; backend HTTP `/healthz` and `/readyz` returned 200; frontend standalone `/api/health` returned 200 |
| Cloud/emulator integration | Not executed: no cloud resources provisioned, no emulator configured |
| Production npm audit retry | Incomplete: registry DNS resolution failed (`ENOTFOUND`) |

The Windows sandbox prevented Next.js path canonicalization and hung asyncio socket-pair creation. Repeating authorized local build/tests outside that sandbox succeeded. Existing warnings remain: Starlette TestClient's httpx deprecation, pytest asyncio configuration warning, and Node's module-type warning in the direct TypeScript helper test.

An initial full-suite run unexpectedly executed two live tests because automatic `.env` loading satisfied their old credential-only gate. They failed with 503 model demand and 429 RPD exhaustion (20 free-tier requests/day reported). No successful live integration is claimed. The corrected explicit gate prevents this from ordinary verification runs. Deliberate future integration requires `FACTORYMIND_RUN_LIVE_TESTS=1` and credentials; do not run until quota is available and the call is intended.

The earlier dependency audit identified five high findings in the development lint dependency chain involving `braces@3.0.3`; the advisory has no patched version, and npm's suggested lint-config downgrade would break the current Next toolchain. No forced downgrade was applied. Verify production dependencies again when registry access is available. [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).

## 10. Remaining blockers and limits

Docker follow-up on October 14: the engine was already running under Docker Desktop / WSL2 (version 29.7.2). The current pipe access failure came from the Codex sandbox; authorized execution outside it succeeded. An initial Docker Hub metadata timeout resolved on retry. Both images built successfully. Backend ran as UID 10001, contained the dataset and loaded all 10,000 records; its actual Uvicorn entry point passed localhost HTTP liveness/readiness checks. Frontend ran as UID 1000 and its standalone server returned HTTP 200 for `/api/health`. Temporary test containers were removed; local image tags remain. No Gemini calls or cloud deployment were made for these checks. No Docker settings or application code changes were necessary for this follow-up.

Verify real Firestore transactions, GCS IAM/generation checks, ADC, OIDC, queue redelivery and instance replacement in a private staging project before declaring deployment ready. Unit fakes and development-profile container checks are not proof of provider integration.

Complete the reviewed migration or consciously start with an empty cloud store. No automatic data migration exists. Confirm model allocation and quota; cloud hosting does not increase Gemini quotas. Enable monitoring/budget alerts and finish registry security audit. Public access requires an authenticated frontend gateway/IAP configuration; private team proxy access is the supported preparation here.

Counterfactuals and visual analysis remain synchronous to preserve existing contracts. Filtered counterfactual context is persisted for a restarted investigation worker, but interrupted parent requests can leave scenario/image orchestration states needing reconciliation. Add durable asynchronous orchestration and owner-fenced lease completion before claiming arbitrary crash recovery or broad multi-instance production robustness. Claim leases prevent simultaneous normal duplicate execution but are not an exactly-once guarantee after a stale worker outlives its lease.

Firestore demo-scale scanning/sorting, report size limits, immutable evidence writes one document at a time, and task enqueue/database writes being separate operations need staging fault testing. Enqueue failures are persisted as failed jobs; an ambiguous response can leave a task to run, so inspect stored job status before a manual rerun. These limitations do not justify representing SQLite as persistent Cloud Run storage or marking a failed model run completed.
