"""
LLM client for code review using Anthropic.
"""
import structlog
import json
from typing import List, Optional
from anthropic import Anthropic
from config.settings import settings
from src.api.models import Finding, Severity
from src.analysis.diff_parser import FileDiff

logger = structlog.get_logger()

class LLMReviewer:
    """AI Code Reviewer using Anthropic."""

    def __init__(self):
        self.mock_reviewer = None
        if not settings.use_real_apis:
            from src.integrations.mock_llm import MockLLMReviewer
            self.mock_reviewer = MockLLMReviewer()
            return

        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    def review_diff(self, diffs: List[FileDiff], static_findings: List[Finding]) -> List[Finding]:
        """
        Review the diffs using LLM, incorporating static analysis context.
        """
        if self.mock_reviewer:
            return self.mock_reviewer.review_diff(diffs, static_findings)

        findings = []
        
        # Filter for relevant files (e.g., Python)
        # For now, we review everything text-based
        
        for diff in diffs:
            if diff.change_type == 'D':
                continue
                
            # Prepare context for this file
            file_findings = [f for f in static_findings if f.file_path == diff.file_path]
            
            # Skip if no content (binary or deleted)
            if not diff.new_content and not diff.added_lines:
                continue

            try:
                file_findings_llm = self._analyze_file(diff, file_findings)
                findings.extend(file_findings_llm)
            except Exception as e:
                logger.error("llm_review_failed", file=diff.file_path, error=str(e))
                
        return findings

    def _analyze_file(self, diff: FileDiff, static_findings: List[Finding]) -> List[Finding]:
        """Analyze a single file diff."""
        
        # Construct prompt
        prompt = self._build_prompt(diff, static_findings)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        content = response.content[0].text
        return self._parse_response(content, diff.file_path)

    def _build_prompt(self, diff: FileDiff, static_findings: List[Finding]) -> str:
        """Build the prompt for the LLM."""
        
        static_context = ""
        if static_findings:
            static_context = "Static Analysis Findings (verify these):\n"
            for f in static_findings:
                static_context += f"- Line {f.line}: {f.message} ({f.rule_id})\n"
        
        # We provide the full new content if available, or just the diff
        code_context = ""
        if diff.new_content:
            code_context = f"File Content:\n```\n{diff.new_content}\n```"
        else:
            code_context = "Diff:\n"
            for line_num, content in diff.added_lines:
                code_context += f"+ {line_num}: {content}\n"
                
        return f"""
You are a senior code reviewer. Analyze the following code changes for bugs, security vulnerabilities, and code quality issues.

File: {diff.file_path}

{static_context}

{code_context}

Instructions:
1. Focus on the CHANGED lines (marked with + in diff or context).
2. Verify any static analysis findings. If they are false positives, ignore them.
3. Look for logical errors, race conditions, and security flaws that static analysis might miss.
4. Provide your output STRICTLY in JSON format as a list of objects.
5. Do not include conversational text.

Format:
[
  {{
    "rule_id": "short-id",
    "severity": "warning|error",
    "line": <line_number>,
    "message": "description",
    "suggestion": "optional fix code"
  }}
]
"""

    def _parse_response(self, content: str, file_path: str) -> List[Finding]:
        """Parse LLM JSON response."""
        findings = []
        try:
            # Extract JSON from potential markdown blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            data = json.loads(content.strip())
            
            if isinstance(data, list):
                for item in data:
                    findings.append(Finding(
                        tool_name="claude-ai",
                        rule_id=item.get("rule_id", "ai-review"),
                        severity=Severity(item.get("severity", "warning").lower()),
                        file_path=file_path,
                        line=item.get("line", 1),
                        message=item.get("message", "Issue found"),
                        suggestion=item.get("suggestion"),
                        confidence=0.8 # AI is probabilistic
                    ))
        except Exception as e:
            logger.error("llm_parse_failed", error=str(e), content=content[:100])
            
        return findings
