"""
Q-Chem Parser Module

Parses raw Q-Chem output text content using regular expression patterns to extract 
numerical data and calculation metadata. Focuses solely on text parsing operations.
"""
import re
import logging
from typing import Optional, Tuple, Dict, Any, Pattern

from PyA3EDA.core.constants import Constants
from PyA3EDA.core.utils.unit_converter import convert_energy_unit


# Regex patterns for data extraction
PATTERNS = {
    # Fixed patterns - only capture valid units, not formatting characters
    "final_energy": re.compile(r"Final energy is\s+([-+]?\d+\.\d+)(?:\s+([A-Za-z][A-Za-z0-9./\-]*))?\s*$", re.MULTILINE),
    "final_energy_fallback": re.compile(r"Total energy =\s+([-+]?\d+\.\d+)(?:\s+([A-Za-z][A-Za-z0-9./\-]*))?\s*$", re.MULTILINE),
    "optimization_status": re.compile(r"(OPTIMIZATION CONVERGED|TRANSITION STATE CONVERGED)"),
    "thermodynamics": re.compile(r"STANDARD THERMODYNAMIC QUANTITIES AT\s+([-+]?\d+\.\d+)\s*K\s+AND\s+([-+]?\d+\.\d+)\s*ATM"),
    "imaginary_frequencies": re.compile(r"This Molecule has\s+(\d+)\s+Imaginary Frequencies"),
    "zero_point_energy": re.compile(r"Zero point vibrational energy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "qrrho_parameters": re.compile(r"Quasi-RRHO corrections using alpha\s*=\s*(\d+),\s*and omega\s*=\s*(\d+)\s*cm\^-1"),
    "qrrho_total_enthalpy": re.compile(r"QRRHO-Total Enthalpy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "total_enthalpy_fallback": re.compile(r"Total Enthalpy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "qrrho_total_entropy": re.compile(r"QRRHO-Total Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    "total_entropy_fallback": re.compile(r"Total Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE)
}


def get_value_with_fallback(content: str, primary_pattern: Pattern, fallback_pattern: Pattern, 
                           default_unit: str = None) -> Tuple[Optional[float], Optional[str], bool]:
    """
    Extract value with unit, falling back to secondary pattern if primary fails.
    
    Args:
        content: Text content to search
        primary_pattern: Primary regex pattern to try first
        fallback_pattern: Fallback regex pattern if primary fails
        default_unit: Default unit if pattern doesn't capture unit
        
    Returns:
        Tuple of (value, unit, fallback_used)
    """
    primary_match = primary_pattern.search(content)
    if primary_match:
        unit = primary_match.group(2) if primary_match.lastindex >= 2 else default_unit
        return float(primary_match.group(1)), unit, False
    
    fallback_match = fallback_pattern.search(content)
    if fallback_match:
        unit = fallback_match.group(2) if fallback_match.lastindex >= 2 else default_unit
        return float(fallback_match.group(1)), unit, True
    
    return None, None, False


def get_single_value(content: str, pattern: Pattern, field_mapping: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Extract single value from pattern and format according to field mapping.
    
    Args:
        content: Text content to search
        pattern: Regex pattern to match
        field_mapping: Dictionary mapping group indices to field names
        
    Returns:
        Dictionary with extracted values
    """
    match = pattern.search(content)
    if not match:
        return {}
    
    if not field_mapping:
        # Default single value extraction
        return {"value": float(match.group(1))}
    
    result = {}
    for group_idx, field_name in field_mapping.items():
        if match.lastindex >= group_idx:
            value = match.group(group_idx)
            # Try to convert to appropriate type
            try:
                if '.' in value:
                    result[field_name] = float(value)
                else:
                    result[field_name] = int(value)
            except ValueError:
                result[field_name] = value
    
    return result


def parse_thermodynamic_data(content: str) -> Dict[str, Any]:
    """
    Parse all thermodynamic data from Q-Chem output content.
    
    Args:
        content: Text content of Q-Chem output file
        
    Returns:
        Dictionary of parsed thermodynamic values with standardized units
    """
    data = {}
    fallback_used = False
    
    # Energy extraction - critical field
    energy_value, energy_unit, energy_fallback = get_value_with_fallback(
        content, 
        PATTERNS["final_energy"],
        PATTERNS["final_energy_fallback"],
        default_unit="Ha"
    )
    
    if energy_value is not None:
        data[f"E ({energy_unit})"] = energy_value
        data["E (kcal/mol)"] = convert_energy_unit(energy_value, energy_unit, "kcal/mol")
        if energy_fallback:
            fallback_used = True
    else:
        return None  # Can't proceed without energy

    # Enthalpy extraction with fallback
    enthalpy_value, enthalpy_unit, enthalpy_fallback = get_value_with_fallback(
        content, 
        PATTERNS["qrrho_total_enthalpy"],
        PATTERNS["total_enthalpy_fallback"]
    )
    
    if enthalpy_value is not None:
        enthalpy_converted = convert_energy_unit(enthalpy_value, enthalpy_unit, "kcal/mol")
        data["Total Enthalpy Corr. (kcal/mol)"] = enthalpy_converted
        if enthalpy_fallback:
            fallback_used = True

    # Entropy extraction with fallback
    entropy_value, entropy_unit, entropy_fallback = get_value_with_fallback(
        content,
        PATTERNS["qrrho_total_entropy"],
        PATTERNS["total_entropy_fallback"]
    )
    
    if entropy_value is not None:
        entropy_converted = convert_energy_unit(entropy_value, entropy_unit, "kcal/mol.K")
        data["Total Entropy Corr. (kcal/mol.K)"] = entropy_converted
        if entropy_fallback:
            fallback_used = True

    # Optimization status
    opt_data = get_single_value(content, PATTERNS["optimization_status"], {1: "status"})
    if opt_data:
        data["Optimization Status"] = opt_data["status"]

    # Temperature and pressure
    thermo_data = get_single_value(content, PATTERNS["thermodynamics"], {1: "temperature", 2: "pressure"})
    if thermo_data:
        data["Temperature (K)"] = thermo_data["temperature"]
        data["Pressure (atm)"] = thermo_data["pressure"]

    # QRRHO parameters
    qrrho_data = get_single_value(content, PATTERNS["qrrho_parameters"], {1: "alpha", 2: "omega"})
    if qrrho_data:
        data["Alpha"] = qrrho_data["alpha"]
        data["Omega (cm^-1)"] = qrrho_data["omega"]

    # Imaginary frequencies
    freq_data = get_single_value(content, PATTERNS["imaginary_frequencies"], {1: "count"})
    if freq_data:
        data["Imaginary Frequencies"] = freq_data["count"]

    # Zero point energy
    zpe_match = PATTERNS["zero_point_energy"].search(content)
    if zpe_match:
        zpe_value = float(zpe_match.group(1))
        zpe_unit = zpe_match.group(2)
        data[f"Zero Point Energy ({zpe_unit})"] = zpe_value

    # Calculate derived values using consistent logic
    _calculate_derived_values(data)

    # Add fallback flag
    data["Fallback Used"] = "Yes" if fallback_used else "No"
    
    return data


def _calculate_derived_values(data: Dict[str, Any]) -> None:
    """
    Calculate derived thermodynamic values (H and G) in place.
    
    Args:
        data: Dictionary containing parsed data to modify
    """
    # Calculate H (kcal/mol)
    if "E (kcal/mol)" in data and "Total Enthalpy Corr. (kcal/mol)" in data:
        data["H (kcal/mol)"] = data["E (kcal/mol)"] + data["Total Enthalpy Corr. (kcal/mol)"]

    # Calculate G (kcal/mol)
    if all(key in data for key in ["H (kcal/mol)", "Temperature (K)", "Total Entropy Corr. (kcal/mol.K)"]):
        data["G (kcal/mol)"] = data["H (kcal/mol)"] - data["Temperature (K)"] * data["Total Entropy Corr. (kcal/mol.K)"]


def parse_sp_thermodynamic_data(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse thermodynamic data from SP (Single Point) Q-Chem output files.
    SP files have different patterns than OPT files.
    
    Args:
        content: Raw text content of the SP output file
        
    Returns:
        Dictionary containing parsed SP data or None if parsing fails
    """
    # TODO: Implement SP-specific parsing patterns
    # Will use similar pattern-based approach as OPT parser
    pass
