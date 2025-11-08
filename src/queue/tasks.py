"""
Background tasks for code review processing.
"""
import structlog
import redis
import json
from datetime import datetime
from typing import Optional

from src.queue.worker import celery_app
from config.settings import settings

logger = structlog.get_logger()


def save_job_state(job_id: str, state_data: dict):
    """Save job state to Redis."""
    r = redis.from_url(settings.redis_url)
    r.setex(
        f"job:{job_id}",
        86400,  # 24 hours TTL
        json.dumps(state_data, default=str)
    )


@celery_app.task(bind=True, name='src.queue.tasks.process_review_job')
def process_review_job(
        self,
        job_id: str,
        repo: str,
        base_sha: str,
        head_sha: str,
        pr_number: Optional[int] = None
):
    """
    Main task for processing a code review job.

    This orchestrates the entire pipeline:
    1. Checkout repo and parse diff
    2. Run static analysis
    3. Generate patches
    4. Verify patches
    5. Post results to PR
    """
    logger.info(
        "job_started",
        job_id=job_id,
        repo=repo,
        base=base_sha,
        head=head_sha,
        pr=pr_number
    )

    # Initialize job state
    job_state = {
        "job_id": job_id,
        "state": "running",
        "created_at": datetime.utcnow(),
        "started_at": datetime.utcnow(),
        "repo": repo,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "pr_number": pr_number,
        "findings_count": 0,
        "patches_generated": 0,
        "patches_applied": 0,
        "findings": [],
        "patches": []
    }

    save_job_state(job_id, job_state)

    try:
        # Step 1: Checkout repo and parse diff
        # (We'll implement these in the next steps)
        logger.info("step_1_checkout_and_diff", job_id=job_id)

        # Step 2: Run static analysis
        logger.info("step_2_static_analysis", job_id=job_id)

        # Step 3: Generate patches
        logger.info("step_3_generate_patches", job_id=job_id)

        # Step 4: Verify patches (if enabled)
        if settings.enable_verification:
            logger.info("step_4_verify_patches", job_id=job_id)

        # Step 5: Post results
        logger.info("step_5_post_results", job_id=job_id)

        # Update job state to done
        job_state["state"] = "done"
        job_state["completed_at"] = datetime.utcnow()
        save_job_state(job_id, job_state)

        logger.info("job_completed", job_id=job_id)

        return {
            "job_id": job_id,
            "status": "success",
            "findings_count": job_state["findings_count"],
            "patches_generated": job_state["patches_generated"]
        }

    except Exception as e:
        logger.error(
            "job_failed",
            job_id=job_id,
            error=str(e),
            exc_info=True
        )

        # Update job state to error
        job_state["state"] = "error"
        job_state["completed_at"] = datetime.utcnow()
        job_state["error"] = str(e)
        save_job_state(job_id, job_state)

        # Re-raise to mark Celery task as failed
        raise