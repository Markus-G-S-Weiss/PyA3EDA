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
