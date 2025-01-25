import logging
import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from .file_operations import FileOperations
from .constants import Constants
from .utilities import Utilities

class DataProcessor(FileOperations):
    """Class for processing chemical calculation data."""
    def __init__(self, config: dict, base_dir: Path):
        super().__init__(base_dir)
        self.config = config
        self.patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict:
        """Compile and return regex patterns."""
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

    def process_files(self, root_dir: Path, method_basis: str, target_catalyst: str) -> list:
        """Process files for a given method-basis combination and catalyst."""
        data_list = []
        catalysts = [c.lower() for c in self.config.get('catalysts', [])]
        reactant1 = self.config.get('reactant1', '').lower()
        reactant2 = self.config.get('reactant2', '').lower()
        target_catalyst = target_catalyst.lower()

        for file_path in root_dir.rglob("*.out"):
            relative_path = file_path.relative_to(root_dir)
            path_str = str(relative_path).lower()
            
            # Include file if it's either nocat or matches the target catalyst
            if ('no_cat' in path_str or 'nocat' in path_str or target_catalyst in path_str):
                if self._is_valid_path(relative_path, catalysts, reactant1, reactant2):
                    content = self.read_file(file_path)
                    if content:
                        data = self._extract_data(content)
                        if data:
                            calculation_label = Utilities.get_calculation_label(relative_path)
                            #data["Method_Basis"] = method_basis
                            data[f"{method_basis}"] = calculation_label
                            data_list.append(data)
        return data_list

    def _is_valid_path(self, relative_path: Path, catalysts: list,
                      reactant1: str, reactant2: str) -> bool:
        """Check if the relative path contains any of the desired paths."""
        path_str = str(relative_path).lower()
        parts = [part.lower() for part in relative_path.parts]
        
        # Check for standard calculation paths
        if any('no_cat' in part or 'nocat' in part for part in parts):
            return True
        if any(part in ['product', 'ts'] for part in parts):
            return True
        if any('frz_cat' in part or 'frz' in part or
               'pol_cat' in part or 'pol' in part or 
               'full_cat' in part or 'full' in part for part in parts):
            return True
            
        # Check for catalysts
        if any(cat in parts for cat in catalysts):
            return True
            
        # Check for reactants
        if reactant1 in path_str or reactant2 in path_str:
            return True
            
        # Exclude unwanted directories (e.g., 'templates')
        if 'templates' in parts:
            return False
            
        return False

    def _extract_data(self, content: str) -> Optional[dict]:
        """Extract data from output file content."""
        data = {}
        fallback_used = False

        # Energy Extraction (No unit to extract; assume Hartrees)
        energy_value = Utilities.get_energy_value(content, self.patterns)
        if energy_value is not None:
            data["E (Ha)"] = energy_value
            # Convert energy from Hartrees to kcal/mol
            energy_value_converted = energy_value * Constants.HARTREE_TO_KCALMOL
            # Store in data with unit in column name
            data["E (kcal/mol)"] = energy_value_converted
        else:
            logging.warning("Final energy value not found.")
            return None  # Can't proceed without energy value

        # Enthalpy Extraction
        enthalpy_value, enthalpy_unit, enthalpy_fallback = Utilities.get_value_with_fallback(
            content,
            self.patterns["qrrho_total_enthalpy"],
            self.patterns["total_enthalpy_fallback"],
        )
        if enthalpy_value is not None:
            # Convert enthalpy to kcal/mol
            if enthalpy_unit in ["kcal/mol"]:
                enthalpy_value_converted = enthalpy_value
                enthalpy_unit_converted = "kcal/mol"
            elif enthalpy_unit in ["Hartree", "Ha", "a.u."]:
                enthalpy_value_converted = enthalpy_value * Constants.HARTREE_TO_KCALMOL
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
        entropy_value, entropy_unit, entropy_fallback = Utilities.get_value_with_fallback(
            content,
            self.patterns["qrrho_total_entropy"],
            self.patterns["total_entropy_fallback"],
        )
        if entropy_value is not None:
            # Convert entropy to kcal/mol·K
            if entropy_unit in ["cal/mol.K", "cal/mol·K"]:
                entropy_value_converted = entropy_value * Constants.CAL_TO_KCAL
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
        for key, pattern in self.patterns.items():
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
