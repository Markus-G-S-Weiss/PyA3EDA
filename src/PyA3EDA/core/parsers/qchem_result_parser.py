"""
Q-Chem Parser Module

Pure parsing functions that extract numerical data from Q-Chem output text content.
Each function focuses on a single parsing task without business logic or cross-file operations.
Returns raw parsed values that can be further processed by extraction logic.
"""
import re
import logging
from typing import Optional, Tuple, Dict, Any, Pattern, List

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
    "total_entropy_fallback": re.compile(r"Total Entropy:\s+([-+]?\d+\.\d+)\s+([A-Za-z][A-Za-z0-9./\-]*)", re.MULTILINE),
    # SMD CDS energy patterns
    "smd_g_enp": re.compile(r"\(3\)\s+G-ENP\(liq\) elect-nuc-pol free energy of system\s+([-+]?\d+\.\d+)\s+a\.u\.", re.MULTILINE),
    "smd_g_s": re.compile(r"\(6\)\s+G-S\(liq\) free energy of system\s+([-+]?\d+\.\d+)\s+a\.u\.", re.MULTILINE),
    "smd_cds_kcal": re.compile(r"\(4\)\s+G-CDS\(liq\) cavity-dispersion-solvent structure\s+([-+]?\d+\.\d+)\s+kcal/mol", re.MULTILINE),
    "smd_cds_summary": re.compile(r"G_CDS\s+=\s+([-+]?\d+\.\d+)\s+kcal/mol", re.MULTILINE),
    "smd_cds_sp_total": re.compile(r"Total:\s+([-+]?\d+\.\d+)\s*\n\s*-+", re.MULTILINE),
    # EDA-specific patterns
    "eda_polarized_energy": re.compile(r"Energy prior to optimization \(guess energy\)\s*=\s*([-+]?\d+\.\d+)", re.MULTILINE),
    "eda_convergence_energy": re.compile(r"^\s*\d+\s+([-+]?\d+\.\d+)\s+[\d.e-]+\s+\d+\s+Convergence criterion met", re.MULTILINE),
    "bsse_energy": re.compile(r"BSSE \(kJ/mol\)\s*=\s*([-+]?\d+\.\d+)", re.MULTILINE)
}


def extract_with_pattern(content: str, primary_pattern: Pattern, fallback_pattern: Pattern = None, 
                        field_mapping: Dict[str, str] = None, default_unit: str = None) -> Tuple[Any, bool]:
    """
    Universal pattern extraction function that handles all parsing scenarios.
    Always uses findall() and takes the last match for consistency.
    
    Args:
        content: Text content to search
        primary_pattern: Primary regex pattern to try first
        fallback_pattern: Optional fallback regex pattern if primary fails
        field_mapping: Optional dictionary mapping group indices to field names
        default_unit: Default unit if pattern doesn't capture unit
        
    Returns:
        Tuple of (result, fallback_used) where result format depends on parameters:
        - Single value: float
        - Value with unit: (float, str)  
        - Multiple fields: Dict[str, Any]
        - Nothing found: None
    """
    fallback_used = False
    
    # Try primary pattern first
    matches = primary_pattern.findall(content)
    
    # Try fallback pattern if primary failed and fallback provided
    if not matches and fallback_pattern:
        matches = fallback_pattern.findall(content)
        fallback_used = True
    
    if not matches:
        return None, fallback_used
    
    # Get the last match (most recent/final occurrence)
    last_match = matches[-1]
    
    # Handle field mapping (for multi-group patterns)
    if field_mapping:
        result = {}
        if isinstance(last_match, tuple):
            for group_idx, field_name in field_mapping.items():
                if group_idx <= len(last_match):
                    value = last_match[group_idx - 1]  # findall is 0-indexed, field_mapping is 1-indexed
                    try:
                        if '.' in str(value):
                            result[field_name] = float(value)
                        else:
                            result[field_name] = int(value)
                    except (ValueError, TypeError):
                        result[field_name] = value
        else:
            # Single value with field mapping
            if 1 in field_mapping:
                try:
                    result[field_mapping[1]] = float(last_match) if '.' in str(last_match) else int(last_match)
                except (ValueError, TypeError):
                    result[field_mapping[1]] = last_match
        return result, fallback_used
    
    # Handle value with unit (tuple result)
    if isinstance(last_match, tuple):
        value = float(last_match[0])
        unit = last_match[1] if len(last_match) > 1 and last_match[1] else default_unit
        return (value, unit), fallback_used
    
    # Handle single value
    return float(last_match), fallback_used


# PURE PARSING FUNCTIONS - Each function parses one specific data type


def parse_energy(content: str) -> Optional[Dict[str, Any]]:
    """Parse final energy from Q-Chem output content."""
    result, fallback_used = extract_with_pattern(
        content, PATTERNS["final_energy"], PATTERNS["final_energy_fallback"], default_unit="Ha")
    
    if result is not None:
        energy_value, energy_unit = result
        return {
            f"E ({energy_unit})": energy_value,
            "E (kcal/mol)": convert_energy_unit(energy_value, energy_unit, "kcal/mol"),
            "energy_fallback_used": fallback_used
        }
    return None


def parse_enthalpy(content: str) -> Optional[Dict[str, Any]]:
    """Parse enthalpy correction from Q-Chem output content."""
    result, fallback_used = extract_with_pattern(
        content, PATTERNS["qrrho_total_enthalpy"], PATTERNS["total_enthalpy_fallback"])
    
    if result is not None:
        enthalpy_value, enthalpy_unit = result
        return {
            "Total Enthalpy Corr. (kcal/mol)": convert_energy_unit(enthalpy_value, enthalpy_unit, "kcal/mol"),
            "enthalpy_fallback_used": fallback_used
        }
    return None


def parse_entropy(content: str) -> Optional[Dict[str, Any]]:
    """Parse entropy correction from Q-Chem output content."""
    result, fallback_used = extract_with_pattern(
        content, PATTERNS["qrrho_total_entropy"], PATTERNS["total_entropy_fallback"])
    
    if result is not None:
        entropy_value, entropy_unit = result
        return {
            "Total Entropy Corr. (kcal/mol.K)": convert_energy_unit(entropy_value, entropy_unit, "kcal/mol.K"),
            "entropy_fallback_used": fallback_used
        }
    return None


def parse_optimization_status(content: str) -> Optional[Dict[str, Any]]:
    """Parse optimization status from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["optimization_status"], field_mapping={1: "status"})
    return {"Optimization Status": result["status"]} if result else None


def parse_thermodynamic_conditions(content: str) -> Optional[Dict[str, Any]]:
    """Parse temperature and pressure from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["thermodynamics"], field_mapping={1: "temperature", 2: "pressure"})
    return {"Temperature (K)": result["temperature"], "Pressure (atm)": result["pressure"]} if result else None


def parse_qrrho_parameters(content: str) -> Optional[Dict[str, Any]]:
    """Parse QRRHO parameters from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["qrrho_parameters"], field_mapping={1: "alpha", 2: "omega"})
    return {"Alpha": result["alpha"], "Omega (cm^-1)": result["omega"]} if result else None


def parse_imaginary_frequencies(content: str) -> Optional[Dict[str, Any]]:
    """Parse imaginary frequencies count from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["imaginary_frequencies"], field_mapping={1: "count"})
    return {"Imaginary Frequencies": result["count"]} if result else None


def parse_zero_point_energy(content: str) -> Optional[Dict[str, Any]]:
    """Parse zero point energy from Q-Chem output content."""
    result, _ = extract_with_pattern(content, PATTERNS["zero_point_energy"], default_unit="kcal/mol")
    
    if result is not None:
        zpe_value, zpe_unit = result
        return {f"Zero Point Energy ({zpe_unit})": zpe_value}
    return None


def parse_smd_cds_raw_values(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse raw SMD CDS energy values from Q-Chem output content.
    Returns only the final/last values since intermediate values are not needed.
    Does NOT perform cross-file validation or complex logic - just extracts raw values.
    """
    result = {}
    
    # Define value extractors - pattern name maps to result key
    extractors = [
        ("smd_g_s", "g_s_final"),
        ("smd_g_enp", "g_enp_final"),
        ("smd_cds_kcal", "cds_kcal_final"),
        ("smd_cds_summary", "cds_summary_final"),
        ("smd_cds_sp_total", "cds_sp_total_final")
    ]
    
    # Extract each value using the same pattern
    for pattern_name, result_key in extractors:
        value, _ = extract_with_pattern(content, PATTERNS[pattern_name])
        if value is not None:
            result[result_key] = value
    
    return result if result else None


def parse_eda_polarized_energy(content: str) -> Optional[Dict[str, Any]]:
    """Parse polarized energy from EDA SP calculations (frz/pol types)."""
    result, _ = extract_with_pattern(content, PATTERNS["eda_polarized_energy"], field_mapping={1: "polarized_energy"})
    return {"polarized_energy": result["polarized_energy"]} if result else None


def parse_eda_convergence_energy(content: str) -> Optional[Dict[str, Any]]:
    """Parse convergence criterion energy from EDA SP calculations (full type)."""
    result, _ = extract_with_pattern(content, PATTERNS["eda_convergence_energy"], field_mapping={1: "convergence_energy"})
    return {"convergence_energy": result["convergence_energy"]} if result else None


def parse_bsse_energy(content: str) -> Optional[Dict[str, Any]]:
    """Parse BSSE energy from EDA SP calculations (full type correction)."""
    result, _ = extract_with_pattern(content, PATTERNS["bsse_energy"], field_mapping={1: "bsse_energy"})
    return {"bsse_energy": result["bsse_energy"]} if result else None
