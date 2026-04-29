"""
Enterprise Agents Platform - FastAPI entrypoint.

Wires up middleware (CORS, auth, request-id), observability (structlog,
optional OpenTelemetry), and routers for the orchestrator and each
specialized worker agent.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from shared.observability import (
    configure_structured_logging,
    setup_opentelemetry,
    create_agent_metrics,
)
from shared.logging_utils import get_logger
from shared.auth import bearer_auth_middleware, derive_user_id

from orchestrator.routes import router as orchestrator_router
from agents.inventory.routes import router as inventory_router
from agents.policy.routes import router as policy_router
from agents.notification.routes import router as notification_router
from agents.analytics.routes import router as analytics_router
from agents.orders.routes import router as orders_router

load_dotenv()

configure_structured_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("main")


def _rate_limit_key(request: Request) -> str:
    """Use bearer-token-derived user_id when available, fall back to IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=[os.getenv("DEFAULT_RATE_LIMIT", "60/minute")],
)

tracer: Optional[object] = None
meter: Optional[object] = None
metrics: Optional[dict] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("platform_starting")

    global tracer, meter, metrics
    if os.getenv("ENABLE_OTEL", "false").lower() == "true":
        tracer, meter = setup_opentelemetry(
            service_name=os.getenv("OTEL_SERVICE_NAME", "enterprise-agents-platform"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        )
        if meter:
            metrics = create_agent_metrics(meter)
            logger.info("metrics_enabled")

    logger.info(
        "platform_ready",
        agents=["orchestrator", "inventory", "policy", "analytics", "orders", "notification"],
        architecture="modular_monolith",
        protocol="a2a",
        auth_enabled=bool(os.getenv("PLATFORM_API_KEY")),
        otel_enabled=os.getenv("ENABLE_OTEL", "false").lower() == "true",
    )

    yield

    logger.info("platform_shutdown")


app = FastAPI(
    title="Enterprise Agents Platform",
    description=(
        "A Level 3 Modular Monolith Agent Swarm built with Google ADK. "
        "Provides enterprise business workflow automation with six specialized agents."
    ),
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------- middleware
class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request_id (and a placeholder user_id) to every request."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        # user_id is set by bearer_auth_middleware below; default for unauth/health.
        if not getattr(request.state, "user_id", None):
            request.state.user_id = derive_user_id(None)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=int(duration_ms),
            user_id=getattr(request.state, "user_id", None),
        )
        return response


app.add_middleware(RequestContextMiddleware)
app.middleware("http")(bearer_auth_middleware)


def _parse_origins(value: str | None) -> list[str]:
    if not value:
        return ["http://localhost:5173", "http://localhost:3000"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


cors_origins = _parse_origins(os.getenv("CORS_ORIGINS"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


# --------------------------------------------------------------- exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        request_id=getattr(request.state, "request_id", None),
        error=str(exc),
        error_type=type(exc).__name__,
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
        },
    )


# ------------------------------------------------------------------ public endpoints
@app.get("/", tags=["Health"])
@limiter.limit("100/minute")
async def root(request: Request):
    return {
        "status": "online",
        "platform": "Enterprise Agents Platform",
        "architecture": "modular_monolith",
        "version": "1.1.0",
        "auth_required": bool(os.getenv("PLATFORM_API_KEY")),
        "agents": [
            "orchestrator",
            "inventory",
            "policy",
            "analytics",
            "orders",
            "notification",
        ],
        "protocols": ["a2a", "mcp"],
        "endpoints": {
            "orchestrator": "/orchestrator",
            "inventory": "/inventory",
            "policy": "/policy",
            "analytics": "/analytics",
            "orders": "/orders",
            "notification": "/notification",
            "docs": "/docs",
            "health": "/health",
        },
    }


@app.get("/health", tags=["Health"])
@limiter.limit("100/minute")
async def health_check(request: Request):
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    return {
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / (1024 * 1024),
        },
    }


@app.get("/ready", tags=["Health"])
@limiter.limit("100/minute")
async def readiness_check(request: Request):
    return {"status": "ready"}


# ------------------------------------------------------------------- routers
app.include_router(orchestrator_router, prefix="/orchestrator", tags=["Orchestrator"])
app.include_router(inventory_router, prefix="/inventory", tags=["Inventory Agent"])
app.include_router(policy_router, prefix="/policy", tags=["Policy Agent"])
app.include_router(analytics_router, prefix="/analytics", tags=["Analytics Agent"])
app.include_router(orders_router, prefix="/orders", tags=["Order Management Agent"])
app.include_router(notification_router, prefix="/notification", tags=["Notification Agent"])


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("ENVIRONMENT", "development") == "development"

    logger.info("uvicorn_starting", host=host, port=port, reload=reload)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=False,  # request_complete log replaces access logs
    )
