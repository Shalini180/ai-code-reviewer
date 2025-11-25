"""
Compute evaluation metrics from run_evaluation.py results.

This script calculates precision, recall, F1, false positive rate, and latency
for each analysis mode based on ground truth labels.
"""
import argparse
import json
import structlog
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict
from datetime import datetime

logger = structlog.get_logger()


def load_results(results_path: str) -> List[Dict[str, Any]]:
    """Load evaluation results from JSONL file."""
    results = []
    with open(results_path, 'r') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def load_ground_truth(ground_truth_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load ground truth labels from JSON file.
    
    Expected format:
    {
        "pr_id_1": [
            {"file": "path/to/file.py", "line": 42, "category": "security"},
            ...
        ],
        ...
    }
    """
    with open(ground_truth_path, 'r') as f:
        return json.load(f)


def finding_signature(finding: Dict[str, Any]) -> str:
    """Create a signature for a finding based on file, line, and category."""
    return f"{finding['file']}:{finding['line']}:{finding['category']}"


def compute_metrics_for_mode(
    results: List[Dict[str, Any]],
    ground_truth: Dict[str, List[Dict[str, Any]]],
    mode: str
) -> Dict[str, Any]:
    """
    Compute metrics for a specific analysis mode.
    
    Returns:
        Dictionary with precision, recall, f1, false_positive_rate, avg_latency_ms
    """
    # Filter results for this mode
    mode_results = [r for r in results if r["analysis_mode"] == mode]
    
    # Track metrics
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    total_latency_ms = 0
    pr_count = 0
    
    for result in mode_results:
        pr_id = result["pr_id"]
        findings = result["findings"]
        latency_ms = result.get("latency_ms", 0)
        
        total_latency_ms += latency_ms
        pr_count += 1
        
        # Get ground truth for this PR
        gt_issues = ground_truth.get(pr_id, [])
        
        # Create sets of finding signatures
        predicted_sigs = {finding_signature(f) for f in findings}
        truth_sigs = {finding_signature(gt) for gt in gt_issues}
        
        # Calculate TP, FP, FN
        tp = len(predicted_sigs & truth_sigs)  # Intersection
        fp = len(predicted_sigs - truth_sigs)  # Predicted but not in truth
        fn = len(truth_sigs - predicted_sigs)  # In truth but not predicted
        
        true_positives += tp
        false_positives += fp
        false_negatives += fn
    
    # Calculate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # False positive rate = FP / (FP + TN)
    # Since we don't have true negatives (all non-issues), we use FP / total_predicted as a proxy
    total_predicted = true_positives + false_positives
    fpr = false_positives / total_predicted if total_predicted > 0 else 0.0
    
    avg_latency_ms = total_latency_ms / pr_count if pr_count > 0 else 0.0
    
    return {
        "mode": mode,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "avg_latency_ms": round(avg_latency_ms, 2),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "total_prs": pr_count
    }


def print_metrics_table(metrics_by_mode: Dict[str, Dict[str, Any]]):
    """Print metrics in a formatted table."""
    print("\n" + "="*80)
    print("EVALUATION METRICS")
    print("="*80)
    
    # Table header
    header = f"{'Mode':<15} {'Precision':<12} {'Recall':<12} {'F1':<12} {'FPR':<12} {'Latency (ms)':<15}"
    print(header)
    print("-"*80)
    
    # Table rows
    for mode in ["static_only", "llm_only", "hybrid"]:
        if mode in metrics_by_mode:
            m = metrics_by_mode[mode]
            row = (
                f"{m['mode']:<15} "
                f"{m['precision']:<12.4f} "
                f"{m['recall']:<12.4f} "
                f"{m['f1_score']:<12.4f} "
                f"{m['false_positive_rate']:<12.4f} "
                f"{m['avg_latency_ms']:<15.2f}"
            )
            print(row)
    
    print("="*80)
    
    # Detailed stats
    print("\nDETAILED STATISTICS")
    print("-"*80)
    for mode in ["static_only", "llm_only", "hybrid"]:
        if mode in metrics_by_mode:
            m = metrics_by_mode[mode]
            print(f"\n{mode.upper()}:")
            print(f"  True Positives:  {m['true_positives']}")
            print(f"  False Positives: {m['false_positives']}")
            print(f"  False Negatives: {m['false_negatives']}")
            print(f"  Total PRs:       {m['total_prs']}")


def main():
    parser = argparse.ArgumentParser(
        description="Compute metrics from evaluation results"
    )
    parser.add_argument(
        "--results",
        required=True,
        help="Path to JSONL results file from run_evaluation.py"
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        help="Path to JSON ground truth file"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file for metrics (default: results/evaluation/metrics_<timestamp>.json)"
    )
    
    args = parser.parse_args()
    
    # Load data
    results = load_results(args.results)
    ground_truth = load_ground_truth(args.ground_truth)
    
    logger.info("loaded_data", results_count=len(results), ground_truth_prs=len(ground_truth))
    
    # Compute metrics for each mode
    modes = ["static_only", "llm_only", "hybrid"]
    metrics_by_mode = {}
    
    for mode in modes:
        metrics = compute_metrics_for_mode(results, ground_truth, mode)
        metrics_by_mode[mode] = metrics
        logger.info("computed_metrics", mode=mode, precision=metrics["precision"], recall=metrics["recall"])
    
    # Print table
    print_metrics_table(metrics_by_mode)
    
    # Prepare output
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = Path("results/evaluation")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"metrics_{timestamp}.json"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write metrics to JSON
    output_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "results_file": args.results,
        "ground_truth_file": args.ground_truth,
        "metrics": metrics_by_mode
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nMetrics saved to: {output_path}")


if __name__ == "__main__":
    main()
