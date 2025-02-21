# PyA3EDA

PyA3EDA is a Python package that automates the analysis of electronic structure data. It reads a YAML configuration file specifying methods, basis sets, catalysts, and reactants (each with charge and multiplicity), and then generates Q‑Chem input files, executes calculations, extracts numerical data via regex from output files, and generates energy profiles.

## Features

- **Modern Package Structure:** Uses a `src` layout with relative imports.
- **Configuration Handling:** Reads configuration once; sanitized names are used for folder and file names, while original names (and associated charge/multiplicity) are preserved for template replacement.
- **Molecule Section Builders:** Uses dedicated functions to build standard molecule sections (for non‑catalyst inputs) and fragmented molecule sections (for catalyst inputs). The fragmented builder parses the catalyst XYZ (using an optional "cat_atoms" token in the comment line) and the reactant XYZ, checks atom counts, and builds the input accordingly.
- **Accurate Status Reporting:** Extracts wall time (in seconds) from Q‑Chem output and converts it into hh:mm:ss format.
- **Modular & Maintainable:** Code is split into dedicated modules for configuration, calculations, commands, data processing, and utilities.

## Installation

Ensure Python 3.8+ is installed. Then, install the package using Hatchling:

```bash
pip install .
```

## Usage

Run the package using:
```bash
pya3eda config.yaml [options]
```

For help run:
```bash
pya3eda --help
```

## Template Files
Place the following templates in a folder called `templates` at the root of your project.

# REM Templates:
- templates/rem/rem_base.rem
- templates/base_template.in
# Molecule (XYZ) Templates:
- For non‑catalyst (standard): e.g.,
   - templates/molecule/prop2enal.xyz
   - templates/molecule/butadiene.xyz
   - templates/molecule/prop2enal-butadiene.xyz
- For catalyst cases (fragmented):
   - Catalyst fragment files: e.g., templates/molecule/lip.xyz
   - Reactant fragment files (can be reused from above)
   - For combined fragments, see examples below.

Refer to the “Template Files” section at the end of this README for examples.

---

## Package Files (Inside `src/PyA3EDA/`)

### 3. `src/PyA3EDA/__init__.py`
```python
"""
PyA3EDA package

This package implements an automated workflow for the analysis of electronic structure data.
It includes modules for input file generation, calculation execution, data extraction, and energy profile generation.
"""

