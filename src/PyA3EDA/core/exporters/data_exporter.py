"""
Data Exporter Module

Pure file writers for direct CSV and XYZ export:
- write_opt_csv: Write OPT data to CSV file
- write_sp_csv: Write SP data to CSV file  
- write_xyz_file: Write single XYZ coordinate file
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any

from PyA3EDA.core.utils.file_utils import write_text


def write_opt_csv(data_list: List[Dict[str, Any]], file_path: Path) -> bool:
    """
    Write OPT data to CSV file.
    
    Args:
        data_list: List of OPT data dictionaries (CSV-ready)
        file_path: Output CSV file path
        
    Returns:
        True if successful, False otherwise
    """
    if not data_list:
        logging.warning("No OPT data to write")
        return False
        
    try:
        # Create DataFrame and save directly
        df = pd.DataFrame(data_list)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(file_path, index=False)
        logging.info(f"Saved {len(df)} OPT rows to {file_path}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to write OPT CSV file {file_path}: {e}")
        return False


def write_sp_csv(data_list: List[Dict[str, Any]], file_path: Path) -> bool:
    """
    Write SP data to CSV file.
    
    Args:
        data_list: List of SP data dictionaries (CSV-ready)
        file_path: Output CSV file path
        
    Returns:
        True if successful, False otherwise
    """
    if not data_list:
        logging.warning("No SP data to write")
        return False
        
    try:
        # Create DataFrame and save directly
        df = pd.DataFrame(data_list)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(file_path, index=False)
        logging.info(f"Saved {len(df)} SP rows to {file_path}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to write SP CSV file {file_path}: {e}")
        return False


def write_xyz_files(data_list: List[Dict[str, Any]], output_dir: Path) -> Dict[str, Path]:
    """
    Write coordinate data to XYZ files.
    
    Args:
        data_list: List of data dictionaries with coordinate information
        output_dir: Output directory for XYZ files
        
    Returns:
        Dictionary mapping file identifiers to file paths
    """
    results = {}
    
    if not data_list:
        logging.warning("No coordinate data to write")
        return results
        
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for data in data_list:
        if not data.get("coordinates"):
            continue
            
        try:
            # Create XYZ content using existing util function
            from PyA3EDA.core.utils.xyz_format_utils import format_xyz_content
            
            coords = data["coordinates"]
            n_atoms = coords.get('n_atoms', 0)
            atoms = coords.get('atoms', [])
            charge = coords.get('Charge', 0)
            multiplicity = coords.get('Multiplicity', 1)
            
            xyz_content = format_xyz_content(n_atoms, charge, multiplicity, atoms)
            if not xyz_content:
                continue
                
            # Generate filename - remove _opt suffix if present
            species = data.get("Species", "unknown")
            file_stem = data.get("output_file_stem", species)
            
            # Remove _opt suffix if it exists at the end
            if file_stem.endswith("_opt"):
                file_stem = file_stem[:-4]
                
            filename = f"{file_stem}.xyz"

            file_path = output_dir / filename
            
            # Write file
            if write_text(file_path, xyz_content):
                results[f"{species}"] = file_path
                logging.debug(f"Written XYZ file: {file_path}")
                
        except Exception as e:
            logging.error(f"Failed to write XYZ file for {data.get('Species', 'unknown')}: {e}")
            continue
    
    logging.info(f"Written {len(results)} XYZ files to {output_dir}")
    return results


def export_all_combos(extracted_data: Dict[str, Dict[str, List[Dict[str, Any]]]], output_dir: Path) -> None:
    """
    Export all extracted method combo data to files.
    
    Args:
        extracted_data: Dictionary mapping method combo names to their extracted data
        output_dir: Output directory for all exports
    """
    if not extracted_data:
        logging.warning("No extracted data provided for export")
        return
    
    logging.info(f"Exporting {len(extracted_data)} method combos to {output_dir}")
    
    total_files = 0
    
    # Export each method combo
    for combo_name, combo_data in extracted_data.items():
        try:
            # Create structured output directories
            method_combo_dir = output_dir / "raw" / combo_name
            xyz_dir = method_combo_dir / "xyz_files"
            
            combo_files = 0
            
            # Export OPT data
            if combo_data.get("opt_data"):
                opt_file_path = method_combo_dir / f"opt_{combo_name}.csv"
                if write_opt_csv(combo_data["opt_data"], opt_file_path):
                    combo_files += 1
                    
            # Export SP data
            if combo_data.get("sp_data"):
                sp_file_path = method_combo_dir / f"sp_{combo_name}.csv"
                if write_sp_csv(combo_data["sp_data"], sp_file_path):
                    combo_files += 1
                    
            # Export XYZ data
            if combo_data.get("xyz_data"):
                xyz_results = write_xyz_files(combo_data["xyz_data"], xyz_dir)
                if xyz_results:
                    combo_files += len(xyz_results)
            
            total_files += combo_files
            logging.info(f"Exported {combo_name}: {combo_files} files")
                
        except Exception as e:
            logging.error(f"Failed to export method combo {combo_name}: {e}")
            continue
    
    logging.info(f"Export completed: {len(extracted_data)} method combos, {total_files} total files")