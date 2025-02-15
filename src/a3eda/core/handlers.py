import logging
from pathlib import Path
from typing import List, Dict, Optional
from .input_generator import InputGenerator
from .status_checker import StatusChecker
from .qchem_calculation import QChemCalculation
from .data_processor import DataProcessor
from .data_exporter import DataExporter
from .energy_profile_generator import EnergyProfileGenerator
from .file_handler import FileHandler

class CommandHandlers:
    """Handles all command operations for A3EDA."""
    
    def __init__(self, config_manager, system_dir: Path, data_dirs: Dict[str, Path]):
        self.config_manager = config_manager
        self.system_dir = system_dir
        self.data_dirs = data_dirs

    def create_data_directories(self) -> None:
        """Create all necessary data directories."""
        for dir_path in self.data_dirs.values():
            dir_path.mkdir(exist_ok=True, parents=True)

    def handle_generation(self, overwrite: Optional[str], run: Optional[str]) -> None:
        """Handle input generation command."""
        generator = InputGenerator(
            self.config_manager.config,
            self.system_dir / 'templates'
        )
        logging.info("Generating input files...")
        generator.generate_inputs(overwrite, run)

    def handle_running(self, run_type: str) -> None:
        """Handle calculation running command."""
        paths = self.config_manager.get_calculation_paths(self.system_dir)
        self._run_existing_inputs(paths, run_type)

    def handle_extraction(self) -> None:
        """Handle data extraction command."""
        self.create_data_directories()
        processor = DataProcessor(self.config_manager.config, self.system_dir)
        exporter = DataExporter(self.data_dirs['raw'])

        for catalyst in self.config_manager.config['catalysts']:
            self._process_catalyst_data(catalyst, processor, exporter)

    def handle_status_check(self) -> None:
        """Handle status checking command."""
        paths = self.config_manager.get_calculation_paths(self.system_dir)
        StatusChecker(paths, self.system_dir).check_all_statuses()

    def _run_existing_inputs(self, paths: List[Path], run_type: str) -> None:
        """Execute existing input files based on their status."""
        for input_file in paths:
            if input_file.exists():
                calc = QChemCalculation(input_file)
                status, details = calc.check_status()
                if run_type == 'all' or run_type == status:
                    logging.info(f'Executing input file: {input_file} (current: {status} - {details})')
                    calc.execute()
                else:
                    logging.info(f'Skipping {input_file} (current: {status} - {details})')
            else:
                logging.warning(f'Input file does not exist: {input_file}')

    def _process_catalyst_data(self, catalyst: str, processor: DataProcessor, 
                             exporter: DataExporter) -> None:
        """Process data for a specific catalyst."""
        for method in self.config_manager.config['methods']:
            for basis in self.config_manager.config['bases']:
                self._process_method_basis(method, basis, catalyst, processor, exporter)

        self._generate_catalyst_profiles(catalyst)

    def _process_method_basis(self, method: str, basis: str, catalyst: str,
                            processor: DataProcessor, exporter: DataExporter) -> None:
        """Process data for a specific method/basis combination."""
        method_basis = f"{method}_{basis}"
        method_basis_dir = self.system_dir / FileHandler.sanitize_filename(method_basis)

        if not method_basis_dir.is_dir():
            logging.warning(f"Directory '{method_basis_dir}' does not exist. Skipping.")
            return

        logging.info(f"Processing method_basis: {method_basis} for catalyst: {catalyst}")
        data_list = processor.process_files(method_basis_dir, method_basis, catalyst)
        
        if data_list:
            filename = f"{method_basis}_{FileHandler.sanitize_filename(catalyst)}"
            exporter.save_method_basis_data(data_list, filename)
        else:
            logging.info(f"No data was extracted for '{method_basis}' with catalyst '{catalyst}'")

    def _generate_catalyst_profiles(self, catalyst: str) -> None:
        """Generate energy profiles for a specific catalyst."""
        profile_generator = EnergyProfileGenerator(
            self.data_dirs['raw'],
            self.data_dirs['profiles'],
            self.config_manager.config,
            catalyst
        )
        profile_generator.generate_profiles()