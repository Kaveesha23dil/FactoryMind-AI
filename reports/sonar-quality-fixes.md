# SonarQube quality gate fixes

The public analysis for `Kaveesha23dil_FactoryMind-AI` was inspected on 2026-10-10.
The reported gate failed at 4.0% new-code duplication, C reliability, and C security.
Source: https://sonarcloud.io/project/issues?id=Kaveesha23dil_FactoryMind-AI

## Security findings addressed

- `pythonsecurity:S8707`: removed the arbitrary `--output` destination from the
  evaluation CLI. Reports now always go to the script repository's
  `reports/anomaly-evaluation.json`; request/CLI arguments never reach filesystem writes.
- `pythonsecurity:S5145`: status-update logging uses a constant message. Incident
  details remain in the persistent audit timeline without request text entering logs.

## Reliability findings addressed

- `typescript:S1082`, `typescript:S6847`: replaced anomaly/telemetry dialog divs
  and click interception with a shared native modal dialog. Escape dismisses it;
  the browser manages modal focus. The backdrop is an actual button.
- `python:S1656`: removed anomaly severity self-assignment.
- `python:S7519`: initialized independent integer severity counts with dict.fromkeys.
- `typescript:S6772`: wrapped checkbox and dashboard legend labels in explicit spans.
- `typescript:S7503`: redirects returns Promise.resolve without a redundant async modifier.
- `typescript:S8786`: replaced trailing-slash regex with a linear character scan.
- Removed mouse-only table-row activation; existing Inspect and record buttons remain.

## Duplication refactoring

Sonar identified repeated blocks between anomaly and incident tables (pagination,
severity filters, and page calculations). Extracted `TablePagination.tsx` and
`SeverityFilter.tsx` and replaced both copies. Native dialog behavior is also shared
in `Modal.tsx`. No quality thresholds or duplication exclusions were changed.

## Verification

- `python -m pytest -v`: **57 passed** (4.45s), including new security export tests.
- `npm run build`: passed production compilation and TypeScript checks.
- `npm run lint`: passed with no findings.
- Cloud findings were fetched read-only; no issue statuses were manually dismissed.

Changes are local and uncommitted. No push or merge was performed. SonarQube Cloud
must analyze the updated revision to establish the resulting ratings and duplication
percentage. The previous cloud gate result is not a measurement of these local fixes.
Maintainability findings outside the failed gate's reliability/security conditions
were not all refactored in this change.
