"""
File Builder Module

This module centralizes the logic for constructing the directory structure and complete
Q-Chem input files based on a sanitized configuration and template files.
It produces a folder tree structured as described by the processed configuration.
It produces a folder tree structured as follows:

    {opt_method}_{opt_dispersion}_{opt_basis}_{opt_solvent}/
    ├── no_cat/
    │   ├── reactants/
    │   │   ├── {Reactant1}/
    │   │   │   ├── {Reactant1}_opt.in
    │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │   │         └── {Reactant1}_sp.in
    │   │   ├── {Reactant2}/
    │   │   │   ├── {Reactant2}_opt.in
    │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │   │         └── {Reactant2}_sp.in
    │   │   └── {Reactant1}-{Reactant2}/
    │   │         ├── {Reactant1}-{Reactant2}_opt.in
    │   │         └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │               └── {Reactant1}-{Reactant2}_sp.in
    │   ├── products/
    │   │   ├── {Product1}/
    │   │   │   ├── {Product1}_opt.in
    │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │   │         └── {Product1}_sp.in
    │   │   └── {Product2}/
    │   │         ├── {Product2}_opt.in
    │   │         └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │   │               └── {Product2}_sp.in
    │   └── ts/
    │         ├── tscomplex_opt.in
    │         └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
    │               └── tscomplex_sp.in
    └── {Catalyst}/
        ├── preTS/
        │   ├── {Catalyst}-{Reactant1}/
        │   │   ├── full_cat/
        │   │   │   ├── preTS_{Catalyst}-{Reactant1}_full_cat_opt.in
        │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │   │   │         └── preTS_{Catalyst}-{Reactant1}_full_cat_sp.in
        │   │   ├── pol_cat/
        │   │   │   ├── preTS_{Catalyst}-{Reactant1}_pol_cat_opt.in
        │   │   │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │   │   │         └── preTS_{Catalyst}-{Reactant1}_pol_cat_sp.in
        │   │   └── frz_cat/
        │   │       ├── preTS_{Catalyst}-{Reactant1}_frz_cat_opt.in
        │   │       └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │   │             └── preTS_{Catalyst}-{Reactant1}_frz_cat_sp.in
        │   └── {Catalyst}-{Reactant1}-{Reactant2}/
        │         ├── full_cat/
        │         │   ├── preTS_{Catalyst}-{Reactant1}-{Reactant2}_full_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_full_cat_sp.in
        │         ├── pol_cat/
        │         │   ├── preTS_{Catalyst}-{Reactant1}-{Reactant2}_pol_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_pol_cat_sp.in
        │         └── frz_cat/
        │               ├── preTS_{Catalyst}-{Reactant1}-{Reactant2}_frz_cat_opt.in
        │               └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │                     └── preTS_{Catalyst}-{Reactant1}-{Reactant2}_frz_cat_sp.in
        ├── postTS/
        │   └── {Catalyst}-{Product1}/
        │         ├── full_cat/
        │         │   ├── postTS_{Catalyst}-{Product1}_full_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── postTS_{Catalyst}-{Product1}_full_cat_sp.in
        │         ├── pol_cat/
        │         │   ├── postTS_{Catalyst}-{Product1}_pol_cat_opt.in
        │         │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │         │         └── postTS_{Catalyst}-{Product1}_pol_cat_sp.in
        │         └── frz_cat/
        │               ├── postTS_{Catalyst}-{Product1}_frz_cat_opt.in
        │               └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
        │                     └── postTS_{Catalyst}-{Product1}_frz_cat_sp.in
        └── ts/
            ├── full_cat/
            │   ├── ts_{Catalyst}-tscomplex_full_opt.in
            │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
            │         └── ts_{Catalyst}-tscomplex_full_sp.in
            ├── pol_cat/
            │   ├── ts_{Catalyst}-tscomplex_pol_opt.in
            │   └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
            │         └── ts_{Catalyst}-tscomplex_pol_sp.in
            └── frz_cat/
                    ├── ts_{Catalyst}-tscomplex_frz_opt.in
                    └── {sp_method}_{sp_dispersion}_{sp_basis}_{sp_solvent}_sp/
                        └── ts_{Catalyst}-tscomplex_frz_sp.in
The module uses molecule builder routines (both standard and fragmented)
to generate the Q-Chem input file content before writing them to disk.
"""

from pathlib import Path
import logging
from itertools import combinations
from PyA3EDA.core.utils.file_utils import read_text, write_text
from PyA3EDA.core.builders.molecule_builder import (
    build_standard_molecule_section, build_fragmented_molecule_section)
from PyA3EDA.core.builders import rem_builder


def get_molecule_section(template: str, molecule_processing_fn, species: str, 
                         catalyst: str = None, mode: str = "opt", 
                         opt_output_path: Path = None, system_dir: Path = None) -> str:
    """
    Returns the molecule section of the input file.
    
    Args:
        template: Template string for the molecule section
        molecule_processing_fn: Function to process the molecule section
        species: Species name
        catalyst: Catalyst name (optional)
        mode: Mode ("opt" or "sp")
        opt_output_path: Path to the optimization output file (for sp mode)
        system_dir: System directory to locate catalyst/substrate templates
        
    Returns:
        Processed molecule section string
    """
    # For SP mode, read the optimization output
    output_text = None
    if mode == "sp" and opt_output_path and opt_output_path.exists():
        output_text = read_text(opt_output_path)
    
    # For fragmented molecule sections, load catalyst and substrate templates
    catalyst_xyz_text = None
    substrate_xyz_text = None
    substrate_id = None
    
    if molecule_processing_fn == build_fragmented_molecule_section and system_dir:
        # Parse the species to get catalyst and substrate IDs
        parts = species.split("-")
        if len(parts) >= 2:
            cat_id = catalyst or parts[0]
            substrate_id = "-".join(parts[1:])
            
            # Load catalyst and substrate templates
            catalyst_template_path = system_dir / "templates" / "molecule" / f"{cat_id}.xyz"
            substrate_template_path = system_dir / "templates" / "molecule" / f"{substrate_id}.xyz"
            
            if catalyst_template_path.exists():
                catalyst_xyz_text = read_text(catalyst_template_path)
                if not catalyst_xyz_text:
                    logging.error(f"Failed to read catalyst template: {catalyst_template_path}")
            else:
                logging.error(f"Missing catalyst template: {catalyst_template_path}")
                
            if substrate_template_path.exists():
                substrate_xyz_text = read_text(substrate_template_path)
                if not substrate_xyz_text:
                    logging.error(f"Failed to read substrate template: {substrate_template_path}")
            else:
                logging.error(f"Missing substrate template: {substrate_template_path}")
    
    # Use the appropriate molecule building function
    if molecule_processing_fn == build_fragmented_molecule_section:
        return molecule_processing_fn(
            template, species, 
            catalyst_xyz_text, substrate_xyz_text,
            catalyst, substrate_id,
            output_text
        )
    else:
        return molecule_processing_fn(template, species, output_text)


def get_rem_section(system_dir: Path, calc: str, rem: dict, category: str, branch: str,
                    mode: str, method: str, basis: str) -> str:
    """
    Returns the REM section. For sp mode, uses sp builder; for opt mode, uses the opt builder.
    """
    if mode == "sp":
        eda2 = "0" if category == "no_cat" or branch == "cat" else rem.get("eda2", "0")
        return rem_builder.build_rem_section_for_sp(
            system_dir, method, basis,
            rem.get("dispersion", "false"), rem.get("solvent", "false"), eda2
        )
    else:
        jobtype = "ts" if branch == "ts" else ("sp" if len(rem.get("molecule_section", "").splitlines()) - 1 == 1 else "opt")
        return rem_builder.build_rem_section_for_opt(
            system_dir, calc, rem["method"], basis,
            rem.get("dispersion", "false"), rem.get("solvent", "false"), jobtype
        )


def build_file_path(system_dir: Path, method: str, basis: str, dispersion: str, solvent: str,
                    category: str, branch: str, species: str, calc_type: str,
                    catalyst_name: str = "", mode: str = "opt", opt_params: dict = None) -> Path:
    """
    Constructs the full input file path using sanitized values.
    For opt mode, folder and file names are built using the provided values.
    For sp mode, the top folder comes from the opt values in opt_params and an extra subfolder is added.
    """
    if mode == "opt":
        top_method, top_basis, top_disp, top_solvent = method, basis, dispersion, solvent
        suffix = "_opt.in"
    elif mode == "sp":
        if opt_params is None:
            raise ValueError("For sp mode, opt_params must be provided.")
        top_method = opt_params.get("method")
        top_basis = opt_params.get("basis")
        top_disp = opt_params.get("dispersion")
        top_solvent = opt_params.get("solvent")
        suffix = "_sp.in"

        # Create sp_folder name without "false" values
        sp_folder_parts = [method]
        
        # Only include dispersion if not false
        if dispersion and dispersion.lower() != "false":
            sp_folder_parts.append(dispersion)
            
        # Always include basis set
        sp_folder_parts.append(basis)
        
        # Only include solvent if not false
        if solvent and solvent.lower() != "false":
            sp_folder_parts.append(solvent)
        
        # Add sp suffix
        sp_folder_parts.append("sp")
        
        # Join parts with underscores
        sp_folder = "_".join(sp_folder_parts)
    else:
        raise ValueError(f"Unknown mode: {mode}")
  
    # Create folder name without "false" values
    folder_parts = [top_method]
    
    # Only include dispersion if not false
    if top_disp and top_disp.lower() != "false":
        folder_parts.append(top_disp)
        
    # Always include basis set
    folder_parts.append(top_basis)
    
    # Only include solvent if not false
    if top_solvent and top_solvent.lower() != "false":
        folder_parts.append(top_solvent)
    
    # Join parts with underscores
    base_folder = system_dir / "_".join(folder_parts)
  
    if category == "no_cat":
        if branch in ("reactants", "products"):
            if mode == "opt":
                relative = Path("no_cat") / branch / species / f"{species}{suffix}"
            else:
                relative = Path("no_cat") / branch / species / sp_folder / f"{species}{suffix}"
        elif branch == "ts":
            if mode == "opt":
                relative = Path("no_cat") / "ts" / f"tscomplex{suffix}"
            else:
                relative = Path("no_cat") / "ts" / sp_folder / f"tscomplex{suffix}"
        else:
            raise ValueError(f"Unknown branch for no_cat: {branch}")
    elif category == "cat":
        if not catalyst_name:
            raise ValueError("For catalyst cases, catalyst_name must be provided.")
        if branch == "preTS":
            if mode == "opt":
                relative = Path(catalyst_name) / "preTS" / species / calc_type / f"preTS_{species}_{calc_type}{suffix}"
            else:
                relative = Path(catalyst_name) / "preTS" / species / calc_type / sp_folder / f"preTS_{species}_{calc_type}{suffix}"
        elif branch == "postTS":
            if mode == "opt":
                relative = Path(catalyst_name) / "postTS" / species / calc_type / f"postTS_{species}_{calc_type}{suffix}"
            else:
                relative = Path(catalyst_name) / "postTS" / species / calc_type / sp_folder / f"postTS_{species}_{calc_type}{suffix}"
        elif branch == "ts":
            if mode == "opt":
                relative = Path(catalyst_name) / "ts" / calc_type / f"ts_{catalyst_name}-tscomplex_{calc_type}{suffix}"
            else:
                relative = Path(catalyst_name) / "ts" / calc_type / sp_folder / f"ts_{catalyst_name}-tscomplex_{calc_type}{suffix}"
        elif branch == "cat":
            if mode == "opt":
                relative = Path(catalyst_name) / "cat" / f"{catalyst_name}{suffix}"
            else:
                relative = Path(catalyst_name) / "cat" / sp_folder / f"{catalyst_name}{suffix}"
        else:
            raise ValueError(f"Unknown branch for catalyst: {branch}")
    else:
        raise ValueError(f"Unknown category: {category}")
  
    full_path = base_folder / relative
    return full_path

def build_and_write_input_file(system_dir: Path,
                               sanitized: dict,
                               original: dict,
                               category: str,
                               branch: str,
                               species: str,
                               calc_type: str,
                               template_base_path: Path,
                               molecule_template_path: Path,
                               molecule_proc_fn,
                               catalyst_name: str = "",
                               mode: str = "opt",
                               overwrite: str = None,
                               sp_strategy: str = "smart") -> None:
    """
    Builds the file path (using sanitized values), creates the file content, and writes it to disk.
    In sp mode the opt_params for file naming are taken from the sanitized version.
    
    Args:
        system_dir: Base system directory
        sanitized: Dictionary with sanitized naming values
        original: Dictionary with original values
        category: Category (no_cat or cat)
        branch: Branch (reactants, products, ts, etc.)
        species: Species name
        calc_type: Calculation type
        template_base_path: Path to base template file
        molecule_template_path: Path to molecule template file
        molecule_proc_fn: Function to process molecule section
        catalyst_name: Catalyst name (optional)
        mode: Mode (opt or sp)
        overwrite: Overwrite criteria (None, "all", "CRASH", "terminated", etc.)
        sp_strategy: Strategy for SP file generation ("always", "smart", "never")
    """
    # SP file generation handling
    opt_output_path = None
    if mode == "sp":
        # Skip SP file generation based on strategy
        if sp_strategy == "never":
            return
            
        opt_params = {
            "method": sanitized["opt_method"],
            "basis": sanitized["opt_basis"],
            "dispersion": sanitized["opt_dispersion"],
            "solvent": sanitized["opt_solvent"]
        }
        
        opt_input_path = build_file_path(
            system_dir,
            opt_params["method"],
            opt_params["basis"],
            opt_params["dispersion"],
            opt_params["solvent"],
            category, branch, species, calc_type, catalyst_name, mode="opt"
        )
        
        if sp_strategy == "smart":
            # Check if optimization was successful
            from PyA3EDA.core.status.status_checker import get_status_for_file
            
            status, details = get_status_for_file(opt_input_path)
            
            if status != "SUCCESSFUL":
                logging.info(f"Skipping SP file generation for {species} - OPT status is {status}: {details}")
                return
                
        opt_output_path = opt_input_path.with_suffix(".out")
    else:
        opt_params = None

    # Build file path
    file_path = build_file_path(
        system_dir,
        sanitized["method"],
        sanitized["basis"],
        sanitized["dispersion"],
        sanitized["solvent"],
        category, branch, species, calc_type, catalyst_name, mode, opt_params
    )
    
    # Check if file exists and determine if we should overwrite
    if file_path.exists():
        from PyA3EDA.core.status.status_checker import should_process_file
        should_write, reason = should_process_file(file_path, overwrite)
        if not should_write:
            logging.info(f"Skipping file ({reason}): {file_path.relative_to(system_dir)}")
            return
        logging.info(f"Overwriting file ({reason}): {file_path.relative_to(system_dir)}")
    
    # Load base template
    base_template = read_text(template_base_path)
    if not base_template:
        logging.error(f"Failed to read template: {template_base_path}")
        return
        
    # Add geom opt section for opt mode
    if mode == "opt":
        geom_file = system_dir / "templates" / "rem" / "geom_opt.rem"
        geom_content = read_text(geom_file)
        if geom_content:
            base_template += "\n\n" + geom_content
        else:
            logging.warning(f"Geometry optimization template not found: {geom_file}")
    
    # Add solvent REM section if solvent is specified
    if sanitized["solvent"] and sanitized["solvent"].lower() != "false":
        solvent_name = sanitized["solvent"]
        solvent_file = system_dir / "templates" / "rem" / f"solvent_{solvent_name}.rem"
        if solvent_file.exists():
            solvent_content = read_text(solvent_file)
            if solvent_content:
                base_template += "\n\n" + solvent_content
        else:
            logging.warning(f"Solvent file not found: {solvent_file}")
    
    # Load molecule template
    molecule_template_raw = read_text(molecule_template_path)
    if not molecule_template_raw:
        logging.error(f"Failed to read molecule template: {molecule_template_path}")
        return
    
    # Generate molecule section
    try:
        # Get molecule section through the unified interface
        molecule_section = get_molecule_section(
            template=molecule_template_raw,
            molecule_processing_fn=molecule_proc_fn,
            species=species,
            catalyst=catalyst_name,
            mode=mode,
            opt_output_path=opt_output_path,
            system_dir=system_dir  # Pass system_dir to locate catalyst/substrate templates
        )
        
        if not molecule_section:
            logging.error(f"Failed to generate molecule section for {species}")
            return
    except Exception as e:
        logging.error(f"Error generating molecule section for {species}: {str(e)}")
        return
    
    # Store molecule section in original values
    original["molecule_section"] = molecule_section
    
    # Prepare REM values
    rem_vals = {
        "method": original["method"],
        "basis": original["basis"],
        "dispersion": original.get("dispersion", "false"),
        "solvent": original.get("solvent", "false"),
        "molecule_section": molecule_section
    }
    
    # Add EDA2 parameter for SP mode
    if mode == "sp":
        rem_vals["eda2"] = original.get("eda2", "0")
    
    # Get REM section
    rem_section = get_rem_section(
        system_dir, calc_type, rem_vals, category, branch, mode,
        rem_vals["method"], rem_vals["basis"]
    )
    
    # Format final content
    content = base_template.format(
        molecule_section=molecule_section.rstrip(),
        rem_section=rem_section.rstrip()
    )
    
    if not content.rstrip():
        logging.error(f"Empty content generated for {file_path}. Skipping file creation.")
        return
    
    # Write the file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if write_text(file_path, content):
        logging.info(f"Input file written to {file_path.relative_to(system_dir)}")
    else:
        logging.error(f"Failed to write input file to {file_path}")

def get_combinations(species_list, min_length=2):
    """
    Generates dash-joined combination strings from a list of species.
    Uses each species' opt value so that file naming is consistent.
    """
    for r in range(min_length, len(species_list) + 1):
        for combo in combinations(species_list, r):
            yield "-".join(spec["name"]["opt"] for spec in combo)


def process_input_files(config_manager, system_dir: Path, mode: str = "generate",
                       overwrite: str = None, sp_strategy: str = "smart"):
    """
    Process input files based on mode - either generate them or yield their paths.
    
    Args:
        config_manager: ConfigManager instance with processed configuration
        system_dir: Base system directory
        mode: "generate" to create files, "yield" to yield paths
        overwrite: Overwrite criteria (None, "all", "CRASH", "terminated", etc.)
        sp_strategy: Strategy for SP file generation ("always", "smart", "never")
    """
    if mode not in ("generate", "yield"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'generate' or 'yield'")
    
    templates_dir = system_dir / "templates"
    base_template_path = templates_dir / "base_template.in"
    processed_config = config_manager.get_builder_config() if hasattr(config_manager, 'get_builder_config') else config_manager

    # Keep track of OPT files already processed to avoid duplicates
    processed_opt_files = set()

    # Helper function to handle both path generation and file writing
    def process_file(method, bs, file_mode, category, branch, species, calc_type="", 
                    catalyst_name="", template_prefix="", molecule_fn=None):
        """
        Process a single input file - either yield its path or build and write it.
        """
        if file_mode == "sp" and not (method["name"].get("sp_enabled", False) and bs.get("sp_enabled", False)):
            return

        # Always build the file path
        if file_mode == "opt":
            file_path = build_file_path(
                system_dir,
                method["name"]["opt"],
                bs["opt"], 
                method["dispersion"]["opt"],
                method["solvent"]["opt"],
                category, branch, species, calc_type, catalyst_name,
                mode=file_mode
            )
            
            # Create a unique key for this OPT file
            opt_key = (
                method["name"]["opt"], bs["opt"], 
                method["dispersion"]["opt"], method["solvent"]["opt"],
                category, branch, species, calc_type, catalyst_name
            )
            
            # If we've already processed this exact OPT file, skip it
            if opt_key in processed_opt_files:
                if mode == "yield":
                    return None
            else:
                # Otherwise mark it as processed
                processed_opt_files.add(opt_key)
                
        else:  # sp
            file_path = build_file_path(
                system_dir,
                method["name"]["sp"],
                bs["sp"],
                method["dispersion"]["sp"],
                method["solvent"]["sp"],
                category, branch, species, calc_type, catalyst_name,
                mode=file_mode,
                opt_params={
                    "method": method["name"]["opt"],
                    "basis": bs["opt"],
                    "dispersion": method["dispersion"]["opt"],
                    "solvent": method["solvent"]["opt"]
                }
            )
        
        # For yield mode, just yield the path
        if mode == "yield":
            return file_path
        
        # For generate mode, build and write the file
        sanitized, original = config_manager.get_common_values(method, bs, file_mode)
        
        # Get molecule template path
        template_name = f"{template_prefix}{species}"
        molecule_template_path = templates_dir / "molecule" / f"{template_name}.xyz"
        
        build_and_write_input_file(
            system_dir=system_dir,
            sanitized=sanitized,
            original=original,
            category=category,
            branch=branch,
            species=species,
            calc_type=calc_type,
            template_base_path=base_template_path,
            molecule_template_path=molecule_template_path,
            molecule_proc_fn=molecule_fn,
            catalyst_name=catalyst_name,
            mode=file_mode,
            overwrite=overwrite,
            sp_strategy=sp_strategy
        )
        
        # Return None for consistency (calling code will filter these)
        return None

    # --- no_cat (non-catalyst) branch ---
    for method in processed_config.get("methods", []):
        for bs in method.get("basis_sets", []):
            # --- Process reactants ---
            for reactant in processed_config.get("reactants", []):
                species = reactant["name"]["opt"]
                
                for file_mode in ("opt", "sp"):
                    result = process_file(
                        method, bs, file_mode, "no_cat", "reactants", species,
                        molecule_fn=build_standard_molecule_section
                    )
                    if mode == "yield" and result:
                        yield result
            
            # --- Process reactant combinations ---
            reactants_incl = [r for r in processed_config.get("reactants", []) if r.get("include", True)]
            if len(reactants_incl) > 1:
                for combo in get_combinations(reactants_incl, min_length=2):
                    for file_mode in ("opt", "sp"):
                        result = process_file(
                            method, bs, file_mode, "no_cat", "reactants", combo,
                            molecule_fn=build_standard_molecule_section
                        )
                        if mode == "yield" and result:
                            yield result
            
            # --- Process products ---
            for product in processed_config.get("products", []):
                species = product["name"]["opt"]
                
                for file_mode in ("opt", "sp"):
                    result = process_file(
                        method, bs, file_mode, "no_cat", "products", species,
                        molecule_fn=build_standard_molecule_section
                    )
                    if mode == "yield" and result:
                        yield result
            
            # --- Process transition state (TS) ---
            for file_mode in ("opt", "sp"):
                result = process_file(
                    method, bs, file_mode, "no_cat", "ts", "tscomplex",
                    molecule_fn=build_standard_molecule_section
                )
                if mode == "yield" and result:
                    yield result
            
            # --- Process catalysts ---
            for catalyst in processed_config.get("catalysts", []):
                cat_name = catalyst["name"]["opt"]
                
                # --- Catalyst itself ---
                for file_mode in ("opt", "sp"):
                    result = process_file(
                        method, bs, file_mode, "cat", "cat", cat_name,
                        catalyst_name=cat_name,
                        molecule_fn=build_standard_molecule_section
                    )
                    if mode == "yield" and result:
                        yield result
                
                # --- preTS: catalyst with reactants ---
                reactants_incl = [r for r in processed_config.get("reactants", []) if r.get("include", True)]
                for combo in get_combinations(reactants_incl, min_length=1):
                    species_combo = f"{cat_name}-{combo}"
                    
                    for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                        for file_mode in ("opt", "sp"):
                            result = process_file(
                                method, bs, file_mode, "cat", "preTS", species_combo,
                                calc_type=calc_type, catalyst_name=cat_name,
                                template_prefix="preTS_",
                                molecule_fn=build_fragmented_molecule_section
                            )
                            if mode == "yield" and result:
                                yield result
                
                # --- postTS: catalyst with products ---
                products_incl = [p for p in processed_config.get("products", []) if p.get("include", True)]
                for combo in get_combinations(products_incl, min_length=1):
                    species_combo = f"{cat_name}-{combo}"
                    
                    for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                        for file_mode in ("opt", "sp"):
                            result = process_file(
                                method, bs, file_mode, "cat", "postTS", species_combo,
                                calc_type=calc_type, catalyst_name=cat_name,
                                template_prefix="postTS_",
                                molecule_fn=build_fragmented_molecule_section
                            )
                            if mode == "yield" and result:
                                yield result
                
                # --- TS: Catalyst TS ---
                for calc_type in ("full_cat", "pol_cat", "frz_cat"):
                    for file_mode in ("opt", "sp"):
                        result = process_file(
                            method, bs, file_mode, "cat", "ts", f"ts_{cat_name}-tscomplex",
                            calc_type=calc_type, catalyst_name=cat_name,
                            molecule_fn=build_fragmented_molecule_section
                        )
                        if mode == "yield" and result:
                            yield result

    if mode == "generate":
        logging.info("Input file generation completed.")


def generate_all_inputs(config_manager, system_dir: Path, overwrite: str = None, sp_strategy: str = "smart") -> None:
    """Generate all Q-Chem input files using the unified config from config_manager."""
    list(process_input_files(config_manager, system_dir, "generate", overwrite, sp_strategy))


def iter_input_paths(config_manager, system_dir: Path):
    """Iterates through the unified config from config_manager and yields input file paths."""
    yield from process_input_files(config_manager, system_dir, "yield")