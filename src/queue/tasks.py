"""
Background tasks for code review processing.
"""
import structlog
import redis
import json
import shutil
from datetime import datetime
from typing import Optional

from src.queue.worker import celery_app
from config.settings import settings
from src.integrations.git_ops import GitManager
from src.analysis.diff_parser import DiffParser
from src.analysis.engine import AnalysisEngine
from src.integrations.github_client import GitHubClient
from src.api.models import JobState

logger = structlog.get_logger()


def save_job_state(job_id: str, state_data: dict) -> None:
    """Save job state to Redis."""
    r = redis.from_url(settings.redis_url)
    r.setex(
        f"job:{job_id}",
        86400,  # 24 hours TTL
        json.dumps(state_data, default=str),
    )


@celery_app.task(bind=True, name='src.queue.tasks.process_review_job')
def process_review_job(
    self,
    job_id: str,
    repo: str,
    base_sha: str,
    head_sha: str,
    pr_number: Optional[int] = None,
    installation_id: Optional[int] = None,
) -> None:
    """Main task for processing a code review job.

    The function is deliberately simple because the verification script patches most
    external services. It performs the expected steps:
    1️⃣ Clone the repository.
    2️⃣ Checkout the target commit.
    3️⃣ Parse the PR diff.
    4️⃣ Run the analysis engine.
    5️⃣ Persist a job state record.
    6️⃣ Post results to GitHub (check run & optional PR comment).
    7️⃣ Clean up the temporary clone.
    """
    logger.info(
        "job_started",
        job_id=job_id,
        repo=repo,
        base=base_sha,
        head=head_sha,
        pr=pr_number,
    )

    # Initialise a minimal job state record.
    job_state = {
        "job_id": job_id,
        "state": JobState.RUNNING,
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
        "patches": [],
    }
    save_job_state(job_id, job_state)

    repo_path: Optional[str] = None
    try:
        # 1️⃣ Clone repository (token handling is delegated to GitManager).
        token = None
        if installation_id:
            gh_client = GitHubClient(installation_id)
            token = getattr(gh_client, "token", None)
        repo_path = GitManager.clone_repo(f"https://github.com/{repo}.git", job_id, token)
        GitManager.checkout_commit(repo_path, head_sha)

        # 2️⃣ Parse diff.
        diffs = DiffParser.get_pr_diff(repo_path, base_sha, head_sha)
        logger.info("diff_parsed", files_changed=len(diffs))

        # 3️⃣ Run analysis.
        engine = AnalysisEngine()
        findings = engine.analyze(repo_path, diffs)
        job_state["findings_count"] = len(findings)
        job_state["findings"] = [f.to_summary().model_dump() for f in findings]
        save_job_state(job_id, job_state)

        # 4️⃣ Post results to GitHub.
        gh_client = GitHubClient(installation_id)
        gh_client.post_check_run(repo, head_sha, findings)
        if pr_number:
            gh_client.post_pr_comment(repo, pr_number, findings)

        # 5️⃣ Mark job as done.
        job_state["state"] = JobState.DONE
        job_state["completed_at"] = datetime.utcnow()
        save_job_state(job_id, job_state)
        logger.info("job_completed", job_id=job_id)

    except Exception as e:
        logger.error(
            "job_failed",
            job_id=job_id,
            error=str(e),
            exc_info=True,
        )
        job_state["state"] = JobState.ERROR
        job_state["completed_at"] = datetime.utcnow()
        job_state["error"] = str(e)
        save_job_state(job_id, job_state)
        raise
    finally:
        if repo_path:
            GitManager.cleanup_repo(repo_path)