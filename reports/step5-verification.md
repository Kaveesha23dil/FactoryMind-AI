# Step 5 implementation verification

Verification date: 2026-10-10. Work on `feature/advanced-ai-investigation`.
Existing functionality was preserved. No commits, pushes, or merges were performed.

Step 5 adds three advanced AI capabilities on top of the Step 4 multi-agent
engine: an interactive evidence graph (P0), genuine counterfactual
investigations (P0), and Gemini visual inspection (P1).

## P0 - Interactive evidence graph

Deterministic projection of stored investigation data; no language-model call is
used to draw it.

- `services/api/services/evidence_graph_service.py` builds nodes from the
  incident, persisted evidence catalog, report hypotheses, and recommended
  actions. Node types: `incident`, `sensor_evidence`, `document_evidence`,
  `visual_evidence`, `hypothesis`, `recommended_action`.
- Edges only exist when the structured records justify them (`SUPPORTS`,
  `CONTRADICTS`, `DERIVED_FROM`, `RELATES_TO`, `RECOMMENDS`); unresolved
  references are dropped rather than invented.
- A deterministic layered layout (`_X_GAP=340`, `_Y_GAP=130`) is computed
  server-side so the frontend does not guess positions.
- `services/api/schemas/evidence_graph.py` (`GraphNode`, `GraphEdge`,
  `EvidenceGraph`).
- Endpoint: `GET /api/investigations/{investigation_id}/graph`.
- Frontend `EvidenceGraphView.tsx` renders a custom SVG (no new dependency) with
  pan, zoom, edge highlighting, a legend, and a node-inspector side panel that
  surfaces the node's supporting records (`data` payload).

## P0 - Counterfactual investigation

Genuine re-run: selected evidence (and the dependency closure over derived
features) is removed from the reasoning context, the full pipeline is re-executed,
and a revised investigation is persisted separately. The original investigation
and its evidence are never mutated.

- `services/api/services/exclusion.py` - pure transforms: feature dependency
  resolution, evidence filtering, anomaly restriction, measurement sanitization,
  baseline restriction.
- `services/api/services/comparison_service.py` - qualitative diff only. There
  are **no numeric confidence deltas**; the anomaly score is a deterministic
  recomputation (`round(sqrt(sum(retained z^2)), 4)`) and is labeled as such.
- `services/api/services/counterfactual_service.py` builds a `PreparedContext`,
  creates a queued revised investigation, runs it **synchronously** (the generic
  worker would rerun without the prepared restricted context), then stores the
  comparison and dependency trace.
- `services/api/agents/orchestrator.py` gained `PreparedContext` and
  `run(..., prepared=None)`; `_build_report` records `excluded_evidence_reused`
  so the critic flags any leakage of excluded evidence.
- Repository/tables: `counterfactual_scenarios` (`services/api/db/database.py`,
  `counterfactual_repository.py`). `investigation_evidence` primary key was
  migrated to composite `(investigation_id, evidence_id)` so revised evidence can
  reuse original evidence IDs.
- Endpoints:
  `POST /api/investigations/{id}/counterfactual`,
  `GET /api/investigations/{id}/counterfactuals`,
  `GET /api/counterfactuals/{scenario_id}`.
- Frontend `CounterfactualPanel.tsx`: evidence exclusion selector, rationale,
  scenario history, and a comparison view (anomaly score/severity shift,
  hypothesis added/removed/retained/shift, contradiction and recommendation
  diffs, dependency trace).

## P1 - Visual inspection

- `services/api/agents/vision_agent.py` + `agents/runtime.py`
  (`run(spec, prompt, image_parts=...)`) route image bytes to Gemini. Output is
  always hedged and carries explicit limitations; it is never presented as a
  confirmed physical diagnosis.
- `services/api/services/image_utils.py` sniffs MIME type and parses dimensions
  manually (no Pillow dependency). `services/api/services/visual_evidence_service.py`
  stores the file, analyzes it via `asyncio.run`, and attaches a
  `visual_observation` evidence record (`EV-VISUAL-00n`) to an investigation when
  one is supplied.
- Uploads accept PNG/JPEG/GIF/WEBP up to `FACTORYMIND_VISUAL_MAX_IMAGE_BYTES`
  (default 5 MB); `python-multipart==0.0.32` was added to `requirements.txt`.
- Endpoints: `POST/GET /api/incidents/{id}/images`, `GET /api/images/{id}`,
  `GET /api/images/{id}/content`, `POST /api/images/{id}/analyze`.
- Frontend `VisualInspectionPanel.tsx`: upload, thumbnail grid, metadata,
  analyze/re-analyze, and observation/limitation review with severity hints.

## Frontend workspace integration

`InvestigationWorkspace.tsx` now has four tabs - **Report**, **Evidence graph**,
**What-if**, and **Visual inspection**. New shared types
(`types/evidenceGraph.ts`, `types/counterfactual.ts`, `types/visual.ts`), API
helpers (`lib/api.ts` including multipart upload), and labels/colors
(`lib/investigations.ts`). Counterfactual reports show a revision banner and any
`excluded_evidence_reused` in the critic panel. Next.js 16 breaking changes were
reviewed from `node_modules/next/dist/docs/` before writing code; the graph uses a
custom SVG to avoid adding a dependency.

## Tests and verification

```powershell
python -m pytest -q          # 101 passed, 1 skipped (live Gemini smoke)
cd apps/web
npx tsc --noEmit             # clean
npm run lint                 # 0 findings
npm run build                # production build passed (Next.js 16 Turbopack)
```

New tests: `tests/test_exclusion.py`, `tests/test_counterfactuals.py`,
`tests/test_evidence_graph.py`, `tests/test_visual_inspection.py`;
`tests/conftest.py` gained a scripted vision response. Counterfactual tests verify
no leakage, dependency closure, and qualitative comparison output.

## Inventory

New backend: `services/api/services/{exclusion,comparison_service,
counterfactual_service,counterfactual_repository,visual_evidence_service,
visual_repository,image_utils,evidence_graph_service}.py`,
`services/api/schemas/{counterfactual,visual_evidence,evidence_graph}.py`,
`services/api/agents/vision_agent.py`,
`services/api/routes/{counterfactuals,visual_inspection,evidence_graph}.py`, and
the four new test modules.

Modified backend: `agents/orchestrator.py`, `agents/runtime.py`,
`services/investigation_service.py`, `db/database.py`, `core/config.py`,
`schemas/{investigation,evidence}.py`, `routes/{investigations,main}.py`,
`requirements.txt`.

New web: `types/{evidenceGraph,counterfactual,visual}.ts`,
`components/investigations/{EvidenceGraphView,CounterfactualPanel,
VisualInspectionPanel}.tsx`.

Modified web: `types/investigation.ts`, `lib/api.ts`, `lib/investigations.ts`,
`components/investigations/InvestigationWorkspace.tsx`.

## Limitations

- The API remains unauthenticated local development tooling and needs hardening
  before public deployment.
- Counterfactuals run synchronously in-request; large contexts should move to the
  worker with a serialized prepared context.
- Visual analysis is a supporting signal only and depends on Gemini availability;
  it is never treated as ground truth.
- The evidence graph layout is a deterministic layered projection, not a
  force-directed optimization.

## Run

```powershell
python -m pip install -r services/api/requirements.txt
python -m uvicorn services.api.main:app --reload --port 8000
# optional standalone worker: python -m services.api.services.investigation_worker
# frontend (apps/web): npm ci && npm run dev
```
