import logging
from pathlib import Path
from typing import Optional

class FileOperations:
    """Base class for file operations."""
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def read_file(self, file_path: Path) -> Optional[str]:
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore").rstrip()
        except Exception as e:
            logging.error(f"Error reading file '{file_path}': {e}")
            return None

    def write_file(self, file_path: Path, content: str) -> bool:
        try:
            file_path.write_text(content)
            return True
        except Exception as e:
            logging.error(f"Error writing file '{file_path}': {e}")
            return False
