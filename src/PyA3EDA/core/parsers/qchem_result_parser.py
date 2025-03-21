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
    "final_energy": re.compile(r"Final energy is\s+([-+]?\d+\.\d+)"),
    "final_energy_fallback": re.compile(r"Total energy =\s+([-+]?\d+\.\d+)"),
    "optimization_status": re.compile(r"(OPTIMIZATION CONVERGED|TRANSITION STATE CONVERGED)"),
    "thermodynamics": re.compile(r"STANDARD THERMODYNAMIC QUANTITIES AT\s+([-+]?\d+\.\d+)\s*K\s+AND\s+([-+]?\d+\.\d+)\s*ATM"),
    "imaginary_frequencies": re.compile(r"This Molecule has\s+(\d+)\s+Imaginary Frequencies"),
    "zero_point_energy": re.compile(r"Zero point vibrational energy:\s+([-+]?\d+\.\d+)\s+(\S+)"),
    "qrrho_parameters": re.compile(r"Quasi-RRHO corrections using alpha\s*=\s*(\d+),\s*and omega\s*=\s*(\d+)\s*cm\^-1"),
    "qrrho_total_enthalpy": re.compile(r"QRRHO-Total Enthalpy:\s+([-+]?\d+\.\d+)\s+(\S+)"),
    "total_enthalpy_fallback": re.compile(r"Total Enthalpy:\s+([-+]?\d+\.\d+)\s+(\S+)"),
    "qrrho_total_entropy": re.compile(r"QRRHO-Total Entropy:\s+([-+]?\d+\.\d+)\s+(\S+)"),
    "total_entropy_fallback": re.compile(r"Total Entropy:\s+([-+]?\d+\.\d+)\s+(\S+)")
}

def get_energy(content: str) -> Optional[float]:
    """Extract final energy from content, with fallback option."""
    for key in ["final_energy", "final_energy_fallback"]:
        match = PATTERNS[key].search(content)
        if match:
            return float(match.group(1))
    return None

def get_value_with_fallback(content: str, primary_pattern: Pattern, fallback_pattern: Pattern) -> Tuple[Optional[float], Optional[str], bool]:
    """Extract value with unit, falling back to secondary pattern if primary fails."""
    primary_match = primary_pattern.search(content)
    if primary_match:
        return float(primary_match.group(1)), primary_match.group(2), False
    fallback_match = fallback_pattern.search(content)
    if fallback_match:
        return float(fallback_match.group(1)), fallback_match.group(2), True
    return None, None, False

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
    
    # Energy extraction (assumed in Hartrees)
    energy_value = get_energy(content)
    if energy_value is not None:
        data["E (Ha)"] = energy_value
        # Convert energy from Hartrees to kcal/mol
        data["E (kcal/mol)"] = energy_value * Constants.HARTREE_TO_KCALMOL
    else:
        return None  # Can't proceed without energy

    # Enthalpy extraction
    enthalpy_value, enthalpy_unit, enthalpy_fallback = get_value_with_fallback(
        content, 
        PATTERNS["qrrho_total_enthalpy"],
        PATTERNS["total_enthalpy_fallback"]
    )
    
    if enthalpy_value is not None:
        # Convert enthalpy to kcal/mol
        enthalpy_value_converted = convert_energy_unit(enthalpy_value, enthalpy_unit, "kcal/mol")
        data["Total Enthalpy Corr. (kcal/mol)"] = enthalpy_value_converted
        
        if enthalpy_fallback:
            fallback_used = True

    # Entropy extraction
    entropy_value, entropy_unit, entropy_fallback = get_value_with_fallback(
        content,
        PATTERNS["qrrho_total_entropy"],
        PATTERNS["total_entropy_fallback"]
    )
    
    if entropy_value is not None:
        # Convert entropy to kcal/mol·K
        entropy_value_converted = convert_energy_unit(entropy_value, entropy_unit, "kcal/mol.K")
        data["Total Entropy Corr. (kcal/mol.K)"] = entropy_value_converted
        
        if entropy_fallback:
            fallback_used = True

    # Extract other data
    for key, pattern in PATTERNS.items():
        # Skip already handled patterns
        if key in [
            "final_energy", 
            "final_energy_fallback",
            "qrrho_total_enthalpy",
            "total_enthalpy_fallback",
            "qrrho_total_entropy",
            "total_entropy_fallback"
        ]:
            continue
            
        match = pattern.search(content)
        if match:
            if key == "optimization_status":
                data["Optimization Status"] = match.group(1)
            elif key == "thermodynamics":
                data["Temperature (K)"] = float(match.group(1))
                data["Pressure (atm)"] = float(match.group(2))
            elif key == "qrrho_parameters":
                data["Alpha"] = int(match.group(1))
                data["Omega (cm^-1)"] = int(match.group(2))
            elif key == "imaginary_frequencies":
                data["Imaginary Frequencies"] = int(match.group(1))
            elif key == "zero_point_energy":
                value = float(match.group(1))
                unit = match.group(2)
                column_name = f"Zero Point Energy ({unit})"
                data[column_name] = value
            else:
                value = float(match.group(1))
                unit = match.group(2) if match.lastindex >= 2 else ""
                column_name = f"{key.replace('_', ' ').title()} ({unit})" if unit else key.replace("_", " ").title()
                data[column_name] = value

    # Calculate H (kcal/mol)
    if "E (kcal/mol)" in data and "Total Enthalpy Corr. (kcal/mol)" in data:
        data["H (kcal/mol)"] = data["E (kcal/mol)"] + data["Total Enthalpy Corr. (kcal/mol)"]

    # Calculate G (kcal/mol)
    if "H (kcal/mol)" in data and "Temperature (K)" in data and "Total Entropy Corr. (kcal/mol.K)" in data:
        data["G (kcal/mol)"] = data["H (kcal/mol)"] - data["Temperature (K)"] * data["Total Entropy Corr. (kcal/mol.K)"]

    # Add 'Fallback Used' column if any fallback was used
    data["Fallback Used"] = "Yes" if fallback_used else "No"
    
    return data
