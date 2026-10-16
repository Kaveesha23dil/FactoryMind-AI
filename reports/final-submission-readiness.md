# FactoryMind AI — final submission readiness

Team: AetherForge. Verified October 16, 2026, Asia/Colombo. Team-supplied submission deadline: October 18, 2026.

**Decision: local/offline demonstration verified; full hosted submission is not ready.** The saved Google-provider report can be demonstrated honestly, including its critic limitations. There is no completed saved Google counterfactual in the inspected history, no captured human approval workflow, and no verified working Google Cloud deployment. Do not describe these as completed capabilities of the competition demo.

## 1. Audit scope and features verified

Inspected backend entry points and routes, dataset extraction/splitting, deterministic scoring/evaluation, agent orchestration/runtime/grounding, evidence/graph/exclusion services, SQLite and Firestore repositories, visual storage, request controls, Settings, saved-demo and counterfactual components, private proxy, Docker/Cloud Build configuration, production validation, OIDC/Tasks, environment templates, deployment guides, tests and actual local saved records. The working tree was initially clean. Existing functionality was preserved; no agent rewrite or new operational configuration API was introduced.

| Feature | Verification and limit |
| --- | --- |
| Dataset loading | 10,000 AI4I records; fixed 6,000/2,000/2,000 train/validation/test split; synthetic benchmark, not live machine telemetry |
| Anomaly detection | Deterministic robust-z-score v1; training-only baselines; current threshold 4.0; 580 unusual observations across the full dataset |
| Incident workflow | Automated API/service tests cover creation, persistence, status transitions, invalid records and duplicates |
| Gemini/ADK agents | Sensor, Knowledge, Investigation and Critic pipeline exercised with scripted ADK responses; one historical Google-provider completed run exists; no new live call performed |
| Knowledge evidence | Retrieval, real packaged passage lookup, persisted references, nested evidence counts, empty retrieval and rejected invented sources tested; documents are synthetic/general reference guidance |
| Hypotheses/critic | Evidence-ID, source and numerical consistency checks; missing evidence, disagreement and bounded revision tested; semantic/physical truth is not guaranteed |
| Evidence Graph | Stored evidence/hypothesis/action projection tested; graph rendered in saved-demo browser test without a model request |
| Counterfactual | Genuine fresh scripted reasoning after dependency-closed exclusions, deterministic recomputation, rejected citation reuse, preserved original, comparison and persistence verified |
| Visual inspection | Upload/type/size/path checks and scripted vision attachment tested; live image interpretation and deployed GCS are unverified |
| Settings | All seven sections, actual read-only values, safe diagnostics, preferences, browser reload persistence, failure/retry and responsive behavior verified |
| Guided Demo | Existing `/demo` verified against an isolated backup of actual saved records; no fabricated result substituted |
| Cloud adapters | Firestore/GCS/Tasks/OIDC implementations and mocked contracts verified; real deployed integration not established |

## 2. Settings verification

- Seven-category navigation works without page reload. Browser tests cover General, AI Configuration, Anomaly Detection, Notifications, Data Management, Security & Access and System Information.
- Editable fields are appearance, density, date format, time format and IANA timezone. Validated browser/origin-scoped localStorage persists these after refresh. Save read-back, reset, invalid timezone, denied storage and Light/Dark/System behavior are tested.
- Anomaly thresholds are **read-only**, matching the actual detector. PATCH configuration requests are rejected. No administrator authorization/audit-backed edit mechanism exists; no historical report is recalculated.
- The configured Gemini model is displayed from the backend. Current saved run records `gemini-3.8-flash`; actual current account allocation was not tested or assumed. No model is switched silently.
- API usage is an explicitly limited sum of recorded completed-report metrics, not quota/billing totals. Latest error category and cooldown are available where recorded; unknown remaining quota stays unknown.
- Operational configuration and secrets are not persisted in the browser. Explicit response schemas and sentinel tests verify redaction of keys/private configuration. Production identity middleware protects Settings; local development retains its existing unauthenticated profile.
- Corrected an inaccurate Settings label: request concurrency is shared through the configured SQLite/Firestore store, not merely per process.
- Preferences and Settings reads leave historical investigations unchanged; the joined regression checks report immutability after Settings access and a rejected threshold update.

Known non-blocking limitations: preferences do not synchronize to user accounts; appearance applies after hydration; same-document browser Back/Forward is not guarded against unsaved changes. Ordinary dashboard links and full document unload are guarded. Notifications, end-user roles, unit conversion and configuration writes are explicitly unavailable.

## 3. Complete workflow regression

New test: `services/api/tests/test_final_workflow.py`.

It loads dataset metadata, selects an actually anomalous benchmark observation, creates an incident, starts an investigation, checks completion records for all four agents, checks retrieved document evidence/provenance and nonzero Knowledge evidence counts, audits hypothesis references, verifies graph nodes correspond to persisted evidence, and runs a counterfactual through the actual orchestrator with scripted ADK responses.

The test observes additional model-runtime calls for the counterfactual; excludes the chosen sensor evidence; verifies deterministic comparison; observes unsupported scripted citation reuse in rejection/critic fields; and confirms the original persisted job is byte-for-byte unchanged as a Python record. Fresh repository/service instances reopen original/revised reports and the scenario comparison without new model calls. Prompt checks reject serialized ground-truth fields. Existing regressions additionally cover derived-feature exclusion, cache separation, source hallucination, numerical consistency, critic disagreement, missing inputs and separate-process persistence.

This is an offline integration test of application behavior, not evidence that Gemini generated these test answers or that a physical failure was diagnosed.

## 4. Reproducible AI evaluation

Machine-readable current results: `reports/final-submission-evaluation.json`.

The existing offline evaluator was reused and minimally extended with a fingerprint of exact held-out membership, an explicit counterfactual exclusion-success rate and an explicit unavailable semantic-citation metric. It opens the source SQLite database read-only; it does not start workers or call Gemini. Running it twice produced **byte-for-byte identical output**.

```powershell
# From C:\Users\kavee\Documents\factorymind-ai
$env:FACTORYMIND_RUN_LIVE_TESTS = '0'
.\services\api\.venv\Scripts\python.exe -m scripts.evaluate_submission --database services/api/data/incidents.db --output reports/final-submission-evaluation.json
```

Dataset SHA-256: `dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e`.

Held-out record-membership SHA-256: `3c24294e5b0241e53961001a8000e952e917acc5533af9b59f372cb10b47bb33`.

Split seed: 42, NumPy PCG64. Baseline fit uses training records only. Threshold tuning uses validation only. Test labels are used solely to calculate metrics; physical-feature extraction and investigation prompts exclude ground-truth failure flags. The configured threshold is unchanged by evaluation.

| Metric | Measured result | Interpretation |
| --- | --- | --- |
| Test support | 2,000 records: 56 failure labels, 1,944 negative labels | Synthetic, imbalanced held-out benchmark |
| Configured threshold | 4.0 | Application configuration, not tuned on this test set |
| Precision / recall / F1 | **0.1695 / 0.3571 / 0.2299** | Unusual observations are not equivalent to labeled failures |
| False-positive rate | **0.0504** | 98 false positives / 1,944 negative labels |
| Confusion matrix | TP 20, FP 98, FN 36, TN 1,846 | Both false alarms and misses remain material |
| Validation-selected threshold | 3.3685 | Evaluation comparison only; not applied to application |
| Tuned test precision / recall / F1 / FPR | 0.1156 / 0.4643 / 0.1851 / 0.1024 | Worse held-out F1; do not retune against the held-out test set |
| Saved hypothesis citation-ID resolution | **23/23, 1.0; one Google-provider report** | Structural ID resolution only |
| Stored source audit | 21 evidence records; no missing/changed passage, ownership/provenance or catalog mismatch detected | Current packaged corpus matches stored references |
| Semantic valid citation rate | **Unavailable** | No independent entailment annotations; historical relationship-level critic reviews absent |
| Saved Google counterfactual exclusion success | **Unavailable, n=0** | No completed stored sample; no 100% claim |
| Counterfactual automated correctness | Offline dependency/exclusion/reasoning/immutability regressions pass | Test coverage, not a measured live-provider success rate |
| Recorded investigation latency | **58.757468 seconds, n=1** | Genuine historical Google job start-to-completion duration; not current latency, p95 or an SLA |
| Saved job outcomes | **1 completed, 9 failed** | Small development history, not a production success-rate estimate |
| Simple stored failure categories | quota 3, unavailable 2, timeout 1, other 3 | Error-text classification only; not independently verified current quota |
| Root-cause top-1/top-3 accuracy | Unavailable | No independent machine-specific root-cause labels |

## 5. Gemini reliability and counterfactual correctness

Existing bounded retries, jitter/backoff, retry metadata, persistent failure states, daily/spending/model-allocation categorization, provider cooldown, shared request leases, duplicate prevention, cache invalidation, explicit rerun and counterfactual separation passed mocked tests. Runtime usage logging records request counts/latency and available tokens without prompts/keys. The SDK-retry-disable test passed; actual current live provider capacity remains untested.

Re-ran `python -m scripts.trace_gemini_usage`, which uses disposable stores and scripted models:

| Scripted workload | Observed ADK model invocations |
| --- | --- |
| Fresh investigation | 4 |
| Unchanged repeat, cache disabled | 4 additional |
| Unchanged repeat, cache enabled | 0 additional |
| Explicit rerun | 4 |
| Counterfactual with one bounded revision | 6 |
| Visual inspection | 1 |

These are model invocations in an offline trace, not live HTTP/billing counts. Settings/demo/graph reads require no Gemini generation. Rate-limit controls cannot grant daily quota or unavailable model allocation.

The counterfactual pipeline removes explicit and dependent evidence/derived measurements before reasoning, recomputes the retained-feature score, bypasses original-report reuse and persists a separate report. A new conclusion can remain similar when retained evidence supports it; correctness means reasoning was rerun with isolated inputs, not that the answer was forced to change. Accepted/stored evidence is checked separately from diagnostic rejected-citation fields, which may legitimately name excluded IDs to explain a rejection.

## 6. Competition demo readiness and walkthrough

Verified saved case: **INV-D944C855CC**, incident **INC-60078D4EB5**, benchmark record **1210**, recorded model **gemini-3.8-flash**, saved October 11, 2026. Eligibility requires four completed agent records, citation links, source consistency and matching evidence catalog; it does not override unresolved criticism.

Use the existing `/demo` page with the reviewed saved store:

1. Explain that record 1210 is a synthetic benchmark observation, not a live physical machine.
2. Show its deterministic anomaly explanation and application-defined severity.
3. Show the historical multi-agent interpretation, visibly labeled saved; this performs no new reasoning.
4. Open the rendered evidence graph and trace a hypothesis to sensor and reference evidence.
5. Read the critic concerns. This report requires attention and is **not an accepted or physically confirmed diagnosis**.
6. Show recommended actions as a technician-review draft. Human approval capture, maintenance dispatch and equipment control are not implemented. Do not claim an action was human-reviewed or executed.
7. Explain the What-if workflow and quota implications. There is currently **no saved Google counterfactual comparison**; the demo honestly says so. Demonstrate offline test coverage separately if needed, explicitly labeled scripted. Do not substitute it for a live/saved Gemini result.

Added `apps/web/tests/saved-demo-browser.mjs`: it reads an isolated SQLite backup of the actual saved case, verifies the numeric explanation, graph, criticism, draft-action notice and absent-comparison notice, enforces GET-only browser API calls, and confirms the persisted report is unchanged. Existing Settings browser tests also passed against this snapshot. No model request was made to animate or populate the walkthrough.

## 7. Google Cloud readiness and actual deployment status

**A working Google Cloud deployment is not verified.** The installed gcloud CLI has an active account and configured project. A read-only `gcloud run services list --platform=managed --filter=metadata.name:factorymind` attempt failed; the CLI reported Cloud Run API unavailable/not enabled in that configured context. No resources were enabled/created and no service URL, deployed data flow or judge access was verified. This does not prove that no deployment exists in another project. No static Firebase host was accepted as backend deployment evidence.

Repository preparation is present:

- Both Dockerfiles use repository-root build context. Backend packages AI4I CSV and knowledge files, installs cloud requirements and runs non-root on `$PORT` (default 8080). Frontend uses `npm ci`, standalone output, static assets, non-root execution and `PORT=8080`.
- Remote Cloud Build manifests exist at `deploy/cloudbuild-api.yaml` and `deploy/cloudbuild-web.yaml`. No remote build was submitted. Docker is not on this session's PATH; current container images were not rebuilt or re-tested. Earlier reports' successful local image tests are historical evidence only.
- Production validation requires Firestore, private GCS, exact JWT audience, allowlisted callers, durable Tasks and a viable timeout budget; rejects ephemeral SQLite/local files, wildcard CORS and scripted production AI.
- The frontend proxy obtains a Google-signed ID token with ADC on the server, forwards the application and serverless auth headers, restricts paths/worker routes, enforces write Origin and upload bounds, and does not send tokens to the browser.
- Backend checks signed ID tokens, audience, verified email and separate frontend/worker allowlists. Cloud Tasks creates OIDC-authenticated delivery with deterministic task IDs. Firestore repositories cover incidents, investigations/evidence, scenarios and image metadata; GCS stores private image bytes.
- Secret Manager injection is documented using `--set-secrets` and scoped `secretAccessor`, with runtime ADC rather than bundled service-account JSON keys. No secret versions or IAM bindings were inspected or changed.
- Actual Firestore/GCS/Tasks, service-to-service OIDC, IAM, Secret Manager and Cloud Run readiness must be smoke-tested after an approved deployment. Mock tests and build configuration do not establish live integration.

Follow `reports/first-cloud-deployment.md` after its explicit approval gate. Keep web and API private. Do not silently migrate local data or carry unfinished jobs into the cloud store; select a reviewed migration/fresh-store strategy. Existing limitations include lease fencing/recovery, synchronous vision/counterfactual crash recovery and Firestore scan-based demo queries.

## 8. Security findings

**P0 for a public deployment:** the frontend proxy represents its service account and has no end-user authentication layer. Origin checks are not user authentication. Publishing that frontend anonymously would allow users to exercise its backend privileges. Keep Cloud Run IAM authentication on both services and establish verified judge access, or implement/test an approved end-user/IAP plan before public exposure. No auth bypass was added here.

Production tests reject anonymous access, intruders, invalid/unverified identities and wrong web/worker principals. Settings exposes an allowlist, not the environment dataclass. Tracked environment files are examples; container ignores exclude .env files, local databases and private credential files. No key, token, private account or project identifier was printed in this report or browser diagnostics.

Existing upload/path/size validation, counterfactual isolation and label-leakage tests pass. This is not a penetration test or a fresh online dependency audit. Prior dependency-audit concerns and any updated advisories require a separate release review; no forced dependency downgrade was applied. No unreviewed changes were made to production IAM or secrets.

## 9. Tests executed

| Check | Final outcome |
| --- | --- |
| Complete backend suite | **211 passed, 2 skipped**, 213 collected; zero failures/errors |
| Joined workflow regression | Passed; included in full suite |
| Existing offline evaluation tests | Passed; included in full suite |
| Repeated offline evaluator | Passed, byte-for-byte identical JSON |
| Scripted model-call trace | Passed; 4 / 0 / 4 / 6 / 1 workload counts above |
| Frontend Node unit tests | **11 passed**, zero failures |
| Type-check | `npx tsc --noEmit` passed |
| Lint | `npm run lint` passed, including new browser runner |
| Frontend production build | Passed; Settings and Demo routes generated |
| Settings headless Edge suite | Passed: navigation, preferences/reload/reset, validation, unsaved dashboard-link warning, theme/OS updates, mobile layout, loading/errors/retry, denied storage, no uncaught browser errors |
| Saved-demo headless Edge suite | Passed against actual saved-data snapshot; graph and caveats visible; GET-only; unchanged report |
| Cloud adapter/auth contracts | Passed mocked backend tests; no live cloud integration claim |
| Live Gemini tests | **2 skipped intentionally**; explicit approval was not given |
| Cloud Run listing | **Blocked/unverified**: API unavailable/not enabled; no cloud changes |
| Docker/container verification | Not executed this task; Docker unavailable on PATH |
| `git diff --check` | Passed; only Git's LF/CRLF normalization warning |

Backend process checks and browser/build workers required approved execution outside the filesystem sandbox. An initial sandbox Python-launch failure was retried successfully; final checks above reflect actual successful executions. Existing non-failing warnings: Starlette httpx TestClient deprecation, unknown pytest asyncio fixture option, Node direct-TypeScript module-type warning, and local `next start` standalone-output recommendation. Production Dockerfile correctly uses the standalone `node server.js` entry point.

Reproduce backend/frontend checks:

```powershell
# Repository root; never set the live flag to 1 without explicit approval.
$env:FACTORYMIND_RUN_LIVE_TESTS = '0'
$env:AI_PROVIDER = 'scripted'
.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests -q --basetemp=.pytest_tmp/final-confirmed --junitxml=.pytest_tmp/final-confirmed.xml
Set-Location apps/web
node --test tests/*.test.mjs
npx tsc --noEmit
npm run lint
npm run build
```

Optional browser runners require an existing Playwright installation and Edge. Set `PLAYWRIGHT_MODULE` to that installation directory if not Node-resolvable. Set `SETTINGS_WEB_URL` and `SETTINGS_API_URL` to disposable local test servers, with scripted AI, disabled async worker and a reviewed temporary SQLite backup; then run `node tests/settings-browser.mjs` and `node tests/saved-demo-browser.mjs`. Do not run these against production. Tests intercept browser reads to supply responses obtained from the isolated real API; they do not verify production CORS/proxy/Google identity flows.

## 10. Changes and outstanding gates before October 18

Files changed/created this task:

- `scripts/evaluate_submission.py`: exact holdout fingerprint, unavailable semantic citation metric and explicit exclusion-success rate.
- `services/api/tests/test_submission.py`: empty/scripted metrics remain unavailable assertions.
- `services/api/tests/test_final_workflow.py`: joined incident-to-counterfactual/reopen regression with prompt capture.
- `apps/web/tests/saved-demo-browser.mjs`: GET-only browser regression against genuine historical saved data.
- `apps/web/src/components/settings/SettingsDashboard.tsx`: correct shared-store concurrency label.
- `reports/final-submission-evaluation.json`: newly measured reproducible results.
- `reports/final-submission-readiness.md`: this report.

No new critical local workflow defect was exposed by the final suite. The remaining gates require actual deployment/access decisions and evidence, not more decorative features:

| When (Asia/Colombo) | Required action | Gate |
| --- | --- | --- |
| October 16 | Review this report and actual critic issues; choose the final demo narrative and disclose dataset/source limits | Do not call the historical report an approved diagnosis |
| October 16 | Approve cloud project/region/budget, private judge-access plan, resource creation/deployment, secret handling and data migration strategy | No cloud deployment authorized by this task |
| October 16–17 | After approval, enable required APIs and execute remote builds/private Cloud Run deployment using the existing guide | Real URLs, health/readiness, Firestore/GCS/Tasks/OIDC and anonymous-write rejection must be verified |
| October 17 | If a full Gemini counterfactual demo is required, explicitly approve a tightly bounded live run and confirm quota/model allocation first | Generate/review/persist a genuine revised report; no available saved comparison today |
| October 17 | Review or rerun unresolved critic findings; require qualified human verification for recommendations | Model output must not be labeled human-approved without actual review |
| October 17 | Rehearse `/demo` using the reviewed saved store, graph and critic; verify all judge links and access from a clean browser | Offline/scripted fallback must be labeled clearly |
| Before October 18 submission | Prepare/check the required competition video, README, architecture/evaluation/source disclosures and authenticated hosted access against the organizer's checklist | Official submission format/eligibility rules were not independently checked in this task |
| Before submission | Approve any desired commit/release/deployment and rerun checks after subsequent code changes | Nothing committed, pushed, merged or deployed here |

No live Gemini requests, paid resource creation, deployment, commits or pushes occurred during this verification. Original saved investigation records were not modified; browser checks used a separate SQLite backup.
