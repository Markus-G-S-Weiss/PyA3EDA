"""
Data Extractor Module

Handles all aspects of data extraction from Q-Chem output files.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict

from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.parsers.qchem_result_parser import parse_thermodynamic_data, parse_sp_thermodynamic_data
from PyA3EDA.core.status.status_checker import should_process_file


def extract_data_from_output(output_path: Path, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract data from a Q-Chem output file using provided metadata.
    Uses appropriate parser based on calculation mode.
    """
    # Read content
    content = read_text(output_path)
    if not content:
        logging.warning(f"Could not read content from: {output_path}")
        return None
    
    # Determine which parser to use based on mode from metadata
    mode = metadata.get("Mode", "unknown")
    
    if mode == "opt":
        # Use OPT parser for optimization calculations
        thermo_data = parse_thermodynamic_data(content)
    elif mode == "sp":
        # Use SP parser for single point calculations
        thermo_data = parse_sp_thermodynamic_data(content)
    else:
        logging.warning(f"Unknown calculation mode '{mode}' for: {output_path}")
        return None
    
    if not thermo_data:
        logging.warning(f"Failed to parse thermodynamic data from: {output_path}")
        return None
    
    # Combine metadata with thermodynamic data (metadata comes first)
    result = {**metadata, **thermo_data}
    
    # Verify essential fields
    for essential_field in ["Method", "Category", "Branch", "Mode"]:
        if essential_field not in result:
            logging.warning(f"Missing essential metadata field '{essential_field}' for: {output_path}")
    
    return result


def extract_all_data(config: dict, system_dir: Path, criteria: str = "SUCCESSFUL") -> List[Dict[str, Any]]:
    """
    Extract all data using metadata from builder (single source of truth).
    Return flat list - no grouping, just raw extracted data.
    """
    logging.info(f"Extracting data with criteria: {criteria}")
    
    from PyA3EDA.core.builders.builder import iter_input_paths
    
    # Get all paths with metadata (single source of truth)
    input_items = list(iter_input_paths(config, system_dir, include_metadata=True))
    
    extracted_data = []
    stats = {"processed": 0, "successful": 0, "errors": 0}
    
    # Simple iteration - extract data with metadata
    for item in input_items:
        if not item or not hasattr(item, 'path') or not hasattr(item, 'metadata'):
            continue
            
        input_path = item.path
        metadata = item.metadata
        
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
        
        # Extract data using metadata from builder
        data = extract_data_from_output(output_path, metadata)
        if not data:
            stats["errors"] += 1
            continue
            
        stats["successful"] += 1
        extracted_data.append(data)
    
    logging.info(f"Data extraction: {stats['successful']} successful, {stats['errors']} errors")
    return extracted_data