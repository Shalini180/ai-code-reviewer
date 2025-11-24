"""
Unit tests for static analysis module.
"""
import pytest
import json
from unittest.mock import MagicMock, patch, Mock
from src.analysis.static import StaticAnalyzer
from src.api.models import Finding, Severity


class TestStaticAnalyzer:
    """Test StaticAnalyzer class."""
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_semgrep_success(self, mock_run):
        """Test successful Semgrep execution."""
        # Mock subprocess output
        semgrep_output = {
            "results": [
                {
                    "path": "/tmp/repo/test.py",
                    "check_id": "python.lang.security.audit.dangerous-function",
                    "start": {"line": 5},
                    "end": {"line": 5},
                    "extra": {
                        "message": "Dangerous function usage detected",
                        "fix": "Use safer alternative"
                    }
                }
            ]
        }
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(semgrep_output)
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Test
        findings = StaticAnalyzer.run_semgrep("/tmp/repo")
        
        assert len(findings) == 1
        assert findings[0].tool_name == "semgrep"
        assert findings[0].rule_id == "python.lang.security.audit.dangerous-function"
        assert findings[0].file_path == "test.py"  # Should be relative
        assert findings[0].line == 5
        assert "Dangerous function" in findings[0].message
        
        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "semgrep" in call_args
        assert "--config=p/security-audit" in call_args
        assert "--json" in call_args
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_semgrep_no_findings(self, mock_run):
        """Test Semgrep with no findings."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"results": []})
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        findings = StaticAnalyzer.run_semgrep("/tmp/repo")
        
        assert len(findings) == 0
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_semgrep_error(self, mock_run):
        """Test Semgrep error handling."""
        mock_result = MagicMock()
        mock_result.returncode = 2  # Error exit code
        mock_result.stdout = ""
        mock_result.stderr = "Semgrep error"
        mock_run.return_value = mock_result
        
        findings = StaticAnalyzer.run_semgrep("/tmp/repo")
        
        # Should return empty list on error
        assert len(findings) == 0
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_semgrep_json_parse_error(self, mock_run):
        """Test Semgrep with invalid JSON output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Should handle exception and return empty list
        findings = StaticAnalyzer.run_semgrep("/tmp/repo")
        assert len(findings) == 0
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_bandit_success(self, mock_run):
        """Test successful Bandit execution."""
        bandit_output = {
            "results": [
                {
                    "filename": "/tmp/repo/module/auth.py",
                    "test_id": "B301",
                    "line_number": 42,
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "issue_text": "Use of pickle detected"
                },
                {
                    "filename": "/tmp/repo/utils.py",
                    "test_id": "B101",
                    "line_number": 10,
                    "issue_severity": "MEDIUM",
                    "issue_confidence": "MEDIUM",
                    "issue_text": "Assert used"
                }
            ]
        }
        
        mock_result = MagicMock()
        mock_result.returncode = 1  # Bandit returns 1 if issues found
        mock_result.stdout = json.dumps(bandit_output)
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        findings = StaticAnalyzer.run_bandit("/tmp/repo")
        
        assert len(findings) == 2
        
        # Check first finding (HIGH severity)
        # Use normpath to handle Windows path separators
        import os
        expected_path = os.path.normpath("module/auth.py")
        
        assert findings[0].tool_name == "bandit"
        assert findings[0].rule_id == "B301"
        assert findings[0].file_path == expected_path
        assert findings[0].line == 42
        assert findings[0].severity == Severity.ERROR
        assert findings[0].confidence == 1.0
        
        # Check second finding (MEDIUM severity)
        assert findings[1].severity == Severity.WARNING
        assert findings[1].confidence == 0.5
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_bandit_no_findings(self, mock_run):
        """Test Bandit with no findings."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"results": []})
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        findings = StaticAnalyzer.run_bandit("/tmp/repo")
        
        assert len(findings) == 0
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_bandit_invalid_json(self, mock_run):
        """Test Bandit with invalid JSON."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        findings = StaticAnalyzer.run_bandit("/tmp/repo")
        
        assert len(findings) == 0
    
    @patch('src.analysis.static.subprocess.run')
    def test_run_bandit_exception(self, mock_run):
        """Test Bandit with subprocess exception."""
        mock_run.side_effect = Exception("Command failed")
        
        findings = StaticAnalyzer.run_bandit("/tmp/repo")
        
        # Should handle exception gracefully
        assert len(findings) == 0
