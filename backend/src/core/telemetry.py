"""
Telemetry and observability setup with structured logging.
"""
import sys
import logging
from typing import Any, Dict
from contextvars import ContextVar
import structlog
from prometheus_client import Counter, Histogram, Gauge

from .config import settings

# Context var for correlation IDs
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(correlation_id)


def setup_logging() -> None:
    """Configure structured logging with structlog."""

    # Processors for structlog
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_development:
        # Pretty console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]
    else:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )


# Get logger instance
def get_logger(name: str = __name__) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Prometheus Metrics

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"]
)

# Agent metrics
agent_executions_total = Counter(
    "agent_executions_total",
    "Total agent executions",
    ["agent_name", "status"]
)

agent_execution_duration_seconds = Histogram(
    "agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["agent_name"]
)

agent_tool_calls_total = Counter(
    "agent_tool_calls_total",
    "Total agent tool calls",
    ["agent_name", "tool_name"]
)

# LLM metrics
llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM API requests",
    ["provider", "model"]
)

llm_tokens_used = Counter(
    "llm_tokens_used",
    "Total LLM tokens consumed",
    ["provider", "model", "type"]  # type: input/output
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"]
)

# Database metrics
db_queries_total = Counter(
    "db_queries_total",
    "Total database queries",
    ["operation", "table"]
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"]
)

# Cache metrics
cache_operations_total = Counter(
    "cache_operations_total",
    "Total cache operations",
    ["operation", "status"]  # operation: get/set/delete, status: hit/miss/success
)

# Session metrics
active_sessions_gauge = Gauge(
    "active_sessions",
    "Number of active sessions"
)

# Memory metrics
memory_retrievals_total = Counter(
    "memory_retrievals_total",
    "Total memory retrievals",
    ["agent_name"]
)

memory_storage_total = Counter(
    "memory_storage_total",
    "Total learnings stored",
    ["agent_name", "learning_type"]
)


def log_agent_execution(
    agent_name: str,
    duration_seconds: float,
    status: str,
    tools_used: list = None,
    error: str = None
) -> None:
    """Log agent execution metrics and details."""
    logger = get_logger("agent")

    agent_executions_total.labels(agent_name=agent_name, status=status).inc()
    agent_execution_duration_seconds.labels(agent_name=agent_name).observe(duration_seconds)

    if tools_used:
        for tool in tools_used:
            agent_tool_calls_total.labels(agent_name=agent_name, tool_name=tool).inc()

    log_data = {
        # Removed "event" key to avoid conflict with first positional parameter
        "agent_name": agent_name,
        "duration_seconds": duration_seconds,
        "status": status,
        "tools_used": tools_used or [],
        "correlation_id": get_correlation_id(),
    }

    if error:
        log_data["error_message"] = error  # Changed from "error" to "error_message"
        logger.error("Agent execution failed", **log_data)
    else:
        logger.info("Agent execution completed", **log_data)


def log_llm_request(
    provider: str,
    model: str,
    duration_seconds: float,
    input_tokens: int,
    output_tokens: int,
    error: str = None
) -> None:
    """Log LLM request metrics."""
    logger = get_logger("llm")

    llm_requests_total.labels(provider=provider, model=model).inc()
    llm_tokens_used.labels(provider=provider, model=model, type="input").inc(input_tokens)
    llm_tokens_used.labels(provider=provider, model=model, type="output").inc(output_tokens)
    llm_request_duration_seconds.labels(provider=provider, model=model).observe(duration_seconds)

    log_data = {
        "event": "llm_request",
        "provider": provider,
        "model": model,
        "duration_seconds": duration_seconds,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "correlation_id": get_correlation_id(),
    }

    if error:
        log_data["error"] = error
        logger.error("LLM request failed", **log_data)
    else:
        logger.info("LLM request completed", **log_data)


def log_db_query(
    operation: str,
    table: str,
    duration_seconds: float,
    error: str = None
) -> None:
    """Log database query metrics."""
    logger = get_logger("database")

    db_queries_total.labels(operation=operation, table=table).inc()
    db_query_duration_seconds.labels(operation=operation, table=table).observe(duration_seconds)

    log_data = {
        "operation": operation,
        "table": table,
        "duration_seconds": duration_seconds,
        "correlation_id": get_correlation_id(),
    }

    if error:
        log_data["error_message"] = error
        logger.error("Database query failed", **log_data)
    else:
        logger.debug("Database query completed", **log_data)


# Initialize logging on import
setup_logging()
