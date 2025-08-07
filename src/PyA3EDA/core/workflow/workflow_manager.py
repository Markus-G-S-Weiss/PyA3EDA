"""
WorkflowManager

Orchestrates the workflow for PyA3EDA.
"""

import logging
from pathlib import Path
from PyA3EDA.core.config.config_manager import ConfigManager

class WorkflowManager:
    def __init__(self, config_manager: ConfigManager, args=None) -> None:
        self.config_manager = config_manager
        self.system_dir = config_manager.config_dir
        self.args = args

    def generate_inputs(self) -> None:
        """
        Delegate input file generation to the builder.
        """
        from PyA3EDA.core.builders import builder
        
        # Extract arguments with safe defaults
        overwrite = getattr(self.args, 'overwrite', None) if self.args else None
        sp_strategy = getattr(self.args, 'sp_strategy', 'smart') if self.args else 'smart'
        
        builder.generate_all_inputs(self.config_manager, self.system_dir, overwrite, sp_strategy)

    def run_calculations(self) -> None:
        """
        Run calculations based on the specified run criteria.
        """
        from PyA3EDA.core.runners.executor import run_all_calculations
        
        # Extract run criteria from args with safe defaults
        run_criteria = getattr(self.args, 'run', None) if self.args else None
        
        run_all_calculations(
            self.config_manager,
            self.system_dir,
            run_criteria
        )

    def check_status(self) -> None:
        """
        Uses the status checker to iterate over expected input paths and
        prints a formatted status report and summary.
        """
        from PyA3EDA.core.status.status_checker import check_all_statuses
        check_all_statuses(self.config_manager, self.system_dir)

    def extract_data(self) -> None:
        """
        Extract and export data.
        """
        from PyA3EDA.core.extractors.data_extractor import extract_all_data
        
        criteria = getattr(self.args, 'extract', None) if self.args else "SUCCESSFUL"
        
        # Single function call - extractor handles everything
        extract_all_data(self.config_manager, self.system_dir, criteria)
