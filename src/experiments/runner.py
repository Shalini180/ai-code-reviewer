"""
Experiment runner for offline code review analysis.

Runs analysis in different modes without using webhooks or GitHub APIs.
"""
import structlog
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from src.analysis.diff_parser import DiffParser
from src.analysis.engine import AnalysisEngine
from src.integrations.git_ops import GitManager
from src.api.models import Finding, AnalysisMode
from config.settings import settings

logger = structlog.get_logger()


@dataclass
class ExperimentConfig:
    """Configuration for an experiment run."""
    name: str
    repos: List[Dict[str, Any]]  # List of {url, base_sha, head_sha, pr_number}
    modes: List[str]  # Analysis modes to test
    output_dir: str = None
    
    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = settings.experiment_results_dir


@dataclass
class ExperimentResult:
    """Result from running analysis on a single PR in a single mode."""
    experiment_name: str
    repo: str
    base_sha: str
    head_sha: str
    pr_number: Optional[int]
    mode: str
    timestamp: str
    findings_count: int
    findings: List[Dict[str, Any]]
    runtime_seconds: float
    error: Optional[str] = None


class ExperimentRunner:
    """Runs offline experiments comparing different analysis modes."""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.results: List[ExperimentResult] = []
        
        # Ensure output directory exists
        os.makedirs(self.config.output_dir, exist_ok=True)

    def run(self) -> str:
        """
        Run all experiments defined in the configuration.
        
        Returns:
            Path to the results file
        """
        logger.info(
            "experiment_started",
            name=self.config.name,
            repos_count=len(self.config.repos),
            modes=self.config.modes
        )
        
        for repo_config in self.config.repos:
            for mode in self.config.modes:
                result = self._run_single_experiment(repo_config, mode)
                self.results.append(result)
        
        # Save results
        results_path = self._save_results()
        
        logger.info(
            "experiment_completed",
            name=self.config.name,
            results_count=len(self.results),
            results_path=results_path
        )
        
        return results_path

    def _run_single_experiment(
        self,
        repo_config: Dict[str, Any],
        mode: str
    ) -> ExperimentResult:
        """
        Run analysis on a single PR in a single mode.
        """
        repo_url = repo_config["url"]
        base_sha = repo_config["base_sha"]
        head_sha = repo_config["head_sha"]
        pr_number = repo_config.get("pr_number")
        
        logger.info(
            "running_experiment",
            repo=repo_url,
            mode=mode,
            base=base_sha[:7],
            head=head_sha[:7]
        )
        
        repo_path = None
        start_time = time.time()
        
        try:
            # Clone repository
            job_id = f"exp_{int(time.time())}"
            repo_path = GitManager.clone_repo(repo_url, job_id)
            GitManager.checkout_commit(repo_path, head_sha)
            
            # Parse diff
            diffs = DiffParser.get_pr_diff(repo_path, base_sha, head_sha)
            
            # Run analysis
            engine = AnalysisEngine()
            findings = engine.analyze(repo_path, diffs, mode=mode)
            
            runtime = time.time() - start_time
            
            result = ExperimentResult(
                experiment_name=self.config.name,
                repo=repo_url,
                base_sha=base_sha,
                head_sha=head_sha,
                pr_number=pr_number,
                mode=mode,
                timestamp=datetime.utcnow().isoformat(),
                findings_count=len(findings),
                findings=[self._finding_to_dict(f) for f in findings],
                runtime_seconds=runtime,
                error=None
            )
            
            logger.info(
                "experiment_success",
                repo=repo_url,
                mode=mode,
                findings=len(findings),
                runtime=f"{runtime:.2f}s"
            )
            
        except Exception as e:
            runtime = time.time() - start_time
            logger.error(
                "experiment_failed",
                repo=repo_url,
                mode=mode,
                error=str(e),
                exc_info=True
            )
            
            result = ExperimentResult(
                experiment_name=self.config.name,
                repo=repo_url,
                base_sha=base_sha,
                head_sha=head_sha,
                pr_number=pr_number,
                mode=mode,
                timestamp=datetime.utcnow().isoformat(),
                findings_count=0,
                findings=[],
                runtime_seconds=runtime,
                error=str(e)
            )
        
        finally:
            if repo_path:
                GitManager.cleanup_repo(repo_path)
        
        return result

    def _finding_to_dict(self, finding: Finding) -> Dict[str, Any]:
        """Convert Finding to dictionary for JSON serialization."""
        return {
            "tool_name": finding.tool_name,
            "rule_id": finding.rule_id,
            "severity": finding.severity.value,
            "file_path": finding.file_path,
            "line": finding.line,
            "message": finding.message,
            "confidence": finding.confidence
        }

    def _save_results(self) -> str:
        """
        Save experiment results to JSONL file.
        
        Returns:
            Path to the results file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config.name}_{timestamp}.jsonl"
        filepath = os.path.join(self.config.output_dir, filename)
        
        with open(filepath, 'w') as f:
            for result in self.results:
                f.write(json.dumps(asdict(result)) + '\\n')
        
        logger.info("results_saved", path=filepath, count=len(self.results))
        return filepath

    def print_summary(self):
        """Print a brief summary of the experiment results."""
        print(f"\\n{'='*60}")
        print(f"Experiment: {self.config.name}")
        print(f"{'='*60}")
        print(f"Total runs: {len(self.results)}")
        print(f"Modes tested: {', '.join(self.config.modes)}")
        print(f"\\nResults by mode:")
        
        for mode in self.config.modes:
            mode_results = [r for r in self.results if r.mode == mode]
            total_findings = sum(r.findings_count for r in mode_results)
            avg_runtime = sum(r.runtime_seconds for r in mode_results) / len(mode_results) if mode_results else 0
            errors = sum(1 for r in mode_results if r.error)
            
            print(f"  {mode}:")
            print(f"    Runs: {len(mode_results)}")
            print(f"    Total findings: {total_findings}")
            print(f"    Avg runtime: {avg_runtime:.2f}s")
            print(f"    Errors: {errors}")
        
        print(f"{'='*60}\\n")
