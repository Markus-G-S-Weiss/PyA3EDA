"""
Status Checker Module

Provides functions for checking the status of Q-Chem calculations,
grouping results by method_basis (first folder of the relative path),
and printing formatted reports with intermediate group summaries and an overall summary.
"""

import logging
from pathlib import Path
from typing import Tuple, Iterator, Dict, List
from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.parsers.qchem_status_parser import parse_qchem_status
from PyA3EDA.core.builders import builder

# Create a separate logger for summary that uses a simple formatter.
summary_logger = logging.getLogger("summary_logger")
if not summary_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    summary_logger.addHandler(handler)
    summary_logger.propagate = False

def iter_status_input_paths(config: dict, system_dir: Path) -> Iterator[Path]:
    """
    Yields expected Q-Chem input paths using the builder's iterator.
    """
    yield from builder.iter_input_paths(config, system_dir)

def get_status_for_file(input_file: Path) -> Tuple[str, str]:
    """
    Reads the output and error files corresponding to the input_file and determines the status.
    """
    output_file = input_file.with_suffix('.out')
    error_file = input_file.with_suffix('.err')
    content = read_text(output_file) if output_file.exists() else ""
    err_content = read_text(error_file) if error_file.exists() else ""
    return parse_qchem_status(content, err_content)

def group_paths_by_method_basis(paths: List[Path], system_dir: Path) -> Dict[str, List[Path]]:
    """
    Groups the given paths by the first folder in their relative path (assumed to be {method}_{basis}).
    """
    groups: Dict[str, List[Path]] = {}
    for path in paths:
        rel_parts = path.relative_to(system_dir).parts
        key = rel_parts[0] if rel_parts else "unknown"
        groups.setdefault(key, []).append(path)
    return groups

def print_group_status(group_key: str, paths: List[Path], system_dir: Path) -> Dict[str, int]:
    """
    Checks statuses for paths in this group, prints a formatted report,
    and returns a summary dictionary of status counts for the group.
    """
    max_path_length = max(
        len(str(path.relative_to(system_dir).parent / path.stem))
        for path in paths
    )
    format_str = f"{{:<{max_path_length}}} | {{:<10}} | {{}}"
    group_counts: Dict[str, int] = {}

    boundary_line = "-" * 60
    # Print a larger header block for the group using the summary_logger.
    summary_logger.info(f"\n{boundary_line}")
    summary_logger.info(f"{' ' * 8}GROUP: {group_key}")
    summary_logger.info(boundary_line)

    for path in paths:
        relative_path = path.relative_to(system_dir).parent / path.stem
        if path.exists():
            status, details = get_status_for_file(path)
        else:
            status, details = 'absent', 'Input file not found'
        group_counts[status] = group_counts.get(status, 0) + 1
        logging.info(format_str.format(str(relative_path), status, details))

    # Print intermediate group summary with indentation.
    summary_logger.info(f"\n{' ' * 4}Summary for {group_key}:")
    for s, count in group_counts.items():
        summary_logger.info(f"    {s} : {count}")
    # summary_logger.info(boundary_line)
    return group_counts

def check_all_statuses(config: dict, system_dir: Path) -> None:
    """
    Iterates over expected input paths (grouped by method_basis), checks their statuses on the fly,
    prints a formatted report for each group along with an intermediate summary, and finally prints
    an overall status summary using the simpler summary logger.
    """
    paths = list(iter_status_input_paths(config, system_dir))
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