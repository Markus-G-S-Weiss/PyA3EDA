#!/usr/bin/env python3

import argparse
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

ESCAPE_MAP = {
    ' ': '-space-',           # Space
    '(': '-paren-',           # Left parenthesis
    ')': '-paren-',           # Right parenthesis
    '[': '-bracket-',         # Left square bracket
    ']': '-bracket-',         # Right square bracket
    '{': '-brace-',           # Left curly brace
    '}': '-brace-',           # Right curly brace
    ',': '-comma-',           # Comma
    ';': '-semicolon-',       # Semicolon
    '*': '-asterisk-',        # Asterisk
    '?': '-qmark-',           # Question mark
    '&': '-and-',             # Ampersand
    '|': '-pipe-',            # Pipe
    '<': '-lt-',              # Less than
    '>': '-gt-',              # Greater than
    '"': '-dq-',              # Double quote
    "'": '-sq-',              # Single quote
    '\\': '-backslash-',      # Backslash
    ':': '-colon-',           # Colon
    '$': '-dollar-',          # Dollar sign
    '~': '-tilde-',           # Tilde
    '!': '-exclamation-',     # Exclamation mark
    '=': '-equal-',           # Equal sign
    '\t': '-tab-',            # Tab
    '\n': '-newline-',        # Newline
}


def read_file(file_path):
    """Read and return the content of a file."""
    try:
        return file_path.read_text().rstrip()
    except FileNotFoundError:
        logging.error(f'Template file not found: {file_path}')
        sys.exit(1)


def verify_templates(required_templates):
    """Ensure all required template files exist."""
    missing_templates = [t for t in required_templates if not t.is_file()]
    if missing_templates:
        for tmpl in missing_templates:
            logging.error(f'Missing template file: {tmpl}')
        sys.exit(1)


def write_input_file(input_file, molecule_section, rem_section, base_template_content, overwrite, calc_type):
    """Generate the input file by filling in placeholders."""
    if input_file.exists() and not overwrite:
        logging.info(f'File exists and will not be overwritten: {input_file}')
        return False
    # Determine jobtype
    num_atoms = count_atoms(molecule_section)
    if calc_type == 'ts':
        jobtype = 'ts'
    else:
        jobtype = 'sp' if num_atoms == 1 else 'opt'

    rem_section_filled = rem_section.format(jobtype=jobtype)
    input_content = base_template_content.format(
        molecule_section=molecule_section.strip(),
        rem_section=rem_section_filled.rstrip())

    input_content = '\n'.join(line.rstrip() for line in input_content.splitlines())

    try:
        input_file.write_text(input_content)
        logging.info(f'Generated input file: {input_file}')
        return True
    except IOError as err:
        logging.error(f'Failed to write input file {input_file}: {err}')
        return False


def count_atoms(molecule_section):
    """Count the number of atoms in the molecule section."""
    # Split into lines and remove empty/whitespace lines
    lines = [line.strip() for line in molecule_section.splitlines() if line.strip()]
    
    if not lines:
        logging.error("Empty molecule section")
        return 0
        
    # First line is charge/multiplicity, skip it
    atom_lines = lines[1:]
    
    return len(atom_lines)


def sanitize_filename(name):
    """Sanitize filename by replacing special characters with safe alternatives."""
    sanitized = name
    for char, replacement in ESCAPE_MAP.items():
        sanitized = sanitized.replace(char, replacement)
    return sanitized

def create_directory_structure(base_dir, paths):
    """Create directory structures with sanitized path names."""
    for path in paths:
        # Split path and sanitize each component
        components = [sanitize_filename(p) for p in path.split('/')]
        dir_path = base_dir / Path(*components)
        dir_path.mkdir(parents=True, exist_ok=True)


def check_calculation_status(out_file):
    """
    Check calculation status and return detailed information.
    Returns tuple of (status, details)
    """
    try:
        # Check if .out file exists
        if out_file.exists():
            # Read .out file content
            content = out_file.read_text()
        else:
            content = None  # Indicates .out file does not exist

        # Read .err file content if it exists
        err_file = out_file.with_suffix('.err')
        err_content = err_file.read_text() if err_file.exists() else ''

        # Check if job was cancelled manually in .err file
        if 'CANCELLED AT' in err_content:
            return 'terminated', 'Job cancelled by Queue'

        # Check for Q-Chem crash in .err file
        if 'Error in Q-Chem run' in err_content or 'Aborted' in err_content:
            # Job crashed, extract error message from .out file
            status = 'CRASH'
            error_msg = 'Q-Chem execution crashed'

            # Attempt to get detailed error message from .out file
            if content:
                if 'error occurred' in content:
                #if 'Q-Chem fatal error occurred' in content:
                    error_pattern = r'error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)'
                    #error_pattern = r'Q-Chem fatal error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)'
                    error_match = re.search(error_pattern, content, re.DOTALL)
                    if error_match:
                        full_msg = error_match.group(1).strip()
                        # Extract message up to the first '.' or ';'
                        error_msg = re.split(r'[.;]|\band\b', full_msg)[0].strip()
                    else:
                        error_msg = 'Unknown fatal error'
                elif 'SGeom Failed' in content:
                    error_msg = 'Geometry optimization failed'
                elif 'SCF failed to converge' in content:
                    error_msg = 'SCF convergence failure'
                elif 'Insufficient memory' in content:
                    error_msg = 'Out of memory'
                else:
                    error_msg = 'Unknown failure'
            return status, error_msg

        # Check if job is still running based on submission file
        input_stem = out_file.with_suffix('').stem
        submission_pattern = f"{input_stem}.in_[0-9]*.[0-9]*"
        submission_files = list(out_file.parent.glob(submission_pattern))
        if submission_files:
            return 'running', 'Job submission file exists'

        # If .out file does not exist
        if content is None:
            return 'nofile', 'Output file not found'

        # Check for running job in .out file
        if 'Running on' in content and 'Thank you very much' not in content:
            return 'running', 'Calculation in progress'

        # Check for successful completion
        if 'Thank you very much' in content:
            time_pattern = r'Total job time:\s*(.*)'
            time_match = re.search(time_pattern, content)
            job_time = time_match.group(1).strip() if time_match else 'unknown'
            return 'SUCCESSFUL', f'Completed in {job_time}'

        # Check for Q-Chem fatal error in .out file
        if 'Q-Chem fatal error occurred' in content:
            error_pattern = r'Q-Chem fatal error occurred.*?\n\s*(.*?)(?:\n\n|\Z)'
            error_match = re.search(error_pattern, content, re.DOTALL)
            if error_match:
                full_msg = error_match.group(1).strip()
                # Extract message up to the first '.' or ';'
                error_msg = re.split(r'[.;]', full_msg)[0].strip()
            else:
                error_msg = 'Unknown fatal error'
            return 'CRASH', error_msg

        # Check for specific errors in .out file
        if 'SGeom Failed' in content:
            return 'CRASH', 'Geometry optimization failed'
        if 'SCF failed to converge' in content:
            return 'CRASH', 'SCF convergence failure'
        if 'Insufficient memory' in content:
            return 'CRASH', 'Out of memory'

        # Check for job termination messages in .out file
        if 'killed' in content.lower() or 'terminating' in content.lower():
            return 'terminated', 'Job terminated unexpectedly'

        # If .out file exists but contains unknown content
        if content.strip():
            return 'CRASH', 'Unknown failure'

        # If .out file exists but is empty
        return 'empty', 'Output file is empty'

    except Exception as e:
        return 'error', f'Error reading output: {str(e)}'


def execute_input_file(input_file):
    """Execute the input file."""
    logging.info(f'Executing qqchem for {input_file}')
    input_dir = input_file.parent
    input_filename = input_file.name
    try:
        subprocess.run(
            [
                'qqchem',
                '-c', '16',
                '-t', '4-00:00:00',
                #'-x', 'compute-2-07-01,compute-2-07-02,compute-2-07-03,compute-2-07-04,compute-2-07-05',
                input_filename
            ],
            check=True,
            cwd=input_dir
        )
        logging.info(f'Submission with qqchem successful for {input_file}')
        time.sleep(0.2)
    except subprocess.CalledProcessError as err:
        logging.error(f'Error executing qqchem for {input_file}: {err}')
    except FileNotFoundError:
        logging.error('qqchem not found. Ensure it is installed and in the PATH.')
        sys.exit(1)


def run_existing_inputs(config, run_option):
    """Execute existing input files based on their status."""
    system_dir = Path.cwd()
    paths = get_calculation_paths(config, system_dir)
    
    for input_file in paths:
        if input_file.exists():
            out_file = input_file.with_suffix('.out')
            status, details = check_calculation_status(out_file)
            
            if run_option == 'all' or run_option == status:
                logging.info(f'Executing input file: {input_file} (current: {status} - {details})')
                execute_input_file(input_file)
            else:
                logging.info(f'Skipping {input_file} (current: {status} - {details})')
        else:
            logging.warning(f'Input file does not exist: {input_file}')


# Updated generate_inputs function
def generate_inputs(config, overwrite_option, run_option):
    """Generate input files and execute if run_option is specified."""
    # Get original names from config
    methods = config['methods']
    bases = config['bases']
    catalysts = config['catalysts']
    reactant1 = config['reactant1']
    reactant2 = config['reactant2']
    
    # Get sanitized names for paths
    san_methods = [sanitize_filename(m) for m in methods]
    san_bases = [sanitize_filename(b) for b in bases]
    san_catalysts = [sanitize_filename(c) for c in catalysts]
    san_reactant1 = sanitize_filename(reactant1)
    san_reactant2 = sanitize_filename(reactant2)
    
    system_dir = Path.cwd()
    template_dir = system_dir / 'templates'

    # Define template file names
    rem_template_names = ['rem_base.rem', 'rem_full_cat.rem', 'rem_pol_cat.rem', 'rem_frz_cat.rem']
    base_template_file = template_dir / 'base_template.in'

    # Collect required templates
    required_templates = [template_dir / 'rem' / name for name in rem_template_names]
    required_templates.append(base_template_file)
    required_templates.extend([template_dir / 'molecule' / fname for fname in [
        f'{reactant1}.mol', f'{reactant2}.mol', 'no_cat_product.mol', 'no_cat_ts.mol']])
    for catalyst in catalysts:
        required_templates.extend([template_dir / 'molecule' / fname for fname in [
            f'{catalyst}.mol',
            f'{catalyst}_reactant.mol',
            f'{catalyst}_product.mol',
            f'{catalyst}_ts.mol']])
    verify_templates(required_templates)

    # Read templates
    def read_templates(template_files):
        return {file.stem: read_file(file) for file in template_files}

    rem_templates = [template_dir / 'rem' / name for name in rem_template_names]
    rem_contents = read_templates(rem_templates)
    rem_base_content = rem_contents['rem_base']

    rem_additions = {
        'full_cat': rem_contents['rem_full_cat'],
        'pol_cat': rem_contents['rem_pol_cat'],
        'frz_cat': rem_contents['rem_frz_cat'],
    }

    base_template_content = read_file(base_template_file)
    molecule_dir = template_dir / 'molecule'

    for method, san_method in zip(methods, san_methods):
        for basis, san_basis in zip(bases, san_bases):
            method_basis = f'{san_method}_{san_basis}'
            logging.info(f'Processing method-basis combination: {method_basis}')
            method_basis_dir = system_dir / method_basis
            method_basis_dir.mkdir(exist_ok=True)
            
            # Use original names in rem_section content
            rem_no_cat = rem_base_content.format(method=method, basis=basis, jobtype='{jobtype}')

            # Generate no_cat inputs with sanitized paths
            no_cat_dir = method_basis_dir / 'no_cat'
            create_directory_structure(no_cat_dir, [
                f'reactants/{san_reactant1}',
                f'reactants/{san_reactant2}',
                'product',
                'ts',
            ])

            # Generate and optionally execute inputs for no_cat calculations
            no_cat_calcs = [
                (reactant1, no_cat_dir / f'reactants/{san_reactant1}/{san_reactant1}_opt.in', 'reactants'),
                (reactant2, no_cat_dir / f'reactants/{san_reactant2}/{san_reactant2}_opt.in', 'reactants'),
                ('no_cat_product', no_cat_dir / 'product/no_cat_product_opt.in', 'product'),
                ('no_cat_ts', no_cat_dir / 'ts/no_cat_ts_opt.in', 'ts'),
            ]
            for mol_name, input_file, calc_type in no_cat_calcs:
                mol_section = read_file(molecule_dir / f'{mol_name}.mol')
                
                # Determine overwrite decision
                out_file = input_file.with_suffix('.out')
                status, details = check_calculation_status(out_file)
                if overwrite_option == 'all' or overwrite_option == status:
                    overwrite_input = True
                else:
                    overwrite_input = False

                write_input_file(
                    input_file, mol_section, rem_no_cat, base_template_content, overwrite_input, calc_type)
                if run_option:
                    execute_input_file(input_file, run_option)

            # Generate catalyst inputs
            for catalyst, san_catalyst in zip(catalysts, san_catalysts):
                logging.info(f'Processing catalyst: {catalyst}')
                cat_dir = method_basis_dir / san_catalyst
                calc_types = ['full_cat', 'pol_cat', 'frz_cat']
                stages = ['reactants', 'product', 'ts']

                # Create directory structure
                paths = []
                for calc_type in calc_types:
                    paths.append(f'reactants/{san_reactant1}/{calc_type}')
                    paths.append(f'product/{calc_type}_product')
                    paths.append(f'ts/{calc_type}_ts')
                paths.append(f'reactants/{san_catalyst}')
                create_directory_structure(cat_dir, paths)

                # Prepare molecule sections
                mol_sections = {}
                # Reactants
                catal_mol_react = read_file(molecule_dir / f'{catalyst}_reactant.mol')
                reactant1_mol = read_file(molecule_dir / f'{reactant1}.mol')
                mol_sections['reactants'] = f"{catal_mol_react}\n{reactant1_mol}"
                # Product
                catal_mol_prod = read_file(molecule_dir / f'{catalyst}_product.mol')
                no_cat_prod_mol = read_file(molecule_dir / 'no_cat_product.mol')
                mol_sections['product'] = f"{catal_mol_prod}\n{no_cat_prod_mol}"
                # TS
                catal_mol_ts = read_file(molecule_dir / f'{catalyst}_ts.mol')
                no_cat_ts_mol = read_file(molecule_dir / 'no_cat_ts.mol')
                mol_sections['ts'] = f"{catal_mol_ts}\n{no_cat_ts_mol}"
                # Catalyst optimization
                mol_sections['catalyst_opt'] = read_file(molecule_dir / f'{catalyst}.mol')

                # Generate and optionally execute input files for each stage and calc_type
                for stage in stages:
                    for calc_type in calc_types:
                        rem_section = f"{rem_no_cat}\n{rem_additions[calc_type]}"
                        if stage == 'reactants':
                            input_file = cat_dir / f'reactants/{san_reactant1}/{calc_type}/{san_reactant1}_{calc_type}_opt.in'
                        else:
                            input_file = cat_dir / f'{stage}/{calc_type}_{stage}/{stage}_{calc_type}_opt.in'
                        mol_section = mol_sections[stage]
                        
                        # Determine overwrite decision
                        out_file = input_file.with_suffix('.out')
                        status, details = check_calculation_status(out_file)
                        if overwrite_option == 'all' or overwrite_option == status:
                            overwrite_input = True
                        else:
                            overwrite_input = False

                        write_input_file(
                            input_file, mol_section, rem_section, base_template_content, overwrite_input, stage)
                        if run_option:
                            execute_input_file(input_file, run_option)
                # Catalyst optimization input
                catalyst_opt_file = cat_dir / f'reactants/{san_catalyst}/{san_catalyst}_opt.in'
                # Determine overwrite decision
                out_file = catalyst_opt_file.with_suffix('.out')
                status, details = check_calculation_status(out_file)
                if overwrite_option == 'all' or overwrite_option == status:
                    overwrite_input = True
                else:
                    overwrite_input = False
                write_input_file(
                    catalyst_opt_file, mol_sections['catalyst_opt'], rem_no_cat, base_template_content, overwrite_input, 'reactants')
                if run_option:
                    execute_input_file(catalyst_opt_file, run_option)


def get_calculation_paths(config, system_dir):
    """Get all possible calculation paths with sanitized names."""
    methods = [sanitize_filename(m) for m in config['methods']]
    bases = [sanitize_filename(b) for b in config['bases']]
    catalysts = [sanitize_filename(c) for c in config['catalysts']]
    reactant1 = sanitize_filename(config['reactant1'])
    reactant2 = sanitize_filename(config['reactant2'])
    
    paths = []
    
    for method in methods:
        for basis in bases:
            method_basis_dir = system_dir / f'{method}_{basis}'
            
            # no_cat paths
            no_cat_dir = method_basis_dir / 'no_cat'
            paths.extend([
                no_cat_dir / f'reactants/{reactant1}/{reactant1}_opt.in',
                no_cat_dir / f'reactants/{reactant2}/{reactant2}_opt.in',
                no_cat_dir / 'product/no_cat_product_opt.in',
                no_cat_dir / 'ts/no_cat_ts_opt.in'
            ])
            
            # catalyst paths
            for catalyst in catalysts:
                cat_dir = method_basis_dir / catalyst
                calc_types = ['full_cat', 'pol_cat', 'frz_cat']
                
                # Add catalyst optimization path
                paths.append(cat_dir / f'reactants/{catalyst}/{catalyst}_opt.in')
                
                # Add paths for each calculation type and stage
                for calc_type in calc_types:
                    paths.extend([
                        cat_dir / f'reactants/{reactant1}/{calc_type}/{reactant1}_{calc_type}_opt.in',
                        cat_dir / f'product/{calc_type}_product/product_{calc_type}_opt.in',
                        cat_dir / f'ts/{calc_type}_ts/ts_{calc_type}_opt.in'
                    ])
    
    return paths

def check_all_statuses(paths):
    """Check and report status for all calculation paths."""
    status_counts = {}
    system_dir = Path.cwd()
    
    # Find the longest relative path length for alignment
    max_path_length = max(len(str(path.relative_to(system_dir).parent / path.stem)) for path in paths)
    # Format string for aligned columns
    format_str = f"{{:<{max_path_length}}} | {{:<10}} | {{}}"
    
    for path in paths:
        relative_path = path.relative_to(system_dir).parent / path.stem
        if path.exists():
            out_file = path.with_suffix('.out')
            status, details = check_calculation_status(out_file)
            status_counts[status] = status_counts.get(status, 0) + 1
            logging.info(format_str.format(
                str(relative_path),
                status,
                details
            ))
        else:
            status = 'absent'
            status_counts[status] = status_counts.get(status, 0) + 1
            logging.info(format_str.format(
                str(relative_path),
                status,
                'Input file not found'
            ))
    
    # Print summary with alignment
    logging.info("\nStatus Summary:")
    max_status_length = max(len(status) for status in status_counts.keys())
    summary_format = f"{{:<{max_status_length}}} : {{:>4}} calculations"
    for status, count in status_counts.items():
        logging.info(summary_format.format(status, count))


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Check calculation statuses or generate inputs.',
        formatter_class=argparse.RawTextHelpFormatter  # Preserve formatting
    )
    parser.add_argument('yaml_config', type=str, help='Path to the configuration YAML file')
    parser.add_argument(
        '-l', '--log', type=str, default='info',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        help='Logging level')
    parser.add_argument(
        '-o', '--overwrite', type=str,
        choices=['all', 'nofile', 'CRASH', 'terminated', 'SUCCESSFUL', 'running'],
        help=(
            'Overwrite input files based on their status (use with --generate):\n'
            '  all        - Overwrite all input files regardless of status.\n'
            '  nofile     - Overwrite inputs where the output file is missing.\n'
            '  CRASH      - Overwrite inputs where the job crashed.\n'
            '  terminated - Overwrite inputs where the job was terminated.\n'
            '  SUCCESSFUL - Overwrite inputs that completed successfully.\n'
            '  running    - Overwrite inputs that are currently running.'
        )
    )
    parser.add_argument(
        '-g', '--generate', action='store_true',
        help='Generate input files and optionally execute calculations')
    parser.add_argument(
        '-r', '--run', type=str,
        choices=['all', 'nofile', 'CRASH', 'terminated', 'SUCCESSFUL', 'running'],
        help=(
            'Execute input files based on their status (use with --generate):\n'
            '  all        - Execute all input files regardless of status.\n'
            '  nofile     - Execute inputs where the output file is missing.\n'
            '  CRASH      - Re-execute inputs where the job crashed.\n'
            '  terminated - Re-execute inputs where the job was terminated.\n'
            '  SUCCESSFUL - Re-execute inputs that completed successfully.\n'
            '  running    - Re-execute inputs that are currently running.'
        )
    )
    return parser.parse_args()


def setup_logging(level):
    """Set up logging configuration."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )


def load_config(config_path):
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    if not config_file.is_file():
        logging.error(f'Configuration file not found: {config_path}')
        sys.exit(1)
    try:
        with config_file.open() as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as err:
        logging.error(f'Error parsing YAML configuration: {err}')
        sys.exit(1)


def main():
    """Main function to execute the script."""
    args = parse_arguments()
    setup_logging(args.log)
    config = load_config(args.yaml_config)
    system_dir = Path.cwd()
    
    if args.generate:
        # Generate inputs and optionally execute
        generate_inputs(config, args.overwrite, args.run)
    elif args.run:
        # Run existing inputs based on the run option
        run_existing_inputs(config, args.run)
    else:
        # Default behavior: check statuses
        paths = get_calculation_paths(config, system_dir)
        check_all_statuses(paths)
    
    logging.info('Processing completed.')


if __name__ == '__main__':
    main()
