"""
Wrappers for static analysis tools (Semgrep, Bandit).
"""
import structlog
import subprocess
import json
import os
from typing import List
from src.api.models import Finding, Severity

logger = structlog.get_logger()

class StaticAnalyzer:
    """Runs static analysis tools."""

    @staticmethod
    def run_semgrep(repo_path: str) -> List[Finding]:
        """
        Run Semgrep on the repository.
        """
        findings = []
        try:
            # Run semgrep with json output
            # We use a basic security config for now
            cmd = [
                "semgrep",
                "--config=p/security-audit",
                "--json",
                "--quiet",
                repo_path
            ]
            
            logger.info("running_semgrep", path=repo_path)
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0 and result.stderr:
                logger.warning("semgrep_error", error=result.stderr)
                # Semgrep might exit with 1 if findings are found, so we check stdout too
            
            if not result.stdout:
                return []

            data = json.loads(result.stdout)
            
            for result in data.get("results", []):
                path = result.get("path", "")
                # Normalize path relative to repo root
                if path.startswith(repo_path):
                    path = os.path.relpath(path, repo_path)
                
                findings.append(Finding(
                    tool_name="semgrep",
                    rule_id=result.get("check_id", "unknown"),
                    severity=Severity.WARNING, # Map semgrep severity if needed
                    file_path=path,
                    line=result.get("start", {}).get("line", 1),
                    end_line=result.get("end", {}).get("line", 1),
                    message=result.get("extra", {}).get("message", "Potential issue found"),
                    suggestion=result.get("extra", {}).get("fix", None)
                ))
                
        except Exception as e:
            logger.error("semgrep_failed", error=str(e))
            
        return findings

    @staticmethod
    def run_bandit(repo_path: str) -> List[Finding]:
        """
        Run Bandit on the repository (Python only).
        """
        findings = []
        try:
            # Run bandit with json output
            cmd = [
                "bandit",
                "-r",
                repo_path,
                "-f", "json",
                "-q"
            ]
            
            logger.info("running_bandit", path=repo_path)
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Bandit returns exit code 1 if issues are found
            
            if not result.stdout:
                return []

            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.warning("bandit_invalid_json", output=result.stdout)
                return []
            
            for result in data.get("results", []):
                path = result.get("filename", "")
                if path.startswith(repo_path):
                    path = os.path.relpath(path, repo_path)
                    
                findings.append(Finding(
                    tool_name="bandit",
                    rule_id=result.get("test_id", "unknown"),
                    severity=Severity.ERROR if result.get("issue_severity") == "HIGH" else Severity.WARNING,
                    file_path=path,
                    line=result.get("line_number", 1),
                    message=result.get("issue_text", "Security issue found"),
                    confidence=1.0 if result.get("issue_confidence") == "HIGH" else 0.5
                ))
                
        except Exception as e:
            logger.error("bandit_failed", error=str(e))
            
        return findings
