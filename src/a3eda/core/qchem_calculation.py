import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Tuple
from .file_operations import FileOperations
from .utilities import Utilities

class QChemCalculation(FileOperations):
    """Class for handling Q-Chem calculations."""
    def __init__(self, input_file: Path, overwrite: bool = False):
        super().__init__(input_file.parent)
        self.input_file = input_file
        self.output_file = input_file.with_suffix('.out')
        self.error_file = input_file.with_suffix('.err')
        self.overwrite = overwrite

    def execute(self):
        """Execute the Q-Chem calculation."""
        logging.info(f'Executing qqchem for {self.input_file}')
        try:
            subprocess.run(
                ['qqchem', '-c', '16', '-t', '10-00:00:00', '-x', 'compute-2-09-05',  self.input_file.name],
                check=True,
                cwd=self.input_file.parent
            )
            logging.info(f'Submission successful for {self.input_file}')
            time.sleep(0.2)
            return True
        except Exception as e:
            logging.error(f'Error executing qqchem for {self.input_file}: {e}')
            return False

    def check_status(self) -> Tuple[str, str]:
        """Check calculation status and return detailed information."""
        # ... existing status checking logic from check_calculation_status ...
        # This would be the same logic as in your original check_calculation_status function
        """
        Check calculation status and return detailed information.
        Returns tuple of (status, details)
        """
        try:
            # Check if .out file exists
            if self.output_file.exists():
                # Read .out file content
                content = self.read_file(self.output_file)
            else:
                content = None  # Indicates .out file does not exist
    
            # Read .err file content if it exists
            err_content = self.read_file(self.error_file) if self.error_file.exists() else ''
    
            # Check if job was cancelled manually in .err file
            if 'CANCELLED AT' in err_content:
                return 'terminated', 'Job cancelled by Queue'
    
            # Check for Q-Chem crash in .err file
            if 'Error in Q-Chem run' in err_content or 'Aborted' in err_content:
                # Job crashed, extract error message from .out file
                status = 'CRASH'
                error_msg = 'Q-Chem execution crashed'
    
                # Attempt to get detailed error message from .out file
                if content:
                    if 'error occurred' in content:
                    #if 'Q-Chem fatal error occurred' in content:
                        error_pattern = r'error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)'
                        #error_pattern = r'Q-Chem fatal error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)'
                        error_match = re.search(error_pattern, content, re.DOTALL)
                        if error_match:
                            full_msg = error_match.group(1).strip()
                            # Extract message up to the first '.' or ';'
                            error_msg = re.split(r'[.;]|\band\b', full_msg)[0].strip()
                        else:
                            error_msg = 'Unknown fatal error'
                    elif 'SGeom Failed' in content:
                        error_msg = 'Geometry optimization failed'
                    elif 'SCF failed to converge' in content:
                        error_msg = 'SCF convergence failure'
                    elif 'Insufficient memory' in content:
                        error_msg = 'Out of memory'
                    else:
                        error_msg = 'Unknown failure'
                return status, error_msg
    
            # Check if job is still running based on submission file
            input_stem = self.output_file.with_suffix('').stem
            submission_pattern = f"{input_stem}.in_[0-9]*.[0-9]*"
            submission_files = list(self.output_file.parent.glob(submission_pattern))
            if submission_files:
                return 'running', 'Job submission file exists'
    
            # If .out file does not exist
            if content is None:
                return 'nofile', 'Output file not found'
    
            # Check for running job in .out file
            if 'Running on' in content and 'Thank you very much' not in content:
                return 'running', 'Calculation in progress'
    
            # Check for successful completion
            if 'Thank you very much' in content:
                time_pattern = r'Total job time:\s*(.*)'
                time_match = re.search(time_pattern, content)
                job_time = time_match.group(1).strip() if time_match else 'unknown'
                return 'SUCCESSFUL', f'Completed in {job_time}'
    
            # Check for Q-Chem fatal error in .out file
            if 'Q-Chem fatal error occurred' in content:
                error_pattern = r'Q-Chem fatal error occurred.*?\n\s*(.*?)(?:\n\n|\Z)'
                error_match = re.search(error_pattern, content, re.DOTALL)
                if error_match:
                    full_msg = error_match.group(1).strip()
                    # Extract message up to the first '.' or ';'
                    error_msg = re.split(r'[.;]', full_msg)[0].strip()
                else:
                    error_msg = 'Unknown fatal error'
                return 'CRASH', error_msg
    
            # Check for specific errors in .out file
            if 'SGeom Failed' in content:
                return 'CRASH', 'Geometry optimization failed'
            if 'SCF failed to converge' in content:
                return 'CRASH', 'SCF convergence failure'
            if 'Insufficient memory' in content:
                return 'CRASH', 'Out of memory'
    
            # Check for job termination messages in .out file
            if 'killed' in content.lower() or 'terminating' in content.lower():
                return 'terminated', 'Job terminated unexpectedly'
    
            # If .out file exists but contains unknown content
            if content.strip():
                return 'CRASH', 'Unknown failure'
    
            # If .out file exists but is empty
            return 'empty', 'Output file is empty'
    
        except Exception as e:
            return 'error', f'Error reading output: {str(e)}'
    
    def write_input_file(self, molecule_section: str, rem_section: str, 
                        base_template_content: str, calc_type: str) -> bool:
        """Generate the input file by filling in placeholders."""
        if self.input_file.exists() and not self.overwrite:
            logging.info(f'File exists and will not be overwritten: {self.input_file}')
            return False

        num_atoms = Utilities.count_atoms(molecule_section)
        jobtype = 'ts' if calc_type == 'ts' else ('sp' if num_atoms == 1 else 'opt')
        
        rem_section_filled = rem_section.format(jobtype=jobtype)
        input_content = base_template_content.format(
            molecule_section=molecule_section.strip(),
            rem_section=rem_section_filled.rstrip())

        return self.write_file(self.input_file, input_content)
