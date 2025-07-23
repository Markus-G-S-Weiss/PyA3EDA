"""
Unit Converter Module

Provides functions for converting between different energy units in computational chemistry.
"""

import logging
from PyA3EDA.core.constants import Constants

def convert_energy_unit(value: float, unit: str, target_unit: str = "kcal/mol") -> float:
    """
    Convert energy value from source unit to target unit.
    
    Args:
        value: The numerical value to convert
        unit: The original unit of the value
        target_unit: The desired output unit
        
    Returns:
        The converted value in target units
    """
    if unit == target_unit:
        return value
    
    # Normalize unit names for comparison
    unit_lower = unit.lower()
    target_lower = target_unit.lower()
    
    # Handle Hartree to kcal/mol conversion
    if unit_lower in ["hartree", "ha", "a.u."] and target_lower == "kcal/mol":
        return value * Constants.HARTREE_TO_KCALMOL
    
    # Handle Hartree to Ha conversion (identity but for consistency)
    if unit_lower in ["hartree", "ha", "a.u."] and target_lower in ["hartree", "ha", "a.u."]:
        return value
    
    # Handle kcal/mol to Hartree conversion
    if unit_lower == "kcal/mol" and target_lower in ["hartree", "ha", "a.u."]:
        return value / Constants.HARTREE_TO_KCALMOL
    
    # Handle kJ/mol to kcal/mol conversion
    if unit_lower == "kj/mol" and target_lower == "kcal/mol":
        return value * Constants.KJMOL_TO_KCALMOL
    
    # Handle kcal/mol to kJ/mol conversion
    if unit_lower == "kcal/mol" and target_lower == "kj/mol":
        return value / Constants.KJMOL_TO_KCALMOL
    
    # Handle kJ/mol to Hartree conversion
    if unit_lower == "kj/mol" and target_lower in ["hartree", "ha", "a.u."]:
        return value * Constants.KJMOL_TO_KCALMOL / Constants.HARTREE_TO_KCALMOL
    
    # Handle Hartree to kJ/mol conversion
    if unit_lower in ["hartree", "ha", "a.u."] and target_lower == "kj/mol":
        return value * Constants.HARTREE_TO_KCALMOL / Constants.KJMOL_TO_KCALMOL
    
    # Handle cal/mol to kcal/mol conversion (for entropy)
    if unit_lower in ["cal/mol.k", "cal/mol·k"] and target_lower == "kcal/mol.k":
        return value * Constants.TO_KILO
    
    # If we don't know how to convert, log warning and return original
    logging.warning(f"Unrecognized unit conversion: {unit} to {target_unit}. Returning original value.")
    return value