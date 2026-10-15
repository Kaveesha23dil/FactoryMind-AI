# FactoryMind AI — first Google Cloud deployment

Prepared October 14, 2026 (Asia/Colombo), AetherForge. This is a reviewed procedure, **not an executed deployment**. Stop at the approval gate below. No cloud resources, remote builds, migrations, or Gemini calls were made while preparing this guide.

## Verified repository and release gates

| Item | Repository evidence / result |
|---|---|
| Backend build | Root context `.`; `services/api/Dockerfile`; Python 3.12; installs `requirements-cloud.txt`, which includes `requirements.txt`; non-root UID 10001 |
| Backend data | Copies `datasets/telemetry/ai4i2020.csv` into `/app/datasets/telemetry/ai4i2020.csv`; knowledge JSON included through `COPY services`; no local DB or `.env` included |
| Backend entry / port | `python -m uvicorn services.api.main:app --host 0.0.0.0 --port ${PORT:-8080}` |
| Frontend build | Root context `.`; `apps/web/Dockerfile`; Node 22; `npm ci`; Next standalone output, static/public assets; non-root `node` |
| Frontend entry / port | `node server.js`; `PORT=8080`, `HOSTNAME=0.0.0.0`; build-time `NEXT_PUBLIC_API_URL=/api/backend` |
| Remote builds | `deploy/cloudbuild-api.yaml` / `cloudbuild-web.yaml`, `_IMAGE` substitution; now explicitly use `CLOUD_LOGGING_ONLY` for the dedicated build identity |
| Storage selection | `FACTORYMIND_PERSISTENCE=firestore` selects all four repository families; `FACTORYMIND_UPLOAD_BACKEND=gcs` selects private image storage; production validation rejects SQLite/local storage |
| Authentication | `core/security.py` verifies Google OAuth2 ID token signatures, exact audience, verified email and caller allowlist; normal APIs use API callers, `/process` uses worker callers |
| Frontend proxy | `src/app/api/backend/[...path]/route.ts` uses ADC `GoogleAuth.getIdTokenClient`, then `fetchIdToken(base.origin)`; passes both Authorization and X-Serverless-Authorization; no browser key/token exposure |
| Tasks | `services/task_dispatch.py` sets task OIDC service-account email and exact audience; deterministic task name; worker route uses production OIDC middleware |
| Evidence | Existing grounding checks preserved; counterfactual `prepared_context` persisted; local data is not automatically imported |

Previous verification: 196 backend tests passed, 2 opt-in live tests skipped; frontend type-check/lint/build and four proxy tests passed. The subsequent Docker follow-up **did** build both images and pass non-root container health checks, despite the earlier unavailable-daemon result. Real GCP integration remains unverified. This guide uses remote Cloud Build as requested and needs no local Docker daemon.

**P0 release gates:** Do not expose the frontend publicly: it has no end-user authentication and its proxy represents the frontend service identity. Keep IAM authentication enabled on both services. Do not enable investigations until exact URLs, distinct caller identities, Secret Manager version, queue IAM, readiness and anonymous-write rejection are verified. Do not import live/unfinished SQLite jobs without reconciliation or claim local data was migrated. A fresh empty store can be chosen explicitly instead. These are configuration/data cutover gates; no additional proven P0 application defect was found for a private, AI-disabled first staging deployment.

Real integration is an acceptance gate before declaring the system production-ready. Known limitations: no automatic migration tool; no owner fencing for an expired job lease; synchronous counterfactual/image orchestration can need manual recovery; Firestore queries scan matching demo records; dependencies still need the pending security audit. A public demo or stronger crash recovery requires additional implementation.

## 1. Google Cloud prerequisites

Use PowerShell 7 and a current Google Cloud CLI. `gcloud` was not found on this session's PATH, so cloud commands could not be syntax-checked locally or executed. Install it using the official installer, reopen PowerShell, then verify `gcloud version`. Use an approved existing project with billing enabled, selected region, budget alerts and organization-policy approval. Project creation/billing attachment is deliberately not automated here. Choose a region supported by Cloud Run, Cloud Tasks, Artifact Registry and Firestore; confirm Firestore location before creation because changing it requires a migration.

All blocks are sequential, not a single unattended script. Run from the repository root. Variables below are PowerShell procedure variables, not invented application environment settings. Replace all `YOUR_...` values.

```powershell
Set-Location 'C:\Users\kavee\Documents\factorymind-ai'
$ErrorActionPreference = 'Stop'
function Invoke-Gcp { & gcloud @args; if ($LASTEXITCODE -ne 0) { throw 'gcloud command failed; stop and inspect the error' } }
$Project = 'YOUR_EXISTING_PROJECT_ID'
$Region = 'YOUR_APPROVED_REGION'
$FirestoreLocation = $Region # Confirm Firestore supports this location first.
$Operator = 'YOUR_OPERATOR_EMAIL'
$TeamMember = "user:$Operator" # Or an approved group:team@example.com.
$UploadsBucket = "$Project-factorymind-uploads" # Globally unique.
$SourceBucket = "$Project-factorymind-build-source" # Globally unique; separate from uploads.
$ApiSa = "factorymind-api@$Project.iam.gserviceaccount.com"
$WebSa = "factorymind-web@$Project.iam.gserviceaccount.com"
$TaskSa = "factorymind-tasks@$Project.iam.gserviceaccount.com"
$BuildSa = "factorymind-build@$Project.iam.gserviceaccount.com"
$Queue = 'factorymind'
$Secret = 'factorymind-gemini-key'
$SecretVersion = '1' # Replace with the confirmed numeric enabled version.
$Registry = "$Region-docker.pkg.dev/$Project/factorymind"
$Release = "first-$(Get-Date -Format yyyyMMddHHmmss)"
$ApiImage = "${Registry}/api:$Release"
$WebImage = "${Registry}/web:$Release"
Invoke-Gcp auth login
Invoke-Gcp config set project $Project
Invoke-Gcp projects describe $Project --format='value(projectId)'
Invoke-Gcp billing projects describe $Project
```

**APPROVAL GATE — STOP HERE.** The rest enables services, creates billable resources, grants IAM, submits builds and deploys. Obtain explicit approval for the project, region, cost budget, private access plan, fresh-store versus migration decision, and resource names before running it. This guide does not authorize execution.

The provisioning operator needs the relevant service enablement, Artifact Registry/Storage/Firestore/Secret Manager/Tasks administration, custom-role and service-account/IAM management permissions. Use a reviewed provisioning identity; do not grant Owner/Editor to runtime identities. Day-to-day deployer needs Cloud Build build submission, Cloud Run deployment, IAM policy updates for these services, source-object creation, `serviceusage.services.use`, and `iam.serviceAccounts.actAs` on the selected build and runtime identities. Organizational policy can restrict these operations; stop on denial rather than weakening authentication.

```powershell
Invoke-Gcp services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com storage.googleapis.com cloudtasks.googleapis.com secretmanager.googleapis.com iam.googleapis.com iamcredentials.googleapis.com logging.googleapis.com --project=$Project
$ProjectNumber = (Invoke-Gcp projects describe $Project --format='value(projectNumber)').Trim()
foreach ($Name in @('factorymind-api','factorymind-web','factorymind-tasks','factorymind-build')) {
    Invoke-Gcp iam service-accounts create $Name --project=$Project --display-name=$Name
}
Invoke-Gcp artifacts repositories create factorymind --project=$Project --location=$Region --repository-format=docker --description='FactoryMind release images'
# Inspect first; create only if (default) does not already exist.
Invoke-Gcp firestore databases list --project=$Project
# Do not run create if the required Native database already exists.
Invoke-Gcp firestore databases create --project=$Project --database='(default)' --location=$FirestoreLocation --type=firestore-native --delete-protection
Invoke-Gcp storage buckets create "gs://$UploadsBucket" --project=$Project --location=$Region --uniform-bucket-level-access --public-access-prevention
Invoke-Gcp storage buckets create "gs://$SourceBucket" --project=$Project --location=$Region --uniform-bucket-level-access --public-access-prevention
Invoke-Gcp secrets create $Secret --project=$Project --replication-policy=automatic
```

Add the Gemini API key as a secret **version through the Secret Manager console**; do not paste it into a command, report, YAML, source file or Docker argument. Use an existing approved secret instead of creating a duplicate if applicable. Confirm version metadata only:

```powershell
Invoke-Gcp secrets versions describe $SecretVersion --secret=$Secret --project=$Project --format='value(state)'
Invoke-Gcp secrets add-iam-policy-binding $Secret --project=$Project --member="serviceAccount:$ApiSa" --role=roles/secretmanager.secretAccessor
Invoke-Gcp projects add-iam-policy-binding $Project --member="serviceAccount:$ApiSa" --role=roles/datastore.user
Invoke-Gcp iam roles create factorymindUploadStore --project=$Project --title='FactoryMind private upload access' --permissions=storage.buckets.get,storage.objects.get,storage.objects.create --stage=GA
Invoke-Gcp storage buckets add-iam-policy-binding "gs://$UploadsBucket" --member="serviceAccount:$ApiSa" --role="projects/$Project/roles/factorymindUploadStore"
Invoke-Gcp artifacts repositories add-iam-policy-binding factorymind --project=$Project --location=$Region --member="serviceAccount:$BuildSa" --role=roles/artifactregistry.writer
Invoke-Gcp projects add-iam-policy-binding $Project --member="serviceAccount:$BuildSa" --role=roles/logging.logWriter
Invoke-Gcp storage buckets add-iam-policy-binding "gs://$SourceBucket" --member="serviceAccount:$BuildSa" --role=roles/storage.objectViewer
Invoke-Gcp storage buckets add-iam-policy-binding "gs://$SourceBucket" --member="user:$Operator" --role=roles/storage.objectCreator
foreach ($Sa in @($ApiSa,$WebSa,$BuildSa,$TaskSa)) {
    Invoke-Gcp iam service-accounts add-iam-policy-binding $Sa --project=$Project --member="user:$Operator" --role=roles/iam.serviceAccountUser
}
Invoke-Gcp iam service-accounts add-iam-policy-binding $TaskSa --project=$Project --member="serviceAccount:$ApiSa" --role=roles/iam.serviceAccountUser
```

Firestore server clients use IAM; browser-client rules should deny direct access if Firebase client access is enabled. Upload objects are private and exposed only through authenticated API reads. No service-account JSON key is needed. Dedicated Cloud Build identity avoids assuming which legacy/default account a new project selects; it needs log writer plus source read and artifact push, not runtime database/secret access. [User-managed Cloud Build identities](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts).

### Safe data cutover decision, before releasing application access

Recommended first staging deployment: explicitly approve an **empty** Firestore store and new private bucket, retain local history untouched. This does not preserve local investigation history in the cloud. If history must be retained, stop and perform this controlled migration before team writes are enabled:

1. Stop local API/standalone workers; drain active jobs. Preserve unresolved/failed records accurately, not as successful reports. Back up with SQLite's backup API so WAL content is included; do not rely on copying only `.db` while a writer is active.
2. Record row counts and SHA-256 hashes of images/CSV/knowledge files. Keep backups in ignored `.migration/`, away from Cloud Build upload sources. Use the actual `FACTORYMIND_DB_PATH` if overridden.
3. Build/review a one-off importer into an empty staging namespace. None exists in this repository. Decode JSON fields, preserve IDs/timestamps/evidence/provenance/cache metadata; reject oversized (>850 KB adapter limit) and invalid citation records. Do not overwrite existing documents. Import incidents first, then events/investigations/evidence, scenarios and images. Do not import ephemeral request leases.
4. Map `incidents` to `factorymind_incidents`, `investigations` to `factorymind_investigations`, `counterfactual_scenarios` to `factorymind_counterfactuals`, `visual_evidence` to `factorymind_images`. Put `incident_events` under incident document `events`, and `investigation_evidence` under investigation document `evidence`. Preserve `(investigation_id,evidence_id)` identity, including reused IDs in counterfactuals.
5. Rebuild active incident locks in `factorymind_incident_locks` using SHA-256 of `record_id:algorithm`; active investigation locks in `factorymind_investigation_locks` use incident ID. Reconcile interrupted jobs to failed with a migration reason on the imported copy; legacy running rows have no cloud leases. Do not mutate the original backup.
6. Upload each original image to `uploads/{storage_ref}` with create-only generation precondition. Verify SHA-256 equality, update imported `storage_backend` to `google_cloud_storage`, keep provenance and original filename. Validate images against the stricter production decoder; quarantine invalid legacy images instead of representing them as available evidence.
7. Compare counts, IDs, report/evidence references and hashes; test duplicate prevention and counterfactual exclusions. Obtain cutover approval, retain backups and an import manifest. Migration is a blocker for a history-preserving deployment until this importer and validation exist.

Local backup command after stopping writers (not executed here):

```powershell
New-Item -ItemType Directory -Force .migration | Out-Null
$DbPath = Join-Path (Get-Location) 'services\api\data\incidents.db'
if ($env:FACTORYMIND_DB_PATH) { $DbPath = $env:FACTORYMIND_DB_PATH }
$DbBackup = Join-Path (Get-Location) '.migration\incidents-backup.db'
& .\services\api\.venv\Scripts\python.exe -c 'import sqlite3,sys,pathlib; p=pathlib.Path(sys.argv[1]).resolve(); s=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()' $DbPath $DbBackup
if ($LASTEXITCODE -ne 0) { throw 'SQLite backup failed' }
Get-FileHash -Algorithm SHA256 $DbBackup
# Back up local image directory separately, respecting any configured path override.
```

## 2. Remote Cloud Build

Both commands run from repository root, not from `apps/web` or `services/api`. Source exclusions are in `.gcloudignore`; Docker exclusions are the matching Dockerfile-specific ignore files. Review the actual upload inventory before uploading any source. It must include the CSV, knowledge JSON, package lockfile, requirements and build configs; exclude `.env`, SQLite, uploaded images, keys, caches, and `.migration`.

```powershell
$UploadFiles = @(Invoke-Gcp meta list-files-for-upload)
if ($UploadFiles | Where-Object { $_ -match '(^|[/\\])\.env($|\.)|\.db$|credentials.*\.json$|service-account.*\.json$|\.migration[/\\]' }) { throw 'Sensitive upload paths found; review .gcloudignore' }
foreach ($Required in @('datasets/telemetry/ai4i2020.csv','services/api/knowledge/documents.json','services/api/requirements-cloud.txt','apps/web/package-lock.json','deploy/cloudbuild-api.yaml','deploy/cloudbuild-web.yaml')) {
    if ($Required -notin ($UploadFiles -replace '\\','/')) { throw "Required upload missing: $Required" }
}
$UploadFiles # Review before the following paid builds.
Invoke-Gcp builds submit . --project=$Project --region=$Region --config=deploy/cloudbuild-api.yaml --service-account="projects/$Project/serviceAccounts/$BuildSa" --gcs-source-staging-dir="gs://$SourceBucket/source" --substitutions="_IMAGE=$ApiImage" --timeout=1800s
Invoke-Gcp builds submit . --project=$Project --region=$Region --config=deploy/cloudbuild-web.yaml --service-account="projects/$Project/serviceAccounts/$BuildSa" --gcs-source-staging-dir="gs://$SourceBucket/source" --substitutions="_IMAGE=$WebImage" --timeout=1800s
$ApiDigest = (Invoke-Gcp artifacts docker images describe $ApiImage --project=$Project --format='value(image_summary.digest)').Trim()
$WebDigest = (Invoke-Gcp artifacts docker images describe $WebImage --project=$Project --format='value(image_summary.digest)').Trim()
if (!$ApiDigest.StartsWith('sha256:') -or !$WebDigest.StartsWith('sha256:')) { throw 'Missing immutable image digest' }
$ApiPinned = "${Registry}/api@$ApiDigest"
$WebPinned = "${Registry}/web@$WebDigest"
```

Do not rebuild after changing runtime environment variables. Retain these digests and build IDs for rollback. Do not use `latest` for a release. Build service-account logging is explicitly configured in the repository files; source bucket permissions are scoped separately. [Cloud Build submit reference](https://cloud.google.com/sdk/gcloud/reference/builds/submit).

## 3. Backend deployment, AI disabled

Resolve the first-service URL dependency with a private bootstrap revision. Configuration validation requires task settings, but the queue need not exist for startup. Queue creation intentionally happens after frontend deployment. Bootstrap has no allowed browser traffic and no Gemini secret/calls.

```powershell
$BackendEnv = Get-Content deploy/backend.env.example.yaml -Raw
$BackendEnv = $BackendEnv.Replace('REPLACE_PRIVATE_BUCKET',$UploadsBucket).Replace('REPLACE_PROJECT',$Project).Replace('REPLACE_REGION',$Region)
$BackendEnv = $BackendEnv.Replace('https://REPLACE_BACKEND.run.app','https://bootstrap.invalid')
$BackendEnv = $BackendEnv.Replace('AI_INVESTIGATION_ENABLED: "true"','AI_INVESTIGATION_ENABLED: "false"')
Set-Content deploy/backend.env.yaml $BackendEnv -Encoding utf8
if (Select-String -Path deploy/backend.env.yaml -Pattern 'REPLACE_|YOUR_') { throw 'Unresolved backend placeholders' }
$ApiDeploy = @('run','deploy','factorymind-api',"--project=$Project","--region=$Region","--image=$ApiPinned","--service-account=$ApiSa",'--no-allow-unauthenticated','--invoker-iam-check','--ingress=all','--port=8080','--timeout=900','--cpu=1','--memory=1Gi','--concurrency=8','--min=0','--max=1','--cpu-throttling','--env-vars-file=deploy/backend.env.yaml','--startup-probe=httpGet.path=/healthz,httpGet.port=8080,timeoutSeconds=5,periodSeconds=10,failureThreshold=24')
Invoke-Gcp @ApiDeploy
$BackendUrl = (Invoke-Gcp run services describe factorymind-api --project=$Project --region=$Region --format='value(status.url)').TrimEnd('/')
if (!$BackendUrl.StartsWith('https://')) { throw 'Backend canonical URL missing' }
$BackendEnv = $BackendEnv.Replace('https://bootstrap.invalid',$BackendUrl)
Set-Content deploy/backend.env.yaml $BackendEnv -Encoding utf8
Invoke-Gcp @ApiDeploy
foreach ($Caller in @($WebSa,$TaskSa)) {
    Invoke-Gcp run services add-iam-policy-binding factorymind-api --project=$Project --region=$Region --member="serviceAccount:$Caller" --role=roles/run.invoker
}
$SafeApiRevision = (Invoke-Gcp run services describe factorymind-api --project=$Project --region=$Region --format='value(status.latestReadyRevisionName)').Trim()
```

`FACTORYMIND_AUTH_AUDIENCE`, `FACTORYMIND_TASKS_TARGET` and frontend backend origin must all match `$BackendUrl`. The API caller is `$WebSa`, worker caller `$TaskSa`. Use distinct identities. Do not use task URL paths or a traffic-tag URL as the ID-token audience. IAM-private services use `--ingress=all` here so private authenticated team proxy and Cloud Tasks can reach them; IAM still denies anonymous traffic. Internal ingress needs separate network configuration, not an arbitrary flag change.

The template selects Firestore `(default)`, prefix `factorymind`, GCS private bucket, Cloud Tasks dispatch, Google provider, explicit model, asynchronous regular investigations, 40-second request timeout, one retry, 900-second dispatch deadline, concurrency one, report cache and provider cooldowns. The six-stage budget check is 876 seconds, below 900. Do not increase retry/timeouts without rechecking it. Scratch `/tmp` DB paths in the image are not production persistence.

## 4. Frontend deployment, private team access

```powershell
$FrontendEnv = (Get-Content deploy/frontend.env.example.yaml -Raw).Replace('https://REPLACE_BACKEND.run.app',$BackendUrl)
Set-Content deploy/frontend.env.yaml $FrontendEnv -Encoding utf8
Invoke-Gcp run deploy factorymind-web --project=$Project --region=$Region --image=$WebPinned --service-account=$WebSa --no-allow-unauthenticated --invoker-iam-check --ingress=all --port=8080 --timeout=900 --cpu=1 --memory=512Mi --concurrency=8 --min=0 --max=1 --cpu-throttling --env-vars-file=deploy/frontend.env.yaml
Invoke-Gcp run services add-iam-policy-binding factorymind-web --project=$Project --region=$Region --member=$TeamMember --role=roles/run.invoker
$FrontendUrl = (Invoke-Gcp run services describe factorymind-web --project=$Project --region=$Region --format='value(status.url)').TrimEnd('/')
$SafeWebRevision = (Invoke-Gcp run services describe factorymind-web --project=$Project --region=$Region --format='value(status.latestReadyRevisionName)').Trim()
```

Access through `gcloud run services proxy` on localhost:8080 matches `FACTORYMIND_WEB_ORIGIN=http://localhost:8080`. Do not browse as 127.0.0.1 for writes or change ports without updating the trusted origin. Sharing the canonical URL does not provide a public login flow. If public competition access is required, stop and implement IAP/end-user authentication first. The proxy's Origin check protects writes but is not end-user authentication. [Google-signed ID tokens and two-header behavior](https://docs.cloud.google.com/run/docs/authenticating/service-to-service).

## 5. Cloud Tasks configuration, initially paused

```powershell
Invoke-Gcp tasks queues create $Queue --project=$Project --location=$Region --max-concurrent-dispatches=1 --max-dispatches-per-second=0.1 --max-attempts=10 --max-retry-duration=3600s --min-backoff=60s --max-backoff=300s --log-sampling-ratio=1
Invoke-Gcp tasks queues pause $Queue --project=$Project --location=$Region
Invoke-Gcp tasks queues add-iam-policy-binding $Queue --project=$Project --location=$Region --member="serviceAccount:$ApiSa" --role=roles/cloudtasks.enqueuer
Invoke-Gcp beta services identity create --service=cloudtasks.googleapis.com --project=$Project
$TasksAgent = "service-$ProjectNumber@gcp-sa-cloudtasks.iam.gserviceaccount.com"
Invoke-Gcp projects add-iam-policy-binding $Project --member="serviceAccount:$TasksAgent" --role=roles/cloudtasks.serviceAgent
Invoke-Gcp iam service-accounts add-iam-policy-binding $TaskSa --project=$Project --member="serviceAccount:$TasksAgent" --role=roles/iam.serviceAccountUser
Invoke-Gcp tasks queues describe $Queue --project=$Project --location=$Region
```

If the queue already exists, inspect it and use `queues update` with the same limits instead of creating/deleting it. Never grant `roles/cloudtasks.serviceAgent` to a runtime account. The task identity belongs to the queue's project, has backend invoker, and is in the worker allowlist. Backend has enqueuer on this queue and actAs on the task identity. Cloud Tasks service agent obtains tokens. [HTTP task authentication requirements](https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks).

Regular investigation work is acknowledged only after handling; model failures persist as failed and return 200 to avoid repeated quota consumption. Duplicate active execution returns 503/Retry-After; expired job claims can recover. The retry window exceeds the 1020-second lease. Counterfactual and image analysis remain synchronous and must be tested separately before use; this queue does not make those parent orchestration flows durable.

## 6. Smoke tests — no Gemini calls first

First inspect policies: neither service should have `allUsers` or `allAuthenticatedUsers`, and IAM invoker checks must remain enabled. Inspect only selected config fields; never dump secret payloads or tokens to logs.

```powershell
Invoke-Gcp run services get-iam-policy factorymind-api --project=$Project --region=$Region
Invoke-Gcp run services get-iam-policy factorymind-web --project=$Project --region=$Region
# These anonymous POSTs must be denied by Cloud Run (normally 403, possibly 401).
$Code = & curl.exe -s -o NUL -w '%{http_code}' --max-time 30 -X POST -H 'Content-Type: application/json' --data '{}' "$BackendUrl/api/incidents"
if ($Code -notin @('401','403')) { throw "Anonymous backend write not denied: $Code" }
$Code = & curl.exe -s -o NUL -w '%{http_code}' --max-time 30 -X POST -H 'Origin: http://localhost:8080' --data '{}' "$FrontendUrl/api/backend/api/incidents"
if ($Code -notin @('401','403')) { throw "Anonymous frontend proxy not denied: $Code" }
# Run in a second terminal and leave it open for the localhost tests:
Invoke-Gcp run services proxy factorymind-web --project=$Project --region=$Region --port=8080
```

In another PowerShell terminal:

```powershell
Invoke-RestMethod http://localhost:8080/api/health
Invoke-RestMethod http://localhost:8080/api/backend/api/incidents?limit=1
# The proxy itself must block the worker endpoint, HTTP 403:
curl.exe -s -o NUL -w '%{http_code}' -X POST -H 'Origin: http://localhost:8080' http://localhost:8080/api/backend/api/investigations/INV-NOPE/process
```

The incident GET through the proxy tests frontend ADC → signed token → Cloud Run IAM → backend signature/audience/role validation → Firestore. A 502/401/403 is a failure to investigate, not a successful smoke test.

For backend `/readyz` and worker authentication, temporarily grant the operator token-creator on the two caller identities for testing, then revoke it. Keep ID tokens only in memory; no `--log-http`, transcript, or echo. This is a reviewed temporary diagnostic privilege, not a runtime requirement.

```powershell
foreach ($Sa in @($WebSa,$TaskSa)) {
    Invoke-Gcp iam service-accounts add-iam-policy-binding $Sa --project=$Project --member="user:$Operator" --role=roles/iam.serviceAccountTokenCreator
}
try {
    $WebToken = (Invoke-Gcp auth print-identity-token --impersonate-service-account=$WebSa --audiences=$BackendUrl --include-email).Trim()
    $Headers = @{ Authorization="Bearer $WebToken"; 'X-Serverless-Authorization'="Bearer $WebToken" }
    Invoke-RestMethod "$BackendUrl/readyz" -Headers $Headers
    # Wrong role: frontend identity must get 403 from the worker endpoint.
    # curl status only; avoid printing the token in a command transcript.
    try { Invoke-RestMethod "$BackendUrl/api/investigations/INV-NOPE/process" -Method Post -Headers $Headers; throw 'Wrong-role request was accepted' }
    catch { if ([int]$_.Exception.Response.StatusCode -ne 403) { throw } }
    $TaskToken = (Invoke-Gcp auth print-identity-token --impersonate-service-account=$TaskSa --audiences=$BackendUrl --include-email).Trim()
    $Headers = @{ Authorization="Bearer $TaskToken"; 'X-Serverless-Authorization'="Bearer $TaskToken" }
    # Correct role reaches the handler but must return 404 for this nonexistent ID; no model runs.
    try { Invoke-RestMethod "$BackendUrl/api/investigations/INV-NOPE/process" -Method Post -Headers $Headers; throw 'Unexpected nonexistent job' }
    catch { if ([int]$_.Exception.Response.StatusCode -ne 404) { throw } }
} finally {
    $WebToken=$null; $TaskToken=$null; $Headers=$null
    foreach ($Sa in @($WebSa,$TaskSa)) {
        Invoke-Gcp iam service-accounts remove-iam-policy-binding $Sa --project=$Project --member="user:$Operator" --role=roles/iam.serviceAccountTokenCreator
    }
}
```

Verify actual queue-to-worker delivery without a model call: operator needs scoped Tasks administration/run permissions already used for provisioning. Create one nonexistent-job probe on the paused queue, force it once, confirm backend request logs show handler 404 rather than auth 401/403, then delete it. HTTP 404 is intentional for this diagnostic only; it is not a completed investigation. [Task creation flags](https://docs.cloud.google.com/sdk/gcloud/reference/tasks/create-http-task).

```powershell
$ProbeTask = "oidc-probe-$Release"
try {
    Invoke-Gcp tasks create-http-task $ProbeTask --project=$Project --location=$Region --queue=$Queue --url="$BackendUrl/api/investigations/INV-NOPE/process" --method=POST --oidc-service-account-email=$TaskSa --oidc-token-audience=$BackendUrl
    Invoke-Gcp tasks run $ProbeTask --project=$Project --location=$Region --queue=$Queue
    Invoke-Gcp tasks describe $ProbeTask --project=$Project --location=$Region --queue=$Queue
    Invoke-Gcp run services logs read factorymind-api --project=$Project --region=$Region --limit=30
} finally {
    Invoke-Gcp tasks delete $ProbeTask --project=$Project --location=$Region --queue=$Queue --quiet
}
```

Before enabling AI, verify a bounded incident creation through the frontend, then read it after replacing/restarting a revision; confirm Firestore persistence and duplicate rejection. Use an anomaly selected from `/api/anomalies` rather than an invented record ID. Upload one permitted image and fetch it through the proxy to prove GCS write/read and metadata linkage; **do not click Analyze**. Check no storage path/public URL/key is exposed. Health/readiness only prove repository/bucket access, not these writes. The existing schemas/UI define payloads; use UI workflows to avoid guessing fields. These tests create a few intentional demo records and need the approved fresh/migrated store.

Only after all checks, model availability/quota confirmation, and approval for one paid/quota-consuming investigation:

```powershell
# Confirm numeric secret version is ENABLED; do not access its payload.
Invoke-Gcp secrets versions describe $SecretVersion --secret=$Secret --project=$Project --format='value(state)'
$EnabledEnv = (Get-Content deploy/backend.env.yaml -Raw).Replace('AI_INVESTIGATION_ENABLED: "false"','AI_INVESTIGATION_ENABLED: "true"')
Set-Content deploy/backend.env.yaml $EnabledEnv -Encoding utf8
Invoke-Gcp run services update factorymind-api --project=$Project --region=$Region --env-vars-file=deploy/backend.env.yaml --set-secrets="GOOGLE_API_KEY=${Secret}:$SecretVersion"
Invoke-Gcp tasks queues resume $Queue --project=$Project --location=$Region
```

Run exactly one investigation from the UI; verify queued → running → completed **or honest failed state**, persisted evidence IDs/citations, critic review, and quota logs. Do not automatically retry 429 RPD/model allocation failures. An unchanged completed report should reuse the report cache; an explicit rerun and counterfactual have different semantics. Do not run live pytest or visual analysis as part of routine deployment. No success is claimed until these real tests pass.

## Rollback and troubleshooting

Keep `$SafeApiRevision`, `$SafeWebRevision`, release digests, environment snapshots without secrets, and the migration manifest. Subsequent successful releases should record their own known-good revision names. For the first release, the safe API revision is AI-disabled; there is no earlier live application to roll back to.

```powershell
Invoke-Gcp tasks queues pause $Queue --project=$Project --location=$Region
Invoke-Gcp run services update-traffic factorymind-api --project=$Project --region=$Region --to-revisions="$SafeApiRevision=100"
Invoke-Gcp run services update-traffic factorymind-web --project=$Project --region=$Region --to-revisions="$SafeWebRevision=100"
Invoke-Gcp run revisions list --service=factorymind-api --project=$Project --region=$Region
Invoke-Gcp run services describe factorymind-api --project=$Project --region=$Region --format='yaml(status.conditions,status.traffic,status.url)'
Invoke-Gcp run services logs read factorymind-api --project=$Project --region=$Region --limit=50
Invoke-Gcp run services logs read factorymind-web --project=$Project --region=$Region --limit=50
Invoke-Gcp builds list --project=$Project --region=$Region --limit=5
# Replace with a failed build ID; no secrets should be printed by these builds.
Invoke-Gcp builds log 'YOUR_BUILD_ID' --project=$Project --region=$Region
Invoke-Gcp tasks queues describe $Queue --project=$Project --location=$Region
Invoke-Gcp tasks list --project=$Project --location=$Region --queue=$Queue --limit=10
```

Traffic rollback does not undo Firestore writes, image uploads, tasks, or secret versions. Pause dispatch, allow running work to finish or reconcile it, compare data to the import manifest, and restore into a separate namespace if needed. Never purge the queue or delete cloud databases/buckets as a troubleshooting shortcut. [Traffic rollback](https://docs.cloud.google.com/sdk/gcloud/reference/run/services/update-traffic).

| Symptom | Check / response |
|---|---|
| Build fails before Docker starts | CLI auth, billing, APIs, actAs on build identity, source bucket upload/read, log writer, artifact writer; use the repository root context |
| Build misses CSV/.env is uploaded | Review upload inventory and .gcloudignore before rebuilding; never upload real secrets |
| Backend fails startup | Production settings, 876-second budget, Firestore Native mode/database, API identity datastore permissions, dataset packaging; never change production to development |
| `/readyz` dependency failure | Bucket exists, custom role includes buckets.get, ADC project/database and Firestore permissions |
| Proxy 502 | Backend origin exact, frontend identity attached, backend invoker binding, Google certificate/metadata egress, backend caller allowlist |
| Backend app 401 | Signed ID token, exact audience, not an OAuth access token; both-header test distinguishes platform and application checks |
| Worker 403 | Worker email/verified identity, task SA invoker and worker allowlist; web identity must remain denied |
| Tasks cannot mint OIDC | Tasks service agent role, task identity in same project, creator actAs, service-agent configuration |
| Frontend writes 403 | Origin exactly localhost:8080 for private proxy access; do not disable Origin check |
| Gemini 429 / 503 | Inspect safe category/model/latency logs; retain bounded retries/cooldowns, confirm quota/model availability; never switch models silently |
| Job remains running | Queue delivery/lease expiration and stored status; inspect before rerunning; no exactly-once guarantee after stale lease ownership |

## Costs, evidence and acceptance

Use one region, request-based CPU, min zero/max one instance for each service, one vCPU, modest memory, queue concurrency one, no VPC connector/load balancer/Cloud SQL/GPU, private access and caches. Idle instances scale down but builds, storage, Firestore operations, log ingestion, soft-deleted storage and Gemini can still cost money. Budgets are alerts, not hard spending caps. Keep build-source retention short after a reviewed lifecycle policy, retain known-good image digests and migration backups, and reduce Tasks log sampling after acceptance. No exact cost estimate or free-tier guarantee is made.

Changed in this preparation: this guide and the two Cloud Build YAML files (log configuration). No agents or API contracts changed. Verification: 22 mocked cloud tests passed; seven representative anonymous POST routes (incident create/scan, investigation start/process, counterfactual, image upload/analyze) returned 401 before handlers ran; all 14 PowerShell blocks parsed successfully; deployment YAML parsed; `git diff --check` passed. The first targeted test invocation hit a Windows temporary-directory permission error; the workspace-temp retry passed. PowerShell parsing verifies syntax, not CLI flags or cloud permissions; gcloud was unavailable here. No live Gemini calls were made. Full prior backend/frontend and Docker results are recorded in `reports/gcp-deployment-readiness.md`; they do not establish real GCP success. The next action is user approval of prerequisites/resources, then execution from an environment with gcloud, in the order above.
