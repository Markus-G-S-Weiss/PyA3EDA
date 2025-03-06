"""
Molecule Builder Module

This module provides functions to build the molecule section for Q-Chem input files.
The overall charge, multiplicity, and atom list are taken from the composite XYZ file.
Fragment-specific attributes (atom count, charge, multiplicity) are obtained from cached
individual files. Naming conventions:
  - Standard (preTS/postTS): e.g. "lip-methylethanoate-hydroxide.xyz" uses:
       Catalyst  -> "lip.xyz"
       Substrate -> "methylethanoate-hydroxide.xyz"
  - TS: e.g. "ts_lip-complex.xyz" uses:
       Catalyst  -> "lip.xyz"
       Substrate -> "ts_complex.xyz"
"""

import logging
from typing import Optional, Dict, Any
from PyA3EDA.core.parsers.xyz_parser import parse_xyz
from PyA3EDA.core.parsers.output_xyz_parser import parse_qchem_output_xyz

# Helper functions for formatting
def _build_standard_section(charge: int, multiplicity: int, atoms: list[str]) -> str:
    """Return a standard molecule section string."""
    return f"{charge} {multiplicity}\n" + "\n".join(atoms)

def _build_fragmented_section(overall_charge: int, overall_mult: int,
                              catalyst_charge: int, catalyst_mult: int, catalyst_atoms: list[str],
                              substrate_charge: int, substrate_mult: int, substrate_atoms: list[str]) -> str:
    """Return a fragmented molecule section string."""
    return (
        f"{overall_charge} {overall_mult}\n"
        f"---\n"
        f"{catalyst_charge} {catalyst_mult}\n"
        f"{chr(10).join(catalyst_atoms)}\n"
        f"---\n"
        f"{substrate_charge} {substrate_mult}\n"
        f"{chr(10).join(substrate_atoms)}"
    )

# Original functions for opt jobs using template XYZ.
def build_standard_molecule_section(xyz_text: str, identifier: str,
                                    override_charge: Optional[int] = None,
                                    override_multiplicity: Optional[int] = None) -> str:
    """
    Build a standard molecule section from a template XYZ file.
    
    Uses the XYZ file specified by 'identifier' to supply the charge, multiplicity, and atom list.
    """
    data: Optional[Dict[str, Any]] = parse_xyz(xyz_text, identifier)
    if data is None:
        logging.error("Failed to parse XYZ for standard molecule.")
        return ""
    charge, mult = data['charge'], data['multiplicity']
    if override_charge is not None:
        charge = override_charge
    if override_multiplicity is not None:
        mult = override_multiplicity
    return _build_standard_section(charge, mult, data['atoms'])

def build_fragmented_molecule_section(composite_xyz_text: str,
                                      composite_id: str,
                                      catalyst_id: Optional[str] = None) -> str:
    """
    Build a fragmented molecule section from a composite XYZ file.
    
    The composite identifier follows the convention: catalyst-substrate1-...
    Cached data for the catalyst and substrate are retrieved for fragment-specific properties.
    """
    composite_data = parse_xyz(composite_xyz_text, composite_id)
    if composite_data is None:
        logging.error("Failed to parse composite XYZ.")
        return ""
    overall_charge = composite_data['charge']
    overall_mult = composite_data['multiplicity']
    composite_atoms = composite_data['atoms']
    total_atoms = composite_data['n_atoms']
    
    parts = composite_id.split("-")
    if len(parts) < 2:
        logging.error("Composite identifier does not contain both catalyst and substrate names.")
        return ""
    catalyst_name = parts[0]
    substrate_lookup_id = "-".join(parts[1:])
    
    catalyst_data = parse_xyz("", catalyst_id if catalyst_id is not None else catalyst_name)
    if catalyst_data is None:
        logging.error(f"No cached data for catalyst with identifier '{catalyst_name}'.")
        return ""
    substrate_data = parse_xyz("", substrate_lookup_id)
    if substrate_data is None:
        logging.error(f"No cached data for substrate with identifier '{substrate_lookup_id}'.")
        return ""
        
    catalyst_N = catalyst_data['n_atoms']
    substrate_N = substrate_data['n_atoms']
    if catalyst_N + substrate_N != total_atoms:
        logging.warning(
            f"Total atoms in composite ({total_atoms}) do not equal sum of catalyst ({catalyst_N}) and substrate ({substrate_N})."
        )
    if len(composite_atoms) < total_atoms:
        logging.error("Insufficient atom lines in composite data.")
        return ""
    
    catalyst_atoms = composite_atoms[:catalyst_N]
    substrate_atoms = composite_atoms[catalyst_N : catalyst_N + substrate_N]
    
    return _build_fragmented_section(overall_charge, overall_mult,
                                     catalyst_data['charge'], catalyst_data['multiplicity'], catalyst_atoms,
                                     substrate_data['charge'], substrate_data['multiplicity'], substrate_atoms)

# Functions for single-point (SP) jobs using coordinates from the output file.
def build_sp_standard_molecule_section(output_text: str, template_xyz_text: str, identifier: str,
                                       override_charge: Optional[int] = None,
                                       override_multiplicity: Optional[int] = None) -> str:
    """
    Build a standard molecule section for a single-point calculation.
    
    Retrieves charge and multiplicity from the template XYZ and updates coordinates
    using output file data.
    """
    cached_data: Optional[Dict[str, Any]] = parse_xyz(template_xyz_text, identifier)
    if cached_data is None:
        logging.error(f"Failed to retrieve cached XYZ data for '{identifier}'.")
        return ""
    parsed_out: Optional[Dict[str, Any]] = parse_qchem_output_xyz(output_text, identifier)
    if parsed_out is None:
        logging.error("Failed to parse output file for updated coordinates.")
        return ""
        
    charge = cached_data['charge']
    multiplicity = cached_data['multiplicity']
    if override_charge is not None:
        charge = override_charge
    if override_multiplicity is not None:
        multiplicity = override_multiplicity
    return _build_standard_section(charge, multiplicity, parsed_out['atoms'])

def build_sp_fragmented_molecule_section(output_text: str, composite_xyz_text: str,
                                           composite_id: str, catalyst_id: Optional[str] = None) -> str:
    """
    Build a fragmented molecule section for a single-point calculation.
    
    Uses cached composite data for charge/multiplicity and fragment properties,
    but updates the coordinate blocks with those parsed from the output file.
    """
    composite_data: Optional[Dict[str, Any]] = parse_xyz(composite_xyz_text, composite_id)
    if composite_data is None:
        logging.error("Failed to parse composite XYZ template.")
        return ""
    parsed_composite: Optional[Dict[str, Any]] = parse_qchem_output_xyz(output_text, composite_id)
    if parsed_composite is None:
        logging.error("Failed to parse output for composite coordinates.")
        return ""
    
    overall_charge = composite_data['charge']
    overall_mult = composite_data['multiplicity']
    total_atoms = composite_data['n_atoms']
    new_atoms = parsed_composite['atoms']
    
    parts = composite_id.split("-")
    if len(parts) < 2:
        logging.error("Composite identifier does not contain both catalyst and substrate names.")
        return ""
    catalyst_name = parts[0]
    substrate_lookup_id = "-".join(parts[1:])
    
    catalyst_data = parse_xyz("", catalyst_id if catalyst_id is not None else catalyst_name)
    if catalyst_data is None:
        logging.error(f"No cached data for catalyst with identifier '{catalyst_name}'.")
        return ""
    substrate_data = parse_xyz("", substrate_lookup_id)
    if substrate_data is None:
        logging.error(f"No cached data for substrate with identifier '{substrate_lookup_id}'.")
        return ""
    catalyst_N = catalyst_data['n_atoms']
    substrate_N = substrate_data['n_atoms']
    
    if len(new_atoms) < total_atoms:
        logging.error("Insufficient atom lines in output composite data.")
        return ""
        
    new_catalyst_atoms = new_atoms[:catalyst_N]
    new_substrate_atoms = new_atoms[catalyst_N : catalyst_N + substrate_N]
    
    return _build_fragmented_section(overall_charge, overall_mult,
                                     catalyst_data['charge'], catalyst_data['multiplicity'], new_catalyst_atoms,
                                     substrate_data['charge'], substrate_data['multiplicity'], new_substrate_atoms)
