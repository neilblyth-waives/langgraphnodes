"""
Health check endpoints for monitoring and load balancing.

Note: Database and Redis are OPTIONAL for the simple supervisor pattern.
Health checks return "healthy" even without them, with status showing availability.
"""
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from typing import Dict, Optional

from ...core.database import check_db_health, db_available
from ...core.cache import check_redis_health, redis_available

router = APIRouter(prefix="/health", tags=["health"])

# Version identifier - update this when making changes
VERSION = "2.0.0"


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str = VERSION
    checks: Dict[str, bool]
    notes: Optional[str] = None


@router.get("/", response_model=HealthResponse)
async def health_check(response: Response):
    """
    Basic health check endpoint.
    Returns 200 if service is running.
    Database and Redis are optional - system is healthy without them.
    """
    # Check individual components
    db_healthy = await check_db_health()
    redis_healthy = await check_redis_health()

    # Overall status - service is healthy even without DB/Redis
    # They're optional for the supervisor pattern
    overall_status = "healthy"

    # Add note if running without optional services
    notes = None
    if not db_healthy or not redis_healthy:
        missing = []
        if not db_healthy:
            missing.append("database")
        if not redis_healthy:
            missing.append("redis")
        notes = f"Running without optional services: {', '.join(missing)}"

    return HealthResponse(
        status=overall_status,
        version=VERSION,
        checks={
            "database": db_healthy,
            "redis": redis_healthy,
        },
        notes=notes
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
    Returns 200 if service is ready to accept traffic.
    Note: Database and Redis are OPTIONAL - service is ready without them.
    """
    db_healthy = await check_db_health()
    redis_healthy = await check_redis_health()

    # Service is ready even without DB/Redis (they're optional)
    return {
        "status": "ready",
        "database": db_healthy,
        "redis": redis_healthy,
        "notes": "Database and Redis are optional. Service works without them."
    }
