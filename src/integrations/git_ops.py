"""
Git operations for cloning and managing repositories.
"""
import os
import shutil
import structlog
from git import Repo, GitCommandError
from typing import Optional
from config.settings import settings

logger = structlog.get_logger()

class GitManager:
    """Manages git repositories for review jobs."""

    @staticmethod
    def clone_repo(repo_url: str, job_id: str, token: Optional[str] = None) -> str:
        """
        Clone a repository to the data directory.
        
        Args:
            repo_url: URL of the repository to clone
            job_id: Unique job identifier
            token: Optional GitHub token for authentication
            
        Returns:
            str: Path to the cloned repository
        """
        # Construct authenticated URL if token provided
        if token:
            # Insert token into URL: https://token@github.com/owner/repo.git
            if "https://" in repo_url:
                auth_url = repo_url.replace("https://", f"https://x-access-token:{token}@", 1)
            else:
                # Fallback or SSH
                auth_url = repo_url
        else:
            auth_url = repo_url

        # Determine target path
        # We use a simplified naming convention for the directory
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        target_path = settings.get_repo_path(repo_name, job_id)

        # Clean up if exists (shouldn't happen with unique job_ids but good safety)
        if os.path.exists(target_path):
            logger.warning("repo_path_exists_cleaning", path=target_path)
            shutil.rmtree(target_path)

        try:
            logger.info("cloning_repo", url=repo_url, path=target_path)
            Repo.clone_from(auth_url, target_path)
            return target_path
        except GitCommandError as e:
            logger.error("clone_failed", error=str(e))
            raise RuntimeError(f"Failed to clone repository: {str(e)}")

    @staticmethod
    def checkout_commit(repo_path: str, commit_sha: str):
        """
        Checkout a specific commit.
        
        Args:
            repo_path: Path to the repository
            commit_sha: SHA of the commit to checkout
        """
        try:
            repo = Repo(repo_path)
            repo.git.checkout(commit_sha)
            logger.info("checked_out_commit", path=repo_path, sha=commit_sha)
        except GitCommandError as e:
            logger.error("checkout_failed", error=str(e))
            raise RuntimeError(f"Failed to checkout commit {commit_sha}: {str(e)}")

    @staticmethod
    def cleanup_repo(repo_path: str):
        """
        Remove the repository directory.
        
        Args:
            repo_path: Path to the repository
        """
        if os.path.exists(repo_path):
            try:
                shutil.rmtree(repo_path)
                logger.info("repo_cleaned_up", path=repo_path)
            except Exception as e:
                logger.error("cleanup_failed", path=repo_path, error=str(e))
