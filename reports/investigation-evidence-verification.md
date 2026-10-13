# Investigation evidence verification — 13 October 2026

## Findings from existing records and architecture

FactoryMind retains its Next.js frontend, FastAPI endpoints, SQLite incident/job/evidence repositories, deterministic robust z-score engine, and bounded four-agent Gemini/Google ADK pipeline. Counterfactual and visual investigation modules remain available. The initial working tree was clean.

Read-only inspection of the configured development database found completed investigation `INV-D944C855CC` with:

| Evidence type | Stored records |
| --- | ---: |
| Source metadata | 1 |
| Anomaly findings | 1 |
| Sensor measurements | 7 |
| Baseline statistics | 7 |
| Manual passages | 5 |

Its persisted Knowledge Agent activity count was **0**. Several report hypotheses already cited actual manual evidence IDs. Three earlier failed investigations also had five manual passages stored before their sensor-agent failures. Retrieval and evidence persistence were therefore functioning; zero in the activity row did not mean zero stored documents.

The available corpus is `services/api/knowledge/documents.json`: **six synthetic/general documents, 14 sections**, with publisher and revision metadata. The repository builds an in-memory document/section lookup and weighted keyword ranking. There are no real factory maintenance records, OEM manuals, embeddings, or external document indexes in this corpus. No synthetic material is represented as factory evidence.

Retrieval is executed deterministically by the orchestrator before model execution, rather than selected by Gemini through function calling. ADK runs schema-constrained agent responses and stores them in session state. This separation is preserved; see [Google ADK's LLM agent documentation](https://github.com/google/adk-docs/blob/main/docs/agents/llm-agents.md).

## Exact defects and corrections

1. **Missing citation IDs in Knowledge Agent input.** `format_knowledge` exposed document/section IDs and text, but omitted the `EV-MANUAL-*` IDs the prompt required. The orchestrator now attaches the IDs from the actual evidence records, matched by document/section identity. Counterfactual exclusions preserve their original IDs rather than renumbering them.
2. **Activity counts trusted redundant model output.** Counts used optional `referenced_evidence_ids`, even when item-level citations existed. Counts now come from unique, validated item citations. Uncited or invalid guidance is removed. The UI separately shows the number of manual passages fetched from the stored-evidence API. Historical counts are labeled “reported”; validated counts are available for new reports.
3. **No-match retrieval substituted unrelated passages.** The repository returned the first passages when the query did not match. It now returns an empty result, including for nonpositive limits. Missing documentation produces no guidance from model memory and an explicit unresolved evidence finding.
4. **Document references were not checked against source text.** Before initial persistence, retrieved document/section IDs, title, heading, and text must match the loaded corpus. Fabricated or altered retrieval records fail the investigation before any evidence is saved. Manual payloads retain publisher/revision metadata.
5. **Intermediate agent output bypassed grounding checks.** Knowledge and sensor item citations are now validated against their permitted evidence types. Unknown source identifiers and inconsistent explicit numerical quantities are checked before downstream use. Validated analyses are persisted with the report for restart/API auditing.
6. **ID existence alone could preserve unsupported relationships.** Hypotheses with no valid support are marked unsupported. An ID assigned both supporting and contradicting roles is removed from both. The critic now produces per-relationship verdicts; rejected or unreviewed relationships are removed. Revisions remain bounded to one.
7. **Critic complaints could coexist with approval.** Previously, a false `revision_required` flag could override substantive contradictions or citation issues. Such complaints now force revision and an unresolved final verdict when they persist. Contradictions, missing evidence, and deterministic findings also reach revision feedback.
8. **Baseline tool disagreed with detector fallback.** The detector falls back to global statistics for individual degenerate machine-type features; the tool returned group statistics wholesale. It now returns the same per-feature statistics used for scoring.
9. **Sensor snapshot consistency was not verified.** Raw rotational speed and torque must match their derived-feature values; mechanical power must equal `torque * 2 * pi * rpm / 60`; all scored feature observations must match the incident snapshot. Missing, non-finite, or inconsistent data fails before model execution. The existing detector still computes robust z-scores, Euclidean anomaly scores, and severity bands in Python.
10. **Derived evidence had misleading provenance.** Mechanical power and process/air temperature difference now identify their deterministic formulas rather than describing themselves as directly recorded values.
11. **Historical/imported measurements could carry extra fields.** The measurement tool now allowlists physical measurements and feature keys, preventing stored failure labels or arbitrary notes from becoming Gemini inputs.
12. **UI obscured evidence quality.** Reports now emphasize primary finding, key evidence, alternatives, missing measurements/documentation, full critic findings, and verification checks. Detailed hypotheses, evidence records, agent summaries/stages, graph, what-if, and visual inspection remain accessible. Hypothesis and critic activity counts have accurate units. Empty timeout messages now identify the elapsed agent limit.

## Files changed

| File | Purpose |
| --- | --- |
| `services/api/agents/prompts.py` | Include actual manual evidence IDs in passage formatting. |
| `services/api/agents/knowledge_agent.py` | Require cited guidance and explicit empty-retrieval behavior. |
| `services/api/agents/critic_agent.py` | Structured relationship-level citation verdicts. |
| `services/api/agents/orchestrator.py` | Bind IDs, validate sources/snapshots, normalize analyses, enforce critique/revisions, remove unsupported links, persist audit details. |
| `services/api/services/knowledge_repository.py` | Genuine empty retrieval results. |
| `services/api/tools/grounding.py` (new) | Source/quantity validation, analysis normalization, snapshot consistency, critic verdict checks. |
| `services/api/tools/anomaly_tools.py` | Match per-feature baseline fallback. |
| `services/api/tools/evidence_tools.py` | Formula provenance and document source metadata. |
| `services/api/tools/incident_tools.py` | Allowlist physical snapshot fields. |
| `services/api/schemas/investigation.py` | Add backward-compatible analysis and citation-review audit fields. |
| `services/api/tests/conftest.py` | Mock relationship-level critic verdicts. |
| `services/api/tests/test_investigation_grounding.py` (new) | Grounding, source tampering, counts, missing data, numerical checks, API consistency, separate-process persistence, counterfactual IDs. |
| `services/api/tests/test_live_gemini_smoke.py` | Bounded smoke call and isolated full live pipeline test. |
| `apps/web/src/components/investigations/InvestigationWorkspace.tsx` | Report presentation and accurate stored-versus-cited counts. |
| `apps/web/src/types/investigation.ts` | Optional audit fields for new reports. |
| `reports/investigation-evidence-verification.md` (new) | This investigation and validation record. |

## Verification

- `python -m pytest --ignore=services/api/tests/test_live_gemini_smoke.py`: **128 passed**. All unit/in-process integration model calls are mocked through the real ADK scripted runtime. Includes 23 new regression cases; existing numerical z-score, severity, exclusion, visual, graph, incident/API, and evaluation tests remain passing.
- Persistence checked using both a fresh repository and a separate Python interpreter reading the saved report. Report catalog/counts also checked against backend API responses.
- `npx tsc --noEmit`: passed.
- `npm run lint`: passed.
- `npm run build`: passed; all 13 static pages generated, including dynamic incident/investigation routes.
- `git diff --check`: passed.
- The initial sandboxed Next.js build failed on Windows filesystem canonicalization/access; the approved outside-sandbox build succeeded. Sandboxed async pytest runs stalled; outside-sandbox backend suites completed normally.
- Separate live execution, with existing backend credentials and temporary records: the sensor smoke test **passed**. The full pipeline **did not pass**: the first attempt exceeded its 60-second sensor limit; a retry with a 120-second per-agent limit reached the critic and received Gemini **503 UNAVAILABLE / high demand**. No full live validation is claimed. The existing production timeout/retry configuration remains unchanged.

## Remaining limits

- Full live Gemini investigation verification requires a successful run when provider capacity is available. The failing run also emitted ADK/OpenTelemetry context-detach messages during cancellation; this dependency behavior remains outside the evidence fixes.
- Source IDs, passage equality, deterministic structured measurements, and explicit unit-bearing quantities/statistics are checked mechanically. Arbitrary prose entailment, paraphrases, omitted units, and source names without IDs cannot be exhaustively proven by these checks. Semantic citation review remains model-assisted and can be wrong; physical fault confirmation requires the recommended verification checks.
- Existing historical reports are preserved, without fabricated backfilled citation metadata or a claim that they passed the new validators. New investigations receive the enhanced validation. The UI exposes their actual stored passages while retaining their historical reported count.
- Only synthetic/general reference documents are available; real machine-specific manuals, inspection results, and vibration/time-series measurements remain missing.
- A pre-existing FastAPI/Starlette test-client deprecation warning about `httpx` remains. No browser-based visual QA was performed; frontend verification used type-checking, lint, and production build.

No API keys were printed, no AI4I failure labels were supplied as investigation inputs, no development investigation records were changed, and no commit, push, or deployment was performed.

## Follow-up: temporary Gemini 503 failures

The reported “attempt 1” was a job attempt, not a provider-call count. Local configuration allowed one agent retry with only a one-second delay; exhausted jobs remain failed. Google recommends exponential backoff for temporary 429/503 responses in its [troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting).

- `services/api/agents/runtime.py` now identifies retryable provider status messages (429, 500, 502, 503, 504 and equivalent transient names), including ADK event errors.
- `services/api/agents/orchestrator.py` retries transient failures/timeouts with delays starting at 5, 10, and 20 seconds plus jitter. Retry configuration is bounded to zero through five retries; permanent errors are not retried.
- `services/api/core/config.py` and `services/api/.env.example` default to three retries. The local, untracked backend `.env` was updated only for `FACTORYMIND_INVESTIGATION_MAX_RETRIES=3`; credentials and other settings were preserved. API and standalone worker processes must restart to load it.
- `apps/web/src/components/investigations/InvestigationWorkspace.tsx` explains the availability failure, distinguishes job attempts, preserves technical details, and offers “Retry investigation” using the existing incident investigation endpoint. This creates a fresh job and leaves the failed record/evidence intact.
- `services/api/tests/test_agent_orchestration.py` adds nine mocked cases covering classification, recovery after two 503 failures, exponential backoff, exhaustion, and immediate rejection of permanent errors.
- Updated backend suite: **137 passed**. No new live Gemini run was attempted for this follow-up; provider availability remains an external limitation. No model was silently replaced, no report was fabricated, and no existing job was automatically re-executed.

## Follow-up: daily quota exhaustion and extension hydration warning

The supplied log reports `429 RESOURCE_EXHAUSTED`, `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, a limit of 20 requests for the configured model, and `RetryInfo.retryDelay=42136s`. This is exhausted daily quota, distinct from the earlier 503 overload. The previous blanket treatment of 429 as retryable was insufficient. Short retries cannot restore this quota.

Corrections:

- `services/api/agents/runtime.py`: distinguish daily quota and long retry delays from short-term rate limiting; close the ADK event iterator explicitly in the same task when errors occur, rather than leaving cleanup to deferred generator finalization.
- `services/api/agents/orchestrator.py`: respect short provider retry delays and stop retrying daily/long-delay failures immediately.
- `services/api/services/investigation_service.py`: derive model/provider cooldowns from persisted failures, reject new investigations during a known cooldown, prevent already-queued jobs from making more calls, and expose an approximate retry timestamp. Reads do not change historical records.
- `services/api/schemas/investigation.py` and `apps/web/src/types/investigation.ts`: optional `retry_available_at` field; no database migration.
- `apps/web/src/components/investigations/InvestigationWorkspace.tsx`: explain quota exhaustion, show the provider's approximate retry window, link usage/billing, and disable immediate retries while the known cooldown is active. Refresh after the window expires to enable retrying.
- `apps/web/src/app/layout.tsx`: locally suppress the warning for extension-added body attributes (`data-gr-ext-installed`, `data-new-gr-c-s-check-loaded`). Existing suppression on `<html>` does not cover `<body>`; React's escape hatch is one level deep. App component mismatches remain visible.
- `services/api/core/config.py` and `services/api/.env.example`: `FACTORYMIND_PROVIDER_COOLDOWN_ENABLED=true` by default. If API project quota/billing has actually changed and the provider's old cooldown no longer applies, explicitly set it to `false` and restart the API/worker to recheck. Re-enable afterward. No billing, API key, or model changes were made automatically.
- `services/api/tests/test_agent_orchestration.py` and `services/api/tests/test_investigations.py`: eight additional mocked cases cover daily/short quota classification, no immediate daily retries, error-stream cleanup, persisted cooldowns/API rejection after restart, and expiry.

Updated backend suite: **145 passed**. Final frontend `npx tsc --noEmit`, `npm run lint`, and `npm run build` all passed. The cooldown comparison uses a timestamp captured after fetching rather than calling an impure clock during React rendering. `git diff --check` passed. No live Gemini calls were made while quota is exhausted. The application fixes improve handling; actual API access still requires quota reset or a suitable project quota/billing change. See [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) and [React's scoped hydration warning guidance](https://react.dev/reference/react-dom/client/hydrateRoot).
