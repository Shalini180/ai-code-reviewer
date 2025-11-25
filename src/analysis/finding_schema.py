"""
Normalized finding schema for evaluation and metrics.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from src.api.models import Finding, Severity
import hashlib


class NormalizedFinding(BaseModel):
    """Unified finding format for evaluation across all analysis modes."""
    
    id: str = Field(..., description="Unique identifier for this finding")
    source: Literal["static", "llm", "hybrid"] = Field(..., description="Origin of the finding")
    file: str = Field(..., description="File path relative to repo root")
    line: int = Field(..., description="Line number (1-based)")
    severity: Literal["LOW", "MEDIUM", "HIGH"] = Field(..., description="Severity level")
    category: Literal["security", "bug", "style", "performance", "other"] = Field(
        ..., description="Issue category"
    )
    message: str = Field(..., description="Human-readable explanation")
    suggested_fix: Optional[str] = Field(None, description="Optional suggested improvement")


def finding_to_normalized(finding: Finding, source: Literal["static", "llm", "hybrid"]) -> NormalizedFinding:
    """
    Convert a Finding object to NormalizedFinding format.
    
    Args:
        finding: Original Finding object
        source: The source of the finding (static, llm, or hybrid)
        
    Returns:
        NormalizedFinding: Converted finding in normalized format
    """
    # Generate unique ID based on file, line, and rule
    id_string = f"{finding.file_path}:{finding.line}:{finding.rule_id}"
    finding_id = hashlib.md5(id_string.encode()).hexdigest()[:12]
    
    # Map severity
    severity_map = {
        Severity.INFO: "LOW",
        Severity.WARNING: "MEDIUM",
        Severity.ERROR: "HIGH"
    }
    severity = severity_map.get(finding.severity, "MEDIUM")
    
    # Infer category from rule_id and tool_name
    category = infer_category(finding.rule_id, finding.tool_name, finding.message)
    
    return NormalizedFinding(
        id=finding_id,
        source=source,
        file=finding.file_path,
        line=finding.line,
        severity=severity,
        category=category,
        message=finding.message,
        suggested_fix=finding.suggestion
    )


def infer_category(
    rule_id: str, 
    tool_name: str, 
    message: str
) -> Literal["security", "bug", "style", "performance", "other"]:
    """
    Infer the category of a finding based on its metadata.
    
    Args:
        rule_id: The rule identifier
        tool_name: The name of the tool that generated the finding
        message: The finding message
        
    Returns:
        Category string
    """
    rule_lower = rule_id.lower()
    message_lower = message.lower()
    
    # Security indicators
    security_keywords = [
        "security", "vulnerability", "injection", "xss", "csrf", "auth",
        "password", "token", "secret", "crypto", "sql", "command",
        "hardcoded", "unsafe", "exploit"
    ]
    
    # Bug indicators
    bug_keywords = [
        "error", "exception", "null", "undefined", "race", "deadlock",
        "leak", "overflow", "underflow", "assert", "crash"
    ]
    
    # Style indicators
    style_keywords = [
        "style", "format", "lint", "convention", "naming", "whitespace",
        "complexity", "unused", "import"
    ]
    
    # Performance indicators
    performance_keywords = [
        "performance", "slow", "inefficient", "optimize", "cache",
        "memory", "cpu", "loop", "n+1", "query"
    ]
    
    # Check for security
    if tool_name in ["semgrep", "bandit"] or any(kw in rule_lower or kw in message_lower for kw in security_keywords):
        return "security"
    
    # Check for performance
    if any(kw in rule_lower or kw in message_lower for kw in performance_keywords):
        return "performance"
    
    # Check for style
    if any(kw in rule_lower or kw in message_lower for kw in style_keywords):
        return "style"
    
    # Check for bugs
    if any(kw in rule_lower or kw in message_lower for kw in bug_keywords):
        return "bug"
    
    # Default to other
    return "other"
