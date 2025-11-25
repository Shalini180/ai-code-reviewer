"""
Offline evaluation runner for AI Code Reviewer.

This script replays PRs through the system in three modes (static_only, llm_only, hybrid)
and logs structured findings for later metrics computation.
"""
import argparse
import json
import time
import structlog
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from src.analysis.engine import AnalysisEngine
from src.analysis.diff_parser import DiffParser, FileDiff
from src.analysis.finding_schema import finding_to_normalized, NormalizedFinding
from src.api.models import AnalysisMode
from config.settings import settings

logger = structlog.get_logger()


def load_pr_list(pr_list_path: str) -> List[Dict[str, Any]]:
    """
    Load PR list from JSON file.
    
    Expected format:
    [
        {
            "pr_id": "unique_id",
            "repo_path": "/path/to/repo",
            "base_sha": "abc123",
            "head_sha": "def456"
        },
        ...
    ]
    """
    with open(pr_list_path, 'r') as f:
        return json.load(f)


def run_evaluation_for_pr(
    pr: Dict[str, Any],
    engine: AnalysisEngine,
    mode: AnalysisMode
) -> Dict[str, Any]:
    """
    Run evaluation for a single PR in a specific mode.
    
    Returns:
        Dictionary with pr_id, analysis_mode, findings, latency_ms, timestamp
    """
    pr_id = pr["pr_id"]
    repo_path = pr["repo_path"]
    base_sha = pr["base_sha"]
    head_sha = pr["head_sha"]
    
    logger.info("running_evaluation", pr_id=pr_id, mode=mode.value)
    
    # Parse diffs
    diffs: List[FileDiff] = DiffParser.get_pr_diff(repo_path, base_sha, head_sha)
    
    # Measure analysis time
    start_time = time.perf_counter()
    findings = engine.analyze(repo_path, diffs, mode=mode.value)
    end_time = time.perf_counter()
    
    latency_ms = int((end_time - start_time) * 1000)
    
    # Convert findings to normalized format
    source_map = {
        AnalysisMode.STATIC_ONLY: "static",
        AnalysisMode.LLM_ONLY: "llm",
        AnalysisMode.HYBRID: "hybrid"
    }
    source = source_map[mode]
    
    normalized_findings = [
        finding_to_normalized(f, source).model_dump()
        for f in findings
    ]
    
    result = {
        "pr_id": pr_id,
        "analysis_mode": mode.value,
        "findings": normalized_findings,
        "latency_ms": latency_ms,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(
        "evaluation_complete",
        pr_id=pr_id,
        mode=mode.value,
        findings_count=len(findings),
        latency_ms=latency_ms
    )
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run offline evaluation of AI Code Reviewer"
    )
    parser.add_argument(
        "--pr-list",
        required=True,
        help="Path to JSON file containing PR list"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSONL file path (default: results/evaluation/<timestamp>.jsonl)"
    )
    
    args = parser.parse_args()
    
    # Load PR list
    pr_list = load_pr_list(args.pr_list)
    logger.info("loaded_pr_list", count=len(pr_list))
    
    # Prepare output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = Path("results/evaluation")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"eval_{timestamp}.jsonl"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize engine
    engine = AnalysisEngine()
    
    # Run evaluation for all PRs and all modes
    modes = [AnalysisMode.STATIC_ONLY, AnalysisMode.LLM_ONLY, AnalysisMode.HYBRID]
    
    results = []
    total_runs = len(pr_list) * len(modes)
    current_run = 0
    
    for pr in pr_list:
        for mode in modes:
            current_run += 1
            logger.info(
                "progress",
                current=current_run,
                total=total_runs,
                pr_id=pr["pr_id"],
                mode=mode.value
            )
            
            try:
                result = run_evaluation_for_pr(pr, engine, mode)
                results.append(result)
            except Exception as e:
                logger.error(
                    "evaluation_failed",
                    pr_id=pr["pr_id"],
                    mode=mode.value,
                    error=str(e)
                )
                # Record error result
                results.append({
                    "pr_id": pr["pr_id"],
                    "analysis_mode": mode.value,
                    "findings": [],
                    "latency_ms": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                })
    
    # Write results to JSONL
    with open(output_path, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    logger.info("evaluation_complete", output_file=str(output_path), total_results=len(results))
    print(f"\nEvaluation complete. Results written to: {output_path}")
    print(f"Total runs: {len(results)}")


if __name__ == "__main__":
    main()
