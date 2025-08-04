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
    # Normalize unit names for comparison
    unit_lower = unit.lower()
    target_lower = target_unit.lower()
    
    # Define equivalent unit groups
    hartree_units = {"hartree", "ha", "a.u."}
    kcalmol_units = {"kcal/mol"}
    kjmol_units = {"kj/mol"}
    calmolkelvin_units = {"cal/mol.k"}
    kcalmolkelvin_units = {"kcal/mol.k"}
    
    # Check if source and target are equivalent (same unit group)
    if ((unit_lower in hartree_units and target_lower in hartree_units) or
        (unit_lower in kcalmol_units and target_lower in kcalmol_units) or
        (unit_lower in kjmol_units and target_lower in kjmol_units) or
        (unit_lower in calmolkelvin_units and target_lower in kcalmolkelvin_units) or
        (unit_lower in kcalmolkelvin_units and target_lower in kcalmolkelvin_units)):
        return value
    
    # Handle Hartree to kcal/mol conversion
    if unit_lower in hartree_units and target_lower in kcalmol_units:
        return value * Constants.HARTREE_TO_KCALMOL
    
    # Handle kcal/mol to Hartree conversion
    if unit_lower in kcalmol_units and target_lower in hartree_units:
        return value / Constants.HARTREE_TO_KCALMOL
    
    # Handle Hartree to kJ/mol conversion
    if unit_lower in hartree_units and target_lower in kjmol_units:
        return value * Constants.HARTREE_TO_KJMOL

    # Handle kJ/mol to Hartree conversion
    if unit_lower in kjmol_units and target_lower in hartree_units:
        return value / Constants.HARTREE_TO_KJMOL

    # Handle kJ/mol to kcal/mol conversion
    if unit_lower in kjmol_units and target_lower in kcalmol_units:
        return value * Constants.KJMOL_TO_KCALMOL
    
    # Handle kcal/mol to kJ/mol conversion
    if unit_lower in kcalmol_units and target_lower in kjmol_units:
        return value / Constants.KJMOL_TO_KCALMOL
    
    # Handle cal/mol to kcal/mol conversion (for entropy)
    if unit_lower in calmolkelvin_units and target_lower in kcalmolkelvin_units:
        return value * Constants.TO_KILO
    
    # If we don't know how to convert, log warning and return original
    logging.warning(f"Unrecognized unit conversion: {unit} to {target_unit}. Returning original value.")
    return value