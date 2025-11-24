"""
Verification script to test the pipeline logic without external dependencies.
Mocks Redis, Celery, and GitHub.
"""
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.getcwd())

from src.api.models import Finding, Severity
from src.analysis.diff_parser import FileDiff

def test_pipeline():
    print("🚀 Starting Pipeline Verification...")

    # Mock Redis
    with patch('redis.from_url') as mock_redis:
        mock_redis.return_value.setex.return_value = True
        
        # Mock Celery
        with patch('src.queue.worker.celery_app.task') as mock_task:
            mock_task.return_value = lambda x: x # Decorator pass-through
            
            # Mock GitManager
            with patch('src.integrations.git_ops.GitManager') as MockGit:
                MockGit.clone_repo.return_value = "/tmp/test_repo"
                MockGit.checkout_commit.return_value = None
                MockGit.cleanup_repo.return_value = None
                
                # Mock DiffParser
                with patch('src.analysis.diff_parser.DiffParser') as MockDiff:
                    MockDiff.get_pr_diff.return_value = [
                        FileDiff(
                            file_path="main.py",
                            change_type="M",
                            added_lines=[(10, "import os"), (11, "os.system('rm -rf /')")],
                            new_content="import os\nos.system('rm -rf /')"
                        )
                    ]
                    
                    # Mock AnalysisEngine
                    with patch('src.analysis.engine.AnalysisEngine') as MockEngine:
                        # Return some fake findings
                        MockEngine.return_value.analyze.return_value = [
                            Finding(
                                tool_name="semgrep",
                                rule_id="python.lang.security.audit.system-call",
                                severity=Severity.ERROR,
                                file_path="main.py",
                                line=11,
                                message="Avoid using os.system",
                                suggestion="Use subprocess.run"
                            )
                        ]
                        
                        # Mock GitHubClient
                        with patch('src.integrations.github_client.GitHubClient') as MockGH:
                            
                            # Import the task to test
                            from src.queue.tasks import process_review_job
                            
                            print("✅ Mocks setup complete.")
                            print("🏃 Running process_review_job...")
                            
                            try:
                                # Call with None for self (bind=True parameter)
                                process_review_job(
                                    None,  # self parameter from bind=True
                                    job_id="test-job-123",
                                    repo="octocat/hello-world",
                                    base_sha="abc",
                                    head_sha="def",
                                    pr_number=1
                                )
                                print("✅ Job completed successfully!")
                                
                            except Exception as e:
                                print(f"❌ Job failed: {e}")
                                raise

if __name__ == "__main__":
    test_pipeline()
