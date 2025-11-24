"""
Telemetry logger setup using structlog.
Provides a simple `setup_logging` function that configures structured logging.
"""
import structlog
import logging
from config.settings import settings


def setup_logging() -> None:
    """Configure structlog and standard logging based on settings.

    - Log level from `settings.log_level`.
    - Console output with pretty formatting.
    - JSON output can be added later if needed.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler()],
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )