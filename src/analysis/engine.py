"""
Core analysis engine that coordinates static analysis and LLM review.
"""
import structlog
from typing import List
from src.api.models import Finding, AnalysisMode
from src.analysis.diff_parser import FileDiff
from src.analysis.static import StaticAnalyzer
from src.integrations.llm import LLMReviewer
from config.settings import settings

logger = structlog.get_logger()

class AnalysisEngine:
    """Coordinates the review pipeline."""

    def __init__(self):
        self.llm_reviewer = LLMReviewer()

    def analyze(self, repo_path: str, diffs: List[FileDiff], mode: str = None) -> List[Finding]:
        """
        Run the analysis pipeline based on the specified mode.
        
        Args:
            repo_path: Path to the checked-out repository
            diffs: List of file diffs to analyze
            mode: Analysis mode (static_only, llm_only, or hybrid). Defaults to settings.analysis_mode
            
        Returns:
            List[Finding]: Aggregated findings
        """
        # Default to settings if mode not provided
        if mode is None:
            mode = settings.analysis_mode
        
        # Normalize mode string
        if isinstance(mode, AnalysisMode):
            mode = mode.value
        
        logger.info("starting_analysis", mode=mode, path=repo_path)
        all_findings = []
        
        # Run static analysis if mode requires it
        if mode in ["static_only", "hybrid"]:
            static_findings = self._run_static_analysis(repo_path, diffs)
            all_findings.extend(static_findings)
            logger.info("static_analysis_complete", count=len(static_findings))
        else:
            static_findings = []
        
        # Run LLM review if mode requires it
        if mode in ["llm_only", "hybrid"]:
            # In hybrid mode, pass static findings as context to LLM
            context_findings = static_findings if mode == "hybrid" else []
            llm_findings = self._run_llm_review(diffs, context_findings)
            all_findings.extend(llm_findings)
            logger.info("llm_review_complete", count=len(llm_findings))
        
        logger.info("analysis_complete", mode=mode, total_findings=len(all_findings))
        return all_findings

    def _run_static_analysis(self, repo_path: str, diffs: List[FileDiff]) -> List[Finding]:
        """
        Run static analysis tools (Semgrep and Bandit).
        
        Args:
            repo_path: Path to the repository
            diffs: List of file diffs
            
        Returns:
            List of findings from static analysis, filtered to changed lines
        """
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
        
        return relevant_static_findings

    def _run_llm_review(self, diffs: List[FileDiff], static_findings: List[Finding]) -> List[Finding]:
        """
        Run LLM-based code review.
        
        Args:
            diffs: List of file diffs
            static_findings: Static analysis findings to provide as context
            
        Returns:
            List of findings from LLM review
        """
        logger.info("starting_llm_review")
        llm_findings = self.llm_reviewer.review_diff(diffs, static_findings)
        return llm_findings

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
