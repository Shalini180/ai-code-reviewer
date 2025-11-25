"""
Mock GitHub client for testing without real API calls.
"""
import structlog
from typing import List
from src.api.models import Finding, Severity

logger = structlog.get_logger()


class MockGitHubClient:
    """Mock GitHub client that logs actions instead of making API calls."""

    def __init__(self, installation_id: int = None):
        self.installation_id = installation_id
        self.token = "mock_token_12345"
        logger.info("mock_github_client_initialized", installation_id=installation_id)

    def post_check_run(self, repo_name: str, head_sha: str, findings: List[Finding]):
        """
        Mock posting a GitHub Check Run.
        """
        logger.info(
            "mock_check_run_posted",
            repo=repo_name,
            sha=head_sha,
            findings_count=len(findings),
            errors=sum(1 for f in findings if f.severity == Severity.ERROR),
            warnings=sum(1 for f in findings if f.severity == Severity.WARNING)
        )
        
        # Log first few findings for debugging
        for i, finding in enumerate(findings[:3]):
            logger.info(
                "mock_check_run_finding",
                index=i,
                file=finding.file_path,
                line=finding.line,
                severity=finding.severity.value,
                message=finding.message[:50]
            )

    def post_pr_comment(self, repo_name: str, pr_number: int, findings: List[Finding]):
        """
        Mock posting a PR comment.
        """
        logger.info(
            "mock_pr_comment_posted",
            repo=repo_name,
            pr=pr_number,
            findings_count=len(findings)
        )
        
        # Generate mock comment body
        if not findings:
            body = "## AI Code Review\\n\\n✅ No issues found! Good job."
        else:
            body = f"## AI Code Review\\n\\nFound {len(findings)} potential issues."
        
        logger.info("mock_pr_comment_body", body=body[:100])
