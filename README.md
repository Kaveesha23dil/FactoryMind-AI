# FactoryMind AI

FactoryMind AI uses Next.js and FastAPI to analyze the AI4I synthetic dataset.
It also runs Gemini-powered, evidence-based root-cause investigations on detected
anomalies using Google ADK multi-agent pipelines.

See [Step 4 run and feature documentation](reports/step4-verification.md) for the
AI investigation features, configuration, agent architecture, API endpoints, tests,
and limitations. The [Step 3 audit](reports/step3-verification.md) covers the anomaly
detection engine, incident management, and evaluation metrics.

Quick start from the repository root:

```powershell
python -m pip install -r services/api/requirements.txt
```

Create `services/api/.env` from `.env.example` (or export in your shell). The worker
needs `GOOGLE_API_KEY` to run real investigations and the secret
`FACTORYMIND_WORKER_SECRET` to authorize processing. Without `GOOGLE_API_KEY`, set
`AI_PROVIDER=scripted` and the investigation input payloads still render.

Run the API and worker:

```powershell
python -m uvicorn services.api.main:app --reload --port 8000
python -m services.api.services.investigation_worker --loop
```

In a second terminal:

```powershell
cd apps/web
npm ci
npm run dev
```

Open http://localhost:3000. API documentation: http://127.0.0.1:8000/docs.

From the incident detail page, use "Investigate with AI" to start an investigation and
review the workspace under AI Investigations. The API is for local development. Add
authentication and authorization before public incident mutations. Scores describe
anomalies, not calibrated failure probabilities.