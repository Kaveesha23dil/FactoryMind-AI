"""FactoryMind AI FastAPI application.

Wires dataset/telemetry, anomaly detection, and incident management routers,
configures CORS from settings, installs structured logging, and warms the
anomaly engine / incident store at startup.

Local development and private Cloud Run profiles share the existing API.
Production enforces verified service principals and durable cloud storage.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.api.core import config
from services.api.routes import (
    anomalies,
    counterfactuals,
    dataset,
    evidence_graph,
    incidents,
    investigations,
    visual_inspection,
)
from services.api.services.anomaly_engine import get_engine
from services.api.routes.incidents import get_service
from services.api.routes.investigations import get_service as get_investigation_service
from services.api.core.logging import JsonLogFormatter, configure_logging
from services.api.core.production import validate_configuration
from services.api.core.security import authorize

configure_logging()
logger = logging.getLogger("factorymind.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    started = time.perf_counter()
    validate_configuration()
    app.state.ready = False
    get_service().initialize()
    investigation_service = get_investigation_service()
    investigation_service.initialize()
    if config.settings.investigation_async and config.settings.job_dispatch == 'thread':
        investigation_service.start_worker()
    summary = get_engine().summary()
    app.state.ready = True
    logger.info(
        "Startup complete in %.2fs: %d observations scored (%d anomalies), store ready at %s",
        time.perf_counter() - started,
        summary["analyzed_sample_count"],
        summary["detected_anomaly_count"],
        config.settings.database_path,
    )
    try:
        yield
    finally:
        app.state.ready = False
        investigation_service.stop_worker()


app = FastAPI(
    title="FactoryMind AI API",
    version="0.3.0",
    description=(
        "Evidence-driven industrial intelligence API. Anomaly severities are "
        "application-defined and are not official equipment safety classes."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware('http')(authorize)


@app.get('/healthz', include_in_schema=False)
def liveness():
    return {'status': 'ok'}


@app.get('/readyz', include_in_schema=False)
def readiness():
    if not getattr(app.state, 'ready', False):
        return JSONResponse({'status':'not_ready'}, status_code=503)
    try:
        get_service().repository.initialize()
        if config.settings.upload_backend == 'gcs':
            from services.api.services.object_storage import object_store
            object_store().check()
    except Exception:
        return JSONResponse({'status':'dependency_unavailable'}, status_code=503)
    return {'status':'ready'}

app.include_router(dataset.router)
app.include_router(anomalies.router)
app.include_router(incidents.router)
app.include_router(investigations.router)
app.include_router(evidence_graph.router)
app.include_router(counterfactuals.router)
app.include_router(visual_inspection.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log the stack trace server-side but never expose it to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": "internal_error"},
    )
