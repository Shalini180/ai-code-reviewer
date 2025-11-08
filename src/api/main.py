"""
FastAPI application entry point.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import structlog
from contextlib import asynccontextmanager

from config.settings import settings
from src.api.routes import router
from src.telemetry.logger import setup_logging

# Setup structured logging
setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("starting_application", log_level=settings.log_level)

    # Create necessary directories
    import os
    os.makedirs(settings.repos_dir, exist_ok=True)
    os.makedirs(settings.artifacts_dir, exist_ok=True)

    yield

    # Shutdown
    logger.info("shutting_down_application")


# Create FastAPI app
app = FastAPI(
    title="AI Code Reviewer",
    description="Automated code review and fixing agent",
    version="0.1.0",
    lifespan=lifespan
)

# Include routes
app.include_router(router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.log_level == "DEBUG" else None
        }
    )


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "ai-code-reviewer",
        "version": "0.1.0",
        "status": "healthy"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    import redis

    health_status = {
        "api": "healthy",
        "redis": "unknown"
    }

    # Check Redis connection
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        health_status["redis"] = "healthy"
    except Exception as e:
        health_status["redis"] = "unhealthy"
        logger.error("redis_health_check_failed", error=str(e))

    all_healthy = all(v == "healthy" for v in health_status.values())

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content=health_status
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )