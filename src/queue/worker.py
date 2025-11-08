"""
Celery worker for background job processing.
"""
from celery import Celery
from config.settings import settings
from src.telemetry.logger import setup_logging

# Setup logging
setup_logging()

# Create Celery app
celery_app = Celery(
    'ai-code-reviewer',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['src.queue.tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.verification_timeout_seconds,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)