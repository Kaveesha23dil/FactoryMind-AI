"""FactoryMind AI FastAPI application.

Wires dataset/telemetry, anomaly detection, and incident management routers,
configures CORS from settings, installs structured logging, and warms the
anomaly engine / incident store at startup.

Local-development API only; state-changing incident endpoints are NOT
authenticated or hardened for public deployment.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.api.core import config
from services.api.routes import anomalies, dataset, incidents, investigations
from services.api.services.anomaly_engine import get_engine
from services.api.routes.incidents import get_service
from services.api.routes.investigations import get_service as get_investigation_service

class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


log_handler = logging.StreamHandler()
log_handler.setFormatter(JsonLogFormatter())
logging.basicConfig(
    level=getattr(logging, config.settings.log_level.upper(), logging.INFO),
    handlers=[log_handler],
)
logger = logging.getLogger("factorymind.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    started = time.perf_counter()
    get_service().initialize()
    investigation_service = get_investigation_service()
    investigation_service.initialize()
    if config.settings.investigation_async:
        investigation_service.start_worker()
    summary = get_engine().summary()
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

app.include_router(dataset.router)
app.include_router(anomalies.router)
app.include_router(incidents.router)
app.include_router(investigations.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log the stack trace server-side but never expose it to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": "internal_error"},
    )
