"""
Observability Module - OpenTelemetry Integration
================================================
Provides structured logging, distributed tracing, and metrics collection
for the Level 3 Modular Monolith Agent Swarm.
"""

import os
import logging
import structlog
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


def configure_structured_logging(log_level: str = "INFO"):
    """
    Configure structured logging with structlog.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level_num = getattr(logging, log_level.upper(), logging.INFO)
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level_num),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logging.basicConfig(
        format="%(message)s",
        level=log_level_num,
    )


def setup_opentelemetry(
    service_name: str = "enterprise-agents-platform",
    otlp_endpoint: Optional[str] = None,
    enable_tracing: bool = True,
    enable_metrics: bool = True
) -> tuple[Optional[trace.Tracer], Optional[metrics.Meter]]:
    """
    Set up OpenTelemetry for distributed tracing and metrics.
    
    Args:
        service_name: Name of the service for identification
        otlp_endpoint: OTLP collector endpoint (e.g., http://localhost:4318)
        enable_tracing: Enable distributed tracing
        enable_metrics: Enable metrics collection
    
    Returns:
        Tuple of (tracer, meter) if enabled, (None, None) otherwise
    """
    if not otlp_endpoint:
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    
    if not otlp_endpoint:
        logger = structlog.get_logger()
        logger.info("OpenTelemetry not configured (no OTLP endpoint)")
        return None, None
    
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("ENVIRONMENT", "development")
    })
    
    tracer = None
    meter = None
    
    if enable_tracing:
        trace_provider = TracerProvider(resource=resource)
        
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=f"{otlp_endpoint}/v1/traces"
        )
        trace_provider.add_span_processor(
            BatchSpanProcessor(otlp_trace_exporter)
        )
        
        trace.set_tracer_provider(trace_provider)
        tracer = trace.get_tracer(__name__)
        
        FastAPIInstrumentor().instrument()
    
    if enable_metrics:
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics")
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(meter_provider)
        meter = metrics.get_meter(__name__)
    
    logger = structlog.get_logger()
    logger.info(
        "OpenTelemetry configured",
        endpoint=otlp_endpoint,
        tracing=enable_tracing,
        metrics=enable_metrics
    )
    
    return tracer, meter


def create_agent_metrics(meter: metrics.Meter):
    """
    Create custom metrics for agent monitoring.
    
    Args:
        meter: OpenTelemetry meter instance
    
    Returns:
        Dictionary of metric instruments
    """
    return {
        "agent_request_counter": meter.create_counter(
            name="agent.requests.total",
            description="Total number of agent requests",
            unit="1"
        ),
        "agent_request_duration": meter.create_histogram(
            name="agent.request.duration",
            description="Agent request duration in seconds",
            unit="s"
        ),
        "agent_error_counter": meter.create_counter(
            name="agent.errors.total",
            description="Total number of agent errors",
            unit="1"
        ),
        "mcp_tool_counter": meter.create_counter(
            name="mcp.tool.calls.total",
            description="Total number of MCP tool calls",
            unit="1"
        ),
        "a2a_call_counter": meter.create_counter(
            name="a2a.calls.total",
            description="Total number of A2A protocol calls",
            unit="1"
        ),
        "session_active_gauge": meter.create_up_down_counter(
            name="sessions.active",
            description="Number of active sessions",
            unit="1"
        )
    }


class AgentMetrics:
    """
    Context manager for tracking agent execution metrics.
    """
    
    def __init__(self, metrics_dict: dict, agent_name: str):
        self.metrics = metrics_dict
        self.agent_name = agent_name
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.metrics["agent_request_counter"].add(
            1, {"agent": self.agent_name}
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time
        
        self.metrics["agent_request_duration"].record(
            duration, {"agent": self.agent_name}
        )
        
        if exc_type is not None:
            self.metrics["agent_error_counter"].add(
                1, {"agent": self.agent_name, "error_type": exc_type.__name__}
            )


logger = structlog.get_logger()
