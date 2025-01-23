#!/home/markus/research/quadbondvenv/bin/python3

#%% Import required libraries
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import logging
from typing import Dict, List, Optional
import yaml

#%% Define ReactionProfilePlotter class
class ReactionProfilePlotter:
    """Class for generating reaction energy profile plots from a3eda output data."""
    
    def __init__(self, data_dir: Path, config_path: Path):
        self.data_dir = Path(data_dir)
        self.profiles_dir = self.data_dir / 'profiles'
        self.raw_dir = self.data_dir / 'raw'
        self.config = self._load_config(config_path)
        
    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        try:
            with config_path.open() as f:
                return yaml.safe_load(f)
        except Exception as e:
            logging.error(f"Error loading config file: {e}")
            return {}

    def _generate_pathway_structures(self) -> Dict[str, List[str]]:
        """Generate pathway structures based on config."""
        if not self.config:
            logging.error("No configuration loaded")
            return {}

        # Extract components from config
        cat = self.config['catalysts'][0].lower()  # Using first catalyst
        r1 = self.config['reactant1'].lower()
        r2 = self.config['reactant2'].lower()

        # Define pathway structures dynamically
        return {
            'nocat': [
                f"{cat}+{r1}+{r2}",
                f"ts-{r1}-{r2}+{cat}",
                f"product+{cat}"
            ],
            'frz': [
                f"{cat}+{r1}+{r2}",
                f"Frz-{cat}-{r1}+{r2}",
                f"Ts-{cat}-frz-{r1}-{r2}",
                f"{cat}-frz-product",
                f"product+{cat}"
            ],
            'pol': [
                f"{cat}+{r1}+{r2}",
                f"Pol-{cat}-{r1}+{r2}",
                f"Ts-{cat}-pol-{r1}-{r2}",
                f"{cat}-pol-product",
                f"product+{cat}"
            ],
            'full': [
                f"{cat}+{r1}+{r2}",
                f"Full-{cat}-{r1}+{r2}",
                f"Ts-{cat}-full-{r1}-{r2}",
                f"{cat}-full-product",
                f"product+{cat}"
            ]
        }

    def _load_profile_data(self, filename: str) -> Optional[pd.DataFrame]:
        """Load profile data from CSV file."""
        try:
            filepath = self.profiles_dir / filename
            return pd.read_csv(filepath)
        except Exception as e:
            logging.error(f"Error loading profile data from {filename}: {e}")
            return None

    def _prepare_energy_dict(self, data: pd.DataFrame, energy_col: str = 'G (kcal/mol)') -> Dict[str, List[float]]:
        """Prepare energy dictionary for plotting from DataFrame."""
        initial_energy = data[energy_col].iloc[0]
        energies = {}
        
        # Get pathway structures from config
        pathways = self._generate_pathway_structures()
        
        # Calculate relative energies for each pathway
        for pathway, structures in pathways.items():
            try:
                energies[pathway] = [
                    data.loc[data['Structure'] == struct, energy_col].iloc[0] - initial_energy
                    for struct in structures
                ]
            except Exception as e:
                logging.warning(f"Could not process pathway {pathway}: {e}")
                continue
                
        return energies

    def plot_profile(self, filename: str, energy_col: str = 'G (kcal/mol)',
                    title: Optional[str] = None, save: bool = False) -> None:
        """Generate reaction energy profile plot."""
        data = self._load_profile_data(filename)
        if data is None:
            return

        energies = self._prepare_energy_dict(data, energy_col)
        if not energies:
            logging.error("No energy data to plot")
            return

        # Create the plot
        plt.figure(figsize=(12, 8))

        # Define x-coordinates for each pathway
        x_coords = {
            'nocat': [0, 2, 4],
            'frz': [0, 1, 2, 3, 4],
            'pol': [0, 1, 2, 3, 4],
            'full': [0, 1, 2, 3, 4]
        }

        # Plot styles
        styles = {
            'nocat': {'color': 'k', 'label': 'No Catalyst'},
            'frz': {'color': 'b', 'label': 'Frozen'},
            'pol': {'color': 'r', 'label': 'Polarized'},
            'full': {'color': 'g', 'label': 'Full'}
        }

        # Plot each pathway
        for pathway, coords in x_coords.items():
            if pathway in energies:
                plt.plot(coords, energies[pathway], 
                        f"{styles[pathway]['color']}-o",
                        label=styles[pathway]['label'],
                        linewidth=2)

        # Customize plot
        plt.xlabel('Reaction Coordinate')
        plt.ylabel(energy_col)
        plt.title(title or 'Reaction Energy Profile')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()

        # Adjust layout
        plt.tight_layout()

        # Save if requested
        if save:
            output_name = f"profile_{filename.replace('.csv', '')}.svg"
            plt.savefig(output_name, format='svg')
            logging.info(f"Saved plot as {output_name}")

        plt.show()

#%% Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create plotter instance with config
    plotter = ReactionProfilePlotter(
        data_dir=Path('data'),
        config_path=Path('config.yaml')
    )
    
    # Find all combined profile CSV files
    combined_profiles = list(plotter.profiles_dir.glob('*_combined_profile.csv'))
    
    if not combined_profiles:
        logging.error("No combined profile CSV files found in the profiles directory")
        exit(1)

    # Generate plots for each profile
    for profile_path in combined_profiles:
        # Extract method and basis set from filename
        method_basis = "_".join(profile_path.stem.split('_')[:-2])  # Remove '_combined_profile'
        
        # Generate both E and G plots
        for energy_col in ['E (kcal/mol)', 'G (kcal/mol)']:
            energy_type = 'Electronic' if 'E (' in energy_col else 'Free'
            title = f'{method_basis} {energy_type} Energy Profile'
            
            logging.info(f"Generating {title}")
            plotter.plot_profile(
                filename=profile_path.name,
                energy_col=energy_col,
                title=title,
                save=True
            )


# %%
