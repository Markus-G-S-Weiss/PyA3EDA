from pathlib import Path
from typing import List
import logging
from .file_operations import FileOperations
from .file_handler import FileHandler
from .qchem_calculation import QChemCalculation

class InputGenerator(FileOperations):
    """Class for generating input files."""
    def __init__(self, config: dict, template_dir: Path):
        super().__init__(template_dir)
        self.config = config
        self.system_dir = Path.cwd()
        self.file_handler = FileHandler(template_dir)

    def generate_inputs(self, overwrite_option: str, run_option: str):
        """Generate input files and execute if run_option is specified."""
        # Get original names from config
        methods = self.config['methods']
        bases = self.config['bases']
        catalysts = self.config['catalysts']
        reactant1 = self.config['reactant1']
        reactant2 = self.config['reactant2']
        
        # Get sanitized names for paths 
        san_methods = [FileHandler.sanitize_filename(m) for m in methods]
        san_bases = [FileHandler.sanitize_filename(b) for b in bases]
        san_catalysts = [FileHandler.sanitize_filename(c) for c in catalysts]
        san_reactant1 = FileHandler.sanitize_filename(reactant1)
        san_reactant2 = FileHandler.sanitize_filename(reactant2)
        
        # Process each method-basis combination
        for method, san_method in zip(methods, san_methods):
            for basis, san_basis in zip(bases, san_bases):
                method_basis_dir = self.system_dir / f'{san_method}_{san_basis}'
                method_basis_dir.mkdir(exist_ok=True)
                
                # Create no_cat directories
                no_cat_dir = method_basis_dir / 'no_cat'
                no_cat_paths = [
                    f'reactants/{san_reactant1}',
                    f'reactants/{san_reactant2}',
                    'product',
                    'ts'
                ]
                self.file_handler.create_directory_structure(no_cat_dir, no_cat_paths)
                
                # Create catalyst directories
                for catalyst, san_catalyst in zip(catalysts, san_catalysts):
                    cat_dir = method_basis_dir / san_catalyst
                    catalyst_paths = []
                    for calc_type in ['full_cat', 'pol_cat', 'frz_cat']:
                        catalyst_paths.extend([
                            f'reactants/{san_reactant1}/{calc_type}',
                            f'product/{calc_type}_product',
                            f'ts/{calc_type}_ts'
                        ])
                    catalyst_paths.append(f'reactants/{san_catalyst}')
                    self.file_handler.create_directory_structure(cat_dir, catalyst_paths)

                self._generate_calculation_inputs(
                    method_basis_dir=method_basis_dir,
                    method=method,
                    basis=basis,
                    catalysts=catalysts,
                    reactant1=reactant1,
                    reactant2=reactant2,
                    overwrite_option=overwrite_option,
                    run_option=run_option
                )

    def _generate_calculation_inputs(self, method_basis_dir: Path, method: str, basis: str,
                                   catalysts: List[str], reactant1: str, reactant2: str,
                                   overwrite_option: str, run_option: str):
        """Generate the actual input files."""
        # Read templates
        template_dir = self.system_dir / 'templates'
        rem_base = self.read_file(template_dir / 'rem/rem_base.rem')
        rem_additions = {
            'full_cat': self.read_file(template_dir / 'rem/rem_full_cat.rem'),
            'pol_cat': self.read_file(template_dir / 'rem/rem_pol_cat.rem'),
            'frz_cat': self.read_file(template_dir / 'rem/rem_frz_cat.rem')
        }
        base_template_content = self.read_file(template_dir / 'base_template.in')

        # Format base REM section
        rem_base_formatted = rem_base.format(method=method, basis=basis, jobtype='{jobtype}')

        # Generate no_cat inputs
        self._generate_no_cat_inputs(
            method_basis_dir=method_basis_dir,
            reactant1=reactant1,
            reactant2=reactant2,
            rem_base=rem_base_formatted,
            base_template_content=base_template_content,  # Changed from base_template
            template_dir=template_dir,
            overwrite_option=overwrite_option,
            run_option=run_option
        )

        # Generate catalyst inputs
        for catalyst in catalysts:
            self._generate_catalyst_inputs(
                method_basis_dir=method_basis_dir,
                catalyst=catalyst,
                reactant1=reactant1,
                rem_base=rem_base_formatted,
                rem_additions=rem_additions,
                base_template_content=base_template_content,  # Changed from base_template
                template_dir=template_dir,
                overwrite_option=overwrite_option,
                run_option=run_option
            )

    def _generate_no_cat_inputs(self, method_basis_dir: Path, reactant1: str, reactant2: str, 
                               rem_base: str, base_template_content: str, template_dir: Path, 
                               overwrite_option: str, run_option: str):
        """Generate no-catalyst input files."""
        no_cat_dir = method_basis_dir / 'no_cat'
        no_cat_calcs = [
            (reactant1, no_cat_dir / f'reactants/{reactant1}/{reactant1}_opt.in', 'reactants'),
            (reactant2, no_cat_dir / f'reactants/{reactant2}/{reactant2}_opt.in', 'reactants'),
            ('no_cat_product', no_cat_dir / 'product/no_cat_product_opt.in', 'product'),
            ('no_cat_ts', no_cat_dir / 'ts/no_cat_ts_opt.in', 'ts'),
        ]
        for mol_name, input_file, calc_type in no_cat_calcs:
            mol_section = self.read_file(template_dir / 'molecule' / f'{mol_name}.mol')
            
            # Determine overwrite decision
            out_file = input_file.with_suffix('.out')
            qchem = QChemCalculation(input_file)
            status, details = qchem.check_status()
            
            # Create new QChemCalculation instance with proper overwrite flag
            qchem = QChemCalculation(
                input_file, 
                overwrite=(overwrite_option == 'all' or overwrite_option == status)
            )
            
            qchem.write_input_file(
                mol_section, rem_base, base_template_content, calc_type)
            if run_option:
                qchem.execute()

    def _generate_catalyst_inputs(self, method_basis_dir: Path, catalyst: str, reactant1: str, rem_base: str, rem_additions: dict, base_template_content: str, template_dir: Path, overwrite_option: str, run_option: str):
        """Generate catalyst-specific input files."""
        cat_dir = method_basis_dir / catalyst
        calc_types = ['full_cat', 'pol_cat', 'frz_cat']
        stages = ['reactants', 'product', 'ts']

        # Prepare molecule sections
        mol_sections = {}
        # Reactants
        catal_mol_react = self.read_file(template_dir / 'molecule' / f'{catalyst}_reactant.mol')
        reactant1_mol = self.read_file(template_dir / 'molecule' / f'{reactant1}.mol')
        mol_sections['reactants'] = f"{catal_mol_react}\n{reactant1_mol}"
        # Product
        catal_mol_prod = self.read_file(template_dir / 'molecule' / f'{catalyst}_product.mol')
        no_cat_prod_mol = self.read_file(template_dir / 'molecule' / 'no_cat_product.mol')
        mol_sections['product'] = f"{catal_mol_prod}\n{no_cat_prod_mol}"
        # TS
        catal_mol_ts = self.read_file(template_dir / 'molecule' / f'{catalyst}_ts.mol')
        no_cat_ts_mol = self.read_file(template_dir / 'molecule' / 'no_cat_ts.mol')
        mol_sections['ts'] = f"{catal_mol_ts}\n{no_cat_ts_mol}"
        # Catalyst optimization
        mol_sections['catalyst_opt'] = self.read_file(template_dir / 'molecule' / f'{catalyst}.mol')

        # Generate and optionally execute input files for each stage and calc_type
        for stage in stages:
            for calc_type in calc_types:
                rem_section = f"{rem_base}\n{rem_additions[calc_type]}"
                if stage == 'reactants':
                    input_file = cat_dir / f'reactants/{reactant1}/{calc_type}/{reactant1}_{calc_type}_opt.in'
                else:
                    input_file = cat_dir / f'{stage}/{calc_type}_{stage}/{stage}_{calc_type}_opt.in'
                mol_section = mol_sections[stage]
                
                # Determine overwrite decision
                out_file = input_file.with_suffix('.out')
                qchem = QChemCalculation(input_file)
                status, details = qchem.check_status()
                
                qchem = QChemCalculation(
                    input_file,
                    overwrite=(overwrite_option == 'all' or overwrite_option == status)
                )
                
                qchem.write_input_file(
                    mol_section, rem_section, base_template_content, stage)
                if run_option:
                    qchem.execute()
        # Catalyst optimization input
        catalyst_opt_file = cat_dir / f'reactants/{catalyst}/{catalyst}_opt.in'
        # Determine overwrite decision
        out_file = catalyst_opt_file.with_suffix('.out')
        qchem = QChemCalculation(catalyst_opt_file)
        status, details = qchem.check_status()
        qchem = QChemCalculation(
            catalyst_opt_file,
            overwrite=(overwrite_option == 'all' or overwrite_option == status)
        )
        qchem.write_input_file(
            mol_sections['catalyst_opt'], rem_base, base_template_content, 'reactants')
        if run_option:
            qchem.execute()