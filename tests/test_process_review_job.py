"""
Unit tests for process_review_job task.
Tests the full workflow with all external services mocked.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from src.queue.tasks import process_review_job
from src.api.models import Finding, Severity, JobState
from src.analysis.diff_parser import FileDiff


class TestProcessReviewJob:
    """Test the main review job processing task."""
    
    @patch('src.queue.tasks.redis.from_url')
    @patch('src.queue.tasks.GitHubClient')
    @patch('src.queue.tasks.AnalysisEngine')
    @patch('src.queue.tasks.DiffParser')
    @patch('src.queue.tasks.GitManager')
    def test_process_review_job_success(
        self,
        mock_git_manager,
        mock_diff_parser,
        mock_analysis_engine_class,
        mock_github_client_class,
        mock_redis
    ):
        """
        Test successful end-to-end review job with realistic webhook payload.
        
        Simulates:
        - GitHub PR webhook triggering a review
        - Cloning repo, parsing diff, running analysis
        - Posting results back to GitHub
        """
        # ========== SETUP MOCKS ==========
        
        # Mock Redis for state persistence
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        
        # Mock GitManager - no real git operations
        mock_git_manager.clone_repo.return_value = "/tmp/test-repo-path"
        mock_git_manager.checkout_commit.return_value = None
        mock_git_manager.cleanup_repo.return_value = None
        
        # Mock DiffParser - return realistic file changes
        mock_diff_parser.get_pr_diff.return_value = [
            FileDiff(
                file_path="src/api/auth.py",
                change_type="M",
                added_lines=[
                    (45, "import pickle"),
                    (46, "def load_session(data):"),
                    (47, "    return pickle.loads(data)")
                ],
                removed_lines=[
                    (45, "def load_session(data):"),
                    (46, "    return json.loads(data)")
                ],
                new_content="import pickle\n\ndef load_session(data):\n    return pickle.loads(data)"
            ),
            FileDiff(
                file_path="src/utils/validation.py",
                change_type="M",
                added_lines=[
                    (12, "user_input = request.args.get('name')"),
                    (13, "os.system(f'echo {user_input}')")
                ],
                new_content="user_input = request.args.get('name')\nos.system(f'echo {user_input}')"
            )
        ]
        
        # Mock AnalysisEngine - return realistic security findings
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = [
            Finding(
                tool_name="bandit",
                rule_id="B301",
                severity=Severity.ERROR,
                file_path="src/api/auth.py",
                line=47,
                message="Use of pickle detected - potential code execution vulnerability",
                suggestion="Use json.loads() or a safer serialization method"
            ),
            Finding(
                tool_name="semgrep",
                rule_id="python.lang.security.audit.dangerous-system-call",
                severity=Severity.ERROR,
                file_path="src/utils/validation.py",
                line=13,
                message="Direct use of os.system with user input - command injection risk",
                suggestion="Use subprocess.run() with shell=False and proper argument passing"
            ),
            Finding(
                tool_name="claude-ai",
                rule_id="ai-security-review",
                severity=Severity.WARNING,
                file_path="src/api/auth.py",
                line=47,
                message="Pickle deserialization is inherently unsafe. Consider using safer alternatives.",
                confidence=0.9
            )
        ]
        mock_analysis_engine_class.return_value = mock_engine
        
        # Mock GitHubClient - no real API calls
        # The client is instantiated twice in the task:
        # 1. To get the token for cloning
        # 2. To post results
        mock_gh_client = MagicMock()
        mock_gh_client.token = "ghs_mock_token_123"  # Mock GitHub token
        mock_gh_client.post_check_run.return_value = None
        mock_gh_client.post_pr_comment.return_value = None
        # Return the same mock instance every time GitHubClient is instantiated
        mock_github_client_class.return_value = mock_gh_client
        
        # ========== EXECUTE TEST ==========
        
        # Realistic webhook-derived job payload
        job_id = "webhook-pr-42-abc123"
        repo = "octocat/secure-app"
        base_sha = "abc123def456"  # Base commit (main branch)
        head_sha = "def456abc789"  # Head commit (PR branch)
        pr_number = 42
        installation_id = 12345  # GitHub App installation ID
        
        # Call the task (with None for self due to bind=True)
        result = process_review_job(
            None,  # self parameter from Celery bind=True
            job_id=job_id,
            repo=repo,
            base_sha=base_sha,
            head_sha=head_sha,
            pr_number=pr_number,
            installation_id=installation_id
        )
        
        # ========== ASSERTIONS ==========
        
        # Verify GitManager was called correctly
        mock_git_manager.clone_repo.assert_called_once_with(
            f"https://github.com/{repo}.git",
            job_id,
            "ghs_mock_token_123"  # Token from the first GitHubClient instance
        )
        mock_git_manager.checkout_commit.assert_called_once_with(
            "/tmp/test-repo-path",
            head_sha
        )
        
        # Verify DiffParser was called
        mock_diff_parser.get_pr_diff.assert_called_once_with(
            "/tmp/test-repo-path",
            base_sha,
            head_sha
        )
        
        # Verify AnalysisEngine was instantiated and analyze was called
        mock_analysis_engine_class.assert_called_once()
        mock_engine.analyze.assert_called_once()
        call_args = mock_engine.analyze.call_args[0]
        assert call_args[0] == "/tmp/test-repo-path"
        assert len(call_args[1]) == 2  # 2 file diffs
        
        # Verify GitHub client was called to post results
        assert mock_github_client_class.call_count == 2  # Once for token, once for posting
        mock_gh_client.post_check_run.assert_called_once()
        mock_gh_client.post_pr_comment.assert_called_once()
        
        # Verify check run was called with correct parameters
        check_run_call = mock_gh_client.post_check_run.call_args
        assert check_run_call[0][0] == repo
        assert check_run_call[0][1] == head_sha
        findings_posted = check_run_call[0][2]
        assert len(findings_posted) == 3
        
        # Verify PR comment was posted
        pr_comment_call = mock_gh_client.post_pr_comment.call_args
        assert pr_comment_call[0][0] == repo
        assert pr_comment_call[0][1] == pr_number
        
        # Verify Redis state was saved (at least twice: RUNNING and DONE)
        assert mock_redis_client.setex.call_count >= 2
        
        # Verify cleanup was called
        mock_git_manager.cleanup_repo.assert_called_once_with("/tmp/test-repo-path")
        
        # Task should complete without raising an exception
        # (If we got here, the task succeeded)
        
    @patch('src.queue.tasks.redis.from_url')
    @patch('src.queue.tasks.GitHubClient')
    @patch('src.queue.tasks.AnalysisEngine')
    @patch('src.queue.tasks.DiffParser')
    @patch('src.queue.tasks.GitManager')
    def test_process_review_job_no_findings(
        self,
        mock_git_manager,
        mock_diff_parser,
        mock_analysis_engine_class,
        mock_github_client_class,
        mock_redis
    ):
        """
        Test review job with clean code (no findings).
        """
        # Setup mocks
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        
        mock_git_manager.clone_repo.return_value = "/tmp/clean-repo"
        mock_git_manager.checkout_commit.return_value = None
        mock_git_manager.cleanup_repo.return_value = None
        
        # Return minimal diff
        mock_diff_parser.get_pr_diff.return_value = [
            FileDiff(
                file_path="README.md",
                change_type="M",
                added_lines=[(1, "# Updated README")],
                new_content="# Updated README"
            )
        ]
        
        # No findings (clean code!)
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = []
        mock_analysis_engine_class.return_value = mock_engine
        
        mock_gh_client = MagicMock()
        mock_github_client_class.return_value = mock_gh_client
        
        # Execute
        process_review_job(
            None,
            job_id="clean-job-123",
            repo="octocat/clean-repo",
            base_sha="abc",
            head_sha="def",
            pr_number=1
        )
        
        # Verify success with no findings
        assert mock_engine.analyze.called
        mock_gh_client.post_check_run.assert_called_once()
        
        # Verify findings count is 0
        check_run_call = mock_gh_client.post_check_run.call_args
        findings = check_run_call[0][2]
        assert len(findings) == 0
        
        mock_git_manager.cleanup_repo.assert_called_once()
    
    @patch('src.queue.tasks.redis.from_url')
    @patch('src.queue.tasks.GitHubClient')
    @patch('src.queue.tasks.AnalysisEngine')
    @patch('src.queue.tasks.DiffParser')
    @patch('src.queue.tasks.GitManager')
    def test_process_review_job_handles_errors(
        self,
        mock_git_manager,
        mock_diff_parser,
        mock_analysis_engine_class,
        mock_github_client_class,
        mock_redis
    ):
        """
        Test that errors are caught and logged properly.
        """
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        
        # Make clone fail
        mock_git_manager.clone_repo.side_effect = RuntimeError("Clone failed: repository not found")
        
        # Execute and expect exception
        with pytest.raises(RuntimeError) as exc_info:
            process_review_job(
                None,
                job_id="error-job",
                repo="octocat/nonexistent",
                base_sha="abc",
                head_sha="def"
            )
        
        assert "Clone failed" in str(exc_info.value)
        
        # Verify error state was saved to Redis
        assert mock_redis_client.setex.called
        # The last call should contain error information
        last_call_args = mock_redis_client.setex.call_args_list[-1]
        state_json = last_call_args[0][2]
        assert "Clone failed" in state_json or "ERROR" in state_json.upper()
