# Free-hosting readiness — FactoryMind AI

Assessment: 2026-10-16. **Optional deployment code is prepared, not deployed.** No public hosted URL, destination database, live provider run or zero-cost account eligibility is verified by this report. Keep AI and writes disabled until external gates pass. See [operator guide](free-hosting-deployment.md).

## Readiness matrix

| Requirement | Status | Evidence / limitation |
|---|---|---|
| Existing local / GCP functionality | Ready | Existing regression suite passes; selectors preserve SQLite/Firestore, local/GCS and thread/Tasks branches |
| Portable configuration | Ready | Strict production validation; Render cannot launch development security; SSL/session port, explicit membership, bounded AI settings required |
| PostgreSQL transport/schema | Unverified | Mock dialect, transactions/fencing contracts and schema tests pass; actual migrated PostgreSQL round-trip is opt-in and skipped |
| Schema/data migration | Requires external configuration | Explicit SQL v001 and backup-first, review-gated importer; no user database copied; manually apply only after approval |
| Private Supabase storage | Unverified | Mock private-bucket/upload/signed-read/error tests pass; actual REST/API key and Storage behavior require hosted smoke tests |
| Supabase Auth and invite list | Requires external configuration | Confirmed user verification and server UUID roles; shared curated workspace; create accounts and configure keys manually |
| Private per-user tenants | Blocked | No ownership isolation is claimed. All allowlisted members see shared curated records. Do not onboard private unrelated users |
| Frontend proxy/login security | Ready | Actual handlers tested with mocked networks; token only in secure HttpOnly cookie; spoofed headers ignored; no Google ADC in portable path |
| Direct public-backend protection | Ready | Auth middleware denies anonymous/unlisted users and viewer writes; production tests exercise these paths |
| Jobs and failure persistence | Ready | Bounded explicit request mode, PostgreSQL lock/token fencing and no automatic worker; duplicate and partial interruption mock tests pass |
| Durable background jobs | Blocked | Not promised on Free hosting; use saved demo or constrained explicit requests. No always-on worker created |
| Real restart/disconnect recovery | Unverified | No hosted process/session loss test against real PostgreSQL; multi-step counterfactual/image interruption may need manual reconciliation |
| Gemini reliability | Ready | Existing quota/cooldown/concurrency/cache/citation controls retained; portable retries disabled and per-user daily operation allowance added |
| Available Gemini model/quota | Requires external configuration | No live call; inspect account allocation before enabling. No silent fallback or guaranteed free quota |
| Counterfactual evidence isolation | Ready | Existing mocked exclusion/reasoning regression tests pass; original and revised IDs/context remain separate |
| Saved demo content | Ready | Existing actual saved Google report remains available locally; no fabricated/counterfactual report generated |
| Hosted saved demo | Requires external configuration | Review/import selected saved records; current local snapshot has no saved counterfactual comparison |
| Dataset/corpus packaging | Ready | Repository-root Python service includes existing CSV and knowledge sources; no local absolute path added |
| Render Python 3.12 deployment | Unverified | Dependencies installed locally, but no native Render build performed; Python version/wheel compatibility must be checked there |
| Render memory/startup | Unverified | No 512 MB compatibility or cold-start timing claim; deployment/provider-dashboard measurement required |
| Render frontend | Ready | Portable production build, standalone asset preparation and loopback smoke checks passed |
| Vercel Hobby alternative | Requires external configuration | Personal non-commercial eligibility and supported function duration must be confirmed; not static hosting |
| Free-plan capacity | Requires external configuration | Two Render services share monthly hours; Supabase pause/storage/egress and Gemini quota remain constraints |
| Secrets | Ready | Exact configured credential values absent from tracked/new source and built static assets; no comprehensive historical Git secret audit claimed |
| Actual end-to-end hosted system | Unverified | No Supabase/Render/Vercel resource creation, deployment or real cloud integration executed |

## Verified tests

Final backend command (from repository root, scripted/no live Gemini):

```powershell
$env:FACTORYMIND_RUN_LIVE_TESTS='0'
$env:AI_PROVIDER='scripted'
& .\services\api\.venv\Scripts\python.exe -m pytest services/api/tests -q --basetemp=.pytest_tmp/free-hosting-final2 --junitxml=.pytest_tmp/free-hosting-final2.xml
```

**243 collected: 240 passed, 3 skipped, 0 failures/errors**, 25.269 seconds as recorded in JUnit XML. Skips are two live Gemini tests and the opt-in real PostgreSQL contract. Warnings: existing Starlette/httpx deprecation and an unknown pytest asyncio configuration option. New coverage includes production guards, auth/member/writer controls, daily usage rejection, cookie/proxy routes, PostgreSQL SQL adaptation/UTC/error redaction/stale writer fences/duplicate execution/partial evidence preservation, private object behavior, metadata selection, migration collection and mocked dry-run guard. Existing numerical, grounding, counterfactual and persistence tests also passed.

From `apps/web`:

- `npm run lint`: passed after fixing a test harness variable that violated Next's reserved `module` rule.
- `npx tsc --noEmit`: passed.
- `node --test tests/*.test.mjs`: **22 passed**, including four actual Route Handler source tests with mocked network/ADC. Existing Node module-type warnings are non-fatal.
- `npm run build` with `FACTORYMIND_DEPLOYMENT_TARGET=render` and `NEXT_PUBLIC_API_URL=/api/backend`: passed, dynamic backend/session routes retained.
- `node scripts/prepare-standalone.mjs`: passed; standalone starts successfully on loopback port 3013.
- Production HTTP smoke: `/login`, `/overview`, `/api/health` returned 200; anonymous `/api/backend/api/incidents` returned 401 with a valid placeholder HTTPS backend configured; worker route returned 403; cross-origin session POST returned 403. The first smoke without a valid backend origin correctly returned configuration 503; rerun with valid HTTPS origin verified authentication rejection. No external backend was called.
- Default/original profile `npm run build`: passed separately.
- `git diff --check`: passed.
- Exact local configured credential scan: zero source/static asset matches; values never printed. Backup directory is now Git-ignored.

No Docker build, hosted Auth/Storage/DB verification, provider memory benchmark or live Gemini run is claimed. Automated approval review rejected the migration CLI dry-run command before execution because it included a schema operation that might create persistent tables. No migration ran; a separate unit test mocked both DDL and connection entry points to verify the default no-write guard safely. A process-memory inspection approval timed out, so no memory measurement was obtained. Neither blocked operation was bypassed.

### Opt-in real database test (manual approval first)

Use an explicitly disposable PostgreSQL database with migration 001 applied; never point tests at production. Set `FACTORYMIND_RUN_POSTGRES_TESTS=1` and `FACTORYMIND_TEST_POSTGRES_URL` securely, then run `services/api/tests/test_postgres_integration.py`. Its repository round trip uses a forced-rollback transaction. Schema setup is a separate deliberate mutation, not part of default tests. Additional hosted smoke tests in the deployment guide are still necessary for locks, restart recovery and Supabase pooler behavior.

## Defects/constraints identified and changes

1. Production originally required Google IAM, Firestore/GCS and Tasks. Added a separate strictly validated portable target while preserving GCP contracts/defaults.
2. Original relational repositories depended on SQLite dialect/rows. Added a narrow PostgreSQL transport, schema migration, UTC normalization, parameter binding, active uniqueness and composite incident/evidence constraints rather than rewriting repositories.
3. Portable public services had no individual visitor authentication. Added Supabase verified sessions and backend role allowlists; no shared visitor secret. This intentionally supports one curated shared workspace only.
4. Cloud Tasks cannot be assumed on a no-billing deployment, and ephemeral background tasks are not durable. Added explicit bounded execution, persisted status, session lock and stale-write fences; partial evidence is retained and requires a new explicit investigation.
5. Object routing/metadata only understood local/GCS. Added private Supabase storage and selection throughout upload/download/readiness/settings; fixed storage-backend metadata selection.
6. Visual analysis did not reject a target investigation from a different incident. Added the same-incident guard before analysis, with a regression test.
7. A cached completed portable execution must not advertise a new run. The execution response now derives `executed` from a real attempt increase, with regression coverage.
8. No reviewed portable migration existed. Added backup-first selection, provenance audit, note/token redaction, optional reviewed image copy, idempotent conflict refusal and no source deletion. Content review remains mandatory.
9. Frontend standalone output needs public/static assets on native Node hosting. Added a build-time copy helper and exact Render build/start configuration.

Agent prompts, deterministic anomaly calculations, model selection default, report grounding, maintenance approval scope and existing chart/UI layout were not rewritten. No synthetic records were inserted. Database report JSON preserves hypotheses, critic notes, actions and raw evidence provenance. No new fake settings/audit/approval persistence is claimed.

## Actions required before public demonstration

1. Approve provisioning only after checking free-plan eligibility/limits; do not add paid services. Confirm whether shared invite-only access meets judging needs.
2. Create/configure Supabase project, private bucket and confirmed member accounts; migrate schema and reviewed records manually, then install a restricted runtime database role.
3. Configure/deploy backend and frontend using their actual environment templates; keep AI and writes false. Do not place backend service-role/Gemini/DB credentials on frontend.
4. Pass actual PostgreSQL/Auth/Storage round trips, anonymous/role isolation, restart persistence, lock recovery, cold-start and memory checks. These are the remaining P0 gates for a writable deployment.
5. Verify the saved report, graph, critic concerns and maintenance actions after import. Preserve labels saying saved and synthetic dataset. No saved counterfactual currently exists to demonstrate offline comparison.
6. Enable presenter writes or one live investigation only after explicit approval and quota/model confirmation. If Render memory, timeout, auth eligibility or free allowances fail, keep the verified local saved demo and defer hosted live AI rather than claiming it works.
7. No commit, push, merge, cloud deployment, paid resource or user-data migration was performed.

## Exact changed/new files
- `.gitignore`
- `apps/web/scripts/prepare-standalone.mjs`
- `apps/web/src/app/(shell)/layout.tsx`
- `apps/web/src/app/api/backend/[...path]/route.ts`
- `apps/web/src/app/api/session/route.ts`
- `apps/web/src/app/login/page.tsx`
- `apps/web/src/components/layout/LoginForm.tsx`
- `apps/web/src/components/layout/PortableAccess.tsx`
- `apps/web/src/components/settings/SettingsDashboard.tsx`
- `apps/web/src/lib/portableProxyPolicy.ts`
- `apps/web/tests/portable-proxy.test.mjs`
- `apps/web/tests/portable-routes.test.mjs`
- `deploy/render-backend.env.example`
- `deploy/render-frontend.env.example`
- `README.md`
- `render.yaml`
- `reports/free-hosting-deployment.md`
- `reports/free-hosting-readiness.md`
- `scripts/migrate_postgres.py`
- `services/api/agents/request_control.py`
- `services/api/core/config.py`
- `services/api/core/portable.py`
- `services/api/core/production.py`
- `services/api/core/security.py`
- `services/api/db/migrations/001_portable.sql`
- `services/api/db/postgres.py`
- `services/api/main.py`
- `services/api/requirements-portable.txt`
- `services/api/routes/investigations.py`
- `services/api/routes/settings.py`
- `services/api/routes/visual_inspection.py`
- `services/api/services/firestore_repository.py`
- `services/api/services/investigation_service.py`
- `services/api/services/object_storage.py`
- `services/api/services/supabase_storage.py`
- `services/api/services/visual_evidence_service.py`
- `services/api/tests/test_portable.py`
- `services/api/tests/test_postgres_integration.py`
