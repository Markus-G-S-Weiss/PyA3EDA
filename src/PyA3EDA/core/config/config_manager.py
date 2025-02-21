"""
Configuration Manager

Loads and sanitizes the YAML configuration file for PyA3EDA.
The configuration includes method(s) (each with dispersion and basis_sets),
catalysts, reactants, and products. Sanitized names are produced for use in folder and file names.
"""

import yaml
from pathlib import Path
from typing import Any, Dict
from PyA3EDA.core.utils.file_utils import sanitize_filename

class ConfigManager:
    def __init__(self, config_path: str) -> None:
        self.config: Dict[str, Any] = self.load_config(config_path)
        self.sanitized_config: Dict[str, Any] = self._sanitize_config()

    def load_config(self, config_path: str) -> Dict[str, Any]:
        config_file = Path(config_path)
        if not config_file.is_file():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        try:
            with config_file.open(encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")

    def _sanitize_config(self) -> Dict[str, Any]:
        sanitized: Dict[str, Any] = {}
        # Process methods: each method includes a name, dispersion, and basis_sets.
        sanitized["methods"] = []
        for method in self.config.get("methods", []):
            sanitized_method = {
                "original": method.get("name", ""),
                "sanitized": sanitize_filename(method.get("name", "")),
                "dispersion": method.get("dispersion", "false"),
                "basis_sets": method.get("basis_sets", [])
            }
            sanitized["methods"].append(sanitized_method)
        # Process catalysts.
        sanitized["catalysts"] = []
        for catalyst in self.config.get("catalysts", []):
            sanitized_catalyst = {
                "original": catalyst.get("name", ""),
                "sanitized": sanitize_filename(catalyst.get("name", "")),
                "charge": catalyst.get("charge"),
                "multiplicity": catalyst.get("multiplicity")
            }
            sanitized["catalysts"].append(sanitized_catalyst)
        # Process reactants.
        sanitized["reactants"] = []
        for reactant in self.config.get("reactants", []):
            sanitized_reactant = {
                "original": reactant.get("name", ""),
                "sanitized": sanitize_filename(reactant.get("name", "")),
                "charge": reactant.get("charge"),
                "multiplicity": reactant.get("multiplicity"),
                "include": reactant.get("include", True)
            }
            sanitized["reactants"].append(sanitized_reactant)
        # Process products.
        sanitized["products"] = []
        for product in self.config.get("products", []):
            sanitized_product = {
                "original": product.get("name", ""),
                "sanitized": sanitize_filename(product.get("name", "")),
                "charge": product.get("charge"),
                "multiplicity": product.get("multiplicity"),
                "include": product.get("include", True)
            }
            sanitized["products"].append(sanitized_product)
        return sanitized
