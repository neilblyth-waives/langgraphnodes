"""
Health check endpoints for monitoring and load balancing.
"""
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from typing import Dict

from ...core.database import check_db_health
from ...core.cache import check_redis_health

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str = "0.1.0"
    checks: Dict[str, bool]


@router.get("/", response_model=HealthResponse)
async def health_check(response: Response):
    """
    Basic health check endpoint.
    Returns 200 if service is running, with detailed component health.
    """
    # Check individual components
    db_healthy = await check_db_health()
    redis_healthy = await check_redis_health()

    # Overall status
    all_healthy = db_healthy and redis_healthy
    overall_status = "healthy" if all_healthy else "degraded"

    # Set HTTP status code
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        checks={
            "database": db_healthy,
            "redis": redis_healthy,
        }
    )


@router.get("/liveness")
async def liveness():
    """
    Kubernetes liveness probe.
    Returns 200 if the service is alive (can handle basic operations).
    """
    return {"status": "alive"}


@router.get("/readiness")
async def readiness(response: Response):
    """
    Kubernetes readiness probe.
    Returns 200 only if service is ready to accept traffic (all dependencies healthy).
    """
    db_healthy = await check_db_health()
    redis_healthy = await check_redis_health()

    if not (db_healthy and redis_healthy):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "database": db_healthy,
            "redis": redis_healthy,
        }

    return {
        "status": "ready",
        "database": db_healthy,
        "redis": redis_healthy,
    }
