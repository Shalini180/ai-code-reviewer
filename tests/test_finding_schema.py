"""
Tests for finding schema conversion and normalization.
"""
import pytest
from src.api.models import Finding, Severity
from src.analysis.finding_schema import (
    NormalizedFinding,
    finding_to_normalized,
    infer_category
)


def test_finding_to_normalized_basic():
    """Test basic conversion from Finding to NormalizedFinding."""
    finding = Finding(
        tool_name="semgrep",
        rule_id="python.security.sql-injection",
        severity=Severity.ERROR,
        file_path="app/db.py",
        line=42,
        message="Potential SQL injection vulnerability",
        suggestion="Use parameterized queries"
    )
    
    normalized = finding_to_normalized(finding, "static")
    
    assert normalized.source == "static"
    assert normalized.file == "app/db.py"
    assert normalized.line == 42
    assert normalized.severity == "HIGH"
    assert normalized.category == "security"
    assert normalized.message == "Potential SQL injection vulnerability"
    assert normalized.suggested_fix == "Use parameterized queries"
    assert len(normalized.id) == 12  # MD5 hash truncated to 12 chars


def test_finding_to_normalized_severity_mapping():
    """Test severity level mapping."""
    # Test INFO -> LOW
    finding_info = Finding(
        tool_name="llm",
        rule_id="style-001",
        severity=Severity.INFO,
        file_path="test.py",
        line=1,
        message="Style issue"
    )
    normalized_info = finding_to_normalized(finding_info, "llm")
    assert normalized_info.severity == "LOW"
    
    # Test WARNING -> MEDIUM
    finding_warning = Finding(
        tool_name="llm",
        rule_id="bug-001",
        severity=Severity.WARNING,
        file_path="test.py",
        line=2,
        message="Potential bug"
    )
    normalized_warning = finding_to_normalized(finding_warning, "llm")
    assert normalized_warning.severity == "MEDIUM"
    
    # Test ERROR -> HIGH
    finding_error = Finding(
        tool_name="bandit",
        rule_id="B101",
        severity=Severity.ERROR,
        file_path="test.py",
        line=3,
        message="Security issue"
    )
    normalized_error = finding_to_normalized(finding_error, "static")
    assert normalized_error.severity == "HIGH"


def test_infer_category_security():
    """Test security category inference."""
    assert infer_category("python.security.sql-injection", "semgrep", "SQL injection") == "security"
    assert infer_category("B201", "bandit", "Hardcoded password found") == "security"
    assert infer_category("security-001", "llm", "Potential XSS vulnerability") == "security"


def test_infer_category_bug():
    """Test bug category inference."""
    assert infer_category("null-check", "llm", "Potential null reference error") == "bug"
    assert infer_category("exception-handling", "static", "Unhandled exception") == "bug"


def test_infer_category_style():
    """Test style category inference."""
    assert infer_category("formatting", "llm", "Inconsistent style formatting") == "style"
    assert infer_category("unused-import", "static", "Unused import detected") == "style"


def test_infer_category_performance():
    """Test performance category inference."""
    assert infer_category("perf-001", "llm", "Inefficient loop detected") == "performance"
    assert infer_category("optimize", "static", "This query is slow") == "performance"


def test_infer_category_other():
    """Test other category as fallback."""
    assert infer_category("custom-rule", "llm", "Some other issue") == "other"


def test_finding_id_uniqueness():
    """Test that finding IDs are unique based on file, line, and rule."""
    finding1 = Finding(
        tool_name="semgrep",
        rule_id="rule-1",
        severity=Severity.WARNING,
        file_path="file1.py",
        line=10,
        message="Issue"
    )
    
    finding2 = Finding(
        tool_name="semgrep",
        rule_id="rule-1",
        severity=Severity.WARNING,
        file_path="file1.py",
        line=20,  # Different line
        message="Issue"
    )
    
    finding3 = Finding(
        tool_name="semgrep",
        rule_id="rule-2",  # Different rule
        severity=Severity.WARNING,
        file_path="file1.py",
        line=10,
        message="Issue"
    )
    
    norm1 = finding_to_normalized(finding1, "static")
    norm2 = finding_to_normalized(finding2, "static")
    norm3 = finding_to_normalized(finding3, "static")
    
    # Different lines should have different IDs
    assert norm1.id != norm2.id
    
    # Different rules should have different IDs
    assert norm1.id != norm3.id
    
    # Same finding should have same ID
    norm1_duplicate = finding_to_normalized(finding1, "static")
    assert norm1.id == norm1_duplicate.id


def test_normalized_finding_model_validation():
    """Test Pydantic model validation."""
    # Valid finding
    valid_finding = NormalizedFinding(
        id="abc123",
        source="static",
        file="test.py",
        line=1,
        severity="MEDIUM",
        category="security",
        message="Test message"
    )
    assert valid_finding.id == "abc123"
    
    # Invalid source
    with pytest.raises(ValueError):
        NormalizedFinding(
            id="abc123",
            source="invalid",  # Not in Literal["static", "llm", "hybrid"]
            file="test.py",
            line=1,
            severity="MEDIUM",
            category="security",
            message="Test"
        )
    
    # Invalid severity
    with pytest.raises(ValueError):
        NormalizedFinding(
            id="abc123",
            source="static",
            file="test.py",
            line=1,
            severity="CRITICAL",  # Not in Literal["LOW", "MEDIUM", "HIGH"]
            category="security",
            message="Test"
        )
    
    # Invalid category
    with pytest.raises(ValueError):
        NormalizedFinding(
            id="abc123",
            source="static",
            file="test.py",
            line=1,
            severity="MEDIUM",
            category="unknown",  # Not in valid categories
            message="Test"
        )
