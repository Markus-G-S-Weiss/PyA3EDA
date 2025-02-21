"""
File Builder Module

This module centralizes the logic for constructing the directory structure and complete
Q-Chem input files based on a sanitized configuration and template files.
It produces a folder tree structured as follows:

  {Method}_{Basis}/
  ├── no_cat/
  │   ├── reactants/
  │   │   ├── {Reactant1}/
  │   │   │   └── {Reactant1}_opt.in
  │   │   ├── {Reactant2}/
  │   │   │   └── {Reactant2}_opt.in
  │   │   └── {Reactant1}-{Reactant2}/
  │   │       └── {Reactant1}-{Reactant2}_opt.in
  │   ├── products/
  │   │   ├── {Product1}/
  │   │   │   └── {Product1}_opt.in
  │   │   └── {Product2}/
  │       └── {Product2}_opt.in
  │   └── ts/
  │       └── tscomplex.in
  └── {Catalyst}/
      ├── preTS/
      │   ├── {Catalyst}-{Reactant1}/
      │   │   ├── full_cat/
      │   │   │   └── preTS_{Catalyst}-{Reactant1}_full_cat_opt.in
      │   │   ├── pol_cat/
      │   │   │   └── preTS_{Catalyst}-{Reactant1}_pol_cat_opt.in
      │   │   └── frz_cat/
      │   │       └── preTS_{Catalyst}-{Reactant1}_frz_cat_opt.in
      │   ├── {Catalyst}-{Reactant2}/
      │   │   ├── full_cat/
      │   │   │   └── preTS_{Catalyst}-{Reactant2}_full_cat_opt.in
      │   │   ├── pol_cat/
      │   │   │   └── preTS_{Catalyst}-{Reactant2}_pol_cat_opt.in
      │   │   └── frz_cat/
      │   │       └── preTS_{Catalyst}-{Reactant2}_frz_cat_opt.in
      │   └── {Catalyst}-{Reactant1}-{Reactant2}/
      │       ├── full_cat/
      │       │   └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_full_cat_opt.in
      │       ├── pol_cat/
      │       │   └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_pol_cat_opt.in
      │       └── frz_cat/
      │           └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_frz_cat_opt.in
      ├── postTS/
      │   └── {Catalyst}-{Product1}/
      │       ├── full_cat/
      │       │   └── postTS_{Catalyst}-{Product1}_full_cat_opt.in
      │       ├── pol_cat/
      │       │   └── postTS_{Catalyst}-{Product1}_pol_cat_opt.in
      │       └── frz_cat/
      │           └── postTS_{Catalyst}-{Product1}_frz_cat_opt.in
      └── ts/
           ├── full_cat/
           │   └── ts_{Catalyst}-tscomplex_full_opt.in
           ├── pol_cat/
           │   └── ts_{Catalyst}-tscomplex_pol_opt.in
           └── frz_cat/
               └── ts_{Catalyst}-tscomplex_frz_opt.in

The module uses molecule builder routines (both standard and fragmented)
to generate the Q-Chem input file content before writing them to disk.
"""

from pathlib import Path
import logging
from itertools import combinations
from PyA3EDA.core.utils.file_utils import read_text, write_text
from PyA3EDA.core.builders.molecule_builder import (
    build_standard_molecule_section, 
    build_fragmented_molecule_section
)
from PyA3EDA.core.builders import rem_builder

def build_file_path(system_dir: Path, method: str, basis: str, category: str,
                    branch: str, species: str, calc_type: str, catalyst_name: str = "") -> Path:
    """
    Constructs the full file path and ensures that all necessary directories exist.
    """
    base_folder = system_dir / f"{method}_{basis}"
    if category == "no_cat":
        if branch in ("reactants", "products"):
            relative = Path("no_cat") / branch / species / f"{species}_opt.in"
        elif branch == "ts":
            relative = Path("no_cat") / "ts" / "tscomplex_opt.in"
        else:
            raise ValueError(f"Unknown branch for no_cat: {branch}")
        full_path = base_folder / relative
    elif category == "cat":
        if not catalyst_name:
            raise ValueError("For catalyst cases, catalyst_name must be provided.")
        if branch == "preTS":
            relative = Path(catalyst_name) / "preTS" / species / calc_type / f"preTS_{species}_{calc_type}_opt.in"
        elif branch == "postTS":
            relative = Path(catalyst_name) / "postTS" / species / calc_type / f"postTS_{species}_{calc_type}_opt.in"
        elif branch == "ts":
            relative = Path(catalyst_name) / "ts" / calc_type / f"ts_{catalyst_name}-tscomplex_{calc_type}_opt.in"
        elif branch == "cat":
            relative = Path(catalyst_name) / "cat" / f"{catalyst_name}_opt.in"
        else:
            raise ValueError(f"Unknown branch for catalyst: {branch}")
        full_path = base_folder / relative
    else:
        raise ValueError(f"Unknown category: {category}")
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return full_path

def build_input_file_content(template_base: str, rem_section: str, molecule_section: str) -> str:
    """
    Assembles the complete Q-Chem input file content by inserting
    the molecule section and the fully formatted REM section into the base template.
    """
    return template_base.format(molecule_section=molecule_section.strip(),
                                rem_section=rem_section.rstrip())

def build_and_write_input_file(system_dir: Path, method: str, basis: str,
                               category: str, branch: str,
                               species: str, calc_type: str,
                               template_base_path: Path,
                               molecule_template_path: Path,
                               rem_substitutions: dict,
                               molecule_processing_fn,
                               catalyst_name: str = "") -> None:
    """
    Constructs the file path, assembles the input file content using a molecule processing function,
    and writes the file to disk.
    """
    file_path = build_file_path(system_dir, method, basis, category, branch, species, calc_type, catalyst_name)
    base_template = read_text(template_base_path)
    molecule_template_raw = read_text(molecule_template_path)
    
    # For fragmented processing, pass catalyst_name to select the proper fragment data.
    if molecule_processing_fn == build_fragmented_molecule_section and catalyst_name:
        molecule_section = molecule_processing_fn(molecule_template_raw, species, catalyst_name)
    else:
        molecule_section = molecule_processing_fn(molecule_template_raw, species) if molecule_processing_fn else molecule_template_raw

    lines = molecule_section.splitlines()
    atom_count = len(lines) - 1 if lines else 0
    jobtype = "ts" if branch == "ts" else ("sp" if atom_count == 1 else "opt")
    rem_section = rem_builder.build_rem_section_for_calc_type(
        system_dir, 
        calc_type, 
        rem_substitutions["method"], 
        basis, 
        rem_substitutions.get("dispersion", "false"),
        jobtype
    )
    content = build_input_file_content(base_template, rem_section, molecule_section)
    if write_text(file_path, content):
        logging.info(f"Input file written to {file_path}")
    else:
        logging.error(f"Failed to write input file to {file_path}")

def get_combinations(species_list: list, min_length: int = 1) -> list:
    """
    Returns all combinations from the species_list with combination length >= min_length,
    preserving configuration order, as hyphen-joined strings.
    """
    combos = []
    n = len(species_list)
    for r in range(min_length, n + 1):
        for comb in combinations(species_list, r):
            names = [item["sanitized"] for item in comb]
            combos.append("-".join(names))
    return combos

def generate_all_inputs(config: dict, system_dir: Path) -> None:
    """
    Generate all Q-Chem input files based on the sanitized configuration.
    """
    templates_dir = system_dir / "templates"
    base_template_path = templates_dir / "base_template.in"
    
    # -------- no_cat branch --------
    for method in config["methods"]:
        for basis in method["basis_sets"]:
            # ----- Reactants -----
            for reactant in config.get("reactants", []):
                species = reactant["sanitized"]
                build_and_write_input_file(
                    system_dir=system_dir,
                    method=method["sanitized"],
                    basis=basis,
                    category="no_cat",
                    branch="reactants",
                    species=species,
                    calc_type="",
                    template_base_path=base_template_path,
                    molecule_template_path=templates_dir / "molecule" / f"{species}.xyz",
                    rem_substitutions={
                        "method": method["original"],
                        "basis": basis,
                        "dispersion": method.get("dispersion", "false")
                    },
                    molecule_processing_fn=build_standard_molecule_section
                )
            reactants_included = [r for r in config.get("reactants", []) if r.get("include", False)]
            if len(reactants_included) > 1:
                for combo in get_combinations(reactants_included, min_length=2):
                    build_and_write_input_file(
                        system_dir=system_dir,
                        method=method["sanitized"],
                        basis=basis,
                        category="no_cat",
                        branch="reactants",
                        species=combo,
                        calc_type="",
                        template_base_path=base_template_path,
                        molecule_template_path=templates_dir / "molecule" / f"{combo}.xyz",
                        rem_substitutions={
                            "method": method["original"],
                            "basis": basis,
                            "dispersion": method.get("dispersion", "false")
                        },
                        molecule_processing_fn=build_standard_molecule_section
                    )
            # ----- Products -----
            for product in config.get("products", []):
                species = product["sanitized"]
                build_and_write_input_file(
                    system_dir=system_dir,
                    method=method["sanitized"],
                    basis=basis,
                    category="no_cat",
                    branch="products",
                    species=species,
                    calc_type="",
                    template_base_path=base_template_path,
                    molecule_template_path=templates_dir / "molecule" / f"{species}.xyz",
                    rem_substitutions={
                        "method": method["original"],
                        "basis": basis,
                        "dispersion": method.get("dispersion", "false")
                    },
                    molecule_processing_fn=build_standard_molecule_section
                )
            products_included = [p for p in config.get("products", []) if p.get("include", False)]
            if len(products_included) > 1:
                for combo in get_combinations(products_included, min_length=2):
                    build_and_write_input_file(
                        system_dir=system_dir,
                        method=method["sanitized"],
                        basis=basis,
                        category="no_cat",
                        branch="products",
                        species=combo,
                        calc_type="",
                        template_base_path=base_template_path,
                        molecule_template_path=templates_dir / "molecule" / f"{combo}.xyz",
                        rem_substitutions={
                            "method": method["original"],
                            "basis": basis,
                            "dispersion": method.get("dispersion", "false")
                        },
                        molecule_processing_fn=build_standard_molecule_section
                    )
            build_and_write_input_file(
                system_dir=system_dir,
                method=method["sanitized"],
                basis=basis,
                category="no_cat",
                branch="ts",
                species="tscomplex",
                calc_type="",
                template_base_path=base_template_path,
                molecule_template_path=templates_dir / "molecule" / "tscomplex.xyz",
                rem_substitutions={
                    "method": method["original"],
                    "basis": basis,
                    "dispersion": method.get("dispersion", "false")
                },
                molecule_processing_fn=build_standard_molecule_section
            )
            
            # -------- Catalyst branch --------
            for catalyst in config.get("catalysts", []):
                # Catalyst-only input file in branch "cat".
                build_and_write_input_file(
                    system_dir=system_dir,
                    method=method["sanitized"],
                    basis=basis,
                    category="cat",
                    branch="cat",
                    species=catalyst["sanitized"],
                    calc_type="",
                    template_base_path=base_template_path,
                    molecule_template_path=templates_dir / "molecule" / f"{catalyst['sanitized']}.xyz",
                    rem_substitutions={
                        "method": method["original"],
                        "basis": basis,
                        "dispersion": method.get("dispersion", "false")
                    },
                    molecule_processing_fn=build_standard_molecule_section,
                    catalyst_name=catalyst["sanitized"]
                )
                
                # preTS: use included reactants.
                reactants_included = [r for r in config.get("reactants", []) if r.get("include", False)]
                for combo in get_combinations(reactants_included):
                    species = f"{catalyst['sanitized']}-{combo}"
                    for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                        build_and_write_input_file(
                            system_dir=system_dir,
                            method=method["sanitized"],
                            basis=basis,
                            category="cat",
                            branch="preTS",
                            species=species,
                            calc_type=calc_type,
                            template_base_path=base_template_path,
                            molecule_template_path=templates_dir / "molecule" / f"preTS_{species}.xyz",
                            rem_substitutions={
                                "method": method["original"],
                                "basis": basis,
                                "dispersion": method.get("dispersion", "false")
                            },
                            molecule_processing_fn=build_fragmented_molecule_section,
                            catalyst_name=catalyst["sanitized"]
                        )
                # postTS: use included products.
                products_included = [p for p in config.get("products", []) if p.get("include", False)]
                for combo in get_combinations(products_included):
                    species = f"{catalyst['sanitized']}-{combo}"
                    for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                        build_and_write_input_file(
                            system_dir=system_dir,
                            method=method["sanitized"],
                            basis=basis,
                            category="cat",
                            branch="postTS",
                            species=species,
                            calc_type=calc_type,
                            template_base_path=base_template_path,
                            molecule_template_path=templates_dir / "molecule" / f"postTS_{species}.xyz",
                            rem_substitutions={
                                "method": method["original"],
                                "basis": basis,
                                "dispersion": method.get("dispersion", "false")
                            },
                            molecule_processing_fn=build_fragmented_molecule_section,
                            catalyst_name=catalyst["sanitized"]
                        )
                # Catalyst TS: one file per calc_type.
                for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                    build_and_write_input_file(
                        system_dir=system_dir,
                        method=method["sanitized"],
                        basis=basis,
                        category="cat",
                        branch="ts",
                        species=f"ts_{catalyst['sanitized']}-tscomplex",
                        calc_type=calc_type,
                        template_base_path=base_template_path,
                        molecule_template_path=templates_dir / "molecule" / f"ts_{catalyst['sanitized']}-tscomplex.xyz",
                        rem_substitutions={
                            "method": method["original"],
                            "basis": basis,
                            "dispersion": method.get("dispersion", "false")
                        },
                        molecule_processing_fn=build_fragmented_molecule_section,
                        catalyst_name=catalyst["sanitized"]
                    )
    logging.info("Input file generation completed.")

def iter_input_paths(config: dict, system_dir: Path):
    """
    Generator that yields expected Q-Chem input file paths based on the sanitized configuration.
    This uses the same logic as generate_all_inputs but yields each path on the fly.
    """
    # -------- no_cat branch --------
    for method in config["methods"]:
        for basis in method["basis_sets"]:
            # Reactants
            for reactant in config.get("reactants", []):
                species = reactant["sanitized"]
                yield build_file_path(system_dir, method["sanitized"], basis, "no_cat", "reactants", species, "", "")
            reactants_included = [r for r in config.get("reactants", []) if r.get("include", False)]
            if len(reactants_included) > 1:
                for combo in get_combinations(reactants_included, min_length=2):
                    yield build_file_path(system_dir, method["sanitized"], basis, "no_cat", "reactants", combo, "", "")
            # Products
            for product in config.get("products", []):
                species = product["sanitized"]
                yield build_file_path(system_dir, method["sanitized"], basis, "no_cat", "products", species, "", "")
            products_included = [p for p in config.get("products", []) if p.get("include", False)]
            if len(products_included) > 1:
                for combo in get_combinations(products_included, min_length=2):
                    yield build_file_path(system_dir, method["sanitized"], basis, "no_cat", "products", combo, "", "")
            # Transition state in no_cat branch
            yield build_file_path(system_dir, method["sanitized"], basis, "no_cat", "ts", "tscomplex", "", "")
            
            # -------- Catalyst branch --------
            for catalyst in config.get("catalysts", []):
                # Catalyst-only file in branch "cat"
                yield build_file_path(system_dir, method["sanitized"], basis, "cat", "cat", catalyst["sanitized"], "", catalyst["sanitized"])
                
                # preTS: using included reactants.
                reactants_included = [r for r in config.get("reactants", []) if r.get("include", False)]
                for combo in get_combinations(reactants_included):
                    species = f"{catalyst['sanitized']}-{combo}"
                    for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                        yield build_file_path(system_dir, method["sanitized"], basis, "cat", "preTS", species, calc_type, catalyst["sanitized"])
                        
                # postTS: using included products.
                products_included = [p for p in config.get("products", []) if p.get("include", False)]
                for combo in get_combinations(products_included):
                    species = f"{catalyst['sanitized']}-{combo}"
                    for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                        yield build_file_path(system_dir, method["sanitized"], basis, "cat", "postTS", species, calc_type, catalyst["sanitized"])
                        
                # Catalyst TS: one file per calc_type.
                for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                    yield build_file_path(system_dir, method["sanitized"], basis, "cat", "ts", f"ts_{catalyst['sanitized']}-tscomplex", calc_type, catalyst["sanitized"])