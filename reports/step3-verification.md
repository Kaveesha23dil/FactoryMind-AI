# Step 3 implementation audit

Audit date: 2026-10-10. Existing work on `feature/anomaly-detection-engine` was preserved.
No commits, pushes, or merges were performed.

## Features checked and repaired

The existing detector, APIs, incident repository, and dashboard already implemented
most of Step 3. This audit repaired finite positive threshold validation, invalid
training-data handling, negative numerical overflow, complete incident contribution
snapshots, persisted detection configuration, stale concurrent status updates,
structured JSON logging, and histogram boundaries aligned to the configured threshold.
The incident chart now uses the saved threshold; legacy snapshots without configuration
do not invent one. The temperature chart uses observation IDs and scatter points.
Nested source measurements render as JSON rather than `[object Object]`.

Anomaly monitoring includes summary statistics, severity/score charts, paginated filters,
feature contributions, observed-vs-baseline evidence, historical failure comparison,
incident creation, and evaluation. Incident management includes filters, detail pages,
snapshots, application event timestamps, status transitions, and timelines.
Investigate with AI remains disabled with Coming in Step 4. No Gemini was implemented.

## Algorithm and evaluation

`robust_zscore_v1`: z = (observed - training median) / (1.4826 * MAD).
MAD=0 falls back to mean absolute deviation, standard deviation, then epsilon (1e-6).
Per-type baselines require 200 training records; small/degenerate groups fall back to
the global baseline. Seven sensor features include derived temperature difference
and mechanical power. Ground-truth labels never enter detection or investigation input.
Overall score is the Euclidean norm; individual z-scores are capped at +/-50.
Feature threshold: 3. Overall threshold: 4. Severity: normal <4, low [4,5),
medium [5,6), high [6,8), critical >=8. These are application severities.

Seed 42 splits 10,000 records into 6,000 train / 2,000 validation / 2,000 test.
Only training fits baselines; threshold selection uses validation only.

| Test metric | Configured 4.0 | Validation-selected 4.0448 |
|---|---:|---:|
| Precision | 0.1818 | 0.1630 |
| Recall | 0.2400 | 0.2000 |
| F1 | 0.2069 | 0.1796 |
| False-positive rate | 0.0421 | 0.0400 |
| TP / TN / FP / FN | 18 / 1844 / 81 / 57 | 15 / 1848 / 77 / 60 |

The test set has 75 failure labels and 1,925 nonfailures. These results show limited
failure-label agreement; unusual observations and failures are different tasks.
The synthetic, imbalanced data has no real timestamps, vibration, or continuous machine
identity. Derived features are correlated and the diagonal detector does not model
covariance. Scores are not calibrated failure probabilities.
Machine-readable metrics: `reports/anomaly-evaluation.json`.

## API endpoints

Existing GET endpoints `/health`, `/api/dataset/summary`, `/api/telemetry`,
and `/api/telemetry/{record_id}` remain available.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | /api/anomalies/summary | Counts, severity, baselines, histogram |
| GET | /api/anomalies | Paginated anomalies; severity, minimum severity, type filters |
| GET | /api/anomalies/{record_id} | All contributions, explanations, incident status |
| GET | /api/anomalies/evaluation | Reproducible held-out metrics |
| POST | /api/incidents | Create from record_id and optional note |
| GET | /api/incidents | Pagination and status/severity filters |
| GET | /api/incidents/{incident_id} | Persisted evidence and timeline |
| PATCH | /api/incidents/{incident_id}/status | Validated transition, optional note |
| POST | /api/incidents/scan | Explicit bounded scan, dry_run supported |
| GET | /api/incidents/{incident_id}/investigation-payload | Label-free future investigation input |

Pagination: limit 1-200, offset >=0. Creation of a duplicate active record/algorithm
returns 409 with existing ID; a SQLite unique index protects concurrent creation.
No incidents are created on startup. Transitions: open -> under_review/resolved;
under_review -> open/resolved; resolved -> under_review. Reopening cannot violate
active uniqueness. Database initialization includes an additive snapshot-config migration.

## File inventory

New files added by this audit: `scripts/evaluate_anomalies.py`,
`services/api/tests/test_dataset_api.py`, `reports/anomaly-evaluation.json`,
and `reports/step3-verification.md`.
Modified by this audit: README.md; services/api/core/config.py; db/database.py;
main.py; schemas/incident.py; services/anomaly_detector.py, anomaly_engine.py,
incident_service.py; tests/test_anomaly_detector.py, test_anomaly_api.py,
test_incident_service.py; apps/web/src/types/incident.ts;
components/incidents/IncidentDetail.tsx; components/charts/TemperatureChart.tsx.

Existing uncommitted Step 3 additions were preserved: anomaly and incident detail
routes; components/anomalies and components/incidents; lib/severity.ts;
types/anomaly.ts and types/incident.ts. Existing changes to sidebar, overview,
telemetry details, badges, API helpers, formatting, anomaly routes/schemas/engine,
incident service, and API tests were preserved.
Pages available: /anomalies, /incidents, /incidents/[incidentId], alongside monitoring.

## Run and verify

From the repository root (Python 3.12):

```powershell
python -m pip install -r services/api/requirements.txt
python -m uvicorn services.api.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd apps/web
npm ci
npm run dev
```

Open http://localhost:3000 and API docs http://127.0.0.1:8000/docs.

```powershell
python -m pytest -v
python -m scripts.evaluate_anomalies
cd apps/web
npm run lint
npm run build
```

Configuration: FACTORYMIND_DATASET_PATH, FACTORYMIND_DB_PATH,
FACTORYMIND_CORS_ORIGINS (comma-separated), FACTORYMIND_LOG_LEVEL,
FACTORYMIND_RANDOM_SEED, FACTORYMIND_ANOMALY_SCORE_THRESHOLD,
FACTORYMIND_FEATURE_Z_THRESHOLD. Frontend: NEXT_PUBLIC_API_URL in apps/web/.env.local.
Restart the backend after changing detector configuration.

Default SQLite file: services/api/data/incidents.db. Existing incidents survive restarts.
Local development endpoints are unauthenticated. Authentication/authorization and
deployment hardening are required before exposing state-changing APIs publicly.
Firestore and Gemini remain future integration work.

Verification checks use FastAPI TestClient and real dataset scoring. Frontend verification
is compilation, TypeScript, and lint; an interactive browser walkthrough was not performed.

Executed results: `python -m pytest -v` passed all 55 tests (4.07 seconds),
including persistence, legacy-schema migration, duplicate prevention, stale status updates,
detector math, label isolation, API validation, evaluation, and Step 2 endpoint regression.
`npm run build` passed production compilation and TypeScript checks; `npm run lint`
passed with no findings. `git diff --check` passed. The initial sandboxed Next.js build
was denied Windows path access; the build succeeded with approved local filesystem access.
