"""
WorkflowManager

Orchestrates the input file generation workflow for PyA3EDA.
"""

import logging
from pathlib import Path
from PyA3EDA.core.config.config_manager import ConfigManager

class WorkflowManager:
    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self.system_dir = Path.cwd()

    def generate_inputs(self) -> None:
        """
        Delegate input file generation to the builder.
        """
        from PyA3EDA.core.builders import builder
        builder.generate_all_inputs(self.config_manager.sanitized_config, self.system_dir)

    def run_calculations(self) -> None:
        logging.info("Calculation submission not implemented.")

    def check_status(self) -> None:
        """
        Uses the status checker to iterate over expected input paths and
        prints a formatted status report and summary.
        """
        from PyA3EDA.core.status.status_checker import check_all_statuses
        check_all_statuses(self.config_manager.sanitized_config, self.system_dir)

    def extract_data(self) -> None:
         logging.info("Data extraction not implemented.")
