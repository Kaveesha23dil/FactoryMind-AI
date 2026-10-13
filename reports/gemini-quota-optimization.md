# Gemini quota optimization — 13 October 2026

This change builds on the existing evidence-verification fixes. It preserves the Sensor, Knowledge, Investigation, Critic, counterfactual, and visual workflows. No live Gemini calls were made during this optimization, because the supplied logs already showed exhausted daily quota. No commit, push, deployment, billing change, or automatic model switch was performed.

## Calls traced and approximate requests before/after

`python scripts/trace_gemini_usage.py` runs the real ADK Runner with scripted models, temporary SQLite stores, synthetic reference documents, and a mock inspection image. It counts calls to the model's `generate_content_async`, rather than inferring counts from UI activity. The resulting [JSON trace](gemini-usage-trace.json) records agent names and prompt character counts, never prompt contents. These are measured mocked model invocations, **not live HTTP or billing measurements**. Healthy Gemini execution normally has one `generateContent` request per such invocation; retries or extra structured-output turns can increase the count.

| Workload | Before optimization | After optimization | Measured result |
| --- | ---: | ---: | --- |
| Fresh investigation | Approximately 4, or 6 with revision | Approximately 4, or 6 with revision | 4: Sensor → Knowledge → Investigation → Critic |
| Unchanged, verified repeat | Approximately 4–6 again | 0 | Cache-disabled baseline: 4 additional turns; cache-enabled repeat: 0 |
| Two identical successful investigation requests | Approximately 8 | Approximately 4 total | 8 with reuse disabled versus 4 with reuse enabled |
| Explicit user rerun | Approximately 4–6 | Approximately 4–6 | 4 new turns |
| Counterfactual | Approximately 4–6 | Approximately 4–6, never the original cache hit | 6 new turns after excluding a cited sensor, including Investigation/Critic revision |
| Visual inspection | Approximately 1 | Approximately 1, plus bounded retries if transiently unsuccessful | 1 Vision turn |

The measured after-change prompt totals were 20,316 characters for the four-turn investigation, 28,599 for the six-turn restricted counterfactual, and 439 for the vision text prompt (image bytes are separate). Character counts are **not token estimates**; actual token usage is recorded only when Gemini supplies it.

The installed SDK default was **five attempts** per request, while application retries also existed. The previous ADK default allowed **500 model calls** in one invocation. Those were inspected from the installed dependencies; no historical billed-request total is claimed. The implementation now sets SDK attempts to **one** and ADK model calls to **four per agent invocation by default**. The application is the sole owner of provider retries. At the default three retries, a pathological six-invocation revision path is bounded to 96 model request attempts (6 × 4 invocation attempts × 4 model calls), while ordinary successful execution still uses 4–6. The quota classifier stops daily/spending/allocation failures on their first failed call, and a recorded cooldown blocks subsequent calls.

## Usage logging and retry ownership

`MeteredGemini` records each model request with:

- `event`, `agent`, `model`, `request_count`, and `latency_ms`;
- `input_tokens` and `output_tokens` when present, otherwise null;
- `error_category` when unsuccessful or cancelled.

These fields are top-level JSON log fields in both the API and standalone worker. A cache hit emits an explicit zero-request event. Successful reports persist their original request metrics in `report.usage`; metrics from a reused report describe its original generation, while the new cache-hit log records zero consumption. Model invocation attempts that fail before dispatch cannot be assumed to be billable HTTP requests. Provider/ADK dependency tracebacks are suppressed in favor of safe category summaries; prompts, image bytes, API keys, and model responses are not logged by the usage meter.

Quota/error classification recognizes RPM, TPM, RPD, spending limits, unavailable model allocation, unknown quota, temporary unavailability, and timeouts when identifiable. A generic “check billing” link in a rate-limit error is not treated as proof of a spending limit. Unknown quota remains explicitly unknown.

HTTP `Retry-After` seconds or HTTP dates and standard `RetryInfo.retryDelay` values are honored. Short delays use the larger of the provider minimum and bounded exponential backoff, with jitter. Long delays, daily quota, spending limits, and zero/unavailable allocations are not repeatedly retried. Shared model cooldowns protect investigations, counterfactuals, and visual requests across processes. If an exhaustion error gives no reset time, a five-minute protective cooldown is used; it is **not** a claim that quota resets in five minutes. Check AI Studio for the actual limit/reset.

## Concurrency, duplicate runs, and persistent outcomes

SQLite request leases limit Gemini calls across the API and standalone worker when both use the same `FACTORYMIND_DB_PATH` and configuration. Leases are released on normal completion/error/cancellation; expired leases from crashed processes are recovered. The lease duration is the configured agent timeout plus a cleanup allowance. Configure every worker with the same concurrency limit.

Investigation execution uses an atomic conditional database claim, so two worker connections cannot run the same queued/running job. The existing unique active-incident index prevents concurrent active investigation jobs; races at job insertion produce the existing duplicate-investigation error rather than another run. Counterfactual jobs remain isolated and use restricted prepared contexts.

Provider failures persist a failed job and mark a running agent failed. No report is marked completed when provider execution fails. A generated report with unresolved critic findings remains visibly revision-required and is excluded from reuse. There is no automatic conversion to scripted output or another model.

## Deterministic caching and report reuse

The anomaly engine already builds and caches deterministic sensor transforms, mechanical power, robust z-scores, and severity for all dataset records. This cache remains the authoritative source, rather than duplicating numerical work in Gemini. Snapshot consistency checks still run during fresh investigations so caching cannot conceal inconsistent measurements.

Knowledge retrieval now uses a bounded in-memory result cache, returns independent copies to callers, and reloads the repository when corpus bytes change. The repository is constructed from the same bytes used as its cache key, avoiding stale source references during file edits.

Completed normal reports are reused only when:

1. The incident, physical snapshot, current anomaly, selected baselines, and retrieved document/section content match.
2. Provider/model identifier, prompt version, instructions, output schemas, relevant configuration, and implementation fingerprints match.
3. The critic does not require revision.
4. The stored evidence catalog and evidence content digest match the original generation.
5. The stored report's content digest still matches, so altered conclusions are not reused.

Fingerprints are persisted with the report, so reuse survives API/worker restart. Inputs are fingerprinted before and after execution; an input change during execution prevents reuse. Historical reports without fingerprints miss the cache safely. Reports with newly attached/modified evidence also miss it. Lookup is bounded to the most recent 100 incident jobs; older matches may miss rather than risk incorrect reuse.

The existing start endpoint accepts the optional `force_rerun=true` query and reports `reused=true` when it returns an existing report. The investigation workspace provides **Rerun with Gemini**. Explicit reruns bypass reuse but continue to respect quota cooldowns. No stored report/evidence is silently modified to look newly generated.

Counterfactuals always run the four-agent reasoning pipeline on their restricted evidence. They never receive or populate the original report cache, and excluded evidence IDs retain their identity. Repeating a counterfactual still performs fresh reasoning. Visual analysis also performs genuine vision reasoning; image analysis outputs are not silently cached by this change.

## Prompt compaction and grounding

The Sensor Agent no longer receives unrelated maintenance passages or a redundant raw-measurement dump. It retains deterministic feature values, scores, baselines, evidence IDs, sources, and provenance. Shared provenance descriptions are emitted once in a registry and referenced by individual records. Knowledge retains exact retrieved passage text/document/section/evidence IDs and its synthetic provenance. Investigation and Critic retain the evidence catalog; no passage is truncated and no cited evidence is discarded to fit a budget. A regression test verifies the reduced sensor prompt size and retained sensor citations/provenance.

## Configuration and model selection

```dotenv
GEMINI_MODEL=gemini-3.8-flash
FACTORYMIND_GEMINI_CONCURRENCY=1
FACTORYMIND_GEMINI_MAX_MODEL_CALLS=4
FACTORYMIND_INVESTIGATION_MAX_RETRIES=3
FACTORYMIND_INVESTIGATION_CACHE_ENABLED=true
FACTORYMIND_PROMPT_VERSION=grounded-v2
FACTORYMIND_PROVIDER_COOLDOWN_ENABLED=true
```

Restart the API and standalone worker to load changed settings. SDK retry attempts are deliberately fixed at one. Model calls per invocation are configurable within 1–8; application retries remain bounded to 0–5. Concurrency controls simultaneous requests, not an RPM/TPM allowance.

The existing model selection is retained. According to the [official model catalog](https://ai.google.dev/gemini-api/docs/models), currently advertised alternatives include `gemini-3.6-flash` and `gemini-3.5-flash-lite`; the current `gemini-3.8-flash` remains the default. Select an alternative explicitly with `GEMINI_MODEL` after checking its project allocation and structured-output/vision suitability. The catalog restricts legacy 2.5 access for new projects, so those are not assumed to be available. Account-specific availability was not checked with live calls. Run the isolated live integration suite and review evidence/critic quality before adopting another model. No automatic fallback is configured.

## Files changed for this optimization

- `services/api/agents/runtime.py`, `request_control.py` (new), `orchestrator.py`, `sensor_agent.py`, `knowledge_agent.py`, `prompts.py`.
- `services/api/core/config.py`, `logging.py` (new), `services/api/db/database.py`, `services/api/main.py`, `services/api/.env.example`.
- `services/api/services/investigation_cache.py` (new), `investigation_repository.py`, `investigation_service.py`, `knowledge_repository.py`, `investigation_worker.py`, `counterfactual_service.py`, `visual_evidence_service.py`.
- `services/api/tools/knowledge_tools.py`, `services/api/routes/investigations.py`, `services/api/schemas/investigation.py`.
- `apps/web/src/lib/api.ts`, `apps/web/src/types/investigation.ts`, `apps/web/src/components/investigations/InvestigationWorkspace.tsx`.
- `services/api/tests/test_quota_optimization.py` (new), `scripts/trace_gemini_usage.py` (new), `reports/gemini-usage-trace.json` (new), this report (new).

Existing uncommitted evidence-quality changes from prior requests were preserved.

## Validation and remaining limits

Verification completed:

- `python -m pytest --ignore=services/api/tests/test_live_gemini_smoke.py`: **174 passed**, including 29 quota-optimization cases.
- `npx tsc --noEmit`: passed.
- `npm run lint`: passed.
- `npm run build`: passed, with all 13 static pages generated.
- `python scripts/trace_gemini_usage.py`: passed; generated the request-count artifact from temporary stores and scripted models.
- `git diff --check`: passed.

New regression coverage includes quota categories, Retry-After, token/latency metering without prompts, report/evidence/config/model/corpus invalidation, persistent reuse, explicit reruns, genuine counterfactual separation, visual request counts, atomic job claims, concurrency/lease cleanup and recovery, and SDK retry ownership.

Live Gemini validation is intentionally not rerun against an exhausted quota. The earlier live full-pipeline failures remain unresolved external availability/quota constraints. Token savings and live billing counts cannot be claimed from mocked responses. With the reported 20-request daily allocation, a healthy four-request fresh investigation still consumes roughly one fifth of that allowance; revisions and visual inspections consume additional requests. Reuse saves requests only for unchanged, verified reports.

SQLite concurrency/cooldowns cover processes sharing this local database, not separate deployments with independent databases. Request leases recover after crashes; interrupted investigation jobs themselves remain running until separately reconciled rather than being automatically replayed, especially because counterfactual prepared contexts must not be guessed after restart. Provider model identifiers do not prove immutable deployed weights; use explicit rerun if provider behavior has changed. The existing FastAPI/Starlette `httpx` deprecation warning remains. No browser visual QA or live allocation verification was performed.
