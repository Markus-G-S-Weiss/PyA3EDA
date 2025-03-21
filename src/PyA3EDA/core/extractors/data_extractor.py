"""
Data Extractor Module

Handles all aspects of data extraction from Q-Chem output files.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict

from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.utils.path_utils import extract_path_metadata
from PyA3EDA.core.parsers.qchem_result_parser import parse_thermodynamic_data
from PyA3EDA.core.status.status_checker import should_process_file


def extract_data_from_output(output_path: Path, system_dir: Path = None) -> Optional[Dict[str, Any]]:
    """
    Extract data from a Q-Chem output file and add path metadata.
    """
    # Read content
    content = read_text(output_path)
    if not content:
        logging.warning(f"Could not read content from: {output_path}")
        return None
    
    # Parse thermodynamic data
    thermo_data = parse_thermodynamic_data(content)
    if not thermo_data:
        logging.warning(f"Failed to parse thermodynamic data from: {output_path}")
        return None
    
    # Get path metadata
    path_metadata = {}
    if system_dir:
        path_metadata = extract_path_metadata(output_path, system_dir)
        if not path_metadata:
            logging.warning(f"Failed to extract path metadata for: {output_path}")
    else:
        logging.warning(f"No system_dir provided for path metadata extraction: {output_path}")
    
    # Combine data (path metadata comes first)
    result = {**path_metadata, **thermo_data}
    
    # Verify essential fields
    for essential_field in ["Method", "Category", "Branch", "Mode"]:
        if essential_field not in result:
            logging.warning(f"Missing essential metadata field '{essential_field}' for: {output_path}")
    
    return result


def extract_all_data(config: dict, system_dir: Path, criteria: str = "SUCCESSFUL") -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Extract all data from the system, grouped by method and mode.
    """
    logging.info(f"Extracting data with criteria: {criteria}")
    
    # Import here to avoid circular imports
    from PyA3EDA.core.builders.builder import iter_input_paths
    
    # Get all paths
    input_paths = list(iter_input_paths(config, system_dir))
    
    # Group data
    grouped_data = defaultdict(lambda: defaultdict(list))
    stats = {"processed": 0, "successful": 0, "errors": 0}
    
    # Process each path
    for input_path in input_paths:
        if not input_path.exists():
            continue
            
        stats["processed"] += 1
        
        # Skip if doesn't match criteria
        should_extract, _ = should_process_file(input_path, criteria)
        if not should_extract:
            continue
            
        # Get output file
        output_path = input_path.with_suffix('.out')
        if not output_path.exists():
            continue
        
        # Extract data
        data = extract_data_from_output(output_path, system_dir)
        if not data:
            stats["errors"] += 1
            continue
            
        # Add to group
        stats["successful"] += 1
        grouped_data[data.get("Method", "unknown")][data.get("Mode", "unknown")].append(data)
    
    # Log summary
    logging.info(f"Data extraction: {stats['successful']} successful, {stats['errors']} errors")
    
    return dict(grouped_data)