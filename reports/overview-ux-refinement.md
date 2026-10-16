# Overview UX refinement

Verified October 16, 2026. Existing light mint, dark green, pastel and rounded-panel design preserved. Pre-existing uncommitted Settings/evaluation/submission work was preserved.

## Changes

- Replaced decorative eyebrow/headline with “From Machine Anomalies to Explainable Decisions.” and the requested description. Removed breadcrumb; reduced top bar to 64px while retaining actual health status and AetherForge identity.
- Kept one primary “Explore AI Demo” CTA. It opens the existing saved-results route when the backend identifies an eligible report. Otherwise the CTA is disabled with a checking/unavailable explanation. No model request is started.
- Removed only the Guided Saved Demo sidebar entry and redundant dataset footer; all seven requested navigation routes remain. The `/demo` route is retained.
- Added “Operations Overview”, the synthetic dataset indicator and concise no-equipment-control disclaimer. Refresh re-fetches real operational data and health; failures display unavailable status and explicitly identify previously loaded values.
- Four compact linked cards show actual detected anomalies, active incidents, completed investigations and failures, in that order. Smaller single icons, consistent numbers and softer existing pastel colors replace oversized decorative artwork.
- Preserved the animated donut and investigation-status bars in equal-width panels. The donut uses the existing supported low/medium/high/critical levels and excludes normal observations. Running and queued statuses remain explicit.
- Recent AI Investigations is now full width with the five latest records, incident IDs, primary finding/progress, status, actual created timestamps and View Report actions. Rows sort by the backend creation timestamp; long findings truncate with full-text title. Dates use existing saved regional preferences. Table is horizontally scrollable without page overflow.
- Removed secondary evidence-integrity marketing panel, dataset-label statistics strip and local search/status controls over only five recent records to simplify hierarchy. Evidence auditing and full investigation filtering remain available in existing features.
- Responsive KPI grid is four columns on desktop, two on tablet/laptop where needed, and one on mobile. Charts stack on smaller widths. Existing chart entrance/update/reduced-motion behavior remains intact.

## Files and reused components

Modified in this task:

- `apps/web/src/components/dashboard/ModernOverview.tsx`
- `apps/web/src/components/dashboard/overview.css`
- `apps/web/src/components/layout/AppSidebar.tsx`
- `apps/web/src/types/submission.ts`

Added:

- `apps/web/tests/overview-browser.mjs`
- `reports/overview-ux-refinement.md`

Reused `apiFetch`, `getHealth`, `formatDateTime`, `AnimatedSeverityDonut`, `AnimatedJobBars`, existing shell/motion/navigation and existing `/demo`, investigation and incident routes. The TypeScript recent-item shape now includes incident IDs and creation timestamps already returned by the backend. No backend API, algorithm, agent, credential, security or storage changes were made for this refinement.

## API integration

Initial load and Refresh read `GET /api/submission/overview` and `GET /health`. The previous additional dataset-summary request was removed. The existing overview payload already provides counts, supported severity distribution, persisted job states, recent records and audited demo eligibility; no new endpoint was necessary. API status reflects the last load/Refresh health result, not a continuous heartbeat.

During read-only browser verification the backend returned 580 anomalies, 25 active incidents, 1 completed investigation and 9 failures. These were compared to the live response in tests; none are hardcoded in the UI. These are development-store values and may change. The five newest jobs currently happen to be failures, so the UI correctly shows no completed finding for those rows rather than inventing summaries.

## Verification

- `npx tsc --noEmit`: passed.
- `npm run lint`: passed.
- `node --test tests/*.test.mjs`: 11 passed.
- `npm run build`: passed; Overview and Guided Demo routes generated successfully.
- Headless Edge overview acceptance test: passed against real backend read responses, with browser-only failure/empty simulations. Checked real KPI/severity/status values, newest-five timestamp ordering, seven sidebar route responses, demo/report navigation, actual Refresh requests, stale/offline and empty states, disabled missing-demo CTA, 1440/1100/768/390px layouts, mobile menu, chart viewport entry, GET-only API calls and no uncaught page errors.
- Desktop and mobile screenshots visually inspected; ignored artifacts are in `.pytest_tmp/overview-refinement/`.
- `git diff --check`: passed; existing LF/CRLF normalization warnings only.
- Backend tests were not repeated: no backend files were changed by this task. Prior uncommitted backend test/evaluation edits belong to the preceding verification task.

Re-run browser test from `apps/web` with an existing Playwright/Edge installation:

```powershell
# PLAYWRIGHT_MODULE may point to an existing Playwright package directory.
$env:SETTINGS_WEB_URL = 'http://localhost:3000'
$env:SETTINGS_API_URL = 'http://127.0.0.1:8000'
node tests/overview-browser.mjs
```

This test performs GETs only. API assertions use actual backend responses; failure/empty responses are intercepted in the isolated browser. It does not create investigations, alter records or call Gemini.

## Remaining limitations

- The investigation board supports in-page filtering, but not a failed-status URL parameter. The failure KPI honestly opens the existing board; select Failed there. No unsupported query string was invented.
- Overview counts represent the API's existing persisted job totals, not a newly introduced provider-filtered metric. Production requires Google provider; development stores may include scripted test runs if operators add them.
- Eligibility for a saved demo does not mean a report is an accepted diagnosis. The demo continues to expose historical critic concerns and missing saved counterfactuals.
- Charts initialize when entering the viewport; a full-page capture taken without scrolling can show their reserved space before entry. Mobile browser verification explicitly exercises both charts.
- No live Gemini request, dependency installation, commit, push, merge or deployment was performed.
