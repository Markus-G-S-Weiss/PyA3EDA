"""
Data Exporter Module

Handles saving of extracted data to CSV files.
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


def get_metadata_columns() -> List[str]:
    """Return standard metadata columns in preferred order."""
    return [
        "Method", "Category", "Branch", "Calc_Type", "Mode", 
        "SP_Method", "Identifier"
    ]


def get_sort_columns() -> List[str]:
    """Return columns to sort by in preferred order."""
    return ["Category", "Branch", "Calc_Type"]


def prepare_dataframe(data_list: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create a DataFrame from data list with proper column ordering and sorting.
    """
    if not data_list:
        logging.warning("Attempted to prepare DataFrame from empty data list")
        return pd.DataFrame()
        
    # Create DataFrame
    df = pd.DataFrame(data_list)
    
    # Exclude Path column if present
    columns_to_keep = [col for col in df.columns if col != "Path"]
    df = df[columns_to_keep]
    
    # Order columns - metadata first, then the rest
    metadata_columns = get_metadata_columns()
    present_metadata = [col for col in metadata_columns if col in df.columns]
    other_columns = [col for col in df.columns if col not in metadata_columns]
    
    # Apply column ordering
    df = df[present_metadata + other_columns]
    
    # Sort DataFrame
    sort_cols = [col for col in get_sort_columns() if col in df.columns]
    if sort_cols:
        try:
            df = df.sort_values(by=sort_cols)
        except Exception as e:
            logging.warning(f"Error sorting DataFrame: {e}")
    
    return df


def export_dataframe(df: pd.DataFrame, output_path: Path) -> bool:
    """
    Export DataFrame to CSV file.
    
    Args:
        df: DataFrame to export
        output_path: Path to save the CSV file
        
    Returns:
        True if successful, False otherwise
    """
    if df.empty:
        logging.warning(f"Cannot export empty DataFrame to {output_path}")
        return False
        
    # Ensure parent directory exists
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"Failed to create directory for {output_path}: {e}")
        return False
    
    # Save CSV
    try:
        df.to_csv(output_path, index=False)
        return True
    except Exception as e:
        logging.error(f"Error saving CSV to {output_path}: {e}")
        return False


def group_sp_data(data_list: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group SP data by SP method.
    """
    groups = {}
    ungrouped_count = 0
    
    for item in data_list:
        # Get SP method
        sp_method = item.get("SP_Method")
        
        if not sp_method:
            # Try to extract from internal path as fallback
            path = item.get("_path", "")
            sp_method = "unknown"
            ungrouped_count += 1
            
            # Parse path to find SP method folder
            if path:
                path_parts = path.replace("\\", "/").split("/")
                for part in path_parts:
                    if part.endswith("_sp"):
                        sp_method = part[:-3]
                        break
        
        # Add to group
        if sp_method not in groups:
            groups[sp_method] = []
        groups[sp_method].append(item)
    
    if ungrouped_count > 0:
        logging.warning(f"Found {ungrouped_count} SP data entries without SP_Method information")
        
    return groups


def export_data(extracted_data: Dict[str, Dict[str, List[Dict[str, Any]]]], 
               output_dir: Path = None,
               prefix: str = "") -> Dict[str, Dict[str, Path]]:
    """
    Save extracted data to CSV files with proper organization.
    """
    if not output_dir:
        raise ValueError("Output directory must be specified")
        
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    total_files = 0
    
    # Process each method group
    for method, mode_data in extracted_data.items():
        method_dir = output_dir / method
        method_results = {}
        
        # Handle each mode
        for mode, data_list in mode_data.items():
            if not data_list:
                continue
                
            if mode == "sp":
                # Group SP data
                sp_groups = group_sp_data(data_list)
                
                # Process each SP group
                for sp_method, sp_data in sp_groups.items():
                    # Create DataFrame
                    df = prepare_dataframe(sp_data)
                    
                    # Create filename
                    filename = f"{prefix}sp_{sp_method}_results.csv"
                    file_path = method_dir / filename
                    
                    # Save CSV
                    if export_dataframe(df, file_path):
                        method_results[f"sp_{sp_method}"] = file_path
                        total_files += 1
                        logging.info(f"Saved {len(sp_data)} SP results for {method} (SP method: {sp_method})")
            else:
                # Process OPT data
                df = prepare_dataframe(data_list)
                
                # Create filename
                filename = f"{prefix}{mode}_{method}_results.csv"
                file_path = method_dir / filename
                
                # Save CSV
                if export_dataframe(df, file_path):
                    method_results[mode] = file_path
                    total_files += 1
                    logging.info(f"Saved {len(data_list)} {mode.upper()} results for {method}")
        
        if method_results:
            results[method] = method_results
    
    # Log summary
    logging.info(f"Saved {total_files} CSV files")
    return results


def extract_and_save(config: dict, system_dir: Path, output_dir: Path = None, criteria: str = "SUCCESSFUL") -> Dict[str, Dict[str, Path]]:
    """
    Coordinate extraction and saving of data.
    """
    # Default output directory
    if output_dir is None:
        output_dir = system_dir / "results"
    
    # Create raw output directory
    raw_output_dir = output_dir / "raw"
    
    # Import here to avoid circular imports
    from PyA3EDA.core.extractors.data_extractor import extract_all_data
    
    # Extract and export data
    return export_data(
        extract_all_data(config, system_dir, criteria),
        raw_output_dir
    )