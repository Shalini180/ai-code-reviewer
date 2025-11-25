#!/usr/bin/env python3
"""
CLI script to evaluate experiment results.

Usage:
    python scripts/evaluate_results.py <results_file.jsonl>
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.experiments.eval import ExperimentEvaluator


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/evaluate_results.py <results_file.jsonl>")
        sys.exit(1)
    
    results_path = sys.argv[1]
    
    print(f"Loading results from: {results_path}\\n")
    
    evaluator = ExperimentEvaluator(results_path)
    evaluator.print_report()


if __name__ == "__main__":
    main()
