#!/home/dal063121/.conda/envs/extrplt/bin/python3

import argparse
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml


def read_file(file_path):
    """
    Read and return the content of a file without trailing blank lines.
    """
    try:
        content = file_path.read_text().rstrip()
        return content
    except FileNotFoundError:
        logging.error(f'Template file not found: {file_path}')
        sys.exit(1)


def verify_templates(required_templates):
    """
    Verify that all required template files exist.
    """
    missing_templates = [
        template for template in required_templates if not template.is_file()
    ]
    if missing_templates:
        for template in missing_templates:
            logging.error(f'Missing template file: {template}')
        sys.exit(1)


def count_atoms(molecule_section):
    """
    Count the number of atoms in a molecule section.
    """
    lines = molecule_section.strip().splitlines()
    # Remove empty lines and strip whitespace
    lines = [line.strip() for line in lines if line.strip()]
    # Find the index of '$molecule'
    try:
        molecule_index = lines.index('$molecule')
    except ValueError:
        logging.error("No '$molecule' line found in molecule section.")
        return 0  # or raise an error

    # The charge and multiplicity line is next
    charge_multiplicity_index = molecule_index + 1
    if charge_multiplicity_index >= len(lines):
        logging.error("No charge and multiplicity line found after '$molecule'.")
        return 0  # or raise an error

    # Start collecting atom lines after the charge/multiplicity line
    atom_lines = []
    for line in lines[charge_multiplicity_index + 1:]:
        if line.startswith('$end'):
            break
        if line:  # Ignore any additional empty lines
            atom_lines.append(line)

    return len(atom_lines)


def write_input_file(
    input_file, molecule_section, rem_section, base_template_content, overwrite
):
    """
    Write the input file by replacing placeholders with actual content.
    """
    if input_file.exists() and not overwrite:
        logging.info(f'File already exists and will not be overwritten: {input_file}')
        return False  # Indicate that file was not written

    # Insert the molecule section into the base template
    input_content = base_template_content.replace(
        '{molecule_section}', molecule_section
    ).replace('{rem_section}', rem_section)

    # Ensure no extra blank lines are added
    input_content = '\n'.join(
        [line.rstrip() for line in input_content.splitlines()]
    )

    # Now, count the number of atoms in the input_content
    num_atoms = count_atoms(input_content)

    # Determine jobtype based on number of atoms
    jobtype = 'sp' if num_atoms == 1 else 'opt'

    # Replace placeholders in the rem_section with the determined jobtype
    rem_section_filled = rem_section.format(jobtype=jobtype)

    # Update input_content with the filled rem section
    input_content = input_content.replace(rem_section, rem_section_filled)

    try:
        input_file.write_text(input_content)
        logging.info(f'Generated input file: {input_file}')
        return True  # Indicate that file was written
    except IOError as err:
        logging.error(f'Failed to write input file {input_file}: {err}')
        return False


def create_no_cat_structure(method_basis_dir, reactant1, reactant2):
    """
    Create directory structure for no_cat calculations.
    """
    no_cat_dir = method_basis_dir / 'no_cat'
    (no_cat_dir / 'reactants' / reactant1).mkdir(parents=True, exist_ok=True)
    (no_cat_dir / 'reactants' / reactant2).mkdir(parents=True, exist_ok=True)
    (no_cat_dir / 'product').mkdir(parents=True, exist_ok=True)
    (no_cat_dir / 'ts').mkdir(parents=True, exist_ok=True)
    return no_cat_dir


def generate_no_cat_inputs(
    no_cat_dir,
    reactant1,
    reactant2,
    rem_no_cat,
    base_template_content,
    template_dir,
    overwrite,
):
    """
    Generate input files for no_cat calculations.
    """
    generated_files = []

    # Reactants
    for mol in [reactant1, reactant2]:
        mol_file = template_dir / 'molecule' / f'{mol}.mol'
        mol_section = read_file(mol_file)
        input_file = no_cat_dir / 'reactants' / mol / f'{mol}_opt.in'

        if write_input_file(
            input_file,
            mol_section,
            rem_no_cat,
            base_template_content,
            overwrite,
        ):
            generated_files.append(input_file)

    # Product
    mol_file = template_dir / 'molecule' / 'no_cat_product.mol'
    mol_section = read_file(mol_file)
    input_file = no_cat_dir / 'product' / 'product_opt.in'
    if write_input_file(
        input_file, mol_section, rem_no_cat, base_template_content, overwrite
    ):
        generated_files.append(input_file)

    # TS (Transition State)
    mol_file = template_dir / 'molecule' / 'no_cat_ts.mol'
    mol_section = read_file(mol_file)
    input_file = no_cat_dir / 'ts' / 'ts_opt.in'
    if write_input_file(
        input_file, mol_section, rem_no_cat, base_template_content, overwrite
    ):
        generated_files.append(input_file)

    return generated_files


def create_catalyst_structure(method_basis_dir, catalyst, reactant1):
    """
    Create directory structure for catalyst calculations.
    """
    cat_dir = method_basis_dir / catalyst
    (cat_dir / 'reactants' / reactant1 / 'full_cat').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'reactants' / reactant1 / 'pol_cat').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'reactants' / reactant1 / 'frz_cat').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'reactants' / catalyst).mkdir(parents=True, exist_ok=True)
    (cat_dir / 'product' / 'full_cat_product').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'product' / 'pol_cat_product').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'product' / 'frz_cat_product').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'ts' / 'full_cat_ts').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'ts' / 'pol_cat_ts').mkdir(parents=True, exist_ok=True)
    (cat_dir / 'ts' / 'frz_cat_ts').mkdir(parents=True, exist_ok=True)
    return cat_dir


def generate_catalyst_inputs(
    cat_dir,
    catalyst,
    reactant1,
    rem_no_cat,
    rem_additions,
    base_template_content,
    template_dir,
    overwrite,
):
    """
    Generate input files for catalyst calculations.
    """
    generated_files = {}

    # Reactant1 with catalyst
    catalyst_mol_file = template_dir / 'molecule' / f'{catalyst}_reactant.mol'
    catalyst_mol_section = read_file(catalyst_mol_file)

    reactant_mol_file = template_dir / 'molecule' / f'{reactant1}.mol'
    reactant_mol_section = read_file(reactant_mol_file)

    combined_mol_section = f"{catalyst_mol_section}\n{reactant_mol_section}"

    calc_types = [
        ('full_cat', rem_additions['full_cat']),
        ('pol_cat', rem_additions['pol_cat']),
        ('frz_cat', rem_additions['frz_cat']),
    ]
    for calc_type, rem_addition in calc_types:
        rem_section = f"{rem_no_cat}\n{rem_addition}"
        input_file = (
            cat_dir
            / 'reactants'
            / reactant1
            / calc_type
            / f'{reactant1}_{calc_type}_opt.in'
        )

        if write_input_file(
            input_file,
            combined_mol_section,
            rem_section,
            base_template_content,
            overwrite,
        ):
            generated_files.setdefault(calc_type, []).append(input_file)

    # Catalyst optimization (no combination needed)
    mol_file = template_dir / 'molecule' / f'{catalyst}.mol'
    mol_section = read_file(mol_file)
    input_file = cat_dir / 'reactants' / catalyst / f'{catalyst}_opt.in'

    if write_input_file(
        input_file,
        mol_section,
        rem_no_cat,
        base_template_content,
        overwrite,
    ):
        generated_files.setdefault('catalyst_opt', []).append(input_file)

    # Product with catalyst
    catalyst_product_mol_file = template_dir / 'molecule' / f'{catalyst}_product.mol'
    catalyst_product_mol_section = read_file(catalyst_product_mol_file)

    no_cat_product_mol_file = template_dir / 'molecule' / 'no_cat_product.mol'
    no_cat_product_mol_section = read_file(no_cat_product_mol_file)

    combined_product_mol_section = f"{catalyst_product_mol_section}\n{no_cat_product_mol_section}"

    calc_types = [
        ('full_cat_product', rem_additions['full_cat']),
        ('pol_cat_product', rem_additions['pol_cat']),
        ('frz_cat_product', rem_additions['frz_cat']),
    ]
    for calc_type, rem_addition in calc_types:
        rem_section = f"{rem_no_cat}\n{rem_addition}"
        input_file = (
            cat_dir
            / 'product'
            / calc_type
            / f'product_{calc_type}_opt.in'
        )

        if write_input_file(
            input_file,
            combined_product_mol_section,
            rem_section,
            base_template_content,
            overwrite,
        ):
            generated_files.setdefault(calc_type, []).append(input_file)

    # TS with catalyst
    catalyst_ts_mol_file = template_dir / 'molecule' / f'{catalyst}_ts.mol'
    catalyst_ts_mol_section = read_file(catalyst_ts_mol_file)

    no_cat_ts_mol_file = template_dir / 'molecule' / 'no_cat_ts.mol'
    no_cat_ts_mol_section = read_file(no_cat_ts_mol_file)

    combined_ts_mol_section = f"{catalyst_ts_mol_section}\n{no_cat_ts_mol_section}"

    calc_types = [
        ('full_cat_ts', rem_additions['full_cat']),
        ('pol_cat_ts', rem_additions['pol_cat']),
        ('frz_cat_ts', rem_additions['frz_cat']),
    ]
    for calc_type, rem_addition in calc_types:
        rem_section = f"{rem_no_cat}\n{rem_addition}"
        input_file = cat_dir / 'ts' / calc_type / f'ts_{calc_type}_opt.in'

        if write_input_file(
            input_file,
            combined_ts_mol_section,
            rem_section,
            base_template_content,
            overwrite,
        ):
            generated_files.setdefault(calc_type, []).append(input_file)

    return generated_files


def collect_input_files(methods, bases, catalysts, system_dir):
    """
    Collect all .in files for the specified methods, bases, and catalysts.
    """
    input_files = []

    for method in methods:
        for basis in bases:
            method_basis_dir = system_dir / f'{method}_{basis}'

            # no_cat calculations
            no_cat_dir = method_basis_dir / 'no_cat'
            for calc_type in ['reactants', 'product', 'ts']:
                for path in (no_cat_dir / calc_type).rglob('*.in'):
                    input_files.append(path)

            # Catalyst calculations
            for catalyst in catalysts:
                cat_dir = method_basis_dir / catalyst
                for calc_type in [
                    'reactants',
                    'product',
                    'ts',
                ]:
                    for subdir in cat_dir.glob(f'{calc_type}/**'):
                        if subdir.is_dir():
                            for path in subdir.rglob('*.in'):
                                input_files.append(path)
    return input_files


def check_calculation_success(out_file):
    """
    Check if the calculation was successful by parsing the output file.
    """
    content = out_file.read_text()
    success_patterns = [
        re.compile(r'Thank you very much'),
    ]
    for pattern in success_patterns:
        if pattern.search(content):
            return True
    return False


def execute_inputs(input_files, run_option):
    """
    Execute input files using qqchem based on the specified run option.
    """
    for input_file in input_files:
        out_file = input_file.with_suffix('.out')
        status = 'nofile'
        execute = False

        if out_file.is_file():
            try:
                if check_calculation_success(out_file):
                    status = 'successful'
                else:
                    status = 'failed'
            except IOError as err:
                logging.error(f'Error reading {out_file}: {err}')
                status = 'failed'
        else:
            status = 'nofile'

        if run_option == 'all' or run_option == status:
            execute = True

        if execute:
            input_dir = input_file.parent
            input_filename = input_file.name
            logging.info(f'Executing qqchem for {input_file} (status: {status}).')
            try:
                subprocess.run(
                    [
                        'qqchem',
                        '-c',
                        '8',
                        '-t',
                        '7-00:00:00',
                        '-x',
                        (
                            'compute-2-07-01,compute-2-07-02,compute-2-07-03,'
                            'compute-2-07-04,compute-2-07-05'
                        ),
                        input_filename,
                    ],
                    check=True,
                    cwd=input_dir
                )
                logging.info(f'Executed qqchem successfully for {input_file}.')
                time.sleep(0.1)
            except subprocess.CalledProcessError as err:
                logging.error(f'Error executing qqchem for {input_file}: {err}')
            except FileNotFoundError:
                logging.error(
                    'qqchem not found. Please ensure it is installed and in the PATH.'
                )
                sys.exit(1)
        else:
            logging.info(f'Skipping {input_file}, status: {status}')


def check_status(input_files):
    """
    Check and report the status of each calculation.
    """
    statuses = {'successful': [], 'failed': [], 'nofile': []}

    for input_file in input_files:
        out_file = input_file.with_suffix('.out')
        status = 'nofile'

        if out_file.is_file():
            try:
                if check_calculation_success(out_file):
                    status = 'successful'
                else:
                    status = 'failed'
            except IOError as err:
                logging.error(f'Error reading {out_file}: {err}')
                status = 'failed'
        else:
            status = 'nofile'

        statuses[status].append(input_file)

    for status, files in statuses.items():
        count = len(files)
        logging.info(f"\nCalculations with status '{status}' ({count}):")
        for file in files:
            logging.info(f'  {file.with_suffix("")}')


def generate_input_files(config, overwrite, run_option):
    """
    Generate the directory structure and input files based on the configuration.
    """
    methods = config['methods']
    bases = config['bases']
    catalysts = config['catalysts']
    reactant1 = config['reactant1']
    reactant2 = config['reactant2']

    system_dir = Path.cwd()
    template_dir = system_dir / 'templates'

    rem_base = template_dir / 'rem' / 'rem_base.rem'
    rem_full_cat = template_dir / 'rem' / 'rem_full_cat.rem'
    rem_pol_cat = template_dir / 'rem' / 'rem_pol_cat.rem'
    rem_frz_cat = template_dir / 'rem' / 'rem_frz_cat.rem'
    base_template = template_dir / 'base_template.in'

    required_templates = [
        rem_base,
        rem_full_cat,
        rem_pol_cat,
        rem_frz_cat,
        base_template,
        template_dir / 'molecule' / 'no_cat_product.mol',
        template_dir / 'molecule' / 'no_cat_ts.mol',
        template_dir / 'molecule' / f'{reactant1}.mol',
        template_dir / 'molecule' / f'{reactant2}.mol',
    ]
    for catalyst in catalysts:
        required_templates.extend(
            [
                template_dir / 'molecule' / f'{catalyst}.mol',
                template_dir / 'molecule' / f'{catalyst}_reactant.mol',
                template_dir / 'molecule' / f'{catalyst}_product.mol',
                template_dir / 'molecule' / f'{catalyst}_ts.mol',
            ]
        )
    verify_templates(required_templates)

    rem_base_content = read_file(rem_base)
    rem_additions = {
        'full_cat': read_file(rem_full_cat),
        'pol_cat': read_file(rem_pol_cat),
        'frz_cat': read_file(rem_frz_cat),
    }
    base_template_content = read_file(base_template)

    for method in methods:
        for basis in bases:
            method_basis = f'{method}_{basis}'
            logging.info(f'Processing method-basis combination: {method_basis}')

            method_basis_dir = system_dir / method_basis
            method_basis_dir.mkdir(exist_ok=True)

            rem_no_cat = rem_base_content.format(method=method, basis=basis, jobtype='{jobtype}')

            no_cat_dir = create_no_cat_structure(
                method_basis_dir, reactant1, reactant2
            )
            generate_no_cat_inputs(
                no_cat_dir,
                reactant1,
                reactant2,
                rem_no_cat,
                base_template_content,
                template_dir,
                overwrite,
            )

            for catalyst in catalysts:
                logging.info(f'Processing catalyst: {catalyst}')

                cat_dir = create_catalyst_structure(
                    method_basis_dir, catalyst, reactant1
                )
                generate_catalyst_inputs(
                    cat_dir,
                    catalyst,
                    reactant1,
                    rem_no_cat,
                    rem_additions,
                    base_template_content,
                    template_dir,
                    overwrite,
                )

    if run_option:
        all_input_files = collect_input_files(methods, bases, catalysts, system_dir)
        execute_inputs(all_input_files, run_option)


def parse_arguments():
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description='Generate directory structures and input files.'
    )
    parser.add_argument('yaml_config', type=str, help='Path to the configuration YAML file')

    parser.add_argument(
        '--log',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        help='Logging level',
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing input files if they exist',
    )
    parser.add_argument(
        '--run',
        type=str,
        choices=['all', 'failed', 'nofile', 'successful'],
        help='Execute input files: all, failed, nofile, or successful calculations',
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check and report the current status of calculations',
    )
    return parser.parse_args()


def setup_logging(level):
    """
    Set up logging configuration.
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )


def load_config(config_path):
    """
    Load configuration from YAML file.
    """
    config_file = Path(config_path)
    if not config_file.is_file():
        logging.error(f'Configuration file not found: {config_path}')
        sys.exit(1)
    try:
        config = yaml.safe_load(config_file.read_text())
        return config
    except yaml.YAMLError as err:
        logging.error(f'Error parsing YAML configuration: {err}')
        sys.exit(1)


# Modify main function to handle '--status' flag
def main():
    """
    Main function to execute the script.
    """
    args = parse_arguments()
    setup_logging(args.log)
    config = load_config(args.yaml_config)

    # Generate input files if not checking status
    if not args.status:
        generate_input_files(config, args.overwrite, args.run)

    # Collect all input files
    methods = config['methods']
    bases = config['bases']
    catalysts = config['catalysts']
    system_dir = Path.cwd()
    all_input_files = collect_input_files(methods, bases, catalysts, system_dir)

    # Check and report status if '--status' flag is used
    if args.status:
        check_status(all_input_files)
        sys.exit(0)

    # Execute inputs if '--run' option is provided
    if args.run:
        execute_inputs(all_input_files, args.run)


if __name__ == '__main__':
    main()
