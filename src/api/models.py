"""
Pydantic models for API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AnalysisMode(str, Enum):
    """Analysis modes for code review."""
    STATIC_ONLY = "static_only"
    LLM_ONLY = "llm_only"
    HYBRID = "hybrid"


class JobState(str, Enum):
    """Job execution states."""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class Severity(str, Enum):
    """Severity levels for findings."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class FindingSummary(BaseModel):
    """Summary of a code finding."""
    rule_id: str
    severity: str
    message: str
    file_path: str
    line: int


class Finding(BaseModel):
    """A code finding from any tool (static analysis or LLM)."""
    tool_name: str = Field(..., description="Tool that generated this finding")
    rule_id: str = Field(..., description="Rule identifier")
    severity: Severity = Field(default=Severity.WARNING)
    file_path: str = Field(..., description="Relative path to the file")
    line: int = Field(..., description="Line number (1-based)")
    end_line: Optional[int] = Field(None, description="End line number")
    message: str = Field(..., description="Short description of the finding")
    suggestion: Optional[str] = Field(None, description="Suggested fix or improvement")
    confidence: float = Field(1.0, description="Confidence score (0.0-1.0)")

    def to_summary(self) -> "FindingSummary":
        """Convert to summary format."""
        return FindingSummary(
            rule_id=self.rule_id,
            severity=self.severity.value,
            message=self.message,
            file_path=self.file_path,
            line=self.line
        )


class PatchSummary(BaseModel):
    """Summary of a generated patch."""
    file_path: str
    rule_id: str
    applied: bool
    loc_changed: int
    risk_score: float


class ReviewRequest(BaseModel):
    """Request to create a new review job."""
    repo: str = Field(..., description="Repository in format 'owner/name'")
    base: str = Field(..., description="Base commit SHA")
    head: str = Field(..., description="Head commit SHA")
    pr: Optional[int] = Field(None, description="Pull request number")
    analysis_mode: Optional[AnalysisMode] = Field(None, description="Analysis mode to use")

    class Config:
        json_schema_extra = {
            "example": {
                "repo": "octocat/hello-world",
                "base": "abc123",
                "head": "def456",
                "pr": 42,
                "analysis_mode": "hybrid"
            }
        }


class ReviewResponse(BaseModel):
    """Response after creating a review job."""
    job_id: str = Field(..., description="Unique job identifier")
    state: JobState = Field(default=JobState.QUEUED)
    message: str = Field(default="Job queued for processing")


class JobStatusResponse(BaseModel):
    """Detailed job status."""
    job_id: str
    state: JobState
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Review details
    repo: str
    base_sha: str
    head_sha: str
    pr_number: Optional[int] = None
    analysis_mode: str = "hybrid"

    # Results
    findings_count: int = 0
    patches_generated: int = 0
    patches_applied: int = 0

    findings: List[FindingSummary] = []
    patches: List[PatchSummary] = []

    # Error details
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class PolicyConfig(BaseModel):
    """Policy configuration."""
    denylist: List[str] = Field(
        default=["auth/**", "secrets/**"],
        description="Path patterns to deny auto-fixing"
    )
    max_loc: int = Field(
        default=30,
        description="Maximum lines of code per patch"
    )
    auto_commit_threshold: float = Field(
        default=0.25,
        description="Risk threshold for auto-commit (0-1)"
    )
    max_files_per_patch: int = Field(
        default=3,
        description="Maximum files to modify per patch"
    )


class PolicyConfigResponse(BaseModel):
    """Response after updating policy."""
    success: bool
    message: str
    config: PolicyConfig


class WebhookPayload(BaseModel):
    """GitHub webhook payload (simplified)."""
    action: str
    repository: Dict[str, Any]
    pull_request: Optional[Dict[str, Any]] = None
    number: Optional[int] = None

    # Allow extra fields
    class Config:
        extra = "allow"