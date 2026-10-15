# Enterprise Settings verification

Date: 2026-10-15. Branch: `codex/enterprise-settings`.

## Repository findings and implementation

The Settings route was a placeholder, and navigation marked it “Soon”. No user preference store, end-user roles, notification subscriptions, operational settings write API or configuration audit trail existed. Runtime configuration is loaded from environment variables; production APIs already require verified, allowlisted Google service identities. The existing frontend API client and private backend proxy are preserved.

The placeholder is now a responsive two-column Settings page with all seven requested categories. It follows the existing mint/teal interface in Light mode and provides navy cards and blue accents in Dark mode. The dashboard structure, agents, investigation contracts, calculations and evidence pipeline are unchanged. No UI dependencies were added.

| Section | Functional behavior |
| --- | --- |
| General | Read-only workspace/application/team/environment; editable theme, density, date format, time format and IANA timezone; save, reset, validation and persistence feedback |
| AI Configuration | Read-only actual model/provider, enabled flag, credential-presence boolean, timeout, bounded retry configuration, request concurrency, model-call budget, report-cache setting, recorded usage and provider cooldown/error category |
| Anomaly Detection | Actual algorithm/version, dimensionless score threshold, robust z-score threshold, severity bands, dataset and deterministic train/validation/test configuration |
| Notifications | Six explicitly disabled event subscriptions; in-app, email, SMS and push delivery marked unavailable |
| Data Management | Dataset origin/classification/count/content digest, selected database/image providers, actual packaged document and passage counts; refresh metadata and link to the existing investigation report review/export workflow |
| Security & Access | Actual authentication mode; absent end-user roles, sessions, access management and audit UI explicitly disclosed |
| System Information | Backend version, frontend package version, API/database status, GCS bucket status when selected, credential-configuration status, environment, refresh and sanitized clipboard summary |

Measurement units remain read-only because unit conversion is not implemented. Dataset metadata explicitly states: “AI4I 2020 is a synthetic predictive maintenance dataset. Records do not represent continuous live telemetry from a physical machine.” Packaged reference documents are not presented as real factory maintenance records. Row indices are never interpreted as timestamps.

## Persistence and UX

Preferences are stored under `factorymind.preferences.v1` in localStorage. The key version identifies the schema. Only five allowlisted fields are accepted; invalid/corrupt stored data falls back to defaults. This scope is the current browser profile and origin, not a user account or shared workspace. No credentials, prompts or operational configuration enter browser storage.

Saving validates values, writes storage, verifies read-back and then reports success. Denied writes report an error and retain unsaved changes. Reset restores the last saved values. Switching sections retains drafts. Dashboard-link navigation and document unload warn about unsaved preferences. Native same-document browser Back/Forward navigation is not intercepted; save before using those controls. This is a remaining navigation-guard limitation.

Theme and density apply through the existing shell. System appearance follows OS preference changes. Cross-tab storage events synchronize saved preferences when there are no local edits. Date/time preferences feed the shared application timestamp formatter, including timezone date rollover. Existing fixed SI/engineering units are preserved. Settings cards opt out of decorative entrance animation; existing reduced-motion support remains intact.

## APIs and security

- `GET /api/settings`: explicit Pydantic response allowlist; safe configuration and metadata only.
- `GET /api/settings/system`: read-only diagnostics; database read probe and, for GCS, a bucket-existence check. Failures return unavailable rather than healthy. Local image storage is Unknown because this endpoint does not verify local filesystem storage.
- No PATCH/POST settings API was added. Operational model, timeout, threshold and credential changes remain administrator-managed deployment configuration. No changes to running or historical investigations are made.

Existing production middleware protects both endpoints. Missing identity produces 401; existing allowlist authorization applies. Local development retains its existing unauthenticated behavior. There is no invented administrator role. Response schemas exclude keys, tokens, service identities, project IDs, private URLs and filesystem paths. Clipboard output is limited to the safe system response plus frontend package/build-recording status.

Settings never generates Gemini content or tests provider connectivity. Credential presence is not described as verified provider health. Usage sums only available recorded fields from the latest 100 completed reports. It excludes unrecorded failed and visual requests and is not provider billing, total usage or remaining quota. Partial token recordings are partial sums, not complete provider totals. Concurrent model requests are reported per process; maximum concurrent investigations is unavailable because no reliable corresponding limit is configured.

## Files created and modified

Created:

- `services/api/routes/settings.py`
- `services/api/schemas/settings.py`
- `services/api/tests/test_settings.py`
- `apps/web/src/lib/preferences.ts`
- `apps/web/src/types/settings.ts`
- `apps/web/src/components/layout/PreferenceBridge.tsx`
- `apps/web/src/components/settings/SettingsDashboard.tsx`
- `apps/web/src/components/settings/settings.css`
- `apps/web/src/app/(shell)/preferences.css`
- `apps/web/tests/preferences.test.mjs`
- `apps/web/tests/settings-browser.mjs`
- `reports/enterprise-settings-verification.md`

Modified:

- `services/api/main.py`: register read-only settings routes.
- `apps/web/src/app/(shell)/settings/page.tsx`: replace placeholder.
- `apps/web/src/app/(shell)/layout.tsx`: mount preference bridge and import theme rules.
- `apps/web/src/components/layout/AppSidebar.tsx`: remove Settings “Soon”.
- `apps/web/src/lib/format.ts`: use validated regional timestamp preferences.

## Verification results

| Check | Result |
| --- | --- |
| Complete backend pytest suite | **210 passed, 2 skipped**, 212 collected; zero errors/failures in JUnit output |
| New Settings API tests | **7 passed**; runtime values, source metadata, secret/private-config redaction, rejected writes, actual/unknown service states, database failure, scoped usage and production 401 protection |
| Frontend Node unit tests | **11 passed**, including 3 preference tests and existing proxy/chart tests |
| `npx tsc --noEmit` | Passed |
| `npm run lint` | Passed |
| `npm run build` | Passed after final UI fixes; Settings prerendered successfully |
| Headless Edge browser suite | Passed against the production frontend and read-only responses fetched from an isolated scripted-AI API |
| Desktop and 390px mobile visual inspection | Passed; local screenshots in ignored `.pytest_tmp/settings-visual/` |
| `git diff --check` | Passed |

Browser checks cover all seven sections, loading, retry, unavailable notifications, invalid timezone handling, unsaved dashboard-link navigation, reset/save/reload persistence, Light/Dark/System and OS theme changes, dark input colors, collapsed mobile navigation, horizontal overflow, API failure, disabled copy action after failure, denied browser storage and no uncaught page errors. Browser interception supplies responses obtained from the isolated real API; it is not a test of production Google authentication or live Cloud services. Only GET requests are allowed by the test assertions.

Run backend tests from the repository root:

```powershell
.\services\api\.venv\Scripts\python.exe -m pytest services/api/tests -q --basetemp=.pytest_tmp/settings-full --junitxml=.pytest_tmp/settings-results.xml
```

Run frontend checks from `apps/web`:

```powershell
node --test tests/*.test.mjs
npx tsc --noEmit
npm run lint
npm run build
```

The optional browser runner requires an existing Playwright installation and Edge. No new browser dependency was installed. Point it at disposable local API/frontend servers; use `AI_PROVIDER=scripted`, `FACTORYMIND_INVESTIGATION_ASYNC=false` and a disposable `FACTORYMIND_DB_PATH` for that API. It reads the API and changes only preferences in its isolated browser context.

```powershell
# Set PLAYWRIGHT_MODULE to the directory of an existing Playwright installation
# if it is not resolvable by Node. Do not point these tests at production.
$env:SETTINGS_WEB_URL = 'http://localhost:3013'
$env:SETTINGS_API_URL = 'http://127.0.0.1:8020'
node tests/settings-browser.mjs
```

The two skipped tests are opt-in live Gemini tests; no live Gemini calls were made. Backend tests used isolated storage and scripted/mocked providers. FastAPI TestClient initially hung inside the sandbox, so the successful suite ran with approved process permissions. Existing warnings: Starlette recommends migrating TestClient from httpx to httpx2; pytest reports an unknown `asyncio_default_fixture_loop_scope` option; direct Node TypeScript imports warn about an unspecified package module type. Local `next start` testing also printed the existing standalone-output startup recommendation; the production build itself passed.

## Remaining limitations and operating notes

- Restart the existing API process to register the new routes; the test API used a separate port and database and does not replace the user's running API.
- Operational configuration editing, audit-backed threshold changes, workspace renaming, notification delivery, account preference sync, unit conversion and user/role/session management remain deferred. No nonfunctional save controls are provided for these features.
- Frontend build SHA, evaluation timestamp, dataset refresh timestamp, reliable overall storage usage and provider remaining quota are not recorded and are shown as unavailable rather than invented.
- GCS/Firestore connectivity and production Google authentication were not tested against live cloud resources. Existing production authentication tests use mocks. No cloud resources were created.
- Theme persistence is browser-only and applied after hydration; a brief default Light appearance can occur before saved appearance is applied. Existing specialized charts keep their existing palette.
- Browser Back/Forward without document unload is not covered by the unsaved-change guard; dashboard links and full unload are covered.
- Automated backup and uploaded maintenance-document indexing are not configured by this feature.

No commit, push, merge or deployment was performed. No secrets were printed or exposed, and no ground-truth labels were added to model inputs.
