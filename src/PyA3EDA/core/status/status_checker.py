"""
Status Checker Module

Provides functions for checking the status of Q-Chem calculations,
grouping results by method_basis (first folder of the relative path),
and printing formatted reports with intermediate group summaries and an overall summary.
"""

import logging
from pathlib import Path
from typing import Tuple, Iterator, Dict, List
from PyA3EDA.core.constants import Constants
from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.parsers.qchem_status_parser import parse_qchem_status
from PyA3EDA.core.builders.builder import iter_input_paths

# Create a separate logger for summary that uses a simple formatter.
summary_logger = logging.getLogger("summary_logger")
if not summary_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    summary_logger.addHandler(handler)
    summary_logger.propagate = False


def get_status_for_file(input_file: Path) -> Tuple[str, str]:
    """
    Reads the output and error files corresponding to the input_file and determines the status.
    """
    output_file = input_file.with_suffix('.out')
    error_file = input_file.with_suffix('.err')
    content = read_text(output_file) if output_file.exists() else ""
    err_content = read_text(error_file) if error_file.exists() else ""
    
    # Check if job is still running based on submission file
    input_stem = input_file.stem
    # Pattern 1: filename.in_jobid.taskid 
    submission_pattern1 = f"{input_stem}.in_[0-9]*.[0-9]*"
    # Pattern 2: .filename.in.jobid.qcin.taskid
    submission_pattern2 = f".{input_stem}.in.[0-9]*.qcin.[0-9]*"
    
    submission_exists = (
        bool(list(input_file.parent.glob(submission_pattern1))) or
        bool(list(input_file.parent.glob(submission_pattern2)))
    )
    
    return parse_qchem_status(content, err_content, submission_exists)


def should_process_file(input_file: Path, criteria: str) -> Tuple[bool, str]:
    """
    Determine if a file should be processed based on criteria.
    
    Args:
        input_file: Path to the input file
        criteria: Criteria for processing ("all", "nofile", or status name)
        
    Returns:
        Tuple[bool, str]: (should_process, reason)
    """
    if not input_file.exists():
        return False, "File doesn't exist"
        
    if criteria is None:
        return False, "No criteria specified"
        
    if criteria.lower() == "all":
        return True, "Process all"
        
    if criteria.lower() == "nofile":
        output_file = input_file.with_suffix('.out')
        if not output_file.exists():
            return True, "Output file doesn't exist"
        return False, "Output file exists"
    
    # Get the actual status
    status, details = get_status_for_file(input_file)
    if status.lower() == criteria.lower():
        return True, f"Status match: {status}"
    
    return False, f"Status mismatch: {status} ≠ {criteria}"

def group_paths_by_method_basis(paths: List[Path], system_dir: Path) -> Dict[str, List[Path]]:
    """
    Groups paths by first folder with proper dispersion formatting.
    """
    # Maps for unsanitizing and dispersion format
    reverse_map = {s: o for o, s in Constants.ESCAPE_MAP.items()}
    disp_map = {
        'empirical_grimme': 'D2', 'empirical_chg': 'CHG', 'empirical_grimme3': 'D3(0)',
        'd3_zero': 'D3(0)', 'd3_bj': 'D3(BJ)', 'd3_cso': 'D3(CSO)', 'd3_zerom': 'D3M(0)', 
        'd3_bjm': 'D3M(BJ)', 'd3_op': 'D3(op)', 'd3': 'D3', 'd4': 'D4'
    }
    
    groups = {}
    for path in paths:
        # Handle paths with no parts
        if not (parts := path.relative_to(system_dir).parts):
            groups.setdefault("unknown", []).append(path)
            continue
            
        # Unsanitize folder name
        folder = parts[0]
        for s, o in reverse_map.items():
            folder = folder.replace(s, o)
        
        # Get method and remaining parts
        method, *rest_parts = folder.split('_', 1) + ['']
        rest = rest_parts[0]
        
        # Format the key
        if rest:
            # Check for dispersion methods
            disp_found = False
            for disp_key, disp_format in disp_map.items():
                if rest.lower().startswith(disp_key):
                    # Get remaining part after dispersion
                    remaining = rest[len(disp_key):].lstrip('_').replace('_', '/') 
                    key = f"{method}-{disp_format}"
                    if remaining:
                        key += f"/{remaining}"
                    disp_found = True
                    break
                    
            if not disp_found:
                key = f"{method}/{rest.replace('_', '/')}"
        else:
            key = method
            
        # Add to group (removing any "/false" parts)
        groups.setdefault(key.replace('/false', ''), []).append(path)
    
    return groups


def print_group_status(group_key: str, paths: List[Path], system_dir: Path) -> Dict[str, int]:
    """
    Checks statuses for paths in this group, prints a formatted report including the calculation mode
    (OPT or SP), and returns a summary dictionary of status counts for the group.
    """
    header_text = "Input File (rel)"
    max_path_length = max(
        max(len(str(path.relative_to(system_dir).parent / path.stem)) for path in paths),
        len(header_text)
    )
    # Format string with fixed widths for each column.
    format_str = f"{{:<{max_path_length}}} | {{:<6}} | {{:<10}} | {{}}"
    group_counts: Dict[str, int] = {}

    boundary_line = "-" * 60
    summary_logger.info(f"\n{boundary_line}")
    summary_logger.info(f"{' ' * 8}GROUP: {group_key}")
    summary_logger.info(boundary_line)
    summary_logger.info(format_str.format(header_text, "Mode", "Status", "Details"))
    summary_logger.info(boundary_line)

    for path in paths:
        relative_path = path.relative_to(system_dir).parent / path.stem
        mode = "SP" if path.stem.endswith("_sp") else "OPT"
        if path.exists():
            status, details = get_status_for_file(path)
        else:
            status, details = 'absent', 'Input file not found'
        group_counts[status] = group_counts.get(status, 0) + 1
        # Use summary_logger to ensure uniform formatting.
        summary_logger.info(format_str.format(str(relative_path), mode, status, details))

    summary_logger.info(f"\n{' ' * 4}Summary for {group_key}:")
    for s, count in group_counts.items():
        summary_logger.info(f"    {s} : {count}")
    return group_counts


def check_all_statuses(config: dict, system_dir: Path) -> None:
    """
    Iterates over expected input paths (grouped by method_basis), checks their statuses on the fly,
    prints a formatted report for each group along with an intermediate summary, and finally prints
    an overall status summary.
    """
    logging.info(f"Status checking started:")
    paths = list(iter_input_paths(config, system_dir))
    if not paths:
        logging.info("No input paths available for status checking.")
        return

    groups = group_paths_by_method_basis(paths, system_dir)
    overall_counts: Dict[str, int] = {}

    for group_key, group_paths in groups.items():
        group_counts = print_group_status(group_key, group_paths, system_dir)
        for s, count in group_counts.items():
            overall_counts[s] = overall_counts.get(s, 0) + count

    # Print overall summary with a boundary block.
    boundary_line = "=" * 60
    summary_logger.info(f"\n{boundary_line}")
    summary_logger.info(f"{' ' * 8}OVERALL STATUS SUMMARY")
    summary_logger.info(boundary_line)
    for s, count in overall_counts.items():
        summary_logger.info(f"    {s} : {count}")
    summary_logger.info(boundary_line)
    logging.info(f"Status checking finished.")
