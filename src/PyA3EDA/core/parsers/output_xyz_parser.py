import re
from typing import Optional, Dict, Any

def parse_qchem_output_xyz(out_text: str, identifier: str) -> Optional[Dict[str, Any]]:
    """
    Parses a Q-Chem output file text to extract the final atomic coordinates from the output.
    
    It finds the last occurrence of the "Standard Nuclear Orientation" block and extracts
    coordinate lines. Each coordinate line is expected to start with an index, an element symbol,
    and three floating point numbers.

    Returns a dictionary with:
      'n_atoms': int,
      'atoms': list[str] (each formatted as "Element   x   y   z")
    
    Note: Charge and multiplicity are not extracted from the output;
          the molecule builder should use the cached/template XYZ data for fragment properties.
    """
    # Locate the last occurrence of the orientation block.
    orient_tag = "Standard Nuclear Orientation"
    orient_positions = [m.start() for m in re.finditer(re.escape(orient_tag), out_text)]
    if not orient_positions:
        return None
    last_orient_index = orient_positions[-1]
    orientation_block = out_text[last_orient_index:]
    
    # Use a robust regex to match coordinate lines in the orientation block.
    coord_line_re = re.compile(
        r"^\s*\d+\s+([A-Za-z]+)\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)[ \t]+"
        r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)[ \t]+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
        re.MULTILINE
    )
    atoms = []
    for line in orientation_block.splitlines():
        match = coord_line_re.match(line)
        if match:
            element = match.group(1)
            x = float(match.group(2))
            y = float(match.group(3))
            z = float(match.group(4))
            atoms.append(f"{element}   {x:14.10f}   {y:14.10f}   {z:14.10f}")
    
    if not atoms:
        return None

    return {
        'n_atoms': len(atoms),
        'atoms': atoms
    }