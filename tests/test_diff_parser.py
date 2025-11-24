"""
Unit tests for diff_parser module.
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from src.analysis.diff_parser import FileDiff, DiffParser


class TestFileDiff:
    """Test FileDiff model."""
    
    def test_file_diff_creation(self):
        """Test creating a FileDiff instance."""
        diff = FileDiff(
            file_path="test.py",
            change_type="M",
            added_lines=[(1, "print('hello')"), (2, "print('world')")],
            removed_lines=[(1, "pass")],
            new_content="print('hello')\nprint('world')"
        )
        
        assert diff.file_path == "test.py"
        assert diff.change_type == "M"
        assert len(diff.added_lines) == 2
        assert len(diff.removed_lines) == 1
        assert diff.new_content is not None


class TestDiffParser:
    """Test DiffParser class."""
    
    def test_parse_unified_diff_simple(self):
        """Test parsing a simple unified diff."""
        diff_text = """@@ -1,2 +1,3 @@
 import os
-print('old')
+print('new')
+print('added')
"""
        added, removed = DiffParser._parse_unified_diff(diff_text)
        
        assert len(added) == 2
        assert len(removed) == 1
        # Line numbers: first hunk @@ -1,2 +1,3 @@ starts at new line 1
        # "import os" is context at line 1
        # "print('new')" is added at line 2
        # "print('added')" is added at line 3
        assert (2, "print('new')") in added
        assert (3, "print('added')") in added
        assert (2, "print('old')") in removed
    
    def test_parse_unified_diff_multiple_hunks(self):
        """Test parsing diff with multiple hunks."""
        diff_text = """@@ -1,2 +1,2 @@
 import os
-old_line
+new_line
@@ -10,3 +10,4 @@
 def foo():
     pass
+    return True
"""
        added, removed = DiffParser._parse_unified_diff(diff_text)
        
        assert len(added) == 2
        assert len(removed) == 1
        # Check line numbers are tracked correctly
        assert any(line_no == 2 for line_no, _ in added)  # Line 2 in first hunk
        assert any(line_no == 12 for line_no, _ in added)  # Line 12 in second hunk
    
    @patch('src.analysis.diff_parser.Repo')
    def test_get_pr_diff_modified_file(self, mock_repo_class):
        """Test getting PR diff for modified files."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        # Mock commits
        mock_base_commit = MagicMock()
        mock_head_commit = MagicMock()
        mock_repo.commit.side_effect = lambda sha: mock_base_commit if sha == "base123" else mock_head_commit
        
        # Mock diff object
        mock_diff = MagicMock()
        mock_diff.new_file = False
        mock_diff.deleted_file = False
        mock_diff.renamed_file = False
        mock_diff.b_path = "test.py"
        mock_diff.a_path = "test.py"
        mock_diff.diff = b"""@@ -1,1 +1,2 @@
 import os
+print('hello')
"""
        # Mock blob for file content
        mock_blob = MagicMock()
        mock_blob.data_stream.read.return_value = b"import os\nprint('hello')"
        mock_diff.b_blob = mock_blob
        
        mock_base_commit.diff.return_value = [mock_diff]
        
        # Test
        diffs = DiffParser.get_pr_diff("/fake/repo", "base123", "head123")
        
        assert len(diffs) == 1
        assert diffs[0].file_path == "test.py"
        assert diffs[0].change_type == "M"
        assert len(diffs[0].added_lines) == 1
        assert diffs[0].new_content == "import os\nprint('hello')"
    
    @patch('src.analysis.diff_parser.Repo')
    def test_get_pr_diff_new_file(self, mock_repo_class):
        """Test getting PR diff for new files."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_base_commit = MagicMock()
        mock_head_commit = MagicMock()
        mock_repo.commit.side_effect = lambda sha: mock_base_commit if sha == "base" else mock_head_commit
        
        mock_diff = MagicMock()
        mock_diff.new_file = True
        mock_diff.deleted_file = False
        mock_diff.renamed_file = False
        mock_diff.b_path = "new_file.py"
        mock_diff.diff = b"""@@ -0,0 +1,2 @@
+def hello():
+    pass
"""
        mock_blob = MagicMock()
        mock_blob.data_stream.read.return_value = b"def hello():\n    pass"
        mock_diff.b_blob = mock_blob
        
        mock_base_commit.diff.return_value = [mock_diff]
        
        diffs = DiffParser.get_pr_diff("/fake/repo", "base", "head")
        
        assert len(diffs) == 1
        assert diffs[0].file_path == "new_file.py"
        assert diffs[0].change_type == "A"
    
    @patch('src.analysis.diff_parser.Repo')
    def test_get_pr_diff_skips_deleted_files(self, mock_repo_class):
        """Test that deleted files are skipped."""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        mock_base_commit = MagicMock()
        mock_head_commit = MagicMock()
        mock_repo.commit.side_effect = lambda sha: mock_base_commit if sha == "base" else mock_head_commit
        
        mock_diff = MagicMock()
        mock_diff.new_file = False
        mock_diff.deleted_file = True
        mock_diff.b_path = "deleted.py"
        
        mock_base_commit.diff.return_value = [mock_diff]
        
        diffs = DiffParser.get_pr_diff("/fake/repo", "base", "head")
        
        assert len(diffs) == 0
