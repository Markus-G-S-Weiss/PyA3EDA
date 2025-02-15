import sys
import logging
from pathlib import Path
from typing import List
from .file_operations import FileOperations
from .constants import Constants

class FileHandler(FileOperations):
    """Class for handling file operations with path sanitization."""
    @staticmethod
    def sanitize_filename(name: str) -> str:
        sanitized = name
        for char, replacement in Constants.ESCAPE_MAP.items():
            sanitized = sanitized.replace(char, replacement)
        return sanitized

    def verify_templates(self, required_templates: List[Path]) -> None:
        """Ensure all required template files exist."""
        missing_templates = [t for t in required_templates if not t.is_file()]
        if missing_templates:
            for tmpl in missing_templates:
                logging.error(f'Missing template file: {tmpl}')
            sys.exit(1)

    def create_directory_structure(self, base_dir: Path, paths: List[str]) -> None:
        """Create directory structures with sanitized path names."""
        for path in paths:
            # Split path and sanitize each component
            components = [self.sanitize_filename(p) for p in path.split('/')]
            dir_path = base_dir / Path(*components)
            dir_path.mkdir(parents=True, exist_ok=True)

