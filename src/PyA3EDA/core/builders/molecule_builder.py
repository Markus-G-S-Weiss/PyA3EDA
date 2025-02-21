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


def build_standard_molecule_section(xyz_text: str, identifier: str,
                                    override_charge: Optional[int] = None,
                                    override_multiplicity: Optional[int] = None) -> str:
    """
    Build a standard molecule section from an XYZ file.
    
    The XYZ file specified by 'identifier' supplies the charge, multiplicity,
    and atom list. Override charge and multiplicity if provided.
    
    Returns a string formatted for Q-Chem.
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
    atoms = data['atoms']
    return f"{charge} {mult}\n" + "\n".join(atoms)


def build_fragmented_molecule_section(composite_xyz_text: str,
                                      composite_id: str,
                                      catalyst_id: Optional[str] = None) -> str:
    """
    Build a fragmented molecule section from a composite XYZ file.
    
    The composite identifier follows the convention:
         catalyst-substrate1-substrate2-...
    The composite file provides the overall charge, multiplicity, and full atom list.
    
    The individual fragment data are obtained from cached files:
      - For standard files (e.g. "lip-methylethanoate-hydroxide.xyz"):
          Catalyst is looked up as "lip" and the substrate as "methylethanoate-hydroxide".
      - For TS files (e.g. "ts_lip-complex.xyz"):
          Catalyst is looked up as "lip" and the substrate as "ts_complex".
    
    The composite atom list is partitioned based on the number of atoms in the catalyst fragment.
    """
    # Parse overall composite data.
    composite_data = parse_xyz(composite_xyz_text, composite_id)
    if composite_data is None:
        logging.error("Failed to parse composite XYZ.")
        return ""
    total_atoms = composite_data['n_atoms']
    overall_charge = composite_data['charge']
    overall_mult = composite_data['multiplicity']
    composite_atoms = composite_data['atoms']

    # Determine lookup keys based on the naming convention.
    parts = composite_id.split("-")
    if len(parts) < 2:
        logging.error("Composite identifier does not contain both catalyst and substrate names.")
        return ""
    catalyst_name = parts[0]
    substrate_parts = parts[1:]
    cat_lookup_id = catalyst_id if catalyst_id is not None else catalyst_name
    substrate_lookup_id = "-".join(substrate_parts)

    # Retrieve catalyst data.
    catalyst_data = parse_xyz("", cat_lookup_id)
    if catalyst_data is None:
        logging.error(f"No cached data for catalyst with identifier '{cat_lookup_id}'.")
        return ""
    catalyst_N = catalyst_data['n_atoms']
    catalyst_charge = catalyst_data['charge']
    catalyst_mult = catalyst_data['multiplicity']

    # Retrieve substrate (combined fragment) data.
    substrate_data = parse_xyz("", substrate_lookup_id)
    if substrate_data is None:
        logging.error(f"No cached data for substrate with identifier '{substrate_lookup_id}'.")
        return ""
    substrate_N = substrate_data['n_atoms']
    substrate_charge = substrate_data['charge']
    substrate_mult = substrate_data['multiplicity']

    if catalyst_N + substrate_N != total_atoms:
        logging.warning(f"Total atoms in composite ({total_atoms}) do not equal sum of catalyst ({catalyst_N}) and substrate ({substrate_N}).")

    # Split composite atom list using the number of catalyst atoms.
    if len(composite_atoms) < total_atoms:
        logging.error("Insufficient atom lines in composite data.")
        return ""
    catalyst_atoms = composite_atoms[:catalyst_N]
    substrate_atoms = composite_atoms[catalyst_N:catalyst_N+substrate_N]

    composite_section = (
        f"{overall_charge} {overall_mult}\n"
        f"---\n"
        f"{catalyst_charge} {catalyst_mult}\n"
        f"{chr(10).join(catalyst_atoms)}\n"
        f"---\n"
        f"{substrate_charge} {substrate_mult}\n"
        f"{chr(10).join(substrate_atoms)}"
    )
    return composite_section
