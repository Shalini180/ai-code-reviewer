"""
Integration tests for the analysis pipeline.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from src.analysis.engine import AnalysisEngine
from src.analysis.diff_parser import FileDiff
from src.api.models import Finding, Severity


class TestAnalysisEngine:
    """Test AnalysisEngine integration."""
    
    @patch('src.analysis.engine.LLMReviewer')
    @patch('src.analysis.engine.StaticAnalyzer')
    def test_analyze_success(self, mock_static, mock_llm_class):
        """Test full analysis pipeline."""
        # Setup mocks
        mock_static.run_semgrep.return_value = [
            Finding(
                tool_name="semgrep",
                rule_id="test-rule",
                severity=Severity.WARNING,
                file_path="main.py",
                line=10,
                message="Test finding"
            )
        ]
        mock_static.run_bandit.return_value = []
        
        mock_llm = MagicMock()
        mock_llm.review_diff.return_value = [
            Finding(
                tool_name="claude-ai",
                rule_id="ai-review",
                severity=Severity.INFO,
                file_path="main.py",
                line=15,
                message="Consider refactoring"
            )
        ]
        mock_llm_class.return_value = mock_llm
        
        # Create test data
        diffs = [
            FileDiff(
                file_path="main.py",
                change_type="M",
                added_lines=[(10, "import os"), (15, "def foo(): pass")],
                new_content="import os\n\ndef foo(): pass"
            )
        ]
        
        # Test
        engine = AnalysisEngine()
        findings = engine.analyze("/tmp/repo", diffs)
        
        # Verify
        assert len(findings) == 2  # 1 static + 1 LLM
        assert findings[0].tool_name == "semgrep"
        assert findings[1].tool_name == "claude-ai"
        
        # Verify static analyzer was called
        mock_static.run_semgrep.assert_called_once_with("/tmp/repo")
        mock_static.run_bandit.assert_called_once_with("/tmp/repo")
        
        # Verify LLM reviewer was called with filtered static findings
        mock_llm.review_diff.assert_called_once()
    
    @patch('src.analysis.engine.LLMReviewer')
    @patch('src.analysis.engine.StaticAnalyzer')
    def test_filter_relevant_findings(self, mock_static, mock_llm_class):
        """Test that findings are filtered to changed lines."""
        # Static finding on a changed line
        relevant_finding = Finding(
            tool_name="semgrep",
            rule_id="test-rule",
            severity=Severity.WARNING,
            file_path="main.py",
            line=10,  # This line was added
            message="Relevant finding"
        )
        
        # Static finding on an unchanged line
        irrelevant_finding = Finding(
            tool_name="semgrep",
            rule_id="test-rule-2",
            severity=Severity.WARNING,
            file_path="main.py",
            line=5,  # This line was NOT added
            message="Irrelevant finding"
        )
        
        mock_static.run_semgrep.return_value = [relevant_finding, irrelevant_finding]
        mock_static.run_bandit.return_value = []
        
        mock_llm = MagicMock()
        mock_llm.review_diff.return_value = []
        mock_llm_class.return_value = mock_llm
        
        diffs = [
            FileDiff(
                file_path="main.py",
                change_type="M",
                added_lines=[(10, "import os")],  # Only line 10 was added
                new_content="import os"
            )
        ]
        
        engine = AnalysisEngine()
        findings = engine.analyze("/tmp/repo", diffs)
        
        # Only the relevant finding should be passed to LLM
        llm_call_args = mock_llm.review_diff.call_args
        static_findings_passed = llm_call_args[0][1]
        
        assert len(static_findings_passed) == 1
        assert static_findings_passed[0].line == 10
    
    @patch('src.analysis.engine.LLMReviewer')
    @patch('src.analysis.engine.StaticAnalyzer')
    def test_filter_by_file_path(self, mock_static, mock_llm_class):
        """Test filtering findings by file path."""
        # Finding in a changed file
        finding_in_changed_file = Finding(
            tool_name="semgrep",
            rule_id="test-rule",
            severity=Severity.WARNING,
            file_path="changed.py",
            line=1,
            message="Finding in changed file"
        )
        
        # Finding in an unchanged file
        finding_in_unchanged_file = Finding(
            tool_name="semgrep",
            rule_id="test-rule-2",
            severity=Severity.WARNING,
            file_path="unchanged.py",
            line=1,
            message="Finding in unchanged file"
        )
        
        mock_static.run_semgrep.return_value = [
            finding_in_changed_file,
            finding_in_unchanged_file
        ]
        mock_static.run_bandit.return_value = []
        
        mock_llm = MagicMock()
        mock_llm.review_diff.return_value = []
        mock_llm_class.return_value = mock_llm
        
        diffs = [
            FileDiff(
                file_path="changed.py",
                change_type="M",
                added_lines=[(1, "import os")],
                new_content="import os"
            )
        ]
        
        engine = AnalysisEngine()
        findings = engine.analyze("/tmp/repo", diffs)
        
        # Only finding in changed.py should be included
        llm_call_args = mock_llm.review_diff.call_args
        static_findings_passed = llm_call_args[0][1]
        
        assert len(static_findings_passed) == 1
        assert static_findings_passed[0].file_path == "changed.py"


class TestPipelineIntegration:
    """Test end-to-end pipeline integration."""
    
    @patch('src.queue.tasks.GitHubClient')
    @patch('src.queue.tasks.AnalysisEngine')
    @patch('src.queue.tasks.DiffParser')
    @patch('src.queue.tasks.GitManager')
    @patch('src.queue.tasks.redis.from_url')
    def test_process_review_job_success(
        self, mock_redis, mock_git, mock_diff, mock_engine_class, mock_gh_class
    ):
        """Test successful end-to-end review job processing."""
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        
        # Mock GitManager
        mock_git.clone_repo.return_value = "/tmp/test-repo"
        mock_git.checkout_commit.return_value = None
        mock_git.cleanup_repo.return_value = None
        
        # Mock DiffParser
        mock_diff.get_pr_diff.return_value = [
            FileDiff(
                file_path="test.py",
                change_type="M",
                added_lines=[(1, "import os")],
                new_content="import os"
            )
        ]
        
        # Mock AnalysisEngine
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = [
            Finding(
                tool_name="semgrep",
                rule_id="test-rule",
                severity=Severity.WARNING,
                file_path="test.py",
                line=1,
                message="Test finding"
            )
        ]
        mock_engine_class.return_value = mock_engine
        
        # Mock GitHubClient
        mock_gh = MagicMock()
        mock_gh_class.return_value = mock_gh
        
        # Import and run the task
        from src.queue.tasks import process_review_job
        
        process_review_job(
            job_id="test-123",
            repo="owner/repo",
            base_sha="base123",
            head_sha="head456",
            pr_number=42
        )
        
        # Verify the workflow
        mock_git.clone_repo.assert_called_once()
        mock_git.checkout_commit.assert_called_once_with("/tmp/test-repo", "head456")
        mock_diff.get_pr_diff.assert_called_once_with("/tmp/test-repo", "base123", "head456")
        mock_engine.analyze.assert_called_once()
        mock_gh.post_check_run.assert_called_once()
        mock_gh.post_pr_comment.assert_called_once()
        mock_git.cleanup_repo.assert_called_once_with("/tmp/test-repo")
        
        # Verify state was saved to Redis
        assert mock_redis_client.setex.called
    
    @patch('src.queue.tasks.GitHubClient')
    @patch('src.queue.tasks.AnalysisEngine')
    @patch('src.queue.tasks.DiffParser')
    @patch('src.queue.tasks.GitManager')
    @patch('src.queue.tasks.redis.from_url')
    def test_process_review_job_error_handling(
        self, mock_redis, mock_git, mock_diff, mock_engine_class, mock_gh_class
    ):
        """Test error handling in review job."""
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        
        # Make clone_repo raise an exception
        mock_git.clone_repo.side_effect = RuntimeError("Clone failed")
        
        from src.queue.tasks import process_review_job
        
        with pytest.raises(RuntimeError):
            process_review_job(
                job_id="test-error",
                repo="owner/repo",
                base_sha="base",
                head_sha="head"
            )
        
        # Verify error state was saved
        assert mock_redis_client.setex.called
        # Check that the last call saved an error state
        last_call_args = mock_redis_client.setex.call_args_list[-1]
        state_json = last_call_args[0][2]
        # The state should contain error information
        assert "Clone failed" in state_json or "ERROR" in state_json
