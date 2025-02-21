"""
Q-Chem Result Parser Module

Defines regular expression patterns and helper functions to extract numerical data from Q-Chem output files.
"""
import re
from typing import Optional, Tuple

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
    for key in ["final_energy", "final_energy_fallback"]:
        match = PATTERNS[key].search(content)
        if match:
            return float(match.group(1))
    return None

def get_value_with_fallback(content: str, primary_pattern: re.Pattern, fallback_pattern: re.Pattern) -> Tuple[Optional[float], Optional[str], bool]:
    primary_match = primary_pattern.search(content)
    if primary_match:
        return float(primary_match.group(1)), primary_match.group(2), False
    fallback_match = fallback_pattern.search(content)
    if fallback_match:
        return float(fallback_match.group(1)), fallback_match.group(2), True
    return None, None, False
