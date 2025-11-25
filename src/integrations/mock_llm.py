"""
Mock LLM client for testing without real Anthropic API calls.
"""
import structlog
import random
from typing import List
from src.api.models import Finding, Severity
from src.analysis.diff_parser import FileDiff
from config.settings import settings

logger = structlog.get_logger()


class MockLLMReviewer:
    """Mock LLM reviewer that returns deterministic findings without API calls."""

    def __init__(self):
        self.model = "mock-claude"
        random.seed(settings.experiment_random_seed)
        logger.info("mock_llm_reviewer_initialized", seed=settings.experiment_random_seed)

    def review_diff(self, diffs: List[FileDiff], static_findings: List[Finding]) -> List[Finding]:
        """
        Generate mock LLM findings based on diff content.
        
        Returns deterministic findings based on file patterns and added lines.
        """
        findings = []
        
        for diff in diffs:
            if diff.change_type == 'D':
                continue
            
            # Generate 0-2 mock findings per file based on file path hash
            num_findings = hash(diff.file_path) % 3
            
            for i in range(num_findings):
                if not diff.added_lines:
                    continue
                
                # Pick a line from added lines
                line_idx = (hash(diff.file_path) + i) % len(diff.added_lines)
                line_num, line_content = diff.added_lines[line_idx]
                
                # Generate mock finding
                findings.append(Finding(
                    tool_name="mock-claude-ai",
                    rule_id=f"mock-ai-{i+1}",
                    severity=Severity.WARNING if i % 2 == 0 else Severity.INFO,
                    file_path=diff.file_path,
                    line=line_num,
                    message=f"Mock LLM finding: Consider reviewing this code pattern",
                    suggestion=f"Mock suggestion for line {line_num}",
                    confidence=0.7
                ))
        
        logger.info("mock_llm_review_complete", findings_count=len(findings))
        return findings
