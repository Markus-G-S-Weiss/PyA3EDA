"""
Executor Module

Handles the execution of Q-Chem calculations via subprocess.
"""
import logging
import subprocess
import time
from pathlib import Path

def execute_qchem(input_file: Path, cores: int = 32, time_limit: str = "30-00:00:00", 
                 node: str = "compute-2-09-05,compute-2-07-01,compute-2-07-02") -> bool:
    """Execute a Q-Chem calculation using qqchem submission script."""
    logging.info(f'Executing qqchem for {input_file}')
    try:
        subprocess.run(
            ['qqchem', '-c', str(cores), '-t', time_limit, '-x', node, input_file.name],
            check=True,
            cwd=input_file.parent
        )
        logging.info(f'Submission successful for {input_file}')
        time.sleep(0.2)  # Small delay to avoid overwhelming the scheduler
        return True
    except Exception as e:
        logging.error(f'Error executing qqchem for {input_file}: {e}')
        return False

def run_all_calculations(config, system_dir, run_criteria=None):
    """
    Run calculations based on the specified run criteria.
    """
    from PyA3EDA.core.builders.builder import iter_input_paths
    from PyA3EDA.core.status.status_checker import should_process_file
    
    if not run_criteria:
        logging.warning("No run criteria specified. Use --run option with a valid criteria.")
        return
    
    logging.info(f"Running calculations with criteria: {run_criteria}")
    
    # Get all input paths and process them based on criteria
    count = 0
    for input_path in iter_input_paths(config, system_dir):
        if not input_path.exists():
            continue
        
        should_run, reason = should_process_file(input_path, run_criteria)
            
        if should_run:
            logging.info(f"Submitting job ({reason}): {input_path.relative_to(system_dir)}")
            if execute_qchem(input_path):
                count += 1
    
    logging.info(f"Total jobs submitted: {count}")
