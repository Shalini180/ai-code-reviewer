"""
GitHub API client for posting results.
"""
import structlog
from typing import List
from github import Github, GithubIntegration
from config.settings import settings
from src.api.models import Finding, Severity

logger = structlog.get_logger()

class GitHubClient:
    """Client for GitHub API interactions."""

    def __init__(self, installation_id: int = None):
        # Authenticate as App
        if settings.github_app_id and settings.github_app_private_key:
            self.integration = GithubIntegration(
                settings.github_app_id,
                settings.github_app_private_key
            )
            if installation_id:
                self.token = self.integration.get_access_token(installation_id).token
                self.gh = Github(self.token)
            else:
                # Fallback or just for jwt generation
                self.gh = Github()
        elif settings.github_token:
            # Dev mode
            self.gh = Github(settings.github_token)
        else:
            logger.warning("no_github_credentials")
            self.gh = None

    def post_check_run(self, repo_name: str, head_sha: str, findings: List[Finding]):
        """
        Create a GitHub Check Run with annotations.
        """
        if not self.gh:
            logger.warning("skipping_github_post_no_client")
            return

        try:
            repo = self.gh.get_repo(repo_name)
            
            # Prepare annotations
            annotations = []
            for f in findings:
                # GitHub API limit is 50 annotations per request
                # We'll just take the top 50 for now
                if len(annotations) >= 50:
                    break
                    
                annotations.append({
                    "path": f.file_path,
                    "start_line": f.line,
                    "end_line": f.end_line or f.line,
                    "annotation_level": "failure" if f.severity == Severity.ERROR else "warning",
                    "message": f.message,
                    "title": f.rule_id
                })

            # Determine conclusion
            conclusion = "success"
            if any(f.severity == Severity.ERROR for f in findings):
                conclusion = "failure"
            elif findings:
                conclusion = "neutral"

            repo.create_check_run(
                name="AI Code Reviewer",
                head_sha=head_sha,
                status="completed",
                conclusion=conclusion,
                output={
                    "title": f"Found {len(findings)} issues",
                    "summary": "AI Code Review completed.",
                    "annotations": annotations
                }
            )
            logger.info("check_run_posted", repo=repo_name, sha=head_sha)
            
        except Exception as e:
            logger.error("github_post_failed", error=str(e))

    def post_pr_comment(self, repo_name: str, pr_number: int, findings: List[Finding]):
        """
        Post a summary comment on the PR.
        """
        if not self.gh:
            return

        try:
            repo = self.gh.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            if not findings:
                body = "## AI Code Review\n\n✅ No issues found! Good job."
            else:
                body = f"## AI Code Review\n\nFound {len(findings)} potential issues.\n\n"
                
                # Group by severity
                errors = [f for f in findings if f.severity == Severity.ERROR]
                warnings = [f for f in findings if f.severity == Severity.WARNING]
                
                if errors:
                    body += "### 🚨 Critical Issues\n"
                    for f in errors:
                        body += f"- **{f.file_path}:{f.line}**: {f.message}\n"
                
                if warnings:
                    body += "\n### ⚠️ Warnings\n"
                    for f in warnings[:10]: # Limit to 10
                        body += f"- **{f.file_path}:{f.line}**: {f.message}\n"
                        
                if len(warnings) > 10:
                    body += f"\n...and {len(warnings) - 10} more warnings."

            pr.create_issue_comment(body)
            logger.info("pr_comment_posted", repo=repo_name, pr=pr_number)
            
        except Exception as e:
            logger.error("pr_comment_failed", error=str(e))
