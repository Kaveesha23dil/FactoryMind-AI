# Full SonarQube findings remediation

Reviewed on 2026-10-11: all 183 unresolved issues returned by the public
SonarQube Cloud API for `Kaveesha23dil_FactoryMind-AI`.
The retrieved rule, file, line, and message inventory is in
[sonar-open-issues.json](sonar-open-issues.json).

## Implemented changes

- Constrained image reads and writes to the resolved storage directory; rejected
  traversal and root-directory references. Added traversal regression tests.
- Removed request-derived values from investigation, revision, and image-analysis
  log messages to prevent log injection.
- Documented HTTP error responses in FastAPI route decorators and migrated the
  upload dependency to `Annotated`.
- Extracted graph-building phases, retained-hypothesis comparison, and excluded
  citation checking into smaller functions; reduced frontend cognitive complexity
  and removed nested conditionals and nested templates.
- Made component props readonly, replaced unstable array-index keys with stable
  data keys, associated form labels with controls, clarified JSX spacing, and
  explicitly handled or ignored asynchronous effect promises.
- Consolidated imports and repeated literals/types; removed unused arguments,
  unnecessary intermediate collections, redundant fixture parentheses, and
  ambiguous string conversion. Exception tests now contain one throwing call.
- Migrated seeded dataset splitting from `RandomState` to `default_rng` (PCG64).
  Split membership and reported metrics changed; refreshed the evaluation JSON
  and corresponding Step 3 metric table. Detection still excludes ground truth,
  baseline fitting uses training only, and threshold selection uses validation.
- Added local SonarJS checks for complexity, nested conditionals/templates,
  readonly props, and repeated unions, plus type-aware promise and label checks.
  Quality thresholds and scanner exclusions were not relaxed.

The earlier pagination, severity-filter, and modal duplication extraction is
already present in the repository; see [sonar-quality-fixes.md](sonar-quality-fixes.md).
The cloud duplication percentage still requires a new scan.

## Reported rule inventory

| Rule | Findings addressed |
|---|---:|
| `python:S1172` | 2 |
| `python:S1192` | 5 |
| `python:S1481` | 1 |
| `python:S3776` | 3 |
| `python:S5778` | 7 |
| `python:S6711` | 1 |
| `python:S7500` | 1 |
| `python:S8410` | 1 |
| `python:S8415` | 38 |
| `python:S9073` | 1 |
| `python:S9083` | 6 |
| `pythonsecurity:S2083` | 1 |
| `pythonsecurity:S5145` | 4 |
| `typescript:S3358` | 34 |
| `typescript:S3776` | 3 |
| `typescript:S3863` | 2 |
| `typescript:S4323` | 1 |
| `typescript:S4624` | 1 |
| `typescript:S6353` | 1 |
| `typescript:S6479` | 5 |
| `typescript:S6551` | 1 |
| `typescript:S6759` | 53 |
| `typescript:S6772` | 2 |
| `typescript:S6853` | 2 |
| `typescript:S7721` | 2 |
| `typescript:S7744` | 1 |
| `typescript:S7770` | 1 |
| `typescript:S9383` | 3 |

## Validation and remaining limits

- Backend suite: 105 passed, 1 skipped. The skipped test is the explicitly opt-in
  live Gemini smoke test; mocked agent and investigation workflows pass.
- `npm run lint`: passed with type-aware checks enabled.
- `npm run build`: passed production compilation, TypeScript, and prerendering.
- Evaluation export: regenerated successfully with generator provenance.
- `git diff --check`: passed.

No cloud issues were manually dismissed. These are local code fixes, not a
confirmed passing cloud analysis. SonarQube Cloud must analyze the changed
revision to establish issue closure, reliability/security ratings, and whether
new-code duplication is at or below 3%. No commit, push, or merge was performed.

`npm audit` separately reports five high findings in the development-tool chain
through `braces` <=3.0.3 (GHSA-vfj7-8cjw-p6xm). The registry currently has no
patched release. The suggested fix downgrades Next's ESLint configuration across
major versions and is incompatible with this project's configuration, so it was
not applied. This advisory is not resolved by the Sonar source-code changes.
The backend test run also emits an upstream TestClient/httpx deprecation warning.
