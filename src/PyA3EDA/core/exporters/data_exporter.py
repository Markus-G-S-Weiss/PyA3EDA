"""
Data Exporter Module

Handles saving of extracted data to CSV files.
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict


# def get_metadata_columns() -> List[str]:
#     """Return standard metadata columns in preferred order."""
#     return [
#         "Method", "Category", "Branch", "Calc_Type", "Mode", 
#         "SP_Method", "Identifier"
#     ]


# def get_sort_columns() -> List[str]:
#     """Return columns to sort by in preferred order."""
#     return ["Category", "Branch", "Calc_Type"]


# def prepare_dataframe(data_list: List[Dict[str, Any]]) -> pd.DataFrame:
#     """
#     Create a DataFrame from data list with proper column ordering and sorting.
#     """
#     if not data_list:
#         logging.warning("Attempted to prepare DataFrame from empty data list")
#         return pd.DataFrame()
        
#     # Create DataFrame
#     df = pd.DataFrame(data_list)
    
#     # Exclude Path column if present
#     columns_to_keep = [col for col in df.columns if col != "Path"]
#     df = df[columns_to_keep]
    
#     # Order columns - metadata first, then the rest
#     metadata_columns = get_metadata_columns()
#     present_metadata = [col for col in metadata_columns if col in df.columns]
#     other_columns = [col for col in df.columns if col not in metadata_columns]
    
#     # Apply column ordering
#     df = df[present_metadata + other_columns]
    
#     # Sort DataFrame
#     sort_cols = [col for col in get_sort_columns() if col in df.columns]
#     if sort_cols:
#         try:
#             df = df.sort_values(by=sort_cols)
#         except Exception as e:
#             logging.warning(f"Error sorting DataFrame: {e}")
    
#     return df


# def export_dataframe(df: pd.DataFrame, output_path: Path) -> bool:
#     """
#     Export DataFrame to CSV file.
    
#     Args:
#         df: DataFrame to export
#         output_path: Path to save the CSV file
        
#     Returns:
#         True if successful, False otherwise
#     """
#     if df.empty:
#         logging.warning(f"Cannot export empty DataFrame to {output_path}")
#         return False
        
#     # Ensure parent directory exists
#     try:
#         output_path.parent.mkdir(parents=True, exist_ok=True)
#     except Exception as e:
#         logging.error(f"Failed to create directory for {output_path}: {e}")
#         return False
    
#     # Save CSV
#     try:
#         df.to_csv(output_path, index=False)
#         return True
#     except Exception as e:
#         logging.error(f"Error saving CSV to {output_path}: {e}")
#         return False


# def clean_method_combo_for_filename(method_combo: str) -> str:
#     """
#     Clean method combination string for use in filenames and directory names.
#     """
#     return method_combo.replace('/', '_').replace('\\', '_')


# def group_sp_data(data_list: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
#     """
#     Group SP data by SP method.
#     """
#     groups = {}
#     ungrouped_count = 0
    
#     for item in data_list:
#         # Get SP method
#         sp_method = item.get("SP_Method")
        
#         if not sp_method:
#             # Try to extract from internal path as fallback
#             path = item.get("_path", "")
#             sp_method = "unknown"
#             ungrouped_count += 1
            
#             # Parse path to find SP method folder
#             if path:
#                 path_parts = path.replace("\\", "/").split("/")
#                 for part in path_parts:
#                     if part.endswith("_sp"):
#                         sp_method = part[:-3]
#                         break
        
#         # Add to group
#         if sp_method not in groups:
#             groups[sp_method] = []
#         groups[sp_method].append(item)
    
#     if ungrouped_count > 0:
#         logging.warning(f"Found {ungrouped_count} SP data entries without SP_Method information")
        
#     return groups


def export_data(extracted_data: List[Dict[str, Any]], output_dir: Path = None) -> Dict[str, Path]:
    """
    Export data to CSV files - group by method combo and mode, create files.
    """
    if not output_dir:
        raise ValueError("Output directory must be specified")
        
    if not extracted_data:
        logging.warning("No data to export")
        return {}
        
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Group by method combo and mode using metadata from builder
    grouped = defaultdict(lambda: defaultdict(list))
    for data in extracted_data:
        method_combo = data.get("Method_Combo", "unknown")
        mode = data.get("Mode", "unknown")
        grouped[method_combo][mode].append(data)
    
    # Create CSV files
    results = {}
    for method_combo, modes in grouped.items():
        method_dir = output_dir / method_combo
        
        for mode, data_list in modes.items():
            if mode == "sp":
                # Group SP by SP_Method_Combo
                sp_groups = defaultdict(list)
                for data in data_list:
                    sp_combo = data.get("SP_Method_Combo", "unknown_sp")
                    sp_groups[sp_combo].append(data)
                
                for sp_combo, sp_data in sp_groups.items():
                    df = pd.DataFrame(sp_data)
                    if "Path" in df.columns:
                        df = df.drop(columns=["Path"])
                    
                    filename = f"sp_{sp_combo}_results.csv"
                    file_path = method_dir / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(file_path, index=False)
                    results[f"{method_combo}_sp_{sp_combo}"] = file_path
                    logging.info(f"Saved {len(sp_data)} SP results to {file_path}")
            else:
                # OPT files
                df = pd.DataFrame(data_list)
                if "Path" in df.columns:
                    df = df.drop(columns=["Path"])
                
                filename = f"opt_{method_combo}_results.csv"
                file_path = method_dir / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(file_path, index=False)
                results[f"{method_combo}_opt"] = file_path
                logging.info(f"Saved {len(data_list)} OPT results to {file_path}")
    
    logging.info(f"Export completed: {len(results)} CSV files saved")
    return results


def extract_and_save(config: dict, system_dir: Path, output_dir: Path = None, 
                    criteria: str = "SUCCESSFUL") -> Dict[str, Path]:
    """
    Simple extract and save - single source of truth flow.
    """
    from PyA3EDA.core.extractors.data_extractor import extract_all_data
    # Extract data
    extracted_data = extract_all_data(config, system_dir, criteria)
    
    # Set default output directory
    if not output_dir:
        output_dir = system_dir / "results" / "raw"
    
    # Export with grouping
    return export_data(extracted_data, output_dir)