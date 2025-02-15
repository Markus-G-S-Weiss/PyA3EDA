from pathlib import Path
from typing import List
import yaml
from .file_handler import FileHandler

class ConfigManager:
    """Class for managing configuration."""
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.sanitized_config = self._sanitize_config()

    def load_config(self, config_path: str) -> dict:
        config_file = Path(config_path)
        if not config_file.is_file():
            raise FileNotFoundError(f'Configuration file not found: {config_path}')
        try:
            with config_file.open() as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as err:
            raise ValueError(f'Error parsing YAML configuration: {err}')

    def _sanitize_config(self) -> dict:
        """Create sanitized version of config values for paths."""
        return {
            'methods': [FileHandler.sanitize_filename(m) for m in self.config['methods']],
            'bases': [FileHandler.sanitize_filename(b) for b in self.config['bases']],
            'catalysts': [FileHandler.sanitize_filename(c) for c in self.config['catalysts']],
            'reactant1': FileHandler.sanitize_filename(self.config['reactant1']),
            'reactant2': FileHandler.sanitize_filename(self.config['reactant2'])
        }

    def get_calculation_paths(self, system_dir: Path) -> List[Path]:
        """Get all possible calculation paths with sanitized names."""
        paths = []
        for method in self.sanitized_config['methods']:
            for basis in self.sanitized_config['bases']:
                method_basis_dir = system_dir / f'{method}_{basis}'
                
                # Add no_cat paths
                no_cat_dir = method_basis_dir / 'no_cat'
                for path in self._get_no_cat_paths(no_cat_dir):
                    paths.append(path)
                
                # Add catalyst paths
                for catalyst in self.sanitized_config['catalysts']:
                    for path in self._get_catalyst_paths(method_basis_dir, catalyst):
                        paths.append(path)
        return paths

    def _get_no_cat_paths(self, no_cat_dir: Path) -> List[Path]:
        """Helper method to generate no_cat paths."""
        return [
            no_cat_dir / f'reactants/{self.sanitized_config["reactant1"]}/{self.sanitized_config["reactant1"]}_opt.in',
            no_cat_dir / f'reactants/{self.sanitized_config["reactant2"]}/{self.sanitized_config["reactant2"]}_opt.in',
            no_cat_dir / 'product/no_cat_product_opt.in',
            no_cat_dir / 'ts/no_cat_ts_opt.in'
        ]

    def _get_catalyst_paths(self, method_basis_dir: Path, catalyst: str) -> List[Path]:
        """Helper method to generate catalyst paths."""
        paths = []
        cat_dir = method_basis_dir / catalyst
        calc_types = ['full_cat', 'pol_cat', 'frz_cat']
        
        paths.append(cat_dir / f'reactants/{catalyst}/{catalyst}_opt.in')
        
        for calc_type in calc_types:
            paths.extend([
                cat_dir / f'reactants/{self.sanitized_config["reactant1"]}/{calc_type}/{self.sanitized_config["reactant1"]}_{calc_type}_opt.in',
                cat_dir / f'product/{calc_type}_product/product_{calc_type}_opt.in',
                cat_dir / f'ts/{calc_type}_ts/ts_{calc_type}_opt.in'
            ])
        return paths