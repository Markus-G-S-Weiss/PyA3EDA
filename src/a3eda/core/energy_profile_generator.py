import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import pandas as pd
from .file_operations import FileOperations

class EnergyProfileGenerator(FileOperations):
    """Class for generating energy profiles."""
    def __init__(self, input_dir: Path, profiles_dir: Path, config: dict, catalyst: str):
        super().__init__(input_dir)
        self.config = config
        self.profiles_dir = profiles_dir
        self.profiles_dir.mkdir(exist_ok=True)
        self.catalyst = catalyst.lower()

    def _get_energy_values(self, df: pd.DataFrame, path: str, stage: str) -> Tuple[Optional[float], Optional[float]]:
        """Get E and G values for a specific path and stage."""
        matching_rows = df[(df['Path'] == path) & (df['Stage'] == stage)]
        if not matching_rows.empty:
            return (matching_rows['E (kcal/mol)'].iloc[0], 
                   matching_rows['G (kcal/mol)'].iloc[0])
        return None, None

    def _create_combined_profile(self, df: pd.DataFrame, method_basis: str, cat: str) -> List[dict]:
        combined_data = []
        # catalysts = [c.lower() for c in self.config.get('catalysts', [])]
        r1 = self.config['reactant1'].lower()
        r2 = self.config['reactant2'].lower()

        combinations = [
            {
                'name': f"{cat}+{r1}+{r2}",
                'components': [
                    {'path': cat, 'stage': 'Reactants'},
                    {'path': r1, 'stage': 'Reactants'},
                    {'path': r2, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Frz-{cat}-{r1}-{r2}",
                'components': [
                    {'path': 'frz', 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Pol-{cat}-{r1}-{r2}",
                'components': [
                    {'path': 'pol', 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Full-{cat}-{r1}-{r2}",
                'components': [
                    {'path': 'full', 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"ts-{r1}-{r2}+{cat}",
                'components': [
                    {'path': 'nocat', 'stage': 'TS'},
                    {'path': cat, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Ts-{cat}-frz-{r1}-{r2}",
                'components': [
                    {'path': 'frz', 'stage': 'TS'}
                ]
            },
            {
                'name': f"Ts-{cat}-pol-{r1}-{r2}",
                'components': [
                    {'path': 'pol', 'stage': 'TS'}
                ]
            },
            {
                'name': f"Ts-{cat}-full-{r1}-{r2}",
                'components': [
                    {'path': 'full', 'stage': 'TS'}
                ]
            },
            {
                'name': f"product+{cat}",
                'components': [
                    {'path': 'nocat', 'stage': 'Product'},
                    {'path': cat, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"{cat}-frz-product",
                'components': [
                    {'path': 'frz', 'stage': 'Product'}
                ]
            },
            {
                'name': f"{cat}-pol-product",
                'components': [
                    {'path': 'pol', 'stage': 'Product'}
                ]
            },
            {
                'name': f"{cat}-full-product",
                'components': [
                    {'path': 'full', 'stage': 'Product'}
                ]
            }
        ]

        for combo in combinations:
            e_sum = 0.0
            g_sum = 0.0
            all_components_found = True
            for component in combo['components']:
                e_val, g_val = self._get_energy_values(df, component['path'], component['stage'])
                if e_val is None or g_val is None:
                    logging.warning(f"Missing energy values for {combo['name']}: {component}")
                    all_components_found = False
                    break
                e_sum += e_val
                g_sum += g_val
            if all_components_found:
                combined_data.append({
                    'Structure': combo['name'],
                    'E (kcal/mol)': e_sum,
                    'G (kcal/mol)': g_sum
                })

        return combined_data

    def _generate_raw_profile(self, df: pd.DataFrame, method_basis: str) -> pd.DataFrame:
        """Generate raw profile data."""
        raw_data = []
        catalysts = [c.lower() for c in self.config.get('catalysts', [])]
        reactant1 = self.config.get('reactant1', '').lower()
        reactant2 = self.config.get('reactant2', '').lower()

        for _, row in df.iterrows():
            label = row.get('Label') or row.get(f"{method_basis}")
            if not label:
                continue

            # Initialize path and stage
            path = 'unknown'
            stage = 'Unknown'

            label_parts = label.lower().split('/')
            label_parts = [part.strip() for part in label_parts]

            # First determine stage
            if any('reactants' in part for part in label_parts):
                stage = 'Reactants'
            elif any(part == 'ts' or 'ts' in part for part in label_parts):
                stage = 'TS'
            elif any('product' in part for part in label_parts):
                stage = 'Product'


            # Then determine path with precedence order
            if any('frz_cat' in part or 'frz' in part for part in label_parts):
                path = 'frz'
            elif any('pol_cat' in part or 'pol' in part for part in label_parts):
                path = 'pol'
            elif any('full_cat' in part or 'full' in part for part in label_parts):
                path = 'full'
            elif any(reactant1 in part for part in label_parts):
                path = reactant1
            elif any(reactant2 in part for part in label_parts):
                path = reactant2
            elif any('no_cat' in part or 'nocat' in part for part in label_parts):
                path = 'nocat'

            elif any(cat in label_parts for cat in catalysts):
                for cat in catalysts:
                    if cat in label_parts:
                        path = cat
                        break
            # elif reactant1 in label_parts:
            #     path = reactant1
            # elif reactant2 in label_parts:
            #     path = reactant2

            if path != 'unknown' and stage != 'Unknown':
                raw_data.append({
                    f"{method_basis}": label,
                    'Path': path,
                    'Stage': stage,
                    'E (kcal/mol)': row.get('E (kcal/mol)'),
                    'G (kcal/mol)': row.get('G (kcal/mol)')
                })

        return pd.DataFrame(raw_data)

    def generate_profiles(self):
        """Generate both raw and combined energy profiles."""
        # Only process CSV files matching this catalyst
        for csv_file in self.base_dir.glob("*.csv"):
            if self.catalyst in csv_file.stem.lower():
                method_basis = "_".join(csv_file.stem.split("_")[:-1])
                df = pd.read_csv(csv_file)

                raw_profile = self._generate_raw_profile(df, method_basis)
                raw_output = self.profiles_dir / f"{csv_file.stem}_raw_profile.csv"
                raw_profile.to_csv(raw_output, index=False)
                logging.info(f"Raw energy profile saved to {raw_output}")

                # Generate combined profile
                combined_data = self._create_combined_profile(raw_profile, method_basis, self.catalyst)
                if combined_data:
                    combined_df = pd.DataFrame(combined_data)
                    combined_output = self.profiles_dir / f"{csv_file.stem}_combined_profile.csv"
                    combined_df.to_csv(combined_output, index=False)
                    logging.info(f"Combined energy profile saved to {combined_output}")
                else:
                    logging.warning(f"No combined profile data generated for {csv_file.stem}")
