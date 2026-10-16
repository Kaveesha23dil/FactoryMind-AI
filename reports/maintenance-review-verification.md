# Maintenance Review verification

Verified October 16, 2026. Project: FactoryMind AI. Team: AetherForge.

## Implemented

Replaced the static Maintenance Drafts landing page with a responsive Maintenance Review workspace using the existing light mint design, dark green headings, white cards and compact spacing. The top now contains the requested heading/subtitle and Refresh, with concise safety information at the bottom.

Three summary cards distinguish actual data from unavailable workflows:

- **Available Drafts:** count of nonblank inspection recommendations from saved, completed Google-provider reports. This is a projection of persisted recommendations, not a new maintenance-record table.
- **Under Review:** Unavailable — technician review state is not persisted.
- **Approved:** Unavailable — technician approval is not implemented. No fake zero, approval status or approval action is supplied.

Recommendation cards show source investigation/incident IDs and links, proposed inspection, first linked hypothesis in report order, distinct resolved supporting-evidence count, report-level critic concerns and draft-only/human-review-required labeling. View Details opens a review panel with summary, action/rationale, linked hypotheses and verification steps, supporting/contradicting records with IDs/source/provenance, missing information, critic notes and a source-report link. Keyboard focus moves to the detail panel and returns to its trigger on close.

What-if reports, if present, are labeled hypothetical drafts rather than new machine observations. All recommendations still require qualified technician review. No approval, rejection, ticket or physical-control action is added.

The existing `InspectionDraft` export component is reused unchanged. It downloads the **whole source investigation's** technician-review text draft, including all recommendations, evidence catalog, existing critic issues and blank technician/approval/date fields. It is not a per-action export, approval record or work authorization. The UI explains this scope.

## Data sourcing and integrity

Only existing read APIs are used:

- `GET /api/investigations?status=completed&limit=100&offset=…`
- `GET /api/investigations/{id}`
- `GET /api/investigations/{id}/evidence`

The loader follows all completed-list pages, filters Google-provider jobs, reads reports/evidence with at most four report loads in parallel, and derives recommendation cards without model calls. Failed, queued, running and scripted jobs are not substituted as genuine recommendations. No new backend endpoint/schema/configuration or operational workflow was introduced.

Report and evidence ownership must match the saved job and incident. Supporting counts deduplicate IDs and require a matching stored record, report catalog membership and nonempty source/provenance. Missing references are visibly flagged and excluded from counts. Unknown linked hypotheses and missing evidence remain visible; no fallback hypothesis/evidence is invented. Stored-source resolution is not proof of semantic support or physical fault confirmation.

Critic concerns remain visible even when a historical `revision_required` flag is false. The view includes issues, citation issues, unsupported claims, contradictions, deterministic findings, excluded-evidence reuse and invalid relationship-review verdicts, with missing information in its own section. Concerns on cards are explicitly report-level, not a new action-specific verdict.

Failed reads or malformed ownership produce an error/retry state rather than an invented zero/empty result. Previously loaded drafts, if retained after Refresh fails, are identified as stale. The genuine empty state reads “No maintenance drafts available” with the requested explanation and View AI Investigations link. Before a successful load, draft count is a dash rather than zero.

Read-only browser verification found **6 recommendations from 1 saved Google-provider report**, `INV-D944C855CC`. These are actual saved development-store values, not hardcoded UI data. Existing critic concerns are shown; the report is not represented as human approved. The source investigation was compared before/after the browser workflow and remained unchanged.

## Files

Modified:

- `apps/web/src/app/(shell)/maintenance/page.tsx`: page title and new workspace component.

Created:

- `apps/web/src/components/maintenance/MaintenanceReview.tsx`: cards, detail review, safe workflow states, loading/error/empty behavior and reused export.
- `apps/web/src/components/maintenance/maintenance.css`: responsive mint workspace styling.
- `apps/web/src/lib/maintenance.ts`: paginated read-only loading and evidence-resolved recommendation projection.
- `apps/web/tests/maintenance.test.mjs`: six data/integrity tests.
- `apps/web/tests/maintenance-browser.mjs`: genuine saved-data browser acceptance test.
- `reports/maintenance-review-verification.md`: this report.

Existing API client, report export, routing, authentication, Gemini orchestration, dataset processing and historical records remain unchanged. Static summary cards use grouped divs so the shell animation observer does not mutate their server markup before hydration; the final browser test also checks hydration errors.

## Verification results

| Check | Result |
| --- | --- |
| Frontend TypeScript | `npx tsc --noEmit` passed |
| ESLint | Passed |
| Frontend production build | Passed; `/maintenance` prerendered successfully |
| Frontend Node unit suite | **17 passed**, including **6 new maintenance tests** |
| Relevant backend regressions | **47 passed**, zero failures/errors/skips |
| Headless Edge, actual saved data | Passed on development and final production builds |
| Responsive and visual checks | Desktop 1440px and mobile 390px; no page overflow; screenshots inspected |
| Export | Actual browser download filename, source/action content, blank approval fields and work-authorization disclaimer verified |
| Integrity/safety | GET-only API calls; unchanged source job; no fabricated records; unavailable approval counters; no Approve/Reject/Create Ticket buttons |
| Empty and failure states | Simulated only inside browser; correct messages, dash vs zero count, retry, no false empty state on failure |
| `git diff --check` | Passed |

Unit tests cover completed Google-provider eligibility, empty actions, missing completed reports, deduplicated resolved IDs, missing provenance, contradiction relationships, historical critic issues, unknown references/hypotheses, foreign ownership, pagination, exclusion of scripted records, actual action counts, incomplete reads/network failure and invalid relationship verdicts. Test fixtures are confined to tests and are not shown as real maintenance data.

The backend tests exercised existing investigation APIs/persistence, evidence grounding, saved-report auditing and the joined original/counterfactual workflow with scripted/mocked model responses and isolated databases. No live Gemini tests or generation calls were performed.

Reproduce from the repository root:

```powershell
$env:FACTORYMIND_RUN_LIVE_TESTS = '0'
$env:AI_PROVIDER = 'scripted'
.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests/test_investigations.py services/api/tests/test_submission.py services/api/tests/test_investigation_grounding.py services/api/tests/test_final_workflow.py -q --basetemp=.pytest_tmp/maintenance-api --junitxml=.pytest_tmp/maintenance-api.xml
Set-Location apps/web
node --test tests/*.test.mjs
npx tsc --noEmit
npm run lint
npm run build
```

Browser runner requires an existing Playwright installation and Edge. Set `PLAYWRIGHT_MODULE` to its package directory if not resolvable. Set `SETTINGS_WEB_URL` to the local test frontend and `SETTINGS_API_URL` to the local API, then run `node tests/maintenance-browser.mjs`. It requires an actual saved Google-provider recommendation to exercise success; it never creates one. Browser API reads are routed through responses fetched from the real local API, with failure/empty responses intercepted only for those tests. Production identity/CORS/cloud deployment are outside this browser test's scope. Screenshots are ignored local artifacts under `.pytest_tmp/maintenance-visual/`.

Existing non-failing warnings remain: Node direct TypeScript module-type warning, Starlette httpx TestClient deprecation, pytest asyncio fixture-option warning, and the local `next start` standalone-output recommendation. No dependency was installed or downgraded.

## Remaining limitations

- Opening details is a UI selection, not a persisted technician review. Approval, rejection, tickets, audit history, reviewer identity and operational execution are unavailable.
- Available draft count is recommendation/action count, not report count or independently persisted work orders. Distinct saved original/revised reports can contain similar recommendations; they are not silently deduplicated into a fabricated maintenance record.
- Draft export retains the existing report-level format rather than creating a signed approval or a new ticket.
- The loader reads all completed-job pages and report/evidence payloads to calculate an accurate current count. This is suitable for the competition dataset; a large deployment would benefit from a separately designed paginated/aggregated maintenance read API. No fleet-scale performance claim is made.
- Saved critic judgments and source references are visible for qualified review; neither a completed job nor a resolved evidence ID proves a physical failure.
- No live Gemini calls, cloud resources, commits, pushes, merges or deployments occurred.
