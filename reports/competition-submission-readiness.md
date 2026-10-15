# FactoryMind AI — competition submission readiness

Team: AetherForge · Prepared October 15, 2026 (Asia/Colombo) · Team-supplied deadline: October 18, 2026.

**Functional Google Cloud deployment requirement: NOT FULFILLED / NOT VERIFIED.** Container preparation and local health checks are not a cloud deployment. No Cloud Run service URL, deployed Firestore/GCS integration, public authenticated judge access, or working submission video was established in this task. A static-only Firebase site must not be described as a live Gemini deployment.

## Audit and priorities

Inspected the frontend routes/components/types/API client, backend routes, detector/evaluation, agent runtime/orchestrator/tools, SQLite and cloud repositories, upload and job execution, tests, Docker/build configuration, prior evidence/cloud/quota reports, and actual local investigation records. The working tree already contained first-deployment documentation and Cloud Build logging changes; these were preserved.

The five highest-impact improvements were:

1. Correct the production proxy health-route mismatch. The client requested `/health`, but the proxy allowed only paths starting with `/api`; a reachable private backend would appear unavailable. The exact single-segment health path is now allowed, while worker/traversal restrictions remain.
2. Add actual operational status to the overview. The old page showed dataset label statistics and incorrectly marked investigations as planned. It now additionally reads anomaly counts, active incidents, job states, severity distribution, recent jobs and explicitly scoped evidence integrity.
3. Improve report credibility. Older saved reports could have critic issues despite `revision_required=false`. Their primary presentation now honors those issues, exposes primary contradicting observations and warns when relationship-level validation was not recorded.
4. Build a guided saved-result walkthrough without quota consumption or invented results. Selection requires a completed Google-provider record, all four completed agent records, resolving hypothesis IDs, matching corpus passages/provenance and catalog/storage equality. It does not certify physical correctness or retroactively validate historical semantic relationships.
5. Add reproducible offline evaluation and a concrete submission checklist. Preserve recommendations as a technician review draft rather than introduce an untested maintenance-ticket state machine before the deadline.

## Verified feature inventory

“Verified” below means the specified local/offline/mocked checks, not an unstated live cloud test.

| Feature | Category | Evidence / practical limit |
|---|---|---|
| AI4I ingestion and deterministic anomaly scoring | Fully functional and locally verified | 10,000 observations; fixed split seed 42; detector/evaluation/API tests; synthetic benchmark only |
| Incidents and local status history | Fully functional and locally verified | SQLite tests, duplicate prevention, persisted local records; 25 currently active |
| Overview status and severity metrics | Fully functional and locally verified | New read-only `/api/submission/overview`; configured repositories; 580 anomalies, 1 completed / 9 failed investigations at inspection |
| Agent orchestration and grounding | Functional with mocked verification; live availability blocked | Four logical Gemini/ADK agents, provenance/numerical checks, critic revision tests; current full live pipeline not revalidated |
| Genuine historical Google-provider investigation | Saved result inspected; partial verification | `INV-D944C855CC`, incident `INC-60078D4EB5`, benchmark record 1210, October 11 saved run; 21 stored evidence records; no claim it passed newer validators |
| Evidence citations | Structurally verified, semantic quality limited | 23/23 hypothesis links resolve; all saved manual passage text matches packaged corpus; historical critic explicitly questioned relationships |
| Report cards and technical details | Implemented, type/build/lint verified | Finding, hypotheses, supporting/contradicting observations, missing information, critic and checks; existing technical details/evidence table retained; no calibrated confidence claims |
| Evidence Graph | Functional with mocked/local data verification | Projection from persisted evidence/hypotheses/actions; unknown relationships omitted and warned; source content visible in graph/report; does not establish causation |
| Counterfactual exclusion and comparison | Functional with mocked verification; live saved comparison missing | Tests cover explicit exclusions, dependency closure, rejected reuse, original immutability, comparison and cache separation; no completed local saved counterfactual |
| Visual inspection | Implemented and mocked/upload checks verified | Existing bounded image handling and vision path retained; no new live image analysis; cloud storage not integration-tested |
| Guided Demo `/demo` | Implemented and local data selection verified | GET-only saved walkthrough, metadata/source checks, critic limitations, graph and draft recommendations; empty state when no eligible run exists |
| Technician review draft | Functional local download; no workflow automation | Report exports recommendations, rationale, hypothesis IDs, evidence IDs and critic issues; approval fields blank |
| Maintenance tickets / approval audit log | Missing, deliberately deferred | No ticket creation, status history, real approval capture, dispatch or equipment commands; UI says so |
| Gemini quota/retry/cache controls | Mocked tests verified; provider limits external | Bounded retries, model configuration, structured usage, daily cooldown, concurrency and repeat-report caching; do not restore daily quota |
| Firestore/GCS/Tasks adapters | Implemented, mocked tests verified; real GCP blocked | Production profile selects durable adapters; no cloud resources or integration created here |
| Private proxy and protected APIs | Local tests verified; real OIDC integration unverified | Signature/audience/email checks; distinct web/worker principals; previous anonymous write checks; health path fixed without exposing worker route |
| Container packaging | Previously locally verified | Both Docker images built; non-root health checks and dataset packaging passed in prior follow-up; images were not rebuilt for this UI/code change |
| Google Cloud live app / authenticated judge access | Missing/unverified | Deployment guide exists; project/billing/IAM/secret/queue setup and explicit deployment approval required |
| Settings page | Placeholder | Not represented as a working administration console |

The local saved history contains nine failed jobs: simple stored-error categorization identifies three quota, two 503 unavailable, one timeout, and three other failures. This is a small development history, not an operational reliability/SLA estimate. Earlier reports describe a successful live sensor smoke test, followed by full-pipeline failures. No new live Gemini requests were made in this enhancement.

## Architecture and technical differentiation

Next.js uses the existing API client and, in cloud builds, a same-origin private proxy. The proxy obtains Google-signed ID tokens server-side. FastAPI checks production caller identity and uses the selected repository adapters. Local development retains SQLite/files; cloud production requires Firestore/GCS and authenticated Cloud Tasks instead of background threads. Cloud-mode status, evidence and shared request controls are persisted. No keys are sent to the browser.

The detector computes physical features and robust z-scores deterministically from benchmark measurements and training baselines. Gemini interprets allowlisted evidence; it does not receive AI4I failure flags as investigation inputs. Packaged maintenance guidance is synthetic/general reference material. The critic challenges citations and requests revisions; deterministic validation rejects unknown IDs, invalid source references and unsupported explicit numerical measurements. A semantic critic remains fallible, and no machine fault is physically verified by this prototype.

Evidence Graph is a stored-data projection rather than a separate invented model explanation. What-if removes selected evidence and dependent features/derived values, reruns permitted reasoning, and compares revised reports while preserving the original. A repeat-original report cache cannot be substituted for counterfactual reasoning. Existing mocked usage trace measured four model invocations for a normal fresh investigation, zero for unchanged report reuse, six for its counterfactual revision case and one for vision. Those are mocked invocation counts, not live HTTP/billing measurements or guaranteed upper totals when retries/revisions occur.

The new submission endpoint performs no model calls. It audits at most the latest 100 completed reports and clearly reports coverage. Count queries and Firestore sorting can still scan matching records, so this is a bounded prototype presentation, not a fleet-scale analytics service.

## Reproducible evaluation

Run from the repository root with the backend environment installed:

```powershell
.\services\api\.venv\Scripts\python.exe -m scripts.evaluate_submission --database services/api/data/incidents.db --output reports/submission-evaluation.json
.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests --basetemp=.pytest_tmp/submission-verification
Set-Location apps/web
npx tsc --noEmit
npm run lint
node --experimental-strip-types --test tests/backend-proxy.test.mjs
npm run build
```

The evaluator opens SQLite in read-only mode, does not start API workers, does not import model responses or mutate original jobs, and never calls Gemini. Use a reviewed local SQLite snapshot when evaluating cloud history; it does not silently read from an unconfigured cloud project. The output records dataset/corpus SHA-256 hashes, split configuration, configured and validation-tuned metrics, stored Google-provider report audits, failure categories and sample sizes. A missing DB produces an explicit missing-snapshot limitation instead of fabricated saved runs. Keep `.env`/keys out of exports.

Measured in `reports/submission-evaluation.json`:

| Metric | Actual result | Interpretation |
|---|---|---|
| Fixed dataset / split | AI4I CSV SHA-256 `dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e`; seed 42; 6000 train / 2000 validation / 2000 test | Baselines fitted only on training observations |
| Configured threshold | 4.0 | Existing detector configuration preserved |
| Held-out precision / recall / F1 | 0.1695 / 0.3571 / 0.2299 | Detection of unusual records is not equivalent to failure prediction |
| Held-out confusion matrix | TP 20, FP 98, FN 36, TN 1846 | Test support 2000, including 56 labeled failures; do not hide the false positives/negatives |
| Validation-selected threshold | 3.3685 | Comparison only; not applied to production configuration |
| Held-out tuned precision / recall / F1 | 0.1156 / 0.4643 / 0.1851 | Validation tuning did not improve test F1; do not optimize further against this test set |
| Citation ID resolution | 23/23 (100%), one saved report | Structural reference validity, **not 100% semantic citation accuracy** |
| Source checks | Zero missing/changed stored manual passages or ownership/provenance issues in that report | Current corpus text matches, but critic concerns persist |
| Semantic valid citation rate | Not independently measured | Historical relationship-level verdicts absent; no independent entailment annotations |
| Root-cause top-1 / top-3 | Not measured | No independent machine-specific root-cause labels suitable for hypothesis ranking |
| Stored completed Google job latency | 58.757468 seconds; n=1 | Historical job duration; insufficient for a latency distribution or current service promise |
| Saved counterfactual leakage rate | Not measured (`null`), n=0 | No saved live counterfactual; never report this as 0% leakage |
| Error/timeout behavior | Automated bounded retry, quota, missing-data, failed-state and restart tests | Offline/mocked evidence, not live chaos testing |

AI4I ground-truth failure columns are used only for offline evaluation/display. They are excluded from Gemini investigation tools. Failure categories are not used to manufacture root-cause accuracy. Relationship validation cannot prove arbitrary paraphrase entailment or absence of implicit/prose counterfactual leakage; the evaluator's structural scope is explicit.

## Enhancements and changed files

- `services/api/services/submission_service.py`: read-only overview, evidence/source audit, honest demo eligibility and job duration.
- `services/api/routes/submission.py`, `services/api/main.py`: authenticated additive GET endpoint; existing API contracts retained.
- `services/api/tests/test_submission.py`: seven regressions for historical critic flags, unknown IDs, altered passages, immutable audits, empty/scripted demo selection, configured-store API and scripted metric exclusion.
- `scripts/evaluate_submission.py`, `reports/submission-evaluation.json`: reproducible offline detector/saved-report evaluation and actual measured output.
- `apps/web/src/lib/backendProxyPolicy.ts`, `apps/web/tests/backend-proxy.test.mjs`: exact health-route allowance and worker/traversal regression coverage.
- `apps/web/src/types/submission.ts`, `components/dashboard/OperationalOverview.tsx`, `components/dashboard/Overview.tsx`: real operational cards, explicit coverage and corrected investigation availability.
- `apps/web/src/app/(shell)/demo/page.tsx`, `components/investigations/GuidedDemo.tsx`: saved-result walkthrough with no AI-triggering controls.
- `components/investigations/InvestigationWorkspace.tsx`, `InspectionDraft.tsx`: effective critic caution, contradiction summary, historical validation warning and review draft download.
- `apps/web/src/app/(shell)/maintenance/page.tsx`, `components/layout/AppSidebar.tsx`: truthful maintenance draft entry and guided-demo navigation.
- `reports/competition-submission-readiness.md`: this audit, evaluation and submission plan.

No agents were rewritten, keys printed, failure labels added to investigation context, original records backfilled, tickets fabricated, or industrial equipment operated. Pre-existing deployment documentation/build changes were retained. No commit, push, cloud resource creation or deployment occurred.

## Three-minute demonstration sequence

Use the actual populated local store or a reviewed imported saved store. An empty Cloud Run store will correctly show no saved demo; do not replace it with a hardcoded completed run.

| Time | Screen / narration |
|---|---|
| 0:00–0:25 | Overview: state “synthetic benchmark,” show 580 detected anomalies and stored incident/investigation statuses; distinguish failure labels from detector outputs |
| 0:25–0:50 | `/demo`: benchmark record 1210 and deterministic anomaly explanation; explain lack of timestamps/machine history and measured values |
| 0:50–1:15 | Historical saved Google-provider result: identify date/model; state no live Gemini call is running and this result predates newer validators |
| 1:15–1:45 | Evidence Graph: click sensor/manual evidence and supporting/contradicting edges; show original IDs and synthetic source passages |
| 1:45–2:10 | Critic assessment: show the questionable relationships rather than treating “supported” as automatic approval; discuss missing commanded setpoint and independent measurements |
| 2:10–2:35 | What-if: explain the tested dependency exclusion, immutable original and comparison UI; explicitly state there is no saved live counterfactual yet; do not start a quota-consuming scenario during this saved walkthrough |
| 2:35–3:00 | Download technician review draft; show blank review/approval; finish with actual evaluation limits and current deployment status |

If a current live pipeline and counterfactual are later approved and succeed, rehearse and save them before recording; label saved playback versus live execution accurately. Avoid reruns during judging when quota is scarce.

## Proposal deck content outline

1. Problem and user: technicians need traceable explanations and verification checks, not unreviewed automatic diagnosis.
2. Demo story: unusual speed/torque observation → evidence → candidate explanations → critic → human review.
3. Architecture: deterministic detector + Gemini/ADK agents + persistent evidence + private cloud execution.
4. Technical differentiation: provenance-bound citations, deterministic quantities, critic disagreement and dependency-aware counterfactual reasoning.
5. Evaluation: fixed split, actual precision/recall/F1, source/ID coverage and explicit semantic/root-cause limitations.
6. Reliability/security: bounded quota controls, durable cloud adapters, protected writes and deployment integration still pending.
7. Responsible scope: synthetic dataset/manuals, draft-only recommendations, no real equipment operation.
8. Delivery/next steps: authenticated deployed demo, successful current end-to-end run, reviewed data import, access instructions and evidence-backed roadmap.

## Required submission links and blockers

The competition's exact official submission fields were not supplied/independently established. Confirm them in the official participant portal; the following are preparation items, not invented URLs or proof of acceptance.

| Submission artifact | Status / next step |
|---|---|
| Working Google Cloud application URL | **Missing / requirement not fulfilled.** Execute the reviewed private deployment procedure only after approval; verify real integrations |
| Judge/team access instructions | Missing. Private proxy access is prepared; public access requires IAP/end-user authentication before removing IAM restrictions |
| Source repository link and allowed access | Supply the actual repository URL and approved access; no push performed here |
| Three-minute demo video URL | Not created; record the sequence above after successful rehearsal |
| Proposal/presentation deck link | Not created; use the outline above and show actual limitations |
| Architecture/evaluation/readiness artifacts | This report, `submission-evaluation.json`, `investigation-evidence-verification.md`, `gcp-deployment-readiness.md`, `first-cloud-deployment.md` |
| Official entry/team/project form | Owner must verify portal fields, eligibility and deadline requirements; team-supplied deadline is October 18 |

Outstanding blockers, in order:

1. Approve the target Google Cloud project/region/budget/private access model and fresh-store versus migration decision. Follow `reports/first-cloud-deployment.md`; preserve IAM protections. Without this, the functional cloud requirement remains unfulfilled.
2. Verify actual Firestore/GCS writes and persistence, proxy ID tokens, task delivery/lease recovery and private judge access in staging. Local mocks/containers do not prove these integrations.
3. Secure quota/model availability and explicitly authorize one current full investigation and, if affordable, one counterfactual. The historical run retains critic issues; do not claim it passed current end-to-end validators.
4. Migrate reviewed history or consciously start empty. No automatic importer exists; saved demo will be unavailable in a fresh cloud store until genuine reviewed results exist there.
5. Finish pending dependency security audit, rehearse/record the demo, prepare the deck, provide real links and verify official submission fields before the team deadline.

## Verification status

Backend automated verification includes existing graph, counterfactual/exclusion, grounding/numerical, empty retrieval, missing-data, quota/retry, cache separation, security, upload and restart/persistence checks. The new feature tests use scripted model responses, and scripted records are explicitly ineligible for the Google-provider guided demo. Live tests remain opt-in and are not run here.

Final verification: **203 backend tests passed, two opt-in live tests skipped (205 total, zero failures/errors)**. This includes seven new submission regressions and the existing graph/exclusion/counterfactual/security suites. Frontend `npx tsc --noEmit`, `npm run lint`, all four proxy tests and `npm run build` passed; the build includes `/demo`. Offline evaluation completed with the measurements above. `git diff --check` passed, with Windows line-ending warnings only. The initial targeted submission tests caught an omitted required repository argument and an incorrect test helper method name; both were corrected before the passing full suite.

Existing Starlette TestClient/httpx deprecation, pytest asyncio config and Node test module-type warnings remain. No browser-based visual or end-to-end click testing has been performed in this enhancement. Docker/cloud deployment checks were not repeated; their earlier results remain scoped to the earlier image versions. No live model requests or paid cloud actions were performed.
