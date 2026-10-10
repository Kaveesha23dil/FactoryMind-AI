# Step 4 implementation verification

Verification date: 2026-10-10. Existing work on
`feature/gemini-multi-agent-investigation` was preserved. No commits, pushes, or
merges were performed.

Step 4 delivers an evidence-driven, Gemini-powered multi-agent root-cause
investigation engine. The four agents (sensor, knowledge, investigation, critic)
run a bounded ADK pipeline; results are stored as persistent investigation jobs and
surfaced in a new AI Investigations workspace in the web app. The "Investigate with
AI" action on incident details is now enabled.

## Agent architecture

- Sensor agent gathers label-free incident and anomaly evidence (fixed measurements,
  per-feature baseline statistics, recorded source values) into a persisted evidence
  catalog with stable IDs (e.g. `EV-SOURCE-001`, `EV-ANOMALY-001`, `EV-SENSOR-00n`,
  `EV-BASELINE-00n`, `EV-MANUAL-00n`).
- Knowledge agent retrieves the top-K matching passages from the local knowledge base
  (`services/api/knowledge/documents.json`) and returns them as untrusted citations.
- Investigation agent produces up to `FACTORYMIND_INVESTIGATION_MAX_HYPOTHESES`
  hypotheses, each with supporting/contradicting evidence IDs, missing evidence,
  verification steps, and an assessment.
- Critic agent verifies conclusions: it checks citations against the evidence catalog
  and knowledge base, flags unsupported claims/contradictions/alternatives, reports
  deterministic findings, and may request a single revision. `citation_issues`
  reject the affected hypothesis; unsupported citations are dropped from the report.
- No model-callable tools. Deterministic Python tools prepare all numbers and evidence
  before model output, so hallucinated citations are distinguished from real ones.
- Bounded pipeline with a per-step timeout (`FACTORYMIND_INVESTIGATION_TIMEOUT_SECONDS`,
  default 90) and exponential backoff, at most `FACTORYMIND_INVESTIGATION_MAX_RETRIES`
  (default 1) revisions.

Hard rules enforced by validation tests: ground-truth failure labels never reach
agents or the frontend; anomaly score is never presented as a failure probability;
unknown evidence IDs are rejected; retrieved documents are treated as untrusted data;
no hardcoded or invented AI output in the app path.

## API endpoints

| Method | Endpoint | Behavior |
|---|---|---|
| POST | /api/incidents/{incident_id}/investigate | 202 with investigation_id; 409 duplicate, 404 incident, 503 disabled |
| GET | /api/investigations | Global paginated list; optional status filter |
| GET | /api/investigations/{investigation_id} | Job state, stage history, agent activity, report |
| GET | /api/incidents/{incident_id}/investigations | Paginated history for an incident |
| GET | /api/investigations/{investigation_id}/evidence | Persisted evidence catalog |
| POST | /api/investigations/{investigation_id}/process | Worker entry (requires X-Worker-Secret) |

Statuses: queued/running/completed/failed. Stages: queued, collecting_evidence,
analyzing_measurements, retrieving_knowledge, generating_hypotheses,
verifying_conclusions, completed, failed.

The process endpoint is idempotent and Cloud Tasks compatible. In-process workers
start with uvicorn when `FACTORYMIND_INVESTIGATION_ASYNC=true`; a standalone worker
runs as `python -m services.api.services.investigation_worker`.

## Configuration

Create `services/api/.env` from `.env.example`. Key settings: `AI_PROVIDER`
(google|scripted), `GEMINI_MODEL` (default gemini-2.5-flash), `GOOGLE_API_KEY`,
`AI_INVESTIGATION_ENABLED`, `FACTORYMIND_INVESTIGATION_ASYNC`,
`FACTORYMIND_WORKER_SECRET`, `FACTORYMIND_KNOWLEDGE_TOP_K`, and the pipeline limits
above. With `AI_PROVIDER=scripted` (no API key) the payloads and UI still work; the
live Gemini smoke test is skipped unless `GOOGLE_API_KEY` is set.

## Frontend

New types in `apps/web/src/types/investigation.ts` and API helpers in `lib/api.ts`.
The list page `/investigations` shows KPI cards and a paginated, filterable log. The
workspace `/investigations/[investigationId]` (dynamic route, `export const instant
= false`) renders agent activity, pipeline stages, critic review cards, hypotheses
with citation chips, critic review, recommended actions (with approval flags),
rejected citations, the evidence catalog, and auto-refreshes while queued/running.
Incident detail now starts investigations and lists previous ones; AI Investigations
appears in the sidebar without the "Soon" badge.

## Tests and verification

```powershell
python -m pytest -q          # 84 passed, 1 skipped (live Gemini smoke)
cd apps/web
npm run lint                 # 0 findings
npm run build                # production build + typecheck passed
```

New tests: validation (evidence IDs, report shape, citation rejection),
`test_agent_orchestration.py` (bounded pipeline with scripted model), and
`test_investigations.py` (start/get/list/process endpoints and service). Tests mock
the model layer with `ScriptedLlm` so the real ADK runner/validation path executes
without network access.

## Inventory

New: `services/api/agents/*`, `services/api/tools/*`,
`services/api/services/{investigation_service,investigation_repository,
investigation_worker,knowledge_repository}.py`, `services/api/schemas/{evidence,
hypothesis,investigation}.py`, `services/api/knowledge/documents.json`,
`.env.example`, `tests/{test_evidence_validation,test_agent_orchestration,
test_investigations,test_live_gemini_smoke}.py`; web
`apps/web/src/types/investigation.ts`, `apps/web/src/lib/investigations.ts`,
`components/investigations/*`, the two `/investigations` pages.

Modified: `requirements.txt`, `core/config.py`, `db/database.py`, `main.py`,
`routes/investigations.py`, `tests/conftest.py`; web `lib/api.ts`,
`components/incidents/IncidentDetail.tsx`, `components/layout/AppSidebar.tsx`,
`README.md`.

## Limitations

Local-development API only; endpoints are unauthenticated and require hardening
before public deployment. The in-process worker is a thread; use Cloud Tasks plus the
idempotent process endpoint for scale. Knowledge base and citation handling assume
the bundled documents. Live runs depend on Gemini availability.

## Run

```powershell
python -m pip install -r services/api/requirements.txt
python -m uvicorn services.api.main:app --reload --port 8000
# optional standalone worker: python -m services.api.services.investigation_worker
# frontend (apps/web): npm ci && npm run dev
```