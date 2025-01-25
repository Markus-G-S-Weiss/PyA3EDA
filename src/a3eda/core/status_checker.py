from pathlib import Path
from typing import List
import logging
from .qchem_calculation import QChemCalculation
from .file_operations import FileOperations

class StatusChecker(FileOperations):
    """Class for checking calculation statuses."""
    def __init__(self, paths: List[Path], base_dir: Path):
        super().__init__(base_dir)
        self.paths = paths
        self.status_counts = {}

    def check_all_statuses(self):
        """Check and report status for all calculation paths."""
        system_dir = Path.cwd()
        max_path_length = max(len(str(path.relative_to(system_dir).parent / path.stem)) 
                            for path in self.paths)
        format_str = f"{{:<{max_path_length}}} | {{:<10}} | {{}}"
        
        for path in self.paths:
            relative_path = path.relative_to(system_dir).parent / path.stem
            if path.exists():
                qchem = QChemCalculation(path)
                status, details = qchem.check_status()
                self.status_counts[status] = self.status_counts.get(status, 0) + 1
                logging.info(format_str.format(str(relative_path), status, details))
            else:
                status = 'absent'
                self.status_counts[status] = self.status_counts.get(status, 0) + 1
                logging.info(format_str.format(str(relative_path), status, 'Input file not found'))
        
        self._print_summary()

    def _print_summary(self):
        """Print summary of calculation statuses."""
        logging.info("\nStatus Summary:")
        max_status_length = max(len(status) for status in self.status_counts.keys())
        summary_format = f"{{:<{max_status_length}}} : {{:>4}} calculations"
        for status, count in self.status_counts.items():
            logging.info(summary_format.format(status, count))
