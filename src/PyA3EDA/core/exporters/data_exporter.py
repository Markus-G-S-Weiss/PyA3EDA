"""
Data Exporter Module

Single responsibility: Take extracted data and write to various file formats.
No data extraction - only file organization and writing.
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

from PyA3EDA.core.utils.file_utils import write_text


def export_all_formats(extracted_data: List[Dict[str, Any]], output_dir: Path) -> Dict[str, Any]:
    """
    Export extracted data to all supported formats.
    Single entry point for all exports.
    
    Args:
        extracted_data: List of extracted data dictionaries
        output_dir: Output directory path
        
    Returns:
        Dictionary containing paths to all exported files
    """
    if not extracted_data:
        logging.warning("No data to export")
        return {}
        
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export CSV files
    csv_results = export_csv_files(extracted_data, output_dir)
    
    # Export XYZ files
    xyz_results = export_xyz_files(extracted_data, output_dir)
    
    # Combine results
    all_results = {
        "csv_files": csv_results,
        "xyz_files": xyz_results,
        "total_csv": len(csv_results),
        "total_xyz": len(xyz_results)
    }
    
    logging.info(f"Export completed: {len(csv_results)} CSV files, {len(xyz_results)} XYZ files")
    return all_results


def group_data_by_method_combo(extracted_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group extracted data by method combo.
    """
    grouped = defaultdict(list)
    for data in extracted_data:
        method_combo = data.get("Method_Combo", "unknown")
        grouped[method_combo].append(data)
    return dict(grouped)


def export_csv_files(extracted_data: List[Dict[str, Any]], output_dir: Path) -> Dict[str, Path]:
    """
    Export CSV files using metadata from builder.
    No data extraction - only file writing.
    """
    # Use shared grouping logic
    grouped = group_data_by_method_combo(extracted_data)
    results = {}
    
    for method_combo, data_list in grouped.items():
        # Use method combo from builder (already clean)
        method_dir = output_dir / method_combo
        
        # Further group by mode for CSV organization
        mode_groups = defaultdict(list)
        for data in data_list:
            mode = data.get("Mode", "unknown")
            mode_groups[mode].append(data)
        
        for mode, mode_data_list in mode_groups.items():
            if mode == "sp":
                # Handle SP grouping
                sp_groups = defaultdict(list)
                for data in mode_data_list:
                    sp_combo = data.get("SP_Method_Combo", "unknown_sp")
                    sp_groups[sp_combo].append(data)
                
                for sp_combo, sp_data in sp_groups.items():
                    # Remove non-CSV columns
                    csv_data = [remove_non_csv_fields(d) for d in sp_data]
                    
                    df = pd.DataFrame(csv_data)
                    filename = f"sp_{sp_combo}_results.csv"
                    file_path = method_dir / filename
                    
                    if save_csv_file(df, file_path):
                        results[f"{method_combo}_sp_{sp_combo}"] = file_path
            else:
                # Handle OPT data
                csv_data = [remove_non_csv_fields(d) for d in mode_data_list]
                
                df = pd.DataFrame(csv_data)
                filename = f"opt_{method_combo}_results.csv"
                file_path = method_dir / filename
                
                if save_csv_file(df, file_path):
                    results[f"{method_combo}_opt"] = file_path
    
    return results


def export_xyz_files(extracted_data: List[Dict[str, Any]], output_dir: Path) -> Dict[str, Path]:
    """
    Export XYZ files using data already extracted.
    No data extraction - only file writing.
    XYZ files are stored in the same method directory as CSV files.
    """
    # Use shared grouping logic
    grouped = group_data_by_method_combo(extracted_data)
    results = {}
    
    for method_combo, data_list in grouped.items():
        # Use same method directory structure as CSV files
        method_dir = output_dir / method_combo
        xyz_dir = method_dir / "xyz"
        xyz_dir.mkdir(parents=True, exist_ok=True)
        
        # Only process OPT data with XYZ coordinates
        for data in data_list:
            if not is_xyz_exportable(data):
                continue
            
            # Create XYZ content from extracted data
            xyz_content = create_xyz_content(data)
            if not xyz_content:
                continue
            
            # Use filename from extracted data, removing _opt suffix
            stem = data['output_file_stem']
            if stem.endswith('_opt'):
                stem = stem[:-4]  # Remove '_opt' suffix
            filename = f"{stem}.xyz"
            xyz_file_path = xyz_dir / filename
            
            if write_text(xyz_file_path, xyz_content):
                results[data['output_file_stem']] = xyz_file_path
                logging.debug(f"Saved XYZ file: {xyz_file_path}")
    
    return results


def remove_non_csv_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove fields that shouldn't be in CSV files.
    """
    # Fields to exclude from CSV
    exclude_fields = ["Path", "output_file_stem", "n_atoms", "atoms"]
    
    return {k: v for k, v in data.items() if k not in exclude_fields}


def is_xyz_exportable(data: Dict[str, Any]) -> bool:
    """
    Check if data contains XYZ coordinates for export.
    """
    return (
        data.get("Mode") == "opt" and 
        "n_atoms" in data and 
        "atoms" in data and 
        data.get("n_atoms", 0) > 0
    )


def create_xyz_content(data: Dict[str, Any]) -> str:
    """
    Create XYZ file content from extracted data.
    Same format as XYZ templates.
    """
    n_atoms = data.get('n_atoms', 0)
    atoms = data.get('atoms', [])
    charge = data.get('Charge', 0)
    multiplicity = data.get('Multiplicity', 1)
    
    if not atoms:
        return ""
    
    content_lines = [
        str(n_atoms),
        f"{charge} {multiplicity}"
    ]
    content_lines.extend(atoms)
    
    return "\n".join(content_lines) + "\n"


def save_csv_file(df: pd.DataFrame, file_path: Path) -> bool:
    """
    Save DataFrame to CSV file.
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(file_path, index=False)
        logging.info(f"Saved {len(df)} rows to {file_path}")
        return True
    except Exception as e:
        logging.error(f"Error saving CSV to {file_path}: {e}")
        return False