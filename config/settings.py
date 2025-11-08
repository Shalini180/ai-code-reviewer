"""
Configuration management using Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic API
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-20250514"

    # GitHub
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_webhook_secret: str = ""
    github_token: str = ""  # Optional, for development

    # Application
    log_level: str = "INFO"
    max_repo_size_mb: int = 500
    max_diff_loc: int = 1000
    worker_concurrency: int = 2

    # Policy
    auto_commit_enabled: bool = False
    auto_commit_risk_threshold: float = 0.25
    max_patch_loc: int = 30
    max_files_per_patch: int = 3
    denylist_paths: str = "auth/**,secrets/**,config/prod/**"

    # Verification
    enable_verification: bool = True
    verification_timeout_seconds: int = 300

    # Directories
    data_dir: str = "data"
    repos_dir: str = "data/repos"
    artifacts_dir: str = "data/artifacts"

    @property
    def denylist_patterns(self) -> List[str]:
        """Parse denylist paths into list."""
        return [p.strip() for p in self.denylist_paths.split(',') if p.strip()]

    def get_repo_path(self, repo_name: str, job_id: str) -> str:
        """Get path for cloned repository."""
        # Sanitize repo name for filesystem
        safe_name = repo_name.replace('/', '_')
        return f"{self.repos_dir}/{job_id}_{safe_name}"

    def get_artifacts_path(self, job_id: str) -> str:
        """Get path for job artifacts."""
        return f"{self.artifacts_dir}/{job_id}"


# Global settings instance
settings = Settings()