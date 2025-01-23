#!/home/dal063121/.conda/envs/extrplt/bin/python3
import argparse
import logging
import sys
import re
from pathlib import Path
from typing import Optional, Tuple
import yaml
import pandas as pd

# Define the conversion constants
HARTREE_TO_KCALMOL = 627.5096080305927  # Ha to kcal/mol
CAL_TO_KCAL = 1e-3  # cal to kcal

def parse_arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Extract data from output files and save to CSV for each method_basis."
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        type=str,
        help="Path to the configuration YAML file (default: 'config.yaml')",
    )
    parser.add_argument(
        "-i",
        "--input_dir",
        default=Path.cwd(),
        type=Path,
        help="Input directory containing method_basis directories (default: current directory)",
    )
    return parser.parse_args()

def load_config(config_path):
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    if not config_file.is_file():
        logging.error(f'Configuration file not found: {config_path}')
        sys.exit(1)
    try:
        with config_file.open() as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as err:
        logging.error(f'Error parsing YAML configuration: {err}')
        sys.exit(1)

def setup_logging():
    """
    Set up logging configuration.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def compile_patterns() -> dict:
    """
    Compile and return regex patterns.
    """
    patterns = {
        "final_energy": re.compile(r"Final energy is\s+([-+]?\d+\.\d+)"),
        "final_energy_fallback": re.compile(r"Total energy =\s+([-+]?\d+\.\d+)"),
        "optimization_status": re.compile(
            r"(OPTIMIZATION CONVERGED|TRANSITION STATE CONVERGED)"
        ),
        "thermodynamics": re.compile(
            r"STANDARD THERMODYNAMIC QUANTITIES AT\s+([-+]?\d+\.\d+)\s*K\s+AND\s+([-+]?\d+\.\d+)\s*ATM"
        ),
        "imaginary_frequencies": re.compile(
            r"This Molecule has\s+(\d+)\s+Imaginary Frequencies"
        ),
        "zero_point_energy": re.compile(
            r"Zero point vibrational energy:\s+([-+]?\d+\.\d+)\s+(\S+)"
        ),
        "qrrho_parameters": re.compile(
            r"Quasi-RRHO corrections using alpha\s*=\s*(\d+),\s*and omega\s*=\s*(\d+)\s*cm\^-1"
        ),
        # Patterns with priority logic for Enthalpy and Entropy
        "qrrho_total_enthalpy": re.compile(
            r"QRRHO-Total Enthalpy:\s+([-+]?\d+\.\d+)\s+(\S+)"
        ),
        "total_enthalpy_fallback": re.compile(
            r"Total Enthalpy:\s+([-+]?\d+\.\d+)\s+(\S+)"
        ),
        "qrrho_total_entropy": re.compile(
            r"QRRHO-Total Entropy:\s+([-+]?\d+\.\d+)\s+(\S+)"
        ),
        "total_entropy_fallback": re.compile(
            r"Total Entropy:\s+([-+]?\d+\.\d+)\s+(\S+)"
        ),
    }
    return patterns

def is_valid_path(relative_path: Path, catalysts: list, reactant1: str, reactant2: str) -> bool:
    """
    Check if the relative path contains any of the desired catalysts or reactants.
    """
    parts = [part.lower() for part in relative_path.parts]
    # Check for standard calculation paths
    if any('no_cat' in part or 'nocat' in part or
           'frz' in part or 'pol' in part or 
           'full' in part for part in parts):
        return True
    # Check for catalysts
    if any(catalyst in parts for catalyst in catalysts):
        return True
    # Check for reactants
    if reactant1 in parts or reactant2 in parts:
        return True
    # Exclude unwanted directories (e.g., 'templates')
    if 'templates' in parts:
        return False
    return False

def process_files(root_dir: Path, patterns: dict, method_basis: str, config: dict) -> list:
    """
    Walk through the directory and process each output file based on the folder structure.
    """
    data_list = []
    catalysts = [c.lower() for c in config.get('catalysts', [])]
    reactant1 = config.get('reactant1', '').lower()
    reactant2 = config.get('reactant2', '').lower()

    for file_path in root_dir.rglob("*.out"):
        relative_path = file_path.relative_to(root_dir)
        # Exclude files not matching the configuration
        if not is_valid_path(relative_path, catalysts, reactant1, reactant2):
            continue
        content = read_file(file_path)
        if content:
            data = extract_data_from_content(content, patterns)
            if data:
                # Generate calculation label based on relative path
                calculation_label = get_calculation_label(relative_path)
                # Include method_basis and label in the data
                data["Method_Basis"] = method_basis
                data["Label"] = calculation_label
                data_list.append(data)
    return data_list

def read_file(file_path: Path) -> Optional[str]:
    """
    Read the content of a file.
    """
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except IOError as e:
        logging.error(f"IOError reading file '{file_path}': {e}")
    except Exception as e:
        logging.exception(f"Unexpected error reading file '{file_path}': {e}")
    return None

def extract_data_from_content(content: str, patterns: dict) -> Optional[dict]:
    """
    Extract data from the content of an output file using the given patterns
    and include units in column names. Energy value is assumed to be in Hartrees.
    """
    data = {}
    fallback_used = False

    # Energy Extraction (No unit to extract; assume Hartrees)
    energy_value = get_energy_value(content, patterns)
    if energy_value is not None:
        data["E (Ha)"] = energy_value
        # Convert energy from Hartrees to kcal/mol
        energy_value_converted = energy_value * HARTREE_TO_KCALMOL
        # Store in data with unit in column name
        data["E (kcal/mol)"] = energy_value_converted
    else:
        logging.warning("Final energy value not found.")
        return None  # Can't proceed without energy value

    # Enthalpy Extraction
    enthalpy_value, enthalpy_unit, enthalpy_fallback = get_value_with_fallback(
        content,
        patterns["qrrho_total_enthalpy"],
        patterns["total_enthalpy_fallback"],
    )
    if enthalpy_value is not None:
        # Convert enthalpy to kcal/mol
        if enthalpy_unit in ["kcal/mol"]:
            enthalpy_value_converted = enthalpy_value
            enthalpy_unit_converted = "kcal/mol"
        elif enthalpy_unit in ["Hartree", "Ha", "a.u."]:
            enthalpy_value_converted = enthalpy_value * HARTREE_TO_KCALMOL
            enthalpy_unit_converted = "kcal/mol"
        else:
            logging.warning(
                f"Unrecognized enthalpy unit: {enthalpy_unit}. Assuming kcal/mol."
            )
            enthalpy_value_converted = enthalpy_value
            enthalpy_unit_converted = "kcal/mol"

        # Store in data with unit in column name
        enthalpy_column_name = f"Total Enthalpy Corr. ({enthalpy_unit_converted})"
        data[enthalpy_column_name] = enthalpy_value_converted

        if enthalpy_fallback:
            fallback_used = True

    # Entropy Extraction
    entropy_value, entropy_unit, entropy_fallback = get_value_with_fallback(
        content,
        patterns["qrrho_total_entropy"],
        patterns["total_entropy_fallback"],
    )
    if entropy_value is not None:
        # Convert entropy to kcal/mol·K
        if entropy_unit in ["cal/mol.K", "cal/mol·K"]:
            entropy_value_converted = entropy_value * CAL_TO_KCAL
            entropy_unit_converted = "kcal/mol.K"
        elif entropy_unit in ["kcal/mol.K", "kcal/mol·K"]:
            entropy_value_converted = entropy_value
            entropy_unit_converted = "kcal/mol.K"
        else:
            logging.warning(
                f"Unrecognized entropy unit: {entropy_unit}. Assuming kcal/mol.K."
            )
            entropy_value_converted = entropy_value
            entropy_unit_converted = "kcal/mol.K"

        # Store in data with unit in column name
        entropy_column_name = f"Total Entropy Corr. ({entropy_unit_converted})"
        data[entropy_column_name] = entropy_value_converted

        if entropy_fallback:
            fallback_used = True

    # Extract other data as before
    for key, pattern in patterns.items():
        if key in [
            "final_energy",
            "final_energy_fallback",
            "qrrho_total_enthalpy",
            "total_enthalpy_fallback",
            "qrrho_total_entropy",
            "total_entropy_fallback",
        ]:
            continue  # Already handled
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
                column_name = (
                    f"{key.replace('_', ' ').title()} ({unit})"
                    if unit
                    else key.replace("_", " ").title()
                )
                data[column_name] = value

    # Calculate H (kcal/mol)
    energy_col = "E (kcal/mol)"
    enthalpy_col = f"Total Enthalpy Corr. (kcal/mol)"
    if energy_col in data and enthalpy_col in data:
        data["H (kcal/mol)"] = data[energy_col] + data[enthalpy_col]

    # Calculate G (kcal/mol)
    entropy_col = f"Total Entropy Corr. (kcal/mol.K)"
    if (
        "H (kcal/mol)" in data
        and "Temperature (K)" in data
        and entropy_col in data
    ):
        data["G (kcal/mol)"] = (
            data["H (kcal/mol)"] - data["Temperature (K)"] * data[entropy_col]
        )

    # Add 'Fallback Used' column if any fallback was used
    if data:
        data["Fallback Used"] = "Yes" if fallback_used else "No"
        return data
    else:
        return None

def get_energy_value(content: str, patterns: dict) -> Optional[float]:
    """
    Extract the energy value from content, assuming it's in Hartrees (Ha) without a unit.
    """
    match = patterns["final_energy"].search(content)
    if match:
        return float(match.group(1))
    match = patterns["final_energy_fallback"].search(content)
    if match:
        return float(match.group(1))
    return None

def get_value_with_fallback(
    content: str,
    primary_pattern: re.Pattern,
    fallback_pattern: re.Pattern,
) -> Tuple[Optional[float], Optional[str], bool]:
    """
    Extract value and unit using primary pattern, fallback to secondary if needed.
    Returns value, unit, and fallback_used flag.
    """
    match = primary_pattern.search(content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        fallback_used = False
        return value, unit, fallback_used
    match = fallback_pattern.search(content)
    if match:
        value = float(match.group(1))
        unit = match.group(2)
        fallback_used = True
        return value, unit, fallback_used
    return None, None, False

def get_calculation_label(relative_path: Path) -> str:
    """
    Generate a calculation label based on the directory structure.
    """
    # Exclude the '.out' file name
    parts = relative_path.parts[:-1]
    # Create labels based on the directory hierarchy
    label = "/".join(parts)
    return label

def save_to_csv(
    data_list: list,
    method_basis_dir: Path,
    method_basis: str,
):
    """
    Save the extracted data for a method_basis to a CSV file named after the method_basis.
    """
    df = pd.DataFrame(data_list)
    
    # Ensure 'Method_Basis' and 'Label' columns exist
    expected_columns = ['Method_Basis', 'Label']
    missing_columns = [col for col in expected_columns if col not in df.columns]
    if missing_columns:
        logging.warning(f"Missing columns {missing_columns} in data. Proceeding without reordering.")
    else:
        # Reorder columns to have 'Method_Basis' and 'Label' as the first columns
        cols = ['Method_Basis', 'Label'] + [col for col in df.columns if col not in ['Method_Basis', 'Label']]
        df = df[cols]
    
    # Output file name is the method_basis with '.csv' extension
    csv_file = method_basis_dir / f"{method_basis}.csv"
    try:
        df.to_csv(csv_file, index=False)
        logging.info(f"Data for '{method_basis}' saved to '{csv_file}'")
    except Exception as e:
        logging.error(f"Failed to save data to '{csv_file}': {e}")

def create_energy_profile_csv(input_dir: Path, config: dict):
    """
    Create separate energy profile CSV files for each method_basis.
    Each CSV file is saved in the 'energy_profiles' folder and named as '{method_basis}_profile.csv'.
    """
    # Create the 'energy_profiles' directory if it doesn't exist
    energy_profiles_dir = input_dir / 'energy_profiles'
    energy_profiles_dir.mkdir(exist_ok=True)

    # Initialize a dictionary to hold profile data for each method_basis
    method_basis_profiles = {}

    # Get catalysts and reactants from config
    catalysts = [c.lower() for c in config.get('catalysts', [])]
    reactant1 = config.get('reactant1', '').lower()
    reactant2 = config.get('reactant2', '').lower()

    # Read each CSV file generated by the extraction script
    csv_files = list(input_dir.rglob("*.csv"))
    for csv_file in csv_files:
        # Skip any existing profile CSV files to avoid duplicates
        if csv_file.parent.name == 'energy_profiles':
            continue
        if csv_file.name.endswith('_profile.csv'):
            continue
        if csv_file.name == "energy_profile.csv":
            continue

        df = pd.read_csv(csv_file)
        method_basis = csv_file.stem  # Get method_basis from file name

        # Initialize the list to store profile data for this method_basis
        if method_basis not in method_basis_profiles:
            method_basis_profiles[method_basis] = []

        # Process each row in the CSV file
        for _, row in df.iterrows():
            # Extract the label
            label = row.get('Label') or row.get(f"{method_basis}")
            if not label:
                continue

            # Initialize path and stage
            path = 'unknown'
            stage = 'Unknown'

            # Split the label into parts
            label_parts = label.lower().split('/')
            label_parts = [part.strip() for part in label_parts]

            # Determine 'Path' based on specific keywords
            # Check for reactants from config
            if any(reactant1 in part for part in label_parts):
                path = reactant1
            elif any(reactant2 in part for part in label_parts):
                path = reactant2
            elif any('no_cat' in part or 'nocat' in part for part in label_parts):
                path = 'nocat'
            elif any('frz_cat' in part or 'frz' in part for part in label_parts):
                path = 'frz'
            elif any('pol_cat' in part or 'pol' in part for part in label_parts):
                path = 'pol'
            elif any('full_cat' in part or 'full' in part for part in label_parts):
                path = 'full'
            # Check catalysts from config
            elif any(cat in part for part in label_parts for cat in catalysts):
                for cat in catalysts:
                    if any(cat in part for part in label_parts):
                        path = cat
                        break

            # Determine 'Stage' based on specific keywords
            if any('reactants' in part for part in label_parts):
                stage = 'Reactants'
            elif any(part == 'ts' or 'ts' in part for part in label_parts):
                stage = 'TS'
            elif any('product' in part for part in label_parts):
                stage = 'Product'

            # Log a warning if Path or Stage is unknown
            if path == 'unknown' or stage == 'Unknown':
                logging.warning(f"Could not determine Path or Stage for label '{label}'")

            # Extract E and G (kcal/mol)
            E = row.get("E (kcal/mol)")
            G = row.get("G (kcal/mol)")

            method_basis_profiles[method_basis].append({
                f"{method_basis}": label,
                "Path": path,
                "Stage": stage,
                "E (kcal/mol)": E,
                "G (kcal/mol)": G
            })

    # Save each method_basis profile to a separate CSV file
    for method_basis, profile_data in method_basis_profiles.items():
        profile_df = pd.DataFrame(profile_data)

        # Save to CSV in the 'energy_profiles' directory
        output_csv = energy_profiles_dir / f"{method_basis}_profile.csv"
        profile_df.to_csv(output_csv, index=False)
        logging.info(f"Energy profile data for '{method_basis}' saved to '{output_csv}'")

def main():
    """
    Main function to extract data from output files and save to CSV for each method_basis.
    """
    args = parse_arguments()
    setup_logging()

    config = load_config(args.config)
    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        logging.error(f"Input directory '{input_dir}' does not exist.")
        exit(1)

    patterns = compile_patterns()

    # Get methods and bases from config
    methods = [m.strip() for m in config.get('methods', [])]
    bases = [b.strip() for b in config.get('bases', [])]
    method_bases = [f"{method}_{basis}" for method in methods for basis in bases]

    # Iterate over each method_basis directory in the input directory
    for method_basis in method_bases:
        method_basis_dir = input_dir / method_basis
        if method_basis_dir.is_dir():
            logging.info(f"Processing method_basis: {method_basis}")
            data_list = process_files(method_basis_dir, patterns, method_basis, config)
            if data_list:
                save_to_csv(
                    data_list,
                    method_basis_dir,
                    method_basis,
                )
            else:
                logging.info(f"No data was extracted for '{method_basis}'.")
        else:
            logging.warning(f"Directory '{method_basis_dir}' does not exist. Skipping.")

    # Create the energy profile CSV files after processing all files
    create_energy_profile_csv(input_dir, config)

if __name__ == "__main__":
    main()
