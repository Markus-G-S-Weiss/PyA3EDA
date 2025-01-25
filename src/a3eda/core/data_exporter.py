import logging
from pathlib import Path
import pandas as pd
from .file_operations import FileOperations

class DataExporter(FileOperations):
    """Class for exporting processed data."""
    def __init__(self, output_dir: Path):
        super().__init__(output_dir)

    def save_method_basis_data(self, data_list: list, filename: str):
        """Save the extracted data to CSV."""
        if not data_list:
            logging.info(f"No data to save for '{filename}'")
            return

        df = pd.DataFrame(data_list)
        
        method_basis = "_".join(filename.split("_")[:-1])
        # Ensure Method_Basis and Label are first columns
        expected_columns = [f"{method_basis}"]#, 'Label']
        
        # Check if expected columns exist
        for col in expected_columns:
            if col not in df.columns:
                logging.warning(f"Missing required column: {col}")
                return
                
        # Reorder columns to put Method_Basis and Label first
        other_cols = [col for col in df.columns if col not in expected_columns]
        df = df[expected_columns + other_cols]
        
        # Create output file directly in raw_data_dir
        csv_file = self.base_dir / f"{filename}.csv"
        
        try:
            df.to_csv(csv_file, index=False)
            logging.info(f"Data saved to '{csv_file}'")
        except Exception as e:
            logging.error(f"Failed to save data to '{csv_file}': {e}")
