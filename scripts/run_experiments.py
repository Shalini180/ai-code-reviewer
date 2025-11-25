#!/usr/bin/env python3
"""
CLI script to run experiments comparing different analysis modes.

Usage:
    python scripts/run_experiments.py [config_file]
    
If no config file is provided, uses experiments/example_config.json
"""
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.experiments.runner import ExperimentRunner, ExperimentConfig


def load_config(config_path: str) -> ExperimentConfig:
    """Load experiment configuration from JSON file."""
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    return ExperimentConfig(
        name=config_data["name"],
        repos=config_data["repos"],
        modes=config_data["modes"],
        output_dir=config_data.get("output_dir")
    )


def main():
    # Get config file path
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "experiments/example_config.json"
    
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        print(f"\\nUsage: python scripts/run_experiments.py [config_file]")
        sys.exit(1)
    
    print(f"Loading experiment configuration from: {config_path}")
    config = load_config(config_path)
    
    print(f"\\nExperiment: {config.name}")
    print(f"Repositories: {len(config.repos)}")
    print(f"Modes: {', '.join(config.modes)}")
    print(f"Output directory: {config.output_dir}")
    print("\\nStarting experiments...\\n")
    
    # Run experiments
    runner = ExperimentRunner(config)
    results_path = runner.run()
    
    # Print summary
    runner.print_summary()
    
    print(f"Results saved to: {results_path}")
    print(f"\\nTo evaluate results, run:")
    print(f"  python scripts/evaluate_results.py {results_path}")


if __name__ == "__main__":
    main()
