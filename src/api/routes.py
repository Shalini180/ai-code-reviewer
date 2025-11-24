"""
API routes for the Code Reviewer.
"""
import structlog
import uuid
import redis
import json
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional

from src.api.models import (
    ReviewRequest, ReviewResponse, JobStatusResponse, 
    WebhookPayload, JobState
)
from src.queue.tasks import process_review_job
from config.settings import settings

logger = structlog.get_logger()
router = APIRouter()


@router.post("/review", response_model=ReviewResponse)
async def create_review_job(request: ReviewRequest):
    """
    Manually trigger a review job.
    """
    job_id = str(uuid.uuid4())
    
    logger.info(
        "manual_review_requested",
        job_id=job_id,
        repo=request.repo
    )

    # Enqueue task
    process_review_job.delay(
        job_id=job_id,
        repo=request.repo,
        base_sha=request.base,
        head_sha=request.head,
        pr_number=request.pr
    )

    return ReviewResponse(
        job_id=job_id,
        state=JobState.QUEUED,
        message="Job queued for processing"
    )


@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """
    Handle GitHub webhooks.
    """
    # TODO: Verify signature using settings.github_webhook_secret
    
    payload = await request.json()
    
    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize", "reopened"]:
            pr = payload.get("pull_request", {})
            repo = payload.get("repository", {})
            installation = payload.get("installation", {})
            
            job_id = str(uuid.uuid4())
            
            repo_full_name = repo.get("full_name")
            head_sha = pr.get("head", {}).get("sha")
            base_sha = pr.get("base", {}).get("sha")
            pr_number = pr.get("number")
            installation_id = installation.get("id")
            
            if not (repo_full_name and head_sha and base_sha):
                logger.warning("invalid_webhook_payload", action=action)
                return {"status": "ignored", "reason": "missing data"}

            logger.info(
                "webhook_pr_event",
                job_id=job_id,
                repo=repo_full_name,
                action=action
            )

            process_review_job.delay(
                job_id=job_id,
                repo=repo_full_name,
                base_sha=base_sha,
                head_sha=head_sha,
                pr_number=pr_number,
                installation_id=installation_id
            )
            
            return {"status": "accepted", "job_id": job_id}
            
    return {"status": "ignored", "reason": "event not handled"}


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a review job.
    """
    r = redis.from_url(settings.redis_url)
    data = r.get(f"job:{job_id}")
    
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job_data = json.loads(data)
    return JobStatusResponse(**job_data)