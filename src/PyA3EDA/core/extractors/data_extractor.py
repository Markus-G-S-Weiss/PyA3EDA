"""
Data Extractor Module
Handles both thermodynamic data and XYZ coordinates in one pass.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict

from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.parsers.qchem_result_parser import parse_thermodynamic_data, parse_sp_thermodynamic_data
from PyA3EDA.core.parsers.output_xyz_parser import parse_qchem_output_xyz
from PyA3EDA.core.status.status_checker import should_process_file


def extract_all_data_from_output(output_path: Path, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extracting ALL data from Q-Chem output files.
    Extracts thermodynamic data and XYZ coordinates in one pass.
    Continues with XYZ extraction even if thermodynamic data fails.
    
    Args:
        output_path: Path to the Q-Chem output file
        metadata: Metadata from builder
        
    Returns:
        Dictionary containing all extracted data or None if no data could be extracted
    """
    # Read content once (single file read)
    content = read_text(output_path)
    if not content:
        logging.warning(f"Could not read content from: {output_path}")
        return None
    
    # Determine mode from metadata
    mode = metadata.get("Mode", "unknown")
    
    # Initialize result with metadata
    result = {**metadata}
    result["output_file_stem"] = output_path.stem
    
    # Track what was successfully extracted
    extraction_success = {"thermo": False, "xyz": False}
    
    # Extract thermodynamic data based on mode
    if mode == "opt":
        thermo_data = parse_thermodynamic_data(content)
        if thermo_data:
            result.update(thermo_data)
            extraction_success["thermo"] = True
        else:
            logging.warning(f"Failed to parse thermodynamic data from: {output_path}")
            
        # Extract XYZ coordinates for OPT files (independent of thermodynamic data)
        species = metadata.get("Species", "unknown")
        xyz_data = parse_qchem_output_xyz(content, species)
        if xyz_data:
            result.update(xyz_data)
            extraction_success["xyz"] = True
            
            # Log if charge/multiplicity defaulted to 0 1
            if xyz_data.get("Charge") == 0 and xyz_data.get("Multiplicity") == 1:
                logging.debug(f"Using default charge/multiplicity (0 1) for {species} from: {output_path}")
        else:
            logging.debug(f"No XYZ coordinates found in: {output_path}")
            
    elif mode == "sp":
        thermo_data = parse_sp_thermodynamic_data(content)
        if thermo_data:
            result.update(thermo_data)
            extraction_success["thermo"] = True
        else:
            logging.warning(f"Failed to parse SP data from: {output_path}")
        # SP files don't have optimized coordinates
    else:
        logging.warning(f"Unknown calculation mode '{mode}' for: {output_path}")
        return None
    
    # Return result if we extracted any data, otherwise None
    if extraction_success["thermo"] or extraction_success["xyz"]:
        # Add extraction status for more detailed statistics
        result["extraction_status"] = extraction_success
        return result
    else:
        logging.warning(f"No data could be extracted from: {output_path}")
        return None


def extract_all_data(config: dict, system_dir: Path, criteria: str = "SUCCESSFUL") -> List[Dict[str, Any]]:
    """
    Extract all data using metadata from builder.
    Return flat list - no grouping, just raw extracted data.
    """
    logging.info(f"Extracting data with criteria: {criteria}")
    
    from PyA3EDA.core.builders.builder import iter_input_paths
    
    # Get all paths with metadata
    input_items = list(iter_input_paths(config, system_dir, include_metadata=True))
    
    extracted_data = []
    stats = {
        "processed": 0, 
        "complete_success": 0,  # Both thermo and xyz (if applicable)
        "partial_success": 0,   # Only thermo OR only xyz
        "total_failures": 0     # No data extracted
    }
    
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
        
        # Extract ALL data in single pass
        data = extract_all_data_from_output(output_path, metadata)
        if not data:
            stats["total_failures"] += 1
            continue
        
        # Analyze extraction success for better statistics
        extraction_status = data.get("extraction_status", {})
        mode = data.get("Mode", "unknown")
        
        if mode == "opt":
            # For OPT: complete success = both thermo and xyz
            if extraction_status.get("thermo") and extraction_status.get("xyz"):
                stats["complete_success"] += 1
            elif extraction_status.get("thermo") or extraction_status.get("xyz"):
                stats["partial_success"] += 1
        elif mode == "sp":
            # For SP: only thermo data expected (no xyz)
            if extraction_status.get("thermo"):
                stats["complete_success"] += 1
            else:
                stats["partial_success"] += 1  # This shouldn't happen for SP, but just in case
        
        extracted_data.append(data)
    
    # Log detailed statistics
    total_extracted = stats["complete_success"] + stats["partial_success"]
    logging.info(f"Data extraction: {total_extracted} extracted ({stats['complete_success']} complete, {stats['partial_success']} partial), {stats['total_failures']} total failures")
    return extracted_data


def extract_and_save(config: dict, system_dir: Path, output_dir: Path = None, 
                    criteria: str = "SUCCESSFUL") -> Dict[str, Any]:
    """
    Main coordination function - extract once, export multiple formats.
    
    Args:
        config: Configuration dictionary
        system_dir: System directory path
        output_dir: Output directory path
        criteria: Extraction criteria
        
    Returns:
        Dictionary of export results
    """
    # Extract all data once
    extracted_data = extract_all_data(config, system_dir, criteria)
    
    # Set default output directory
    if not output_dir:
        output_dir = system_dir / "results" / "raw"
    
    # Export data in multiple formats using single extracted data
    from PyA3EDA.core.exporters.data_exporter import export_all_formats
    return export_all_formats(extracted_data, output_dir)