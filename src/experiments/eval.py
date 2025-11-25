"""
Evaluation framework for analyzing experiment results.

Computes metrics and overlap analysis between different analysis modes.
"""
import structlog
import json
from typing import List, Dict, Any, Set
from collections import defaultdict
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class ModeMetrics:
    """Metrics for a single analysis mode."""
    mode: str
    total_runs: int
    total_findings: int
    avg_findings_per_run: float
    severity_distribution: Dict[str, int]
    tool_distribution: Dict[str, int]
    avg_runtime: float
    error_count: int


class ExperimentEvaluator:
    """Evaluates experiment results and computes comparative metrics."""

    def __init__(self, results_path: str):
        self.results_path = results_path
        self.results: List[Dict[str, Any]] = []
        self._load_results()

    def _load_results(self):
        """Load experiment results from JSONL file."""
        with open(self.results_path, 'r') as f:
            for line in f:
                if line.strip():
                    self.results.append(json.loads(line))
        
        logger.info("results_loaded", path=self.results_path, count=len(self.results))

    def compute_metrics(self) -> Dict[str, ModeMetrics]:
        """
        Compute metrics for each analysis mode.
        
        Returns:
            Dictionary mapping mode name to ModeMetrics
        """
        metrics_by_mode = {}
        
        # Group results by mode
        results_by_mode = defaultdict(list)
        for result in self.results:
            results_by_mode[result["mode"]].append(result)
        
        # Compute metrics for each mode
        for mode, mode_results in results_by_mode.items():
            severity_dist = defaultdict(int)
            tool_dist = defaultdict(int)
            total_findings = 0
            total_runtime = 0
            error_count = 0
            
            for result in mode_results:
                total_findings += result["findings_count"]
                total_runtime += result["runtime_seconds"]
                
                if result.get("error"):
                    error_count += 1
                
                for finding in result["findings"]:
                    severity_dist[finding["severity"]] += 1
                    tool_dist[finding["tool_name"]] += 1
            
            metrics = ModeMetrics(
                mode=mode,
                total_runs=len(mode_results),
                total_findings=total_findings,
                avg_findings_per_run=total_findings / len(mode_results) if mode_results else 0,
                severity_distribution=dict(severity_dist),
                tool_distribution=dict(tool_dist),
                avg_runtime=total_runtime / len(mode_results) if mode_results else 0,
                error_count=error_count
            )
            
            metrics_by_mode[mode] = metrics
        
        return metrics_by_mode

    def compute_overlap(self, mode1: str, mode2: str) -> Dict[str, Any]:
        """
        Compute overlap of findings between two modes.
        
        Findings are considered the same if they have the same file_path, line, and rule_id.
        
        Returns:
            Dictionary with overlap statistics
        """
        # Get all findings for each mode
        findings1 = self._get_findings_set(mode1)
        findings2 = self._get_findings_set(mode2)
        
        # Compute overlap
        intersection = findings1 & findings2
        union = findings1 | findings2
        only_mode1 = findings1 - findings2
        only_mode2 = findings2 - findings1
        
        overlap_stats = {
            "mode1": mode1,
            "mode2": mode2,
            "mode1_total": len(findings1),
            "mode2_total": len(findings2),
            "intersection": len(intersection),
            "union": len(union),
            "only_mode1": len(only_mode1),
            "only_mode2": len(only_mode2),
            "jaccard_similarity": len(intersection) / len(union) if union else 0,
            "overlap_percentage": (len(intersection) / len(union) * 100) if union else 0
        }
        
        return overlap_stats

    def _get_findings_set(self, mode: str) -> Set[tuple]:
        """
        Get set of unique findings for a mode.
        
        Each finding is represented as a tuple (file_path, line, rule_id).
        """
        findings_set = set()
        
        for result in self.results:
            if result["mode"] == mode:
                for finding in result["findings"]:
                    finding_key = (
                        finding["file_path"],
                        finding["line"],
                        finding["rule_id"]
                    )
                    findings_set.add(finding_key)
        
        return findings_set

    def generate_report(self) -> str:
        """
        Generate a textual report comparing all modes.
        
        Returns:
            Formatted report string
        """
        metrics = self.compute_metrics()
        
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("EXPERIMENT EVALUATION REPORT")
        report_lines.append("=" * 70)
        report_lines.append(f"Results file: {self.results_path}")
        report_lines.append(f"Total results: {len(self.results)}")
        report_lines.append("")
        
        # Mode-wise statistics
        report_lines.append("MODE-WISE STATISTICS")
        report_lines.append("-" * 70)
        
        for mode, m in sorted(metrics.items()):
            report_lines.append(f"\\n{mode.upper()}:")
            report_lines.append(f"  Total runs: {m.total_runs}")
            report_lines.append(f"  Total findings: {m.total_findings}")
            report_lines.append(f"  Avg findings/run: {m.avg_findings_per_run:.2f}")
            report_lines.append(f"  Avg runtime: {m.avg_runtime:.2f}s")
            report_lines.append(f"  Errors: {m.error_count}")
            
            if m.severity_distribution:
                report_lines.append(f"  Severity distribution:")
                for severity, count in sorted(m.severity_distribution.items()):
                    report_lines.append(f"    {severity}: {count}")
            
            if m.tool_distribution:
                report_lines.append(f"  Tool distribution:")
                for tool, count in sorted(m.tool_distribution.items()):
                    report_lines.append(f"    {tool}: {count}")
        
        # Overlap analysis
        modes = list(metrics.keys())
        if len(modes) >= 2:
            report_lines.append("")
            report_lines.append("OVERLAP ANALYSIS")
            report_lines.append("-" * 70)
            
            for i in range(len(modes)):
                for j in range(i + 1, len(modes)):
                    overlap = self.compute_overlap(modes[i], modes[j])
                    report_lines.append(f"\\n{overlap['mode1']} vs {overlap['mode2']}:")
                    report_lines.append(f"  {overlap['mode1']} findings: {overlap['mode1_total']}")
                    report_lines.append(f"  {overlap['mode2']} findings: {overlap['mode2_total']}")
                    report_lines.append(f"  Shared findings: {overlap['intersection']}")
                    report_lines.append(f"  Only in {overlap['mode1']}: {overlap['only_mode1']}")
                    report_lines.append(f"  Only in {overlap['mode2']}: {overlap['only_mode2']}")
                    report_lines.append(f"  Jaccard similarity: {overlap['jaccard_similarity']:.3f}")
                    report_lines.append(f"  Overlap: {overlap['overlap_percentage']:.1f}%")
        
        # Summary interpretation
        report_lines.append("")
        report_lines.append("INTERPRETATION")
        report_lines.append("-" * 70)
        report_lines.append(self._generate_interpretation(metrics))
        
        report_lines.append("")
        report_lines.append("=" * 70)
        
        return "\\n".join(report_lines)

    def _generate_interpretation(self, metrics: Dict[str, ModeMetrics]) -> str:
        """Generate plain English interpretation of results."""
        lines = []
        
        if "static_only" in metrics and "llm_only" in metrics:
            static = metrics["static_only"]
            llm = metrics["llm_only"]
            
            lines.append(f"Static analysis found {static.total_findings} issues across {static.total_runs} runs,")
            lines.append(f"while LLM-only found {llm.total_findings} issues.")
            
            if static.total_findings > llm.total_findings:
                lines.append("Static tools detected more issues overall.")
            elif llm.total_findings > static.total_findings:
                lines.append("LLM detected more issues overall.")
            else:
                lines.append("Both approaches found similar numbers of issues.")
        
        if "hybrid" in metrics:
            hybrid = metrics["hybrid"]
            lines.append(f"\\nHybrid mode (combining both) found {hybrid.total_findings} issues,")
            lines.append(f"averaging {hybrid.avg_findings_per_run:.1f} per run.")
        
        if len(metrics) > 1:
            fastest = min(metrics.values(), key=lambda m: m.avg_runtime)
            slowest = max(metrics.values(), key=lambda m: m.avg_runtime)
            lines.append(f"\\n{fastest.mode} was fastest ({fastest.avg_runtime:.2f}s avg),")
            lines.append(f"while {slowest.mode} took {slowest.avg_runtime:.2f}s on average.")
        
        return " ".join(lines)

    def print_report(self):
        """Print the evaluation report to stdout."""
        print(self.generate_report())
