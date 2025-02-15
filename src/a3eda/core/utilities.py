import logging
import re
from pathlib import Path
from typing import Optional, Tuple

class Utilities:
    """Static utility functions used across classes."""
    @staticmethod
    def get_energy_value(content: str, patterns: dict) -> Optional[float]:
        """Extract energy value from content."""
        for pattern_name in ["final_energy", "final_energy_fallback"]:
            match = patterns[pattern_name].search(content)
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def get_value_with_fallback(content: str, primary_pattern: re.Pattern,
                               fallback_pattern: re.Pattern) -> Tuple[Optional[float], Optional[str], bool]:
        """Extract value and unit using primary pattern, fallback to secondary if needed."""
        primary_match = primary_pattern.search(content)
        if primary_match:
            return float(primary_match.group(1)), primary_match.group(2), False
        fallback_match = fallback_pattern.search(content)
        if fallback_match:
            return float(fallback_match.group(1)), fallback_match.group(2), True
        return None, None, False

    @staticmethod
    def get_calculation_label(relative_path: Path) -> str:
        """Generate a calculation label based on the directory structure."""
        parts = relative_path.parts[:-1]
        return "/".join(parts)

    @staticmethod
    def count_atoms(molecule_section: str) -> int:
        """Count the number of atoms in the molecule section."""
        lines = [line.strip() for line in molecule_section.splitlines() if line.strip()]
        if not lines:
            logging.error("Empty molecule section")
            return 0
        return len(lines[1:])  # First line is charge/multiplicity
