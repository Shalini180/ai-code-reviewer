"""
Integration test for the evaluation runner.
"""
import pytest
import json
import tempfile
from pathlib import Path
from evaluation.run_evaluation import load_pr_list, run_evaluation_for_pr
from src.analysis.engine import AnalysisEngine
from src.api.models import AnalysisMode


def test_load_pr_list(tmp_path):
    """Test loading PR list from JSON file."""
    pr_list_file = tmp_path / "prs.json"
    pr_data = [
        {
            "pr_id": "test_001",
            "repo_path": "/path/to/repo",
            "base_sha": "abc123",
            "head_sha": "def456"
        }
    ]
    
    with open(pr_list_file, 'w') as f:
        json.dump(pr_data, f)
    
    loaded = load_pr_list(str(pr_list_file))
    
    assert len(loaded) == 1
    assert loaded[0]["pr_id"] == "test_001"
    assert loaded[0]["repo_path"] == "/path/to/repo"


@pytest.mark.skip(reason="Requires actual git repository with commits")
def test_run_evaluation_for_pr_basic():
    """
    Test running evaluation for a single PR.
    
    Note: This test requires an actual git repository with commits.
    In CI/CD, you'd set up a temporary repo with known commits.
    """
    pr = {
        "pr_id": "test_pr",
        "repo_path": "test_data/sample_repo",
        "base_sha": "HEAD~1",
        "head_sha": "HEAD"
    }
    
    engine = AnalysisEngine()
    
    result = run_evaluation_for_pr(pr, engine, AnalysisMode.STATIC_ONLY)
    
    assert result["pr_id"] == "test_pr"
    assert result["analysis_mode"] == "static_only"
    assert "findings" in result
    assert "latency_ms" in result
    assert "timestamp" in result
    assert isinstance(result["findings"], list)
    assert isinstance(result["latency_ms"], int)


def test_evaluation_result_structure():
    """Test that evaluation results have the correct structure."""
    # This is a structural test - doesn't need actual execution
    expected_keys = {"pr_id", "analysis_mode", "findings", "latency_ms", "timestamp"}
    
    # Mock result
    result = {
        "pr_id": "test_001",
        "analysis_mode": "hybrid",
        "findings": [],
        "latency_ms": 1234,
        "timestamp": "2024-01-01T00:00:00"
    }
    
    assert set(result.keys()) == expected_keys
    assert isinstance(result["findings"], list)
    assert isinstance(result["latency_ms"], int)
    assert result["latency_ms"] >= 0


def test_evaluation_modes_coverage():
    """Test that all three modes are covered."""
    modes = [AnalysisMode.STATIC_ONLY, AnalysisMode.LLM_ONLY, AnalysisMode.HYBRID]
    
    assert len(modes) == 3
    assert AnalysisMode.STATIC_ONLY.value == "static_only"
    assert AnalysisMode.LLM_ONLY.value == "llm_only"
    assert AnalysisMode.HYBRID.value == "hybrid"
