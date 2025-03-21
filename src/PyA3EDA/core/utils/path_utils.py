"""
Path Utilities Module

Provides functions for working with paths, including grouping and metadata extraction.
"""

import logging
from pathlib import Path
from typing import Dict, Any


def extract_path_metadata(path: Path, system_dir: Path = None) -> Dict[str, Any]:
    """
    Extract standardized metadata from a file path.
    """
    metadata = {}
    
    if not system_dir:
        logging.warning(f"Cannot extract path metadata: system_dir not provided for {path}")
        return metadata
        
    try:
        # Convert to relative path
        rel_path = path.relative_to(system_dir)
        path_str = str(rel_path)
        parts = rel_path.parts
        
        # Basic metadata
        if len(parts) >= 1:
            metadata["Method"] = parts[0]
        else:
            logging.warning(f"Cannot extract Method from path: {path_str}")
        
        if len(parts) >= 2:
            metadata["Category"] = parts[1]
        else:
            logging.warning(f"Cannot extract Category from path: {path_str}")
            
        if len(parts) >= 3:
            metadata["Branch"] = parts[2]
        else:
            logging.warning(f"Cannot extract Branch from path: {path_str}")
        
        # Extract calculation type
        if "full_cat" in path_str:
            metadata["Calc_Type"] = "full_cat"
        elif "pol_cat" in path_str:
            metadata["Calc_Type"] = "pol_cat"
        elif "frz_cat" in path_str:
            metadata["Calc_Type"] = "frz_cat"
        
        # Extract mode and SP method
        if path.stem.endswith("_sp"):
            metadata["Mode"] = "sp"
            # Find SP folder
            sp_folder_found = False
            for part in parts:
                if part.endswith("_sp"):
                    metadata["SP_Method"] = part[:-3]
                    sp_folder_found = True
                    break
            if not sp_folder_found:
                logging.warning(f"SP file without identifiable SP method folder: {path_str}")
        else:
            metadata["Mode"] = "opt"
            
        # Add identifier and path
        metadata["Identifier"] = path.stem
        metadata["Path"] = path_str
        
    except Exception as e:
        logging.warning(f"Error extracting metadata from path {path}: {str(e)}")
        
    return metadata
# def extract_metadata_from_path(file_path: Path, system_dir: Path) -> Dict[str, str]:
#     """
#     Extract metadata from a file path based on the PyA3EDA directory structure.
    
#     Args:
#         file_path: Path to the file
#         system_dir: Base system directory
    
#     Returns:
#         Dictionary containing metadata extracted from the path
#     """
#     try:
#         # Get relative path from system_dir
#         relative_path = file_path.relative_to(system_dir)
#         parts = relative_path.parts
#         file_stem = file_path.stem
        
#         # First folder is method/basis
#         metadata = {}
#         if parts and len(parts) > 0:
#             metadata["Method Base"] = parts[0]
            
#         # Parse the rest based on folder structure
#         if len(parts) > 1:
#             if parts[1] == "no_cat":
#                 metadata["Category"] = "no_cat"
#                 if len(parts) > 2:
#                     metadata["Branch"] = parts[2]
#                     if len(parts) > 3:
#                         metadata["Species"] = parts[3]
#             else:
#                 metadata["Category"] = "cat"
#                 metadata["Catalyst"] = parts[1]
#                 if len(parts) > 2:
#                     metadata["Branch"] = parts[2]  # preTS, postTS, ts
#                     if len(parts) > 3:
#                         metadata["Species"] = parts[3]
#                         if len(parts) > 4:
#                             metadata["Calc Type"] = parts[4]  # full_cat, pol_cat, frz_cat
        
#         # Get file name information
#         if "_opt" in file_stem:
#             metadata["Mode"] = "opt"
#         elif "_sp" in file_stem:
#             metadata["Mode"] = "sp"
            
#         return metadata
            
#     except Exception as e:
#         logging.error(f"Error extracting metadata from path {file_path}: {e}")
#         return {}


# def group_paths_by_method(paths_with_metadata: List[Tuple[Path, Dict[str, str]]]) -> Dict[str, List[Tuple[Path, Dict[str, str]]]]:
#     """
#     Groups paths by method/basis and formats nice group names.
    
#     Args:
#         paths_with_metadata: List of (path, metadata) tuples
        
#     Returns:
#         Dictionary mapping method groups to lists of (path, metadata) tuples
#     """
#     # Maps for dispersion format
#     disp_map = {
#         'empirical_grimme': 'D2', 'empirical_chg': 'CHG', 'empirical_grimme3': 'D3(0)',
#         'd3_zero': 'D3(0)', 'd3_bj': 'D3(BJ)', 'd3_cso': 'D3(CSO)', 'd3_zerom': 'D3M(0)', 
#         'd3_bjm': 'D3M(BJ)', 'd3_op': 'D3(op)', 'd3': 'D3', 'd4': 'D4'
#     }
    
#     groups = {}
#     for path, metadata in paths_with_metadata:
#         # Get method base from metadata (already available)
#         method_base = metadata.get("Method Base", "unknown")
        
#         # Format the key from the method base
#         if "_" in method_base:
#             parts = method_base.split("_")
#             method = parts[0]
            
#             # Format dispersion if present
#             if len(parts) > 1:
#                 disp_part = parts[1]
#                 for disp_key, disp_format in disp_map.items():
#                     if disp_part.startswith(disp_key):
#                         key = f"{method}-{disp_format}"
#                         # Add remaining parts
#                         if len(parts) > 2:
#                             key += f"/{'/'.join(parts[2:])}"
#                         break
#                 else:
#                     # No dispersion match found
#                     key = f"{method}/{'/'.join(parts[1:])}"
#             else:
#                 key = method
#         else:
#             key = method_base
            
#         # Add to group (removing any "/false" parts)
#         groups.setdefault(key.replace('/false', ''), []).append((path, metadata))
    
#     return groups


# def get_paths_with_metadata(config: dict, system_dir: Path) -> List[Tuple[Path, Dict[str, str]]]:
#     """
#     Get all input paths with their metadata directly from the builder.
    
#     Args:
#         config: Configuration dictionary
#         system_dir: Base system directory
        
#     Returns:
#         List of (path, metadata) tuples for all valid input files
#     """
#     result = []
#     # Use the builder's include_metadata parameter
#     for item in iter_input_paths(config, system_dir, include_metadata=True):
#         if item is None:
#             continue
            
#         path, metadata = item
#         if path.exists():
#             result.append((path, metadata))
    
#     return result


# def get_grouped_paths(config: dict, system_dir: Path) -> Dict[str, List[Tuple[Path, Dict[str, str]]]]:
#     """
#     Get paths with metadata grouped by method.
    
#     Args:
#         config: Configuration dictionary
#         system_dir: Base system directory
        
#     Returns:
#         Dictionary mapping method groups to lists of (path, metadata) tuples
#     """
#     paths_with_metadata = get_paths_with_metadata(config, system_dir)
#     return group_paths_by_method(paths_with_metadata)
