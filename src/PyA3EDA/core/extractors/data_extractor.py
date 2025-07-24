"""
Data Extractor Module
Orchestrates data extraction using pure parsing functions.
Handles business logic, cross-file operations, and extraction decisions.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict

from PyA3EDA.core.utils.file_utils import read_text
from PyA3EDA.core.parsers.qchem_result_parser import (
    parse_energy, parse_enthalpy, parse_entropy, parse_optimization_status,
    parse_thermodynamic_conditions, parse_qrrho_parameters, parse_imaginary_frequencies,
    parse_zero_point_energy, parse_smd_cds_raw_values, parse_eda_polarized_energy, 
    parse_eda_convergence_energy, parse_bsse_energy
)
from PyA3EDA.core.parsers.output_xyz_parser import parse_qchem_output_xyz
from PyA3EDA.core.status.status_checker import should_process_file
from PyA3EDA.core.utils.unit_converter import convert_energy_unit


# EXTRACTION ORCHESTRATION FUNCTIONS (using metadata directly)

def _extract_opt_thermodynamic_data(content: str) -> Dict[str, Any]:
    """
    Extract thermodynamic data from OPT files using pure parsing functions.
    
    Args:
        content: Q-Chem OPT output content
        
    Returns:
        Dictionary with extracted thermodynamic data
    """
    data = {}
    fallback_used = False
    
    # Define parsers with their fallback flag names
    parsers = [
        (parse_energy, "energy_fallback_used"),
        (parse_enthalpy, "enthalpy_fallback_used"),
        (parse_entropy, "entropy_fallback_used"),
        (parse_optimization_status, None),
        (parse_thermodynamic_conditions, None),
        (parse_qrrho_parameters, None),
        (parse_imaginary_frequencies, None),
        (parse_zero_point_energy, None)
    ]
    
    # Extract energy first (required)
    energy_data = parse_energy(content)
    if not energy_data:
        return {}  # Cannot proceed without energy
    
    # Process all parsers
    for parser_func, fallback_key in parsers:
        parser_data = parser_func(content)
        if parser_data:
            data.update(parser_data)
            if fallback_key and parser_data.get(fallback_key):
                fallback_used = True
    
    # Calculate derived values
    _calculate_derived_values(data)
    
    # Add fallback flag
    data["Fallback Used"] = "Yes" if fallback_used else "No"
    
    return data


def _extract_sp_thermodynamic_data(sp_content: str, metadata: Dict[str, Any], opt_content: str = None) -> Dict[str, Any]:
    """
    Extract thermodynamic data from SP files using pure parsing functions.
    Now handles both regular SP and EDA SP calculations.
    
    Args:
        sp_content: Q-Chem SP output content
        metadata: Metadata for extraction decisions
        opt_content: Optional OPT content for CDS validation
        
    Returns:
        Dictionary with extracted SP thermodynamic data
    """
    data = {}
    
    # Check if this is an EDA calculation using metadata directly
    calc_type = metadata.get("Calc_Type", "")
    eda2 = metadata.get("eda2", "0")
    is_eda = calc_type in ["full_cat", "pol_cat", "frz_cat"] and eda2 != "0"
    
    # Add debug logging for transparency
    if calc_type in ["full_cat", "pol_cat", "frz_cat"]:
        logging.debug(f"EDA calc type detected: {calc_type}, eda2: {eda2}, is_eda: {is_eda}")
    
    if is_eda:
        # Handle EDA-specific energy extraction - get type directly from calc_type
        eda_type = ("frz" if "frz" in calc_type else 
                   "pol" if "pol" in calc_type else 
                   "full" if "full" in calc_type else "unknown")
            
        logging.debug(f"Processing EDA {eda_type} calculation for SP file")
        eda_data = _extract_eda_sp_energy(sp_content, eda_type, metadata)
        if eda_data:
            data.update(eda_data)
        else:
            logging.warning(f"Failed to extract EDA {eda_type} energy data")
            return {}  # Cannot proceed without EDA energy
    else:
        # Handle regular SP energy extraction
        logging.debug("Processing regular SP calculation")
        energy_data = parse_energy(sp_content)
        if not energy_data:
            logging.warning("Failed to extract energy from regular SP calculation")
            return {}  # Cannot proceed without energy
        
        # Set SP energy fields from parsed energy data
        first_energy_key = list(energy_data.keys())[0]
        energy_unit = first_energy_key.split('(')[1].split(')')[0]
        data[f"SP_E ({energy_unit})"] = energy_data[first_energy_key]
        data["SP_E (kcal/mol)"] = energy_data["E (kcal/mol)"]
        data["SP_Fallback Used"] = "Yes" if energy_data.get("energy_fallback_used") else "No"
        
        # Extract SMD CDS energy only if SMD solvation is used (metadata directly)
        if metadata.get("SP_Solvent", "gas").lower() != "gas":
            cds_data = _extract_smd_cds_energy(opt_content, sp_content)
            if cds_data:
                data.update(cds_data)
                logging.debug(f"Applied CDS correction: {cds_data.get('G_CDS (kcal/mol)', 0):.4f} kcal/mol for regular SP")
        
        logging.debug(f"Regular SP energy extraction successful: {data['SP_E (kcal/mol)']:.4f} kcal/mol")
    
    return data


def _extract_eda_sp_energy(sp_content: str, eda_type: str, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract energy from EDA SP calculations based on the EDA type.
    
    Args:
        sp_content: SP file content
        eda_type: Type of EDA calculation (frz, pol, full)
        metadata: File metadata
        
    Returns:
        Dictionary with extracted EDA energy data or None if extraction fails
    """
    data = {}
    
    # Extract base energy based on EDA type
    base_energy_ha = None
    fallback_reason = None
    
    if eda_type in ["frz", "pol"]:
        polarized_data = parse_eda_polarized_energy(sp_content)
        if polarized_data:
            base_energy_ha = polarized_data["polarized_energy"]
            fallback_reason = f"polarized_energy_{eda_type}"
        else:
            logging.warning(f"Failed to extract polarized energy for EDA {eda_type} calculation")
            fallback_reason = f"no_polarized_energy_{eda_type}"
            
    elif eda_type == "full":
        convergence_data = parse_eda_convergence_energy(sp_content)
        if convergence_data:
            base_energy_ha = convergence_data["convergence_energy"]
            fallback_reason = "convergence_no_bsse_full"  # Will be updated if BSSE found
        else:
            logging.warning(f"Failed to extract convergence energy for EDA {eda_type} calculation")
            fallback_reason = "no_convergence_full"
            
    else:
        logging.warning(f"Unknown EDA type: {eda_type}. Expected: frz, pol, or full")
        fallback_reason = f"unknown_eda_type_{eda_type}"
    
    # Handle extraction failure - return None columns with consistent structure
    if base_energy_ha is None:
        return {
            "SP_E_base (Ha)": None, "SP_E_base (kcal/mol)": None,
            "SP_E (Ha)": None, "SP_E (kcal/mol)": None,
            "SP_Fallback Used": fallback_reason
        }
    
    # Convert base energy and set columns
    base_energy_kcal = convert_energy_unit(base_energy_ha, "Ha", "kcal/mol")
    data.update({
        "SP_E_base (Ha)": base_energy_ha,
        "SP_E_base (kcal/mol)": base_energy_kcal
    })
    
    # Initialize final energy (will accumulate corrections)
    final_energy_ha = base_energy_ha
    final_energy_kcal = base_energy_kcal
    
    # Apply CDS correction if SMD solvation is used (metadata directly)
    if metadata.get("SP_Solvent", "gas").lower() != "gas":
        cds_data = _extract_smd_cds_energy(None, sp_content)
        if cds_data:
            cds_value_kcal = cds_data.get("G_CDS (kcal/mol)", 0.0)
            cds_value_ha = cds_data.get("G_CDS (Ha)", 0.0)
            
            # Set CDS correction columns and update final energy
            data.update({
                "SP_CDS (Ha)": cds_value_ha,
                "SP_CDS (kcal/mol)": cds_value_kcal
            })
            
            final_energy_ha += cds_value_ha
            final_energy_kcal += cds_value_kcal
            logging.debug(f"Applied CDS correction: {cds_value_kcal:.4f} kcal/mol for EDA {eda_type}")
    
    # Apply BSSE correction for full EDA calculations only
    if eda_type == "full":
        bsse_data = parse_bsse_energy(sp_content)
        if bsse_data:
            bsse_kj = bsse_data["bsse_energy"]
            bsse_value_kcal = convert_energy_unit(bsse_kj, "kJ/mol", "kcal/mol")
            bsse_value_ha = convert_energy_unit(bsse_kj, "kJ/mol", "Ha")
            
            # Set BSSE correction columns and update final energy
            data.update({
                "SP_BSSE (kJ/mol)": bsse_kj,
                "SP_BSSE (kcal/mol)": bsse_value_kcal,
                "SP_BSSE (Ha)": bsse_value_ha
            })
            
            final_energy_ha += bsse_value_ha
            final_energy_kcal += bsse_value_kcal
            fallback_reason = "convergence_bsse_full"
            logging.debug(f"Applied BSSE correction: {bsse_value_kcal:.4f} kcal/mol for EDA full")
    
    # Set final energy columns and fallback reason
    data.update({
        "SP_E (Ha)": final_energy_ha,
        "SP_E (kcal/mol)": final_energy_kcal,
        "SP_Fallback Used": fallback_reason
    })
    
    logging.debug(f"EDA {eda_type} energy extraction successful: base={base_energy_kcal:.4f}, final={final_energy_kcal:.4f} kcal/mol")
    return data


def _extract_smd_cds_energy(opt_content: str = None, sp_content: str = None) -> Optional[Dict[str, Any]]:
    """
    Extract and validate SMD CDS energy using cross-file validation.
    
    Args:
        opt_content: OPT file content for primary CDS calculation
        sp_content: SP file content for validation
        
    Returns:
        Dictionary with validated CDS energy or None
    """
    primary_value = None
    primary_source = None
    validation_info = {}
    
    # Extract raw SMD values from OPT content
    if opt_content:
        opt_raw_data = parse_smd_cds_raw_values(opt_content)
        if opt_raw_data:
            # Primary method: Calculate from G-S and G-ENP components
            if "g_s_final" in opt_raw_data and "g_enp_final" in opt_raw_data:
                g_s_final = opt_raw_data["g_s_final"]
                g_enp_final = opt_raw_data["g_enp_final"]
                cds_hartree = g_s_final - g_enp_final
                primary_value = convert_energy_unit(cds_hartree, "Ha", "kcal/mol")
                primary_source = "opt_calculated_from_components"
                
                # Validation 1: Against OPT summary (4 decimal tolerance)
                if "cds_summary_final" in opt_raw_data:
                    summary_val = opt_raw_data["cds_summary_final"]
                    validation_info["opt_summary_match"] = abs(primary_value - summary_val) <= 0.0001
                    validation_info["opt_summary_diff"] = abs(primary_value - summary_val)
                    if not validation_info["opt_summary_match"]:
                        logging.warning(f"CDS validation failed (OPT 4dp): hartree={primary_value:.4f}, opt_summary={summary_val:.4f} kcal/mol")
            
            # Fallback to OPT summary if components not available
            elif "cds_summary_final" in opt_raw_data:
                primary_value = opt_raw_data["cds_summary_final"]
                primary_source = "opt_summary_value"
    
    # Validation 2: Against SP file total (3 decimal tolerance)
    if sp_content and primary_value is not None:
        sp_raw_data = parse_smd_cds_raw_values(sp_content)
        if sp_raw_data and "cds_sp_total_final" in sp_raw_data:
            sp_val = sp_raw_data["cds_sp_total_final"]
            validation_info["sp_total_match"] = abs(primary_value - sp_val) <= 0.001
            validation_info["sp_total_diff"] = abs(primary_value - sp_val)
            if not validation_info["sp_total_match"]:
                logging.warning(f"CDS validation failed (SP 3dp): hartree={primary_value:.3f}, sp_total={sp_val:.3f} kcal/mol")
    
    if primary_value is None:
        return None
    
    # Return consolidated result with OPT-derived CDS for SP calculations
    result = {
        "G_CDS (Ha)": convert_energy_unit(primary_value, "kcal/mol", "Ha"),
        "G_CDS (kcal/mol)": primary_value,
        "G_CDS_Source": primary_source
    }
    result.update(validation_info)
    return result


def _calculate_derived_values(data: Dict[str, Any]) -> None:
    """
    Calculate derived thermodynamic values (H and G) in place.
    
    Args:
        data: Dictionary containing parsed data to modify
    """
    # Use CDS energy for calculations if available (SMD solvent calculations)
    base_energy_key = "G_CDS (kcal/mol)" if "G_CDS (kcal/mol)" in data else "E (kcal/mol)"
    
    # Calculate H (kcal/mol)
    if base_energy_key in data and "Total Enthalpy Corr. (kcal/mol)" in data:
        data["H (kcal/mol)"] = data[base_energy_key] + data["Total Enthalpy Corr. (kcal/mol)"]

    # Calculate G (kcal/mol)
    if all(key in data for key in ["H (kcal/mol)", "Temperature (K)", "Total Entropy Corr. (kcal/mol.K)"]):
        data["G (kcal/mol)"] = data["H (kcal/mol)"] - data["Temperature (K)"] * data["Total Entropy Corr. (kcal/mol.K)"]


def extract_sp_data_with_opt_content(output_path: Path, sp_content: str, metadata: Dict[str, Any], opt_content: str = None) -> Optional[Dict[str, Any]]:
    """
    Extract SP data with direct access to OPT content, eliminating cross-file dependencies.
    
    Args:
        output_path: Path to the SP output file
        sp_content: SP file content (already read)
        metadata: SP metadata from builder
        opt_content: OPT content for SMD validation (if needed)
        
    Returns:
        Dictionary containing extracted SP data or None if extraction fails
    """
    # Initialize result with metadata
    result = {**metadata}
    result["output_file_stem"] = output_path.stem
    
    # Extract SP thermodynamic data with OPT content
    thermo_data = _extract_sp_thermodynamic_data(sp_content, metadata, opt_content)
    if thermo_data:
        result.update(thermo_data)
        result["extraction_status"] = {"thermo": True, "xyz": False}
        return result
    else:
        logging.warning(f"Failed to parse SP data from: {output_path}")
        return None


def extract_all_data_from_output(output_path: Path, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract data from Q-Chem output files.
    Now primarily used for OPT files since SP files are handled by the pre-grouped approach.
    
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
    
    # Extract data based on mode
    if mode == "opt":
        # Extract thermodynamic data
        thermo_data = _extract_opt_thermodynamic_data(content)
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
        # SP files should now be processed by extract_sp_data_with_opt_content
        logging.warning(f"SP file {output_path} should be processed by pre-grouped approach, not this function")
        return None
        
    else:
        logging.warning(f"Unknown calculation mode '{mode}' for: {output_path}")
        return None
    
    # Return result if we extracted any data, otherwise None
    if extraction_success["thermo"] or extraction_success["xyz"]:
        # Add extraction status for statistics
        result["extraction_status"] = extraction_success
        return result
    else:
        logging.warning(f"No data could be extracted from: {output_path}")
        return None


def extract_all_data(config: dict, system_dir: Path, criteria: str = "SUCCESSFUL") -> List[Dict[str, Any]]:
    """
    Extract all data using pre-grouped file processing to eliminate cross-file dependencies.
    Groups files by calculation (species, calc_type, method_combo) and processes pairs together.
    """
    logging.info(f"Extracting data with criteria: {criteria}")
    
    from PyA3EDA.core.builders.builder import iter_input_paths
    
    # Get all paths with metadata
    input_items = list(iter_input_paths(config, system_dir, include_metadata=True))
    
    # Pre-group files by calculation (species, calc_type, method_combo)
    calculation_groups = defaultdict(dict)
    
    for item in input_items:
        if not item or not hasattr(item, 'path') or not hasattr(item, 'metadata'):
            continue
            
        input_path = item.path
        metadata = item.metadata
        
        if not input_path.exists():
            continue
            
        # Create unique key for this calculation
        calc_key = (
            metadata.get("Species", "unknown"),
            metadata.get("Calc_Type", "unknown"), 
            metadata.get("Method_Combo", "unknown")
        )
        
        mode = metadata.get("Mode", "unknown")
        calculation_groups[calc_key][mode] = {
            "path": input_path,
            "metadata": metadata,
            "output_path": input_path.with_suffix('.out')
        }
    
    # Process grouped calculations
    extracted_data = []
    stats = {
        "processed_calculations": 0,
        "processed_files": 0, 
        "complete_success": 0,
        "partial_success": 0,
        "total_failures": 0
    }
    
    def _process_file(file_info, mode_type, criteria, stats, opt_content=None):
        """Process a single file and update statistics."""
        if not file_info["output_path"].exists():
            return None, None
            
        should_extract, _ = should_process_file(file_info["path"], criteria)
        if not should_extract:
            return None, None
            
        stats["processed_files"] += 1
        content = read_text(file_info["output_path"])
        
        if not content:
            logging.warning(f"Could not read {mode_type.upper()} content from: {file_info['output_path']}")
            stats["total_failures"] += 1
            return None, content
        
        # Extract data based on mode type
        if mode_type == "opt":
            data = extract_all_data_from_output(file_info["output_path"], file_info["metadata"])
        elif mode_type == "sp":
            # Determine if OPT content is needed for SMD validation (metadata directly)
            needs_opt_content = (file_info["metadata"].get("SP_Solvent", "gas").lower() != "gas" and opt_content)
            data = extract_sp_data_with_opt_content(
                file_info["output_path"], 
                content,
                file_info["metadata"],
                opt_content if needs_opt_content else None
            )
        else:
            data = None
        
        if data:
            stats["complete_success"] += 1
        else:
            stats["total_failures"] += 1
            
        return data, content
    
    for calc_key, modes in calculation_groups.items():
        stats["processed_calculations"] += 1
        logging.debug(f"Processing calculation group: {calc_key}")
        
        # Process OPT files first to get content for SP cross-validation
        opt_content = None
        
        if "opt" in modes:
            opt_data, opt_content = _process_file(modes["opt"], "opt", criteria, stats)
            if opt_data:
                extracted_data.append(opt_data)
        
        # Process SP files with direct access to OPT content
        if "sp" in modes:
            sp_data, _ = _process_file(modes["sp"], "sp", criteria, stats, opt_content)
            if sp_data:
                extracted_data.append(sp_data)
    
    # Log detailed statistics
    total_extracted = stats["complete_success"] + stats["partial_success"]
    logging.info(f"Pre-grouped extraction: {stats['processed_calculations']} calculation groups, "
                f"{stats['processed_files']} files processed, {total_extracted} successful extractions, "
                f"{stats['total_failures']} failures")
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