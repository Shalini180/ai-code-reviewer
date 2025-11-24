"""
Parses Git diffs into structured objects for analysis.
"""
import structlog
from typing import List, Optional, Tuple
from pydantic import BaseModel
from git import Repo, Diff

logger = structlog.get_logger()

class FileDiff(BaseModel):
    """Represents the diff of a single file."""
    file_path: str
    change_type: str  # 'A' (added), 'M' (modified), 'D' (deleted), 'R' (renamed)
    added_lines: List[Tuple[int, str]] = []  # List of (line_number, content)
    removed_lines: List[Tuple[int, str]] = [] # List of (line_number, content)
    new_content: Optional[str] = None # Full content of the file after changes (if available)

class DiffParser:
    """Parses git diffs."""

    @staticmethod
    def get_pr_diff(repo_path: str, base_sha: str, head_sha: str) -> List[FileDiff]:
        """
        Get the diff between two commits.
        
        Args:
            repo_path: Path to the repository
            base_sha: Base commit SHA
            head_sha: Head commit SHA
            
        Returns:
            List[FileDiff]: List of changed files and their diffs
        """
        repo = Repo(repo_path)
        
        # Get diff objects from GitPython
        # create_patch=True ensures we get the diff text
        diffs = repo.commit(base_sha).diff(repo.commit(head_sha), create_patch=True)
        
        parsed_diffs = []
        
        for d in diffs:
            # Skip deleted files for now as we can't review them
            if d.deleted_file:
                continue
                
            file_path = d.b_path if d.b_path else d.a_path
            
            # Determine change type
            if d.new_file:
                change_type = 'A'
            elif d.deleted_file:
                change_type = 'D'
            elif d.renamed_file:
                change_type = 'R'
            else:
                change_type = 'M'
                
            # Parse the unified diff string to find added/removed lines
            # GitPython provides the diff as bytes, need to decode
            diff_text = d.diff.decode('utf-8', errors='replace') if d.diff else ""
            
            added_lines, removed_lines = DiffParser._parse_unified_diff(diff_text)
            
            # Get full content of the new file for context
            try:
                # We can read the file from disk since we should have checked out head_sha
                # But wait, the worker might have checked out head_sha already?
                # If not, we can read from the blob
                new_content = d.b_blob.data_stream.read().decode('utf-8', errors='replace')
            except Exception:
                new_content = None

            parsed_diffs.append(FileDiff(
                file_path=file_path,
                change_type=change_type,
                added_lines=added_lines,
                removed_lines=removed_lines,
                new_content=new_content
            ))
            
        return parsed_diffs

    @staticmethod
    def _parse_unified_diff(diff_text: str) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]:
        """
        Parse a unified diff string to extract line numbers and content.
        
        Returns:
            Tuple of (added_lines, removed_lines)
            Each is a list of (line_number, content)
        """
        added = []
        removed = []
        
        # Simple parser for unified diff
        # @@ -1,2 +1,2 @@
        
        current_old_line = 0
        current_new_line = 0
        
        lines = diff_text.split('\n')
        for line in lines:
            if line.startswith('@@'):
                # Parse header: @@ -old_start,old_len +new_start,new_len @@
                # Example: @@ -10,5 +10,6 @@
                try:
                    parts = line.split(' ')
                    # parts[1] is -old
                    # parts[2] is +new
                    
                    old_info = parts[1].lstrip('-')
                    new_info = parts[2].lstrip('+')
                    
                    current_old_line = int(old_info.split(',')[0]) if ',' in old_info else int(old_info)
                    current_new_line = int(new_info.split(',')[0]) if ',' in new_info else int(new_info)
                except ValueError:
                    continue
                    
            elif line.startswith('+') and not line.startswith('+++'):
                added.append((current_new_line, line[1:]))
                current_new_line += 1
            elif line.startswith('-') and not line.startswith('---'):
                removed.append((current_old_line, line[1:]))
                current_old_line += 1
            elif not line.startswith('\\'): # Skip "No newline at end of file"
                current_old_line += 1
                current_new_line += 1
                
        return added, removed
