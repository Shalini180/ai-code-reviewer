"""
Core analysis engine that coordinates static analysis and LLM review.
"""
import structlog
from typing import List
from src.api.models import Finding
from src.analysis.diff_parser import FileDiff
from src.analysis.static import StaticAnalyzer
from src.integrations.llm import LLMReviewer
from config.settings import settings

logger = structlog.get_logger()

class AnalysisEngine:
    """Coordinates the review pipeline."""

    def __init__(self):
        self.llm_reviewer = LLMReviewer()

    def analyze(self, repo_path: str, diffs: List[FileDiff]) -> List[Finding]:
        """
        Run the full analysis pipeline.
        
        Args:
            repo_path: Path to the checked-out repository
            diffs: List of file diffs to analyze
            
        Returns:
            List[Finding]: Aggregated findings
        """
        all_findings = []
        
        # 1. Run Static Analysis
        # We run this on the whole repo (or changed files if optimized)
        # For now, we run on the whole repo to get context, but filter results to changed files
        logger.info("starting_static_analysis", path=repo_path)
        static_findings = []
        
        # Semgrep
        semgrep_findings = StaticAnalyzer.run_semgrep(repo_path)
        static_findings.extend(semgrep_findings)
        
        # Bandit (if Python)
        bandit_findings = StaticAnalyzer.run_bandit(repo_path)
        static_findings.extend(bandit_findings)
        
        # Filter static findings to only those in changed lines/files
        relevant_static_findings = self._filter_relevant_findings(static_findings, diffs)
        all_findings.extend(relevant_static_findings)
        
        logger.info("static_analysis_complete", count=len(relevant_static_findings))

        # 2. Run LLM Review
        # We pass the relevant static findings as context
        logger.info("starting_llm_review")
        llm_findings = self.llm_reviewer.review_diff(diffs, relevant_static_findings)
        all_findings.extend(llm_findings)
        
        logger.info("llm_review_complete", count=len(llm_findings))
        
        return all_findings

    def _filter_relevant_findings(self, findings: List[Finding], diffs: List[FileDiff]) -> List[Finding]:
        """
        Filter findings to only those that touch changed lines.
        """
        relevant = []
        changed_files = {d.file_path: d for d in diffs}
        
        for finding in findings:
            if finding.file_path not in changed_files:
                continue
                
            diff = changed_files[finding.file_path]
            
            # Check if finding line is in added lines
            # Or if it's a file-level issue (line 0 or 1)
            is_relevant = False
            
            # Simple check: is the line in the added lines?
            # Note: Static analysis might report issues on lines that weren't changed but are affected
            # For strict PR review, we usually only comment on changed lines
            for line_num, _ in diff.added_lines:
                if finding.line == line_num:
                    is_relevant = True
                    break
            
            # Also include if it's in the removed lines? No, we can't comment on deleted lines easily.
            
            # If we want to be broader, we can include any finding in a changed file
            # But that might be noisy. Let's stick to changed lines for now.
            if is_relevant:
                relevant.append(finding)
                
        return relevant
