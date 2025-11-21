import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from shared.observability import (
    configure_structured_logging,
    setup_opentelemetry,
    create_agent_metrics,
    logger
)

from orchestrator.routes import router as orchestrator_router
from agents.inventory.routes import router as inventory_router
from agents.policy.routes import router as policy_router
from agents.notification.routes import router as notification_router
from agents.analytics.routes import router as analytics_router
from agents.orders.routes import router as orders_router

load_dotenv()

configure_structured_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))

limiter = Limiter(key_func=get_remote_address)

tracer: Optional[object] = None
meter: Optional[object] = None
metrics: Optional[dict] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    logger.info("Starting Enterprise Agents Platform...")
    
    global tracer, meter, metrics
    if os.getenv("ENABLE_OTEL", "false").lower() == "true":
        tracer, meter = setup_opentelemetry(
            service_name=os.getenv("OTEL_SERVICE_NAME", "enterprise-agents-platform"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        )
        
        if meter:
            metrics = create_agent_metrics(meter)
            logger.info("Metrics collection enabled")
    
    logger.info(
        "Configuration loaded",
        base_url=os.getenv("BASE_URL", "http://localhost:8000"),
        session_persistence=os.getenv("ENABLE_SESSION_PERSISTENCE", "true"),
        memory=os.getenv("ENABLE_MEMORY", "true"),
        hitl=os.getenv("ENABLE_HITL", "true")
    )
    
    logger.info(
        "Platform initialized",
        agents=["orchestrator", "inventory", "policy", "analytics", "orders", "notification"],
        architecture="modular_monolith",
        protocol="a2a"
    )
    
    yield
    
    logger.info("Shutting down Enterprise Agents Platform...")
    
    logger.info("Shutdown complete")

app = FastAPI(
    title="Enterprise Agents Platform",
    description=(
        "A Level 3 Modular Monolith Agent Swarm built with Google ADK. "
        "Provides enterprise business workflow automation with six specialized agents: "
        "Orchestrator (with Memory), Inventory Agent, Policy Agent, Analytics Agent, "
        "Order Management Agent, and Notification Agent (with HITL workflow). "
        "All agents support session persistence and communicate via A2A Protocol."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for structured error responses.
    """
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "path": request.url.path
        }
    )


@app.get("/", tags=["Health"])
@limiter.limit("100/minute")
async def root(request: Request):
    """
    Root endpoint - Platform status overview.
    """
    return {
        "status": "online",
        "platform": "Enterprise Agents Platform",
        "architecture": "modular_monolith",
        "version": "1.0.0",
        "agents": {
            "orchestrator": {
                "status": "active",
                "role": "coordinator",
                "model": "gemini-1.5-flash-lite",
                "capabilities": ["memory", "a2a_client", "context_aggregation"]
            },
            "inventory": {
                "status": "active",
                "role": "worker",
                "model": "gemini-1.5-flash-lite",
                "capabilities": ["session_persistence", "mcp_database", "read_only_sql"]
            },
            "policy": {
                "status": "active",
                "role": "worker",
                "model": "gemini-1.5-flash-lite",
                "capabilities": ["session_persistence", "mcp_rag", "vector_search"]
            },
            "analytics": {
                "status": "active",
                "role": "worker",
                "model": "gemini-1.5-flash-lite",
                "capabilities": ["session_persistence", "trend_analysis", "forecasting", "reporting"]
            },
            "orders": {
                "status": "active",
                "role": "worker",
                "model": "gemini-1.5-flash-lite",
                "capabilities": ["session_persistence", "purchase_orders", "supplier_management", "procurement"]
            },
            "notification": {
                "status": "active",
                "role": "worker",
                "model": "gemini-1.5-flash-lite",
                "capabilities": ["session_persistence", "mcp_smtp", "hitl_workflow"]
            }
        },
        "protocols": ["a2a", "mcp"],
        "endpoints": {
            "orchestrator": "/orchestrator",
            "inventory": "/inventory",
            "policy": "/policy",
            "analytics": "/analytics",
            "orders": "/orders",
            "notification": "/notification",
            "docs": "/docs",
            "health": "/health"
        }
    }


@app.get("/health", tags=["Health"])
@limiter.limit("100/minute")
async def health_check(request: Request):
    """
    Kubernetes-style health check endpoint.
    """
    import psutil
    
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    return {
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / (1024 * 1024)
        }
    }


@app.get("/ready", tags=["Health"])
@limiter.limit("100/minute")
async def readiness_check(request: Request):
    """
    Kubernetes readiness probe - checks if service can accept traffic.
    """
    return {"status": "ready"}

app.include_router(
    orchestrator_router,
    prefix="/orchestrator",
    tags=["Orchestrator"]
)

app.include_router(
    inventory_router,
    prefix="/inventory",
    tags=["Inventory Agent"]
)

app.include_router(
    policy_router,
    prefix="/policy",
    tags=["Policy Agent"]
)

app.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["Analytics Agent"]
)

app.include_router(
    orders_router,
    prefix="/orders",
    tags=["Order Management Agent"]
)

app.include_router(
    notification_router,
    prefix="/notification",
    tags=["Notification Agent"]
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("ENVIRONMENT", "development") == "development"
    
    logger.info(
        "Starting Uvicorn server",
        host=host,
        port=port,
        reload=reload
    )
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=True
    )