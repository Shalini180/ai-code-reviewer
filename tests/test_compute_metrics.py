"""
Tests for compute_metrics.py
"""
import pytest
import json
import tempfile
from pathlib import Path
from evaluation.compute_metrics import (
    load_results,
    load_ground_truth,
    finding_signature,
    compute_metrics_for_mode
)


def test_load_results(tmp_path):
    """Test loading results from JSONL file."""
    results_file = tmp_path / "results.jsonl"
    
    results_data = [
        {"pr_id": "pr1", "analysis_mode": "static_only", "findings": [], "latency_ms": 100},
        {"pr_id": "pr1", "analysis_mode": "llm_only", "findings": [], "latency_ms": 200}
    ]
    
    with open(results_file, 'w') as f:
        for result in results_data:
            f.write(json.dumps(result) + '\n')
    
    loaded = load_results(str(results_file))
    
    assert len(loaded) == 2
    assert loaded[0]["pr_id"] == "pr1"
    assert loaded[1]["analysis_mode"] == "llm_only"


def test_load_ground_truth(tmp_path):
    """Test loading ground truth from JSON file."""
    gt_file = tmp_path / "ground_truth.json"
    
    gt_data = {
        "pr1": [
            {"file": "test.py", "line": 10, "category": "security"}
        ],
        "pr2": [
            {"file": "test.py", "line": 20, "category": "bug"}
        ]
    }
    
    with open(gt_file, 'w') as f:
        json.dump(gt_data, f)
    
    loaded = load_ground_truth(str(gt_file))
    
    assert len(loaded) == 2
    assert "pr1" in loaded
    assert len(loaded["pr1"]) == 1
    assert loaded["pr1"][0]["category"] == "security"


def test_finding_signature():
    """Test finding signature generation."""
    finding = {
        "file": "src/main.py",
        "line": 42,
        "category": "security"
    }
    
    sig = finding_signature(finding)
    
    assert sig == "src/main.py:42:security"


def test_compute_metrics_perfect_match():
    """Test metrics computation with perfect precision and recall."""
    results = [
        {
            "pr_id": "pr1",
            "analysis_mode": "static_only",
            "findings": [
                {"file": "test.py", "line": 10, "category": "security"},
                {"file": "test.py", "line": 20, "category": "bug"}
            ],
            "latency_ms": 100
        }
    ]
    
    ground_truth = {
        "pr1": [
            {"file": "test.py", "line": 10, "category": "security"},
            {"file": "test.py", "line": 20, "category": "bug"}
        ]
    }
    
    metrics = compute_metrics_for_mode(results, ground_truth, "static_only")
    
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["true_positives"] == 2
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 0
    assert metrics["avg_latency_ms"] == 100.0


def test_compute_metrics_with_false_positives():
    """Test metrics with false positives."""
    results = [
        {
            "pr_id": "pr1",
            "analysis_mode": "static_only",
            "findings": [
                {"file": "test.py", "line": 10, "category": "security"},
                {"file": "test.py", "line": 20, "category": "bug"},
                {"file": "test.py", "line": 30, "category": "style"}  # False positive
            ],
            "latency_ms": 100
        }
    ]
    
    ground_truth = {
        "pr1": [
            {"file": "test.py", "line": 10, "category": "security"},
            {"file": "test.py", "line": 20, "category": "bug"}
        ]
    }
    
    metrics = compute_metrics_for_mode(results, ground_truth, "static_only")
    
    assert metrics["precision"] == pytest.approx(2/3, abs=0.01)
    assert metrics["recall"] == 1.0
    assert metrics["true_positives"] == 2
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 0


def test_compute_metrics_with_false_negatives():
    """Test metrics with false negatives (missed issues)."""
    results = [
        {
            "pr_id": "pr1",
            "analysis_mode": "llm_only",
            "findings": [
                {"file": "test.py", "line": 10, "category": "security"}
            ],
            "latency_ms": 200
        }
    ]
    
    ground_truth = {
        "pr1": [
            {"file": "test.py", "line": 10, "category": "security"},
            {"file": "test.py", "line": 20, "category": "bug"},
            {"file": "test.py", "line": 30, "category": "performance"}
        ]
    }
    
    metrics = compute_metrics_for_mode(results, ground_truth, "llm_only")
    
    assert metrics["precision"] == 1.0  # All predictions were correct
    assert metrics["recall"] == pytest.approx(1/3, abs=0.01)  # Caught 1 out of 3
    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 2


def test_compute_metrics_no_findings():
    """Test metrics when no findings are reported."""
    results = [
        {
            "pr_id": "pr1",
            "analysis_mode": "static_only",
            "findings": [],
            "latency_ms": 50
        }
    ]
    
    ground_truth = {
        "pr1": [
            {"file": "test.py", "line": 10, "category": "security"}
        ]
    }
    
    metrics = compute_metrics_for_mode(results, ground_truth, "static_only")
    
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1_score"] == 0.0
    assert metrics["true_positives"] == 0
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 1


def test_compute_metrics_multiple_prs():
    """Test metrics across multiple PRs."""
    results = [
        {
            "pr_id": "pr1",
            "analysis_mode": "hybrid",
            "findings": [
                {"file": "test1.py", "line": 10, "category": "security"}
            ],
            "latency_ms": 100
        },
        {
            "pr_id": "pr2",
            "analysis_mode": "hybrid",
            "findings": [
                {"file": "test2.py", "line": 20, "category": "bug"}
            ],
            "latency_ms": 150
        }
    ]
    
    ground_truth = {
        "pr1": [
            {"file": "test1.py", "line": 10, "category": "security"}
        ],
        "pr2": [
            {"file": "test2.py", "line": 20, "category": "bug"}
        ]
    }
    
    metrics = compute_metrics_for_mode(results, ground_truth, "hybrid")
    
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["total_prs"] == 2
    assert metrics["avg_latency_ms"] == 125.0  # (100 + 150) / 2
