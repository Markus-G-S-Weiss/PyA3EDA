"""
WorkflowManager

Orchestrates the input file generation workflow for PyA3EDA.
"""

import logging
from pathlib import Path
from PyA3EDA.core.config.config_manager import ConfigManager

class WorkflowManager:
    def __init__(self, config_manager: ConfigManager, args=None) -> None:
        self.config_manager = config_manager
        self.system_dir = Path.cwd()
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
        from PyA3EDA.core.builders.builder import iter_input_paths
        from PyA3EDA.core.status.status_checker import should_process_file
        from PyA3EDA.core.runners.executor import execute_qchem
        
        # Extract run criteria from args with safe defaults
        run_criteria = getattr(self.args, 'run', None) if self.args else None
        
        if not run_criteria:
            logging.warning("No run criteria specified. Use --run option with a valid criteria.")
            return
        
        logging.info(f"Running calculations with criteria: {run_criteria}")
        
        # Get all input paths and process them based on criteria
        count = 0
        for input_path in iter_input_paths(self.config_manager.processed_config, self.system_dir):
            if not input_path.exists():
                continue
            
            should_run, reason = should_process_file(input_path, run_criteria)
                
            if should_run:
                logging.info(f"Submitting job ({reason}): {input_path.relative_to(self.system_dir)}")
                if execute_qchem(input_path):
                    count += 1
        
        logging.info(f"Total jobs submitted: {count}")

    def check_status(self) -> None:
        """
        Uses the status checker to iterate over expected input paths and
        prints a formatted status report and summary.
        """
        from PyA3EDA.core.status.status_checker import check_all_statuses
        check_all_statuses(self.config_manager.processed_config, self.system_dir)

    def extract_data(self) -> None:
         logging.info("Data extraction not implemented.")
